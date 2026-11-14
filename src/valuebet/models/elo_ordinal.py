"""Mapowanie Elo → rozkład 1X2 przez regresję porządkową (ordered logit).

Po co to istnieje
-----------------
Elo daje ``elo_expected_home`` w skali [0, 1], gdzie remis liczy się jako
0.5. To nie jest rozkład na trzy wyniki — do log loss, EV i porównania z
rynkiem potrzebujemy ``(P(1), P(X), P(2))``. Najprostsze uczciwe
przejście: jeden ukryty wynik ``β · elo_diff`` i dwa progi, między
którymi leży remis::

    P(2) = sigma(θ₁ - β·d)
    P(X) = sigma(θ₂ - β·d) - sigma(θ₁ - β·d)
    P(1) = 1 - sigma(θ₂ - β·d)

Trzy parametry na kilkaset-kilka tysięcy meczów. Nie da się tego
przeuczyć, a szerokość pasma remisu (θ₂ - θ₁) jest dopasowana do ligi,
zamiast wzięta z sufitu.

To jest warstwa KALIBRACJI, nie model
--------------------------------------
Elo nie ma etapu trenowania — rating to deterministyczna funkcja
historii. Jedyne, co jest dopasowywane, to te trzy parametry. Zgodnie z
regułą 9 dopasowujemy je na sezonach SPRZED sezonu testowego (walk-forward
w ``backtest/elo_baseline.py``) i nigdy na tym samym zbiorze, na którym
liczymy metryki.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import minimize
from scipy.special import expit

__all__ = ["OrdinalElo", "outcome_index"]

#: Indeksy wyników w macierzy prawdopodobieństw: kolumna 0 = gospodarz,
#: 1 = remis, 2 = gość. Ta sama konwencja w ``backtest/metrics.py``.
HOME, DRAW, AWAY = 0, 1, 2


def outcome_index(home_goals: ArrayLike, away_goals: ArrayLike) -> NDArray[np.int64]:
    """(gole gospodarza, gole gościa) → 0/1/2 = 1/X/2."""
    hg = np.asarray(home_goals, dtype=np.float64)
    ag = np.asarray(away_goals, dtype=np.float64)
    if np.isnan(hg).any() or np.isnan(ag).any():
        raise ValueError("outcome_index: wynik musi być znany dla każdego meczu")
    return np.where(hg > ag, HOME, np.where(hg == ag, DRAW, AWAY)).astype(np.int64)


@dataclass(frozen=True)
class OrdinalElo:
    """Dopasowany ordered logit. Niemutowalny — ``fit`` zwraca nową instancję."""

    beta: float
    theta_low: float
    theta_high: float
    n_fit: int

    def __post_init__(self) -> None:
        if not self.theta_low < self.theta_high:
            raise ValueError("progi muszą być uporządkowane: theta_low < theta_high")

    @staticmethod
    def _unpack(params: NDArray[np.float64]) -> tuple[float, float, float]:
        # θ₂ = θ₁ + exp(gap) wymusza uporządkowanie progów bez ograniczeń w solverze.
        beta, theta_low, log_gap = params
        return float(beta), float(theta_low), float(theta_low + np.exp(log_gap))

    @staticmethod
    def _probabilities(
        diff: NDArray[np.float64], beta: float, theta_low: float, theta_high: float
    ) -> NDArray[np.float64]:
        latent = beta * diff
        cdf_low = expit(theta_low - latent)
        cdf_high = expit(theta_high - latent)
        probs = np.column_stack([1.0 - cdf_high, cdf_high - cdf_low, cdf_low])
        return np.asarray(probs, dtype=np.float64)

    @classmethod
    def fit(cls, elo_diff: ArrayLike, outcome: ArrayLike) -> OrdinalElo:
        """Maksimum wiarygodności na (elo_diff, wynik). Deterministyczne.

        ``elo_diff`` powinien już zawierać atut boiska (tak jak ``elo_diff``
        z ``compute_elo``). Skalujemy go przez 400, żeby β było rzędu 1 i
        solver nie walczył z warunkowaniem.
        """
        diff = np.asarray(elo_diff, dtype=np.float64) / 400.0
        y = np.asarray(outcome, dtype=np.int64)
        if diff.ndim != 1 or diff.shape != y.shape:
            raise ValueError(
                "elo_diff i outcome muszą być wektorami tej samej długości"
            )
        if len(y) < 30:
            raise ValueError(f"za mało meczów do dopasowania: {len(y)} < 30")
        if not set(np.unique(y)) <= {HOME, DRAW, AWAY}:
            raise ValueError("outcome musi być w {0, 1, 2}")

        def nll(params: NDArray[np.float64]) -> float:
            beta, lo, hi = cls._unpack(params)
            probs = cls._probabilities(diff, beta, lo, hi)
            picked = np.clip(probs[np.arange(len(y)), y], 1e-12, 1.0)
            return float(-np.log(picked).sum())

        # Start: β=1 (nachylenie Elo), remis symetryczny ±0.5 wokół zera.
        start = np.array([1.0, -0.5, 0.0], dtype=np.float64)
        result = minimize(nll, start, method="L-BFGS-B")
        if not result.success:
            raise RuntimeError(f"ordered logit nie zbiegł: {result.message}")
        beta, lo, hi = cls._unpack(np.asarray(result.x, dtype=np.float64))
        return cls(beta=beta, theta_low=lo, theta_high=hi, n_fit=len(y))

    def predict_proba(self, elo_diff: ArrayLike) -> NDArray[np.float64]:
        """Macierz (n, 3) w kolejności 1 / X / 2. Wiersze sumują się do 1."""
        diff = np.asarray(elo_diff, dtype=np.float64) / 400.0
        return self._probabilities(diff, self.beta, self.theta_low, self.theta_high)
