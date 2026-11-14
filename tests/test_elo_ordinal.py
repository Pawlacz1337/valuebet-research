"""Testy ordered logit Elo → 1X2."""

from __future__ import annotations

import numpy as np
import pytest

from valuebet.models.elo_ordinal import AWAY, DRAW, HOME, OrdinalElo, outcome_index


def _synthetic(
    n: int, *, beta: float, lo: float, hi: float, seed: int = 1
) -> tuple[np.ndarray, np.ndarray]:
    """Wyniki wylosowane z ordered logit o znanych parametrach."""
    rng = np.random.default_rng(seed)
    diff = rng.normal(0.0, 150.0, size=n)
    probs = OrdinalElo(beta=beta, theta_low=lo, theta_high=hi, n_fit=0).predict_proba(
        diff
    )
    u = rng.random(n)
    cum = probs.cumsum(axis=1)
    y = (u[:, None] > cum).sum(axis=1)
    return diff, y.astype(np.int64)


def test_outcome_index_mapping() -> None:
    y = outcome_index([2, 1, 0], [0, 1, 3])
    assert y.tolist() == [HOME, DRAW, AWAY]


def test_outcome_index_rejects_missing_result() -> None:
    with pytest.raises(ValueError, match="musi być znany"):
        outcome_index([1.0, np.nan], [0.0, 0.0])


def test_predict_proba_is_distribution_and_monotone() -> None:
    model = OrdinalElo(beta=1.2, theta_low=-0.4, theta_high=0.5, n_fit=0)
    diff = np.linspace(-400, 400, 41)
    p = model.predict_proba(diff)
    assert p.shape == (41, 3)
    assert np.allclose(p.sum(axis=1), 1.0)
    assert (p >= 0).all()
    assert (np.diff(p[:, HOME]) > 0).all()  # silniejszy gospodarz → częściej 1
    assert (np.diff(p[:, AWAY]) < 0).all()
    # Remis najczęstszy w okolicy wyrównanych drużyn, nie na krańcach.
    assert p[20, DRAW] > p[0, DRAW] and p[20, DRAW] > p[-1, DRAW]


def test_fit_recovers_known_parameters() -> None:
    true = {"beta": 1.1, "lo": -0.45, "hi": 0.55}
    diff, y = _synthetic(40_000, **true)
    model = OrdinalElo.fit(diff, y)
    assert model.beta == pytest.approx(true["beta"], abs=0.08)
    assert model.theta_low == pytest.approx(true["lo"], abs=0.05)
    assert model.theta_high == pytest.approx(true["hi"], abs=0.05)
    assert model.n_fit == 40_000


def test_fit_is_deterministic() -> None:
    diff, y = _synthetic(2000, beta=1.0, lo=-0.5, hi=0.5)
    a = OrdinalElo.fit(diff, y)
    b = OrdinalElo.fit(diff, y)
    assert (a.beta, a.theta_low, a.theta_high) == (b.beta, b.theta_low, b.theta_high)


def test_fit_rejects_tiny_sample() -> None:
    with pytest.raises(ValueError, match="za mało"):
        OrdinalElo.fit(np.zeros(10), np.zeros(10, dtype=int))


def test_fit_rejects_bad_outcome() -> None:
    diff = np.zeros(50)
    y = np.full(50, 3)
    with pytest.raises(ValueError, match="outcome"):
        OrdinalElo.fit(diff, y)


def test_thresholds_must_be_ordered() -> None:
    with pytest.raises(ValueError, match="uporządkowane"):
        OrdinalElo(beta=1.0, theta_low=0.5, theta_high=-0.5, n_fit=0)
