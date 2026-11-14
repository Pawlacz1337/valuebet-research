"""Przebieg diagnostyczny DC z zapisem PRZYROSTOWYM (STEP4_ENSEMBLE §11.8).

Dlaczego zapis przyrostowy
---------------------------
Przebieg 2026-10-01 szedł kilkadziesiąt minut i zginął razem z powłoką,
zabierając cały bufor stdout. Drugi padł na bezpieczniku po tym samym
czasie. Wynik ma lądować na dysku **w trakcie**, nie na końcu — każda
sekcja dopisywana od razu, plik ma przetrwać śmierć procesu.

Klucz pliku to skrót commita: inny commit = inny plik, bo liczby z
różnych wersji modelu nie są porównywalne i nie wolno ich pomylić.

Lockbox
-------
Wszystko liczone wyłącznie na sezonach deweloperskich. Każda liczba
przechodzi przez ``assert_no_lockbox`` zanim trafi do raportu.
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
from valuebet.backtest.lockbox import (
    LOCKBOX_SEASONS,
    assert_no_lockbox,
    split_dev_lockbox,
)
from valuebet.backtest.market_benchmark import (
    MIN_CLUSTERS,
    clustered_slope,
    implied_goal_rates,
    over_probability,
)
from valuebet.backtest.metrics import (
    log_loss_per_match,
    market_probabilities,
    paired_bootstrap_diff,
)
from valuebet.provenance import frozen_commit, generated_by

log = logging.getLogger("diagnostics")

SCRIPT = Path(__file__)
ROOT = SCRIPT.resolve().parents[1]


class IncrementalReport:
    """Słownik, który zapisuje się na dysk po każdym ``set``."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.flush()

    def flush(self) -> None:
        self.path.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        print(f"[zapisano] {self.path.name}: {list(self.data)}", flush=True)


def clustered_mean(
    values: np.ndarray, groups: np.ndarray, *, n_boot: int = 8000, seed: int = 0
) -> dict[str, Any]:
    """Średnia z CI klastrowym. Poniżej ``MIN_CLUSTERS`` klastrów — ``None``.

    Nie liczba. Raport z 21:09 wydrukował dla koszyka zasilanego jednym
    sezonem przedział zerowej szerokości i z ~ -9e14; to ma się nie dać.
    """
    unique = np.unique(groups)
    out: dict[str, Any] = {
        "n": len(values),
        "n_clusters": len(unique),
        "mean": float(np.mean(values)),
    }
    if len(unique) < MIN_CLUSTERS:
        out.update(ci_low=None, ci_high=None, note=f"n/d ({len(unique)} klastrów)")
        return out
    rng = np.random.default_rng(seed)
    index = {g: np.flatnonzero(groups == g) for g in unique}
    sums = np.array([values[index[g]].sum() for g in unique])
    counts = np.array([len(index[g]) for g in unique], dtype=float)
    pick = rng.integers(0, len(unique), size=(n_boot, len(unique)))
    draws = sums[pick].sum(1) / counts[pick].sum(1)
    low, high = (float(v) for v in np.quantile(draws, [0.025, 0.975]))
    out.update(ci_low=low, ci_high=high, significant=bool(low > 0 or high < 0))
    return out


def _slope_dict(result: Any) -> dict[str, Any]:
    return {
        "slope": result.slope,
        "ci_low": None if not result.has_ci else result.ci_low,
        "ci_high": None if not result.has_ci else result.ci_high,
        "half_width": None if not result.has_ci else result.half_width,
        "n": result.n,
        "n_clusters": result.n_clusters,
        "correlation": result.correlation,
        "sd_x": result.sd_x,
        "sd_y": result.sd_y,
        "describe": result.describe(),
    }


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    logging.getLogger("valuebet.models.dixon_coles").setLevel(logging.ERROR)
    # Etykieta commita = fakt (FSA #0 F-24): odmowa przy brudnym drzewie.
    commit = frozen_commit(script=SCRIPT, root=ROOT)
    report = IncrementalReport(Path("reports") / f"diag_{commit}.json")
    report.set("commit", commit)
    report.set("generated_by", generated_by(script=SCRIPT, root=ROOT))

    matches = pd.read_parquet("data/interim/football_data/matches.parquet")
    closing = pd.read_parquet("data/interim/football_data/closing_odds.parquet")

    print("[1/6] Elo walk-forward", flush=True)
    elo = run_elo_baseline(matches, closing)
    print("[2/6] DC walk-forward (cache xi — to trwa)", flush=True)
    dc = run_dixon_coles_baseline(matches, closing)

    report.set(
        "seasons",
        [
            {
                "season": s.season,
                "n": s.n,
                "n_train": s.n_train,
                "xi": s.xi,
                "tau_strength": s.tau_strength,
                "tau_openness": s.tau_openness,
                "n_validation_seasons": s.n_validation_seasons,
                "n_rejected_xi": s.n_rejected_xi,
                "condition_number": s.condition_number,
                "n_dropped_teams": s.n_dropped_teams,
                "n_fits": s.n_fits,
                "n_unknown_team_matches": s.n_unknown_team_matches,
                "log_loss_dc": s.log_loss_dc,
            }
            for s in dc.seasons
            # Jedna definicja lockboxa w całym repo. Literały w drugim
            # miejscu rozjechałyby się przy zmianie podziału i nikt by
            # tego nie zauważył.
            if s.season not in LOCKBOX_SEASONS
        ],
    )

    joined = dc.predictions.merge(
        elo.predictions[["match_id", "p_home", "p_draw", "p_away"]],
        on="match_id",
        suffixes=("_dc", "_elo"),
        validate="one_to_one",
    )
    dev, _ = split_dev_lockbox(joined)
    assert_no_lockbox(dev, what="przebieg diagnostyczny")
    indexed = matches.set_index("match_id")
    dev = dev.assign(
        real=(
            indexed.loc[dev.match_id, "home_goals"]
            + indexed.loc[dev.match_id, "away_goals"]
        ).to_numpy(),
        pred=(dev.lambda_home + dev.mu_away).to_numpy(),
    )
    dev.to_parquet(Path("reports") / f"dev_{commit}.parquet")
    y = dev.outcome.to_numpy()
    groups = dev.season.to_numpy()

    print("[3/6] rozrzut i kwartyle", flush=True)
    report.set(
        "goal_spread",
        {
            "sd_pred": float(dev.pred.std()),
            "min_pred": float(dev.pred.min()),
            "max_pred": float(dev.pred.max()),
            "sd_real": float(dev.real.std()),
            "correlation_pred_real": float(np.corrcoef(dev.pred, dev.real)[0, 1]),
        },
    )
    q1, q3 = dev.pred.quantile(0.25), dev.pred.quantile(0.75)
    subsets = {
        "cala_proba": dev,
        "dolny_kwartyl": dev[dev.pred <= q1],
        "gorny_kwartyl": dev[dev.pred >= q3],
        "koszyk_px_030": dev[dev.p_draw_dc >= 0.30],
    }
    report.set(
        "goal_level",
        {
            name: clustered_mean(
                (sub.real - sub.pred).to_numpy(), sub.season.to_numpy()
            )
            for name, sub in subsets.items()
            if len(sub) > 0
        },
    )

    print("[4/6] kalibracja remisow", flush=True)
    draw = (y == 1).astype(float)
    p_draw = dev.p_draw_dc.to_numpy()
    buckets = []
    for lo, hi in [(0.0, 0.24), (0.24, 0.27), (0.27, 0.30), (0.30, 0.33), (0.33, 1.0)]:
        mask = (p_draw >= lo) & (p_draw < hi)
        if mask.sum() < 25:
            continue
        stats = clustered_mean(draw[mask], groups[mask])
        stats.update(bucket=[lo, hi], predicted=float(p_draw[mask].mean()))
        if stats.get("ci_low") is not None:
            se = (stats["ci_high"] - stats["ci_low"]) / 3.92
            stats["z"] = (
                (stats["mean"] - stats["predicted"]) / se if se > 0 else None
            )
        else:
            stats["z"] = None
        buckets.append(stats)
    report.set("draw_calibration", buckets)

    print("[5/6] sparowane 1X2", flush=True)
    ll_dc = dev.ll_dc.to_numpy()
    ll_elo = log_loss_per_match(
        dev[["p_home_elo", "p_draw_elo", "p_away_elo"]].to_numpy(), y
    )
    previous = Path("reports") / "dev_fb9ec10.parquet"
    pairs: dict[str, Any] = {
        "ll_dc": float(ll_dc.mean()),
        "ll_elo": float(ll_elo.mean()),
    }
    diff = paired_bootstrap_diff(ll_dc, ll_elo, groups=groups)
    pairs["dc_minus_elo"] = {
        "mean": diff.mean_diff,
        "ci_low": diff.ci_low,
        "ci_high": diff.ci_high,
        "significant": diff.excludes_zero,
    }
    if previous.exists():
        old = pd.read_parquet(previous)[["match_id", "ll_dc"]].rename(
            columns={"ll_dc": "ll_old"}
        )
        merged = dev.merge(old, on="match_id", validate="one_to_one")
        d2 = paired_bootstrap_diff(
            merged.ll_dc.to_numpy(),
            merged.ll_old.to_numpy(),
            groups=merged.season.to_numpy(),
        )
        pairs["dc_minus_fb9ec10"] = {
            "mean": d2.mean_diff,
            "ci_low": d2.ci_low,
            "ci_high": d2.ci_high,
            "significant": d2.excludes_zero,
        }
    pairs["per_season"] = [
        {
            "season": s,
            "n": int((groups == s).sum()),
            "ll_dc": float(ll_dc[groups == s].mean()),
            "ll_elo": float(ll_elo[groups == s].mean()),
        }
        for s in sorted(set(groups))
    ]
    report.set("paired_1x2", pairs)

    print("[6/6] G4", flush=True)
    pinnacle = market_probabilities(
        closing.loc[
            closing.bookmaker == "pinnacle",
            ["match_id", "odds_home", "odds_draw", "odds_away"],
        ]
    )
    mk = dev.merge(
        pinnacle[["match_id", "p_home", "p_draw"]].rename(
            columns={"p_home": "q_home", "p_draw": "q_draw"}
        ),
        on="match_id",
        how="inner",
    )
    g4: dict[str, Any] = {
        "n_with_pinnacle": len(mk),
        "n_dev": len(dev),
        "n_without_pinnacle": int(len(dev) - len(mk)),
    }
    for label, use_model_rho in (("rho_model", True), ("rho_zero", False)):
        rates = [
            implied_goal_rates(qh, qd, rho if use_model_rho else 0.0)
            for qh, qd, rho in zip(mk.q_home, mk.q_draw, mk.rho, strict=True)
        ]
        lam = np.array([r[0] for r in rates])
        mu = np.array([r[1] for r in rates])
        failed = int((~np.isfinite(lam)).sum())
        slope = clustered_slope(mk.pred.to_numpy(), lam + mu, mk.season.to_numpy())
        entry = _slope_dict(slope)
        entry["n_not_inverted"] = failed
        entry["pct_not_inverted"] = 100.0 * failed / max(len(mk), 1)
        g4[f"c_slope_{label}"] = entry
    report.set("g4", g4)

    over = np.array(
        [
            over_probability(float(lam), float(mu), float(rho))
            for lam, mu, rho in zip(
                dev.lambda_home, dev.mu_away, dev.rho, strict=True
            )
        ]
    )
    realised = (dev.real.to_numpy() > 2.5).astype(float)
    ou = []
    for lo, hi in [(0.0, 0.45), (0.45, 0.50), (0.50, 0.55), (0.55, 1.0)]:
        mask = (over >= lo) & (over < hi)
        if mask.sum() < 25:
            continue
        stats = clustered_mean(realised[mask], groups[mask])
        stats.update(bucket=[lo, hi], predicted=float(over[mask].mean()))
        if stats.get("ci_low") is not None:
            se = (stats["ci_high"] - stats["ci_low"]) / 3.92
            stats["z"] = (
                (stats["mean"] - stats["predicted"]) / se if se > 0 else None
            )
        else:
            stats["z"] = None
        ou.append(stats)
    g4["b_over25_reliability"] = ou
    g4["b_over25_spread"] = {
        "sd": float(over.std()),
        "mean_predicted": float(over.mean()),
        "realised": float(realised.mean()),
    }
    g4["d_draw_slope"] = _slope_dict(
        clustered_slope(
            mk.p_draw_dc.to_numpy(), mk.q_draw.to_numpy(), mk.season.to_numpy()
        )
    )
    g4["f_outcome_slope"] = _slope_dict(
        clustered_slope(dev.pred.to_numpy(), dev.real.to_numpy(), groups)
    )
    g4["e_pol_csv_has_totals"] = False
    g4["e_note"] = (
        "POL.csv ma wylacznie 1X2 (PSC/MaxC/AvgC/BFEC/B365C). "
        "Bezposredni benchmark totali czeka na poller."
    )
    report.set("g4", g4)

    print("GOTOWE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
