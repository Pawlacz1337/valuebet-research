"""§11.10 A — walidacja instrumentu „suma goli z 1X2" na Premier League.

Pytanie: czy suma goli wyprowadzona z samego rynku 1X2 mierzy to, co
mierzyć ma? Ekstraklasa nie pozwala tego sprawdzić, bo ``POL.csv`` nie ma
kursów O/U. Premier League ma zamknięcie Pinnacle i dla 1X2
(``PSCH/PSCD/PSCA``), i dla totali (``PC>2.5`` / ``PC<2.5``), więc mamy
**dwa niezależne odczyty tej samej wielkości**.

Kryterium ważności (spisane PRZED wynikiem, §11.10 A):
``sd(T_1x2) / sd(T_ou) ∈ [0.8, 1.25]`` **i** korelacja ``≥ 0.7``.

To walidacja narzędzia pomiarowego, nie rozszerzenie zakresu gry.
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from valuebet.backtest.lockbox import assert_no_lockbox
from valuebet.backtest.market_benchmark import (
    clustered_slope,
    implied_goal_rates,
    implied_total_from_over,
)
from valuebet.ingest.football_data_main import (
    RAW_SUBDIR,
    MainLeagueFile,
    parse_main_league,
    write_season_raw,
)
from valuebet.ingest.raw_store import RawStore
from valuebet.net.http import HttpClient
from valuebet.pricing.shin import ShinNotConvergedError, shin_probabilities
from valuebet.provenance import frozen_commit, generated_by

LEAGUE = "E0"
SEASONS = ("1920", "2021", "2122", "2223", "2324", "2425")
#: Mediana rho z dopasowań DC Ekstraklasy (reports/dev_313591a.parquet).
RHO_MEDIAN = -0.0702
SCRIPT = Path(__file__)
ROOT = SCRIPT.resolve().parents[1]


#: Próg wiarygodności CI — ten sam co ``clv.MIN_CLUSTERS_RELIABLE`` i
#: ``metrics.BootstrapDiff.reliable`` (FSA #0 F-23).
MIN_CLUSTERS_RELIABLE = 8


def instrument_verdict(
    *, ci_low: float | None, ci_high: float | None, n_clusters: int
) -> str:
    """Werdykt z liczb, nie z kryterium bez mocy (FSA #0 W.10, F-23).

    „ważny” tylko przy CI nachylenia ``T_ou ~ T_1x2`` obejmującym 1 na
    wiarygodnej liczbie klastrów; CI wykluczające 1 → „obciążony (skala)”;
    za mało klastrów albo brak CI → „niewiarygodny statystycznie”.
    """
    if ci_low is None or ci_high is None or n_clusters < MIN_CLUSTERS_RELIABLE:
        return "niewiarygodny statystycznie"
    if ci_low <= 1.0 <= ci_high:
        return "ważny"
    return "obciążony (skala)"


def fetch(client: HttpClient, file: MainLeagueFile) -> str:
    """Jeden plik sezonu przez jedyny klient sieciowy (odstęp ≥ 10 s, robots.txt)."""
    response = client.get(file.url)
    if response.status_code != 200:
        raise RuntimeError(f"{file.url}: HTTP {response.status_code}")
    return str(response.text)


def load_or_fetch(
    client: HttpClient, store: RawStore, *, now: Callable[[], datetime]
) -> list[tuple[MainLeagueFile, str, Path]]:
    """Pliki sezonów z raw; pobiera **tylko brakujące** (FSA #0 F-23, F-26).

    Pętla pobierania idzie przez ``HttpClient`` — odstęp per host pilnuje
    klient, nie ta funkcja.
    """
    out = []
    for season in SEASONS:
        file = MainLeagueFile(league=LEAGUE, season=season)
        path = store.latest(RAW_SUBDIR, file.label, ".csv")
        if path is None:
            text = fetch(client, file)
            # data/raw jest niemodyfikowalne (reguła 12) — zapis z manifestem.
            path = write_season_raw(store, file, text.encode("utf-8"), now=now())
        else:
            text = path.read_text(encoding="utf-8")
        out.append((file, text, path))
    return out


def main() -> int:
    # Etykieta = fakt (FSA #0 F-24): odmowa przy brudnym drzewie.
    commit = frozen_commit(script=SCRIPT, root=ROOT)
    store = RawStore()
    report: dict[str, Any] = {
        "commit": commit,
        "generated_by": generated_by(script=SCRIPT, root=ROOT),
        "league": LEAGUE,
        "seasons": list(SEASONS),
    }
    frames = []

    with HttpClient(clock=time.time, sleep=time.sleep) as client:
        loaded = load_or_fetch(client, store, now=lambda: datetime.now(UTC))
    now = datetime.now(UTC)
    for file, text, path in loaded:
        report.setdefault("raw_files", []).append(path.as_posix())
        parsed = parse_main_league(
            text, league=LEAGUE, season_code=file.season, source_url=file.url, now=now
        )
        print(
            f"  {file.label}: {parsed.attrs['n_kept']} z {parsed.attrs['n_raw']} "
            f"(odrzucone: niekompletne {parsed.attrs['n_dropped_incomplete']}, "
            f"złe kursy {parsed.attrs['n_dropped_bad_odds']})",
            flush=True,
        )
        frames.append(parsed)

    data = pd.concat(frames, ignore_index=True)
    # Lockbox toru M (FSA #0 F-21): ten skrypt woła clustered_slope, więc
    # sezony lockboxa nie mogą wejść do liczby — niezależnie od ligi.
    assert_no_lockbox(data, what="walidacja instrumentu")
    report["n_matches"] = len(data)
    report["n_seasons"] = int(data.season.nunique())

    # Rynki po Shinie: 1X2 (trójstronny) i O/U 2.5 (dwustronny).
    q_1x2 = []
    q_over = []
    for row in data.itertuples(index=False):
        try:
            three = shin_probabilities(
                np.array([row.odds_home, row.odds_draw, row.odds_away], dtype=float),
                strict=True,
            ).probabilities
        except ShinNotConvergedError:
            three = np.full(3, np.nan)
        try:
            over = shin_probabilities(
                np.array([row.odds_over25, row.odds_under25], dtype=float), strict=True
            ).probabilities[0]
        except ShinNotConvergedError:
            over = np.nan
        q_1x2.append(three)
        q_over.append(over)
    q_1x2_arr = np.asarray(q_1x2, dtype=float)
    q_over_arr = np.asarray(q_over, dtype=float)
    report["n_shin_failed_1x2"] = int(np.isnan(q_1x2_arr).any(axis=1).sum())
    report["n_shin_failed_ou"] = int(np.isnan(q_over_arr).sum())

    variants: dict[str, Any] = {}
    for label, rho in (("rho_zero", 0.0), ("rho_median_ekstraklasa", RHO_MEDIAN)):
        t_1x2 = np.full(len(data), np.nan)
        t_ou = np.full(len(data), np.nan)
        for i in range(len(data)):
            if np.isnan(q_1x2_arr[i]).any():
                continue
            lam, mu = implied_goal_rates(q_1x2_arr[i][0], q_1x2_arr[i][1], rho)
            if not np.isfinite(lam) or not np.isfinite(mu) or mu <= 0:
                continue
            t_1x2[i] = lam + mu
            if np.isfinite(q_over_arr[i]):
                t_ou[i] = implied_total_from_over(q_over_arr[i], lam / mu, rho)

        ok = np.isfinite(t_1x2) & np.isfinite(t_ou)
        sd_1x2 = float(np.std(t_1x2[ok]))
        sd_ou = float(np.std(t_ou[ok]))
        ratio = sd_1x2 / sd_ou if sd_ou > 0 else float("nan")
        correlation = float(np.corrcoef(t_1x2[ok], t_ou[ok])[0, 1])
        slope = clustered_slope(t_1x2[ok], t_ou[ok], data.season.to_numpy()[ok])
        valid = bool(0.8 <= ratio <= 1.25 and correlation >= 0.7)
        variants[label] = {
            "rho": rho,
            "n_usable": int(ok.sum()),
            "n_not_inverted_1x2": int((~np.isfinite(t_1x2)).sum()),
            "n_not_solved_ou": int(np.isfinite(t_1x2).sum() - ok.sum()),
            "sd_T_1x2": sd_1x2,
            "sd_T_ou": sd_ou,
            "sd_ratio": ratio,
            "correlation": correlation,
            "mean_T_1x2": float(np.mean(t_1x2[ok])),
            "mean_T_ou": float(np.mean(t_ou[ok])),
            "slope_T_ou_on_T_1x2": {
                "slope": slope.slope,
                "ci_low": None if not slope.has_ci else slope.ci_low,
                "ci_high": None if not slope.has_ci else slope.ci_high,
                "n_clusters": slope.n_clusters,
                "describe": slope.describe(),
            },
            "valid_old_criterion": valid,
            "criterion_old": "sd_ratio in [0.8, 1.25] AND correlation >= 0.7 (bez mocy, W.10)",
            "reliable": slope.n_clusters >= MIN_CLUSTERS_RELIABLE,
            "verdict": instrument_verdict(
                ci_low=slope.ci_low if slope.has_ci else None,
                ci_high=slope.ci_high if slope.has_ci else None,
                n_clusters=slope.n_clusters,
            ),
        }
    report["variants"] = variants
    report["verdicts"] = {k: v["verdict"] for k, v in variants.items()}

    out = Path("reports") / f"instrument_validation_{commit}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
