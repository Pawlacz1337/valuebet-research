"""Testy benchmarku rynkowego (STEP4_ENSEMBLE §11.4).

Najważniejszy jest round-trip odwracania: generujemy 1X2 ze znanych
``(lambda, mu, rho)`` i sprawdzamy, czy solver je odzyskuje ze stałego
punktu startowego.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from valuebet.backtest.market_benchmark import (
    MIN_CLUSTERS,
    clustered_slope,
    implied_goal_rates,
    market_goal_sums,
    outcome_probabilities,
    over_probability,
)

GRID_LAMBDA = (0.4, 0.9, 1.4, 1.9, 2.4, 3.8)
GRID_MU = (0.3, 0.8, 1.3, 1.8, 2.8)
GRID_RHO = (-0.15, -0.08, 0.0, 0.05)


@pytest.mark.parametrize("lam", GRID_LAMBDA)
@pytest.mark.parametrize("mu", GRID_MU)
def test_round_trip_recovers_rates(lam: float, mu: float) -> None:
    """Siatka 30 przypadkow x 4 rho — odzyskanie ze stałego startu."""
    for rho in GRID_RHO:
        q_home, q_draw, _ = outcome_probabilities(lam, mu, rho)
        got_lam, got_mu = implied_goal_rates(q_home, q_draw, rho)
        assert got_lam == pytest.approx(lam, rel=1e-5), f"lambda dla rho={rho}"
        assert got_mu == pytest.approx(mu, rel=1e-5), f"mu dla rho={rho}"


def test_inconsistent_probabilities_return_nan() -> None:
    """``q_1 + q_X >= 1`` nie opisuje żadnego meczu — NaN, nie liczba."""
    lam, mu = implied_goal_rates(0.7, 0.4, -0.08)
    assert np.isnan(lam) and np.isnan(mu)


@pytest.mark.parametrize("bad", [(-0.1, 0.3), (0.0, 0.3), (0.5, 0.0), (1.2, 0.1)])
def test_invalid_probabilities_return_nan(bad: tuple[float, float]) -> None:
    lam, mu = implied_goal_rates(bad[0], bad[1], -0.08)
    assert np.isnan(lam) and np.isnan(mu)


def test_inversion_is_deterministic() -> None:
    """Stały start => ten sam wynik przy każdym wywołaniu."""
    q_home, q_draw, _ = outcome_probabilities(1.7, 1.1, -0.06)
    first = implied_goal_rates(q_home, q_draw, -0.06)
    second = implied_goal_rates(q_home, q_draw, -0.06)
    assert first == second


def test_over_probability_matches_matrix_sum() -> None:
    lam, mu, rho = 1.6, 1.2, -0.07
    over = over_probability(lam, mu, rho, 2.5)
    under = over_probability(lam, mu, rho, -0.5) - over
    assert 0.0 < over < 1.0
    assert over + under == pytest.approx(1.0, abs=1e-12)


def test_over_probability_rises_with_goals() -> None:
    low = over_probability(1.0, 0.8, -0.07)
    high = over_probability(2.2, 1.6, -0.07)
    assert high > low


def test_outcome_probabilities_sum_to_one() -> None:
    probs = outcome_probabilities(1.5, 1.2, -0.08)
    assert sum(probs) == pytest.approx(1.0, abs=1e-12)


# ---------------------------------------------------------------------------
# Nachylenie z bootstrapem klastrowym
# ---------------------------------------------------------------------------


def _clustered_data(slope: float, n_clusters: int, per: int = 60, seed: int = 0):
    rng = np.random.default_rng(seed)
    groups = np.repeat([f"s{i}" for i in range(n_clusters)], per)
    x = rng.normal(2.6, 0.1, size=n_clusters * per)
    y = slope * (x - x.mean()) + 2.6 + rng.normal(0.0, 0.02, size=len(x))
    return x, y, groups


def test_slope_recovers_known_value() -> None:
    x, y, g = _clustered_data(1.0, 10)
    result = clustered_slope(x, y, g)
    assert result.slope == pytest.approx(1.0, abs=0.05)
    assert result.has_ci
    assert result.half_width < 0.05


def test_slope_interval_covers_truth_across_seeds() -> None:
    """Pokrycie sprawdzamy po wielu losowaniach, nie po jednym.

    Przedział 95% z definicji chybia co dwudziesty raz — pojedynczy seed
    nie jest testem pokrycia, tylko testem tego seeda.
    """
    covered = 0
    for seed in range(20):
        x, y, g = _clustered_data(1.0, 10, seed=seed)
        result = clustered_slope(x, y, g, seed=seed)
        covered += int(result.ci_low <= 1.0 <= result.ci_high)
    assert covered >= 16


def test_slope_detects_too_wide_predictions() -> None:
    """Za szerokie predykcje dają nachylenie poniżej 1 — sedno testu G4(c)."""
    x, y, g = _clustered_data(0.37, 10)
    result = clustered_slope(x, y, g)
    assert result.slope == pytest.approx(0.37, abs=0.05)
    assert result.ci_high < 1.0


def test_few_clusters_give_no_interval() -> None:
    """Przy < 5 klastrach przedział to NaN, a opis mówi „n/d".

    W raporcie 21:09 koszyk zasilany jednym sezonem wydrukował CI zerowej
    szerokości i z-score rzędu -9e14. To ma być niemożliwe.
    """
    x, y, g = _clustered_data(1.0, MIN_CLUSTERS - 1)
    result = clustered_slope(x, y, g)
    assert not result.has_ci
    assert np.isnan(result.ci_low) and np.isnan(result.ci_high)
    assert np.isnan(result.half_width)
    assert "n/d" in result.describe()
    assert f"{MIN_CLUSTERS - 1} klastrów" in result.describe()


def test_slope_ignores_non_finite_rows() -> None:
    """Mecze nieodwrócone (NaN) nie mogą wywalić regresji ani jej przesunąć."""
    x, y, g = _clustered_data(1.0, 10)
    x_with_gaps = x.copy()
    x_with_gaps[::37] = np.nan
    result = clustered_slope(x_with_gaps, y, g)
    assert result.n == int(np.isfinite(x_with_gaps).sum())
    assert result.slope == pytest.approx(1.0, abs=0.06)


def test_market_goal_sums_flags_failed_inversions() -> None:
    """Mecz nieodwrócony zostaje w ramce z NaN, żeby dało się go policzyć."""
    predictions = pd.DataFrame(
        {
            "match_id": ["a", "b"],
            "lambda_home": [1.6, 1.4],
            "mu_away": [1.1, 1.2],
            "rho": [-0.07, -0.07],
        }
    )
    good_home, good_draw, _ = outcome_probabilities(1.5, 1.2, -0.07)
    market = pd.DataFrame(
        {
            "match_id": ["a", "b"],
            "p_home": [good_home, 0.7],
            "p_draw": [good_draw, 0.4],  # niespójne: suma > 1
        }
    )
    out = market_goal_sums(predictions, market)
    assert bool(out.loc[0, "inverted"])
    assert not bool(out.loc[1, "inverted"])
    assert out.loc[0, "market_total"] == pytest.approx(2.7, abs=1e-4)
    assert np.isnan(out.loc[1, "market_total"])
    assert out["our_total"].tolist() == pytest.approx([2.7, 2.6])
