"""Testy metryk kalibracji. Accuracy nie ma tu czego szukać."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from valuebet.backtest.metrics import (
    constant_probabilities,
    log_loss,
    log_loss_per_match,
    market_probabilities,
    paired_bootstrap_diff,
    reliability_table,
)
from valuebet.pricing.shin import shin_forward


def test_log_loss_of_certain_correct_prediction_is_zero() -> None:
    assert log_loss([[1.0, 0.0, 0.0]], [0]) == pytest.approx(0.0, abs=1e-12)


def test_log_loss_of_uniform_is_log3() -> None:
    p = np.full((5, 3), 1 / 3)
    assert log_loss(p, [0, 1, 2, 0, 1]) == pytest.approx(np.log(3))


def test_log_loss_per_match_picks_realised_outcome() -> None:
    p = [[0.5, 0.3, 0.2], [0.5, 0.3, 0.2]]
    ll = log_loss_per_match(p, [0, 2])
    assert ll.tolist() == pytest.approx([-np.log(0.5), -np.log(0.2)])


@pytest.mark.parametrize(
    ("probs", "message"),
    [
        ([[0.5, 0.5]], r"\(n, 3\)"),
        ([[0.5, 0.3, np.nan]], "NaN"),
        ([[0.5, 0.3, 0.3]], "nie sumują"),
        ([[1.2, -0.1, -0.1]], r"poza \[0, 1\]"),
    ],
)
def test_log_loss_rejects_invalid_distributions(
    probs: list[list[float]], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        log_loss(probs, [0])


def test_constant_probabilities_come_from_train_only() -> None:
    train = [0, 0, 0, 1, 2]  # 60/20/20
    p = constant_probabilities(train, n=4)
    assert p.shape == (4, 3)
    assert p[0].tolist() == pytest.approx([0.6, 0.2, 0.2])
    with pytest.raises(ValueError, match="pusty"):
        constant_probabilities([], n=1)


def test_paired_bootstrap_identical_series_has_zero_diff() -> None:
    a = np.random.default_rng(0).random(200)
    d = paired_bootstrap_diff(a, a)
    assert d.mean_diff == 0.0
    assert d.ci_low <= 0.0 <= d.ci_high
    assert not d.excludes_zero
    assert d.n == 200


def test_paired_bootstrap_detects_constant_shift() -> None:
    rng = np.random.default_rng(0)
    b = rng.random(500)
    a = b + 0.1
    d = paired_bootstrap_diff(a, b)
    assert d.mean_diff == pytest.approx(0.1)
    assert d.excludes_zero
    assert d.ci_low > 0.09


def test_paired_bootstrap_is_deterministic() -> None:
    rng = np.random.default_rng(3)
    a, b = rng.random(100), rng.random(100)
    x = paired_bootstrap_diff(a, b, seed=7)
    y = paired_bootstrap_diff(a, b, seed=7)
    assert (x.ci_low, x.ci_high) == (y.ci_low, y.ci_high)


def test_paired_bootstrap_requires_same_matches() -> None:
    with pytest.raises(ValueError, match="tej samej długości"):
        paired_bootstrap_diff([1.0, 2.0], [1.0])


def test_reliability_table_bins_cover_all_and_closed_at_one() -> None:
    p = np.array([0.0, 0.05, 0.5, 0.95, 1.0])
    y = np.array([0.0, 0.0, 1.0, 1.0, 1.0])
    t = reliability_table(p, y, n_bins=10)
    assert t["n"].sum() == 5
    assert t["bin_high"].iloc[-1] == 1.0  # p = 1.0 trafia do ostatniego koszyka
    assert set(t.columns) >= {
        "bin_low",
        "bin_high",
        "n",
        "mean_predicted",
        "mean_observed",
        "gap",
    }


def test_reliability_table_calibrated_source_has_small_gaps() -> None:
    rng = np.random.default_rng(0)
    p = rng.random(50_000)
    y = (rng.random(50_000) < p).astype(float)
    t = reliability_table(p, y)
    assert (t["gap"].abs() < 0.02).all()
    assert (t["mean_observed"].diff().dropna() > 0).all()  # rosnące koszyki


def test_reliability_table_accepts_elo_scale_observations() -> None:
    t = reliability_table([0.5, 0.5, 0.5], [1.0, 0.5, 0.0])
    assert t["mean_observed"].iloc[0] == pytest.approx(0.5)


def test_market_probabilities_roundtrip_through_shin() -> None:
    true = np.array([0.5, 0.28, 0.22])
    odds = shin_forward(true, z=0.03)
    closing = pd.DataFrame(
        {
            "match_id": ["m1"],
            "odds_home": [odds[0]],
            "odds_draw": [odds[1]],
            "odds_away": [odds[2]],
        }
    )
    out = market_probabilities(closing)
    assert out["match_id"].tolist() == ["m1"]
    assert out[["p_home", "p_draw", "p_away"]].to_numpy()[0] == pytest.approx(
        true, abs=1e-6
    )
    assert out.attrs["not_converged"] == 0


def test_market_probabilities_rejects_duplicates_and_missing_columns() -> None:
    dup = pd.DataFrame(
        {
            "match_id": ["a", "a"],
            "odds_home": [2.0, 2.0],
            "odds_draw": [3.0, 3.0],
            "odds_away": [4.0, 4.0],
        }
    )
    with pytest.raises(ValueError, match="jeden bukmacher"):
        market_probabilities(dup)
    with pytest.raises(ValueError, match="brak kolumn"):
        market_probabilities(pd.DataFrame({"match_id": ["a"], "odds_home": [2.0]}))


# ---------------------------------------------------------------------------
# Bootstrap klastrowy — CI dla liczb raportowanych na zewnątrz.
# ---------------------------------------------------------------------------


def _clustered_series(
    n_groups: int, per_group: int, *, between_sd: float, seed: int = 0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Dane z efektem grupowym: różnica ma wspólne przesunięcie per grupa."""
    rng = np.random.default_rng(seed)
    groups = np.repeat(np.arange(n_groups), per_group)
    shift = rng.normal(0.0, between_sd, size=n_groups)[groups]
    b = rng.random(n_groups * per_group)
    a = b + shift + rng.normal(0.0, 0.01, size=len(b))
    return a, b, groups


def test_clustered_bootstrap_reports_group_count() -> None:
    a, b, g = _clustered_series(12, 50, between_sd=0.05)
    d = paired_bootstrap_diff(a, b, groups=g)
    assert d.n == 600
    assert d.n_groups == 12
    assert d.is_clustered
    assert d.reliable


def test_iid_bootstrap_has_no_groups_and_is_not_clustered() -> None:
    a, b, _ = _clustered_series(12, 50, between_sd=0.05)
    d = paired_bootstrap_diff(a, b)
    assert d.n_groups is None
    assert not d.is_clustered
    assert d.reliable  # iid nigdy nie jest „niewiarygodny", tylko optymistyczny


def test_clustered_bootstrap_is_wider_when_effect_is_between_groups() -> None:
    """Sedno naprawy: przy korelacji wewnątrzgrupowej CI iid jest za wąskie.

    Efekt siedzi MIĘDZY grupami, więc losowanie pojedynczych obserwacji
    uśrednia go i udaje precyzję, której nie ma.
    """
    a, b, g = _clustered_series(12, 50, between_sd=0.05)
    iid = paired_bootstrap_diff(a, b)
    clustered = paired_bootstrap_diff(a, b, groups=g)
    width_iid = iid.ci_high - iid.ci_low
    width_clustered = clustered.ci_high - clustered.ci_low
    assert width_clustered > 2.0 * width_iid


def test_clustered_bootstrap_keeps_point_estimate() -> None:
    """Klastrowanie zmienia tylko CI. Wartość punktowa jest ta sama."""
    a, b, g = _clustered_series(10, 40, between_sd=0.05)
    assert paired_bootstrap_diff(a, b, groups=g).mean_diff == pytest.approx(
        paired_bootstrap_diff(a, b).mean_diff
    )


def test_clustered_bootstrap_weights_by_group_size() -> None:
    """Średnia ważona liczebnością, nie średnia ze średnich grupowych.

    Grupa o 100 meczach i grupa o 1 meczu nie mogą ważyć tak samo — inaczej
    ostatni, obcięty sezon przesuwałby liczbę pooled.
    """
    a = np.array([1.0] * 100 + [10.0])
    b = np.zeros(101)
    g = np.array(["duza"] * 100 + ["mala"])
    d = paired_bootstrap_diff(a, b, groups=g)
    assert d.mean_diff == pytest.approx((100 * 1.0 + 10.0) / 101)
    # Gdyby ważyło po grupach, dolny kraniec siedziałby przy 5.5.
    assert d.ci_low < 3.0


def test_few_clusters_flagged_unreliable() -> None:
    a, b, g = _clustered_series(3, 100, between_sd=0.05)
    d = paired_bootstrap_diff(a, b, groups=g)
    assert d.n_groups == 3
    assert not d.reliable


def test_clustered_bootstrap_is_deterministic() -> None:
    a, b, g = _clustered_series(9, 30, between_sd=0.03, seed=5)
    x = paired_bootstrap_diff(a, b, groups=g, seed=11)
    y = paired_bootstrap_diff(a, b, groups=g, seed=11)
    assert (x.ci_low, x.ci_high) == (y.ci_low, y.ci_high)


def test_groups_length_is_validated() -> None:
    with pytest.raises(ValueError, match="groups musi mieć"):
        paired_bootstrap_diff([1.0, 2.0, 3.0], [0.0, 0.0, 0.0], groups=[0, 1])
