"""M4 — jednorazowa ocena na lockboxie (STEP4_ENSEMBLE §11.11, pkt 8).

Zakres zawężony świadomie. Po M2 wiemy, że model nie wnosi informacji
ponad rynek, więc lockbox nie służy już wyborowi architektury — służy
**jednej rzeczy**: sprawdzeniu, czy zamrożone Elo i DC wypadają na
odłożonych sezonach podobnie jak na zbiorze deweloperskim. Wyraźnie gorzej
= decyzje zostały dopasowane do dev.

Zamrożenie
----------
Elo i DC z commita zapisanego w raporcie, zero zmian w ``models/`` i
``features/`` przed przebiegiem. Skrypt sam to sprawdza i odmawia startu,
jeśli te katalogi mają niezacommitowane zmiany — inaczej „zamrożone" jest
deklaracją, nie faktem.

Klastry = kolejki, nie sezony
------------------------------
Dwa sezony to dwa klastry sezonowe, czyli mniej niż ``MIN_CLUSTERS``;
każdy przedział wyszedłby ``n/d``. Kolejka jest najmniejszą jednostką, w
której mecze dzielą stan modelu i kolejkę terminarza, więc to naturalny
klaster. Przybliżamy ją **tygodniem ISO** — football-data nie podaje
numeru kolejki, a mecze jednej kolejki leżą w jednym tygodniu.

Dwie referencje, osobno
-----------------------
Pinnacle tam, gdzie jest; Betfair Exchange tam, gdzie Pinnacle'a nie ma.
**Nigdy sklejone w jedną liczbę** — exchange ma inną strukturę marży i
innych graczy (ROADMAP, Część II).

Jeden przebieg — i był
----------------------
Lockbox został obejrzany 2026-10-01 (``reports/lockbox_3433f2c.json``).
Rejestr obejrzeń ``reports/lockbox_views.jsonl`` ma jeden wpis; przy ≥ 1
wpisie (albo przy braku rejestru) skrypt kończy się błędem **zanim**
dotknie danych. Flagi obejścia nie ma (FSA #0 W.8).

Lockbox nie jest dziewiczy
--------------------------
Zadeklarowano go 2026-09-30, po tym jak log loss obu sezonów pojawił się
w raportach walk-forward. Żadna decyzja nie została na nich oparta, ale
końcowy wynik trzeba czytać z tą poprawką — i raport ją niesie.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from valuebet.backtest.dixon_coles_baseline import run_dixon_coles_baseline
from valuebet.backtest.elo_baseline import run_elo_baseline
from valuebet.backtest.lockbox import LOCKBOX_SEASONS
from valuebet.backtest.market_benchmark import MIN_CLUSTERS
from valuebet.backtest.metrics import (
    log_loss_per_match,
    market_probabilities,
    paired_bootstrap_diff,
)
from valuebet.provenance import frozen_commit, generated_by

SCRIPT = Path(__file__)
ROOT = SCRIPT.resolve().parents[1]


#: Rejestr obejrzeń lockboxa. Każdy przebieg dopisuje wiersz; przebieg przy
#: niepustym rejestrze jest odrzucany.
LOCKBOX_VIEWS = Path("reports/lockbox_views.jsonl")


def _assert_never_viewed() -> None:
    """Drugie obejrzenie lockboxa jest niemożliwe — bez flagi obejścia."""
    if not LOCKBOX_VIEWS.exists():
        raise RuntimeError(
            f"brak rejestru obejrzeń {LOCKBOX_VIEWS} — nie wiadomo, ile razy lockbox "
            "był obejrzany, więc traktujemy go jako obejrzany"
        )
    views = [line for line in LOCKBOX_VIEWS.read_text(encoding="utf-8").splitlines() if line.strip()]
    if views:
        raise RuntimeError(
            f"lockbox już obejrzany ({len(views)} wpis(y) w {LOCKBOX_VIEWS}) — drugi "
            "przebieg unieważniłby jego rolę (STEP4_ENSEMBLE §2, FSA #0 W.8)"
        )


def _round_cluster(frame: pd.DataFrame) -> np.ndarray:
    """Tydzień ISO jako przybliżenie kolejki, w obrębie sezonu."""
    stamps = pd.to_datetime(frame["kickoff_utc"])
    iso = stamps.dt.isocalendar()
    return (
        frame["season"].astype(str)
        + "-W"
        + iso["year"].astype(str)
        + "."
        + iso["week"].astype(str).str.zfill(2)
    ).to_numpy()


def _paired(a: np.ndarray, b: np.ndarray, groups: np.ndarray) -> dict[str, Any]:
    n_clusters = len(np.unique(groups))
    if n_clusters < MIN_CLUSTERS:
        return {
            "mean": float(np.mean(a - b)),
            "ci_low": None,
            "ci_high": None,
            "n": len(a),
            "n_clusters": n_clusters,
            "note": f"n/d ({n_clusters} klastrow)",
        }
    diff = paired_bootstrap_diff(a, b, groups=groups)
    return {
        "mean": diff.mean_diff,
        "ci_low": diff.ci_low,
        "ci_high": diff.ci_high,
        "n": diff.n,
        "n_clusters": n_clusters,
        "significant": diff.excludes_zero,
    }


def main() -> int:
    # Rejestr obejrzeń PRZED czymkolwiek innym — także przed konfiguracją logów.
    _assert_never_viewed()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    logging.getLogger("valuebet.models.dixon_coles").setLevel(logging.ERROR)
    # Zamrożenie i etykieta przez valuebet.provenance (FSA #0 F-24).
    commit = frozen_commit(script=SCRIPT, root=ROOT)
    out = Path("reports") / f"lockbox_{commit}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "commit_frozen": commit,
        "generated_by": generated_by(script=SCRIPT, root=ROOT),
        "lockbox_seasons": list(LOCKBOX_SEASONS),
        "cluster_unit": "tydzien ISO w obrebie sezonu (przyblizenie kolejki)",
        "caveat": (
            "Lockbox NIE jest dziewiczy: zadeklarowany 2026-09-30, po tym jak "
            "log loss obu sezonow pojawil sie w raportach walk-forward. Zadna "
            "decyzja nie zostala na nich oparta, ale wynik czytaj z ta poprawka."
        ),
    }

    def flush() -> None:
        out.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        print(f"[zapisano] {out.name}: {list(report)}", flush=True)

    flush()
    matches = pd.read_parquet("data/interim/football_data/matches.parquet")
    closing = pd.read_parquet("data/interim/football_data/closing_odds.parquet")

    print("[1/3] Elo", flush=True)
    elo = run_elo_baseline(matches, closing)
    print("[2/3] DC (cache xi)", flush=True)
    dc = run_dixon_coles_baseline(matches, closing)

    joined = dc.predictions.merge(
        elo.predictions[["match_id", "p_home", "p_draw", "p_away"]],
        on="match_id",
        suffixes=("_dc", "_elo"),
        validate="one_to_one",
    ).merge(
        matches[["match_id", "kickoff_utc"]], on="match_id", validate="one_to_one"
    )
    box = joined[joined.season.isin(LOCKBOX_SEASONS)].copy()
    if box.empty:
        raise RuntimeError("lockbox pusty — sprawdź LOCKBOX_SEASONS")
    box["cluster"] = _round_cluster(box)
    y = box.outcome.to_numpy()
    clusters = box["cluster"].to_numpy()

    ll_dc = box.ll_dc.to_numpy()
    ll_elo = log_loss_per_match(
        box[["p_home_elo", "p_draw_elo", "p_away_elo"]].to_numpy(), y
    )
    report["n"] = len(box)
    report["n_clusters"] = len(np.unique(clusters))
    report["per_season"] = [
        {
            "season": s,
            "n": int((box.season == s).sum()),
            "ll_dc": float(ll_dc[(box.season == s).to_numpy()].mean()),
            "ll_elo": float(ll_elo[(box.season == s).to_numpy()].mean()),
        }
        for s in sorted(box.season.unique())
    ]
    report["ll"] = {"dc": float(ll_dc.mean()), "elo": float(ll_elo.mean())}
    report["dc_minus_elo"] = _paired(ll_dc, ll_elo, clusters)
    flush()

    print("[3/3] luki do rynku, osobno per referencja", flush=True)
    gaps: dict[str, Any] = {}
    for bookmaker in ("pinnacle", "betfair_exchange"):
        subset = closing.loc[
            closing.bookmaker == bookmaker,
            ["match_id", "odds_home", "odds_draw", "odds_away"],
        ]
        if subset.empty:
            continue
        probs = market_probabilities(subset)
        merged = box.merge(
            probs[["match_id", "p_home", "p_draw", "p_away"]].rename(
                columns={"p_home": "q_h", "p_draw": "q_d", "p_away": "q_a"}
            ),
            on="match_id",
            how="inner",
        )
        if merged.empty:
            continue
        yy = merged.outcome.to_numpy()
        cl = merged["cluster"].to_numpy()
        ll_market = log_loss_per_match(merged[["q_h", "q_d", "q_a"]].to_numpy(), yy)
        ll_dc_sub = merged.ll_dc.to_numpy()
        ll_elo_sub = log_loss_per_match(
            merged[["p_home_elo", "p_draw_elo", "p_away_elo"]].to_numpy(), yy
        )
        gaps[bookmaker] = {
            "n": len(merged),
            "seasons": sorted(merged.season.unique()),
            "ll_market": float(ll_market.mean()),
            "ll_dc": float(ll_dc_sub.mean()),
            "ll_elo": float(ll_elo_sub.mean()),
            "elo_minus_market": _paired(ll_elo_sub, ll_market, cl),
            "dc_minus_market": _paired(ll_dc_sub, ll_market, cl),
        }
        report["gaps"] = gaps
        flush()

    print("GOTOWE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
