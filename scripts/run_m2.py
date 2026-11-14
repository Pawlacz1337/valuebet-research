"""M2 — test pokrywania, plus rozkład na osie (STEP4_ENSEMBLE §11.10 B i C).

M2 pyta o jedno: czy pula logarytmiczna **Pinnacle po Shinie + nasz DC**
przewiduje 1X2 lepiej niż **sam Pinnacle**. Jeśli nie, model nie wnosi
informacji ponad rynek i jego rola pieniężna kończy się na kombinacjach
wycenianych z danych rynkowych.

Reguła 19 nienaruszona i to jest tu subtelne
---------------------------------------------
Kurs rynkowy **nie może być cechą modelu**. Tutaj nie jest: DC został
dopasowany bez dostępu do kursów, a pula łączy dwie **gotowe** prognozy.
Pinnacle wchodzi jawnie jako **cel shrinkage** — dokładnie ten jeden
wyjątek, który reguła 19 dopuszcza, i jest oznaczony.

Waga walk-forward
-----------------
Waga modelu dla sezonu ``S`` dobierana wyłącznie na sezonach wcześniejszych
od ``S``. Dobranie jej na całym zbiorze byłoby przeciekiem, a przy wadze
bliskiej zera — przeciekiem, który ładnie wygląda.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

from valuebet.backtest.lockbox import assert_no_lockbox
from valuebet.backtest.market_benchmark import clustered_slope, implied_goal_rates
from valuebet.backtest.metrics import (
    log_loss_per_match,
    market_probabilities,
    paired_bootstrap_diff,
)
from valuebet.provenance import frozen_commit, generated_by

COMMIT = "313591a"
SCRIPT = Path(__file__)
ROOT = SCRIPT.resolve().parents[1]
_EPS = 1e-12


def log_pool(
    model: np.ndarray, market: np.ndarray, weight: float
) -> np.ndarray:
    """Pula logarytmiczna: ``q ∝ model^w * market^(1-w)``, renormalizowana.

    Logarytmiczna, nie arytmetyczna: mieszanka arytmetyczna dwóch
    skalibrowanych prognoz jest systematycznie niedopewna, a tutaj zależy
    nam, żeby ``w = 0`` dawało **dokładnie** rynek.
    """
    logs = weight * np.log(np.clip(model, _EPS, 1.0)) + (1.0 - weight) * np.log(
        np.clip(market, _EPS, 1.0)
    )
    pooled = np.exp(logs - logs.max(axis=1, keepdims=True))
    return np.asarray(pooled / pooled.sum(axis=1, keepdims=True), dtype=np.float64)


def fit_weight(model: np.ndarray, market: np.ndarray, y: np.ndarray) -> float:
    """Waga minimalizująca log loss puli, w [0, 1]."""

    def loss(weight: float) -> float:
        return float(log_loss_per_match(log_pool(model, market, weight), y).mean())

    return float(minimize_scalar(loss, bounds=(0.0, 1.0), method="bounded").x)


def main() -> int:
    # COMMIT opisuje artefakt wejściowy (dev_<COMMIT>.parquet); etykieta pliku
    # wyjściowego to commit, który go liczy (FSA #0 F-24).
    commit = frozen_commit(script=SCRIPT, root=ROOT)
    report: dict[str, Any] = {
        "commit": commit,
        "input_commit": COMMIT,
        "generated_by": generated_by(script=SCRIPT, root=ROOT),
    }
    out_path = Path("reports") / f"m2_{commit}.json"

    dev = pd.read_parquet(Path("reports") / f"dev_{COMMIT}.parquet")
    assert_no_lockbox(dev, what="M2")
    closing = pd.read_parquet("data/interim/football_data/closing_odds.parquet")
    pinnacle = market_probabilities(
        closing.loc[
            closing.bookmaker == "pinnacle",
            ["match_id", "odds_home", "odds_draw", "odds_away"],
        ]
    )
    frame = dev.merge(
        pinnacle[["match_id", "p_home", "p_draw", "p_away"]].rename(
            columns={"p_home": "m_home", "p_draw": "m_draw", "p_away": "m_away"}
        ),
        on="match_id",
        how="inner",
        validate="one_to_one",
    ).sort_values("season")

    model = frame[["p_home_dc", "p_draw_dc", "p_away_dc"]].to_numpy()
    market = frame[["m_home", "m_draw", "m_away"]].to_numpy()
    y = frame.outcome.to_numpy()
    seasons = sorted(frame.season.unique())

    # --- C. M2 -----------------------------------------------------------
    weights: dict[str, float] = {}
    pooled = np.empty_like(model)
    used = np.zeros(len(frame), dtype=bool)
    for i, season in enumerate(seasons):
        mask = (frame.season == season).to_numpy()
        if i == 0:
            # Brak sezonów wcześniejszych — nie ma na czym dobrać wagi.
            # Zero znaczy „sam rynek", czyli najostrożniejszy wybór.
            weight = 0.0
        else:
            earlier = frame.season.isin(seasons[:i]).to_numpy()
            weight = fit_weight(model[earlier], market[earlier], y[earlier])
        weights[season] = weight
        pooled[mask] = log_pool(model[mask], market[mask], weight)
        used[mask] = True

    ll_pool = log_loss_per_match(pooled[used], y[used])
    ll_market = log_loss_per_match(market[used], y[used])
    ll_model = log_loss_per_match(model[used], y[used])
    groups = frame.season.to_numpy()[used]
    diff = paired_bootstrap_diff(ll_pool, ll_market, groups=groups)

    report["m2"] = {
        "n": int(used.sum()),
        "n_seasons": len(seasons),
        "weights_per_season": weights,
        "ll_pool": float(ll_pool.mean()),
        "ll_market": float(ll_market.mean()),
        "ll_model": float(ll_model.mean()),
        "pool_minus_market": {
            "mean": diff.mean_diff,
            "ci_low": diff.ci_low,
            "ci_high": diff.ci_high,
            "significant": diff.excludes_zero,
        },
        "verdict": (
            "model wnosi informacje ponad rynek"
            if diff.ci_high < 0
            else "model NIE wnosi informacji ponad rynek"
        ),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(json.dumps(report["m2"], indent=2, ensure_ascii=False), flush=True)

    # --- B. Rozkład na osie ----------------------------------------------
    rho_median = float(np.median(frame.rho.to_numpy()))
    axes: dict[str, Any] = {"rho_median_model": rho_median}
    our_a = np.log(frame.lambda_home.to_numpy()) + np.log(frame.mu_away.to_numpy())
    our_b = np.log(frame.lambda_home.to_numpy()) - np.log(frame.mu_away.to_numpy())

    for label, rho_value in (("rho_model", None), ("rho_zero", 0.0)):
        rates = [
            implied_goal_rates(qh, qd, rho if rho_value is None else rho_value)
            for qh, qd, rho in zip(
                frame.m_home, frame.m_draw, frame.rho, strict=True
            )
        ]
        lam = np.array([r[0] for r in rates])
        mu = np.array([r[1] for r in rates])
        ok = np.isfinite(lam) & np.isfinite(mu)
        market_a = np.where(ok, np.log(np.where(ok, lam, 1)) + np.log(np.where(ok, mu, 1)), np.nan)
        market_b = np.where(ok, np.log(np.where(ok, lam, 1)) - np.log(np.where(ok, mu, 1)), np.nan)
        slope_a = clustered_slope(our_a, market_a, frame.season.to_numpy())
        slope_b = clustered_slope(our_b, market_b, frame.season.to_numpy())
        axes[label] = {
            "n_not_inverted": int((~ok).sum()),
            "A_openness": {
                "slope": slope_a.slope,
                "ci_low": None if not slope_a.has_ci else slope_a.ci_low,
                "ci_high": None if not slope_a.has_ci else slope_a.ci_high,
                "r": slope_a.correlation,
                "sd_ours": slope_a.sd_x,
                "sd_market": slope_a.sd_y,
                "describe": slope_a.describe(),
            },
            "B_edge": {
                "slope": slope_b.slope,
                "ci_low": None if not slope_b.has_ci else slope_b.ci_low,
                "ci_high": None if not slope_b.has_ci else slope_b.ci_high,
                "r": slope_b.correlation,
                "sd_ours": slope_b.sd_x,
                "sd_market": slope_b.sd_y,
                "describe": slope_b.describe(),
            },
        }
    report["axes"] = axes
    out_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(json.dumps(axes, indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
