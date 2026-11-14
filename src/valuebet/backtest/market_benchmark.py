"""Benchmark kalibracji wobec zamknięcia rynku (STEP4_ENSEMBLE §11.4).

Po co to istnieje
-----------------
Nachylenie regresji zrealizowanej sumy goli na przewidywanej **nie ma
mocy**. Zrealizowana suma to niemal czysty szum Poissona (sd 1.63) wobec
rozrzutu prawdziwej oczekiwanej sumy rzędu 0.14, więc korelacja wychodzi
r ~ 0.07 i przedział ufności nachylenia obejmuje prawie wszystko
(zmierzone: [0.31, 1.80]).

Ten sam test da się zrobić z mocą, jeśli zamiast wyniku użyć celu o
wielokrotnie mniejszym szumie: **sumy goli implikowanej z kursów 1X2
Pinnacle na zamknięciu**.

Własność wieży
--------------
Jeśli nasza predykcja jest skalibrowana przy naszej informacji, a rynek na
zamknięciu wie co najmniej tyle co my, to::

    E[T_rynek | T_nasze] = T_nasze

czyli nachylenie regresji ``T_rynek`` na ``T_nasze`` wynosi 1. Predykcje za
szerokie dają nachylenie < 1, za wąskie > 1. Szum w zmiennej objaśnianej
nie obciąża nachylenia, więc wolno nam użyć celu, który sam jest
oszacowaniem.

Błąd standardowy wychodzi ~20x mniejszy niż przy nachyleniu wobec wyniku.

Granice użycia — reguły 7 i 19
-------------------------------
Kursy zamknięcia są tu **wyłącznie diagnostyką**. Nie są cechą modelu, nie
są ceną wejścia i nie są celem strojenia. Wynik tego benchmarku nie jest
zaproszeniem do dokalibrowania DC — obowiązuje reguła stopu ze
STEP4_ENSEMBLE §11.5.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy.optimize import brentq, least_squares

from valuebet.models.dixon_coles import MAX_GOALS_DEFAULT, matrix_from_rates

__all__ = [
    "MIN_CLUSTERS",
    "ClusteredSlope",
    "clustered_slope",
    "implied_goal_rates",
    "implied_total_from_over",
    "outcome_probabilities",
    "over_probability",
]

#: Poniżej tylu klastrów bootstrap klastrowy nie zwraca liczby, tylko NaN.
#: W raporcie z 21:09 koszyk zasilany jednym sezonem dał przedział zerowej
#: szerokości i z ~ -9e14. Taka liczba ma się nie dać wydrukować.
MIN_CLUSTERS = 5

#: Stały punkt startowy odwracania, w log-przestrzeni. Stały, bo wynik ma
#: być deterministyczny i niezależny od tego, co akurat przewidział model.
_START = (np.log(1.4), np.log(1.1))

#: Powyżej tego residuum uznajemy odwrócenie za nieudane i zwracamy NaN.
#: Nigdy cicha liczba — mecz, którego nie dało się odwrócić, ma zniknąć
#: z benchmarku jawnie i być policzony.
_RESIDUAL_TOLERANCE = 1e-7


def outcome_probabilities(
    lam: float, mu: float, rho: float, *, max_goals: int = MAX_GOALS_DEFAULT
) -> tuple[float, float, float]:
    """``(P(1), P(X), P(2))`` z macierzy wyników."""
    matrix = matrix_from_rates(lam, mu, rho, max_goals=max_goals)
    return (
        float(np.tril(matrix, -1).sum()),
        float(np.trace(matrix)),
        float(np.triu(matrix, 1).sum()),
    )


def over_probability(
    lam: float,
    mu: float,
    rho: float,
    line: float = 2.5,
    *,
    max_goals: int = MAX_GOALS_DEFAULT,
) -> float:
    """``P(suma goli > line)`` z macierzy. Linia połówkowa — bez pusha."""
    matrix = matrix_from_rates(lam, mu, rho, max_goals=max_goals)
    grid = np.arange(matrix.shape[0])
    totals = grid[:, None] + grid[None, :]
    return float(matrix[totals > line].sum())


def implied_goal_rates(
    q_home: float,
    q_draw: float,
    rho: float,
    *,
    max_goals: int = MAX_GOALS_DEFAULT,
) -> tuple[float, float]:
    """Odwrócenie 1X2 rynku na ``(lambda, mu)`` przy naszym ``rho``.

    Szuka ``(lambda, mu)`` spełniających ``P_DC(1) = q_home`` i
    ``P_DC(X) = q_draw`` przy zadanym ``rho``. Dwa równania, dwie
    niewiadome — rozwiązanie jest lokalnie jednoznaczne, ale nie ma postaci
    zamkniętej, więc idziemy ``least_squares`` po ``(log lambda, log mu)``.

    Praca w log-przestrzeni utrzymuje dodatniość bez ograniczeń w solverze.

    Zwraca ``(nan, nan)``, gdy wejście jest niespójne (``q_home + q_draw >= 1``
    albo któreś ``q <= 0``) lub residuum przekracza tolerancję. **Nigdy nie
    zwraca cichej liczby dla meczu, którego nie udało się odwrócić** —
    takie mecze mają być policzone i zgłoszone.
    """
    if not (0.0 < q_home < 1.0 and 0.0 < q_draw < 1.0):
        return float("nan"), float("nan")
    if q_home + q_draw >= 1.0:
        return float("nan"), float("nan")

    target = np.array([q_home, q_draw], dtype=np.float64)

    def residual(log_rates: NDArray[np.float64]) -> NDArray[np.float64]:
        lam, mu = np.exp(log_rates)
        home, draw, _ = outcome_probabilities(
            float(lam), float(mu), rho, max_goals=max_goals
        )
        return np.array([home, draw], dtype=np.float64) - target

    solution = least_squares(
        residual, np.array(_START), xtol=1e-12, ftol=1e-12, gtol=1e-12
    )
    if float(np.abs(solution.fun).max()) > _RESIDUAL_TOLERANCE:
        return float("nan"), float("nan")
    lam, mu = np.exp(solution.x)
    return float(lam), float(mu)


def implied_total_from_over(
    q_over: float,
    ratio: float,
    rho: float,
    line: float = 2.5,
    *,
    max_goals: int = MAX_GOALS_DEFAULT,
) -> float:
    """Suma goli ``T``, przy której ``P_DC(suma > line) = q_over``.

    Drugi, **niezależny** odczyt tej samej wielkości co
    ``implied_goal_rates``: tam suma bierze się z rynku 1X2, tu z rynku
    totali. Porównanie obu odpowiada na pytanie, czy wyprowadzanie sumy
    goli z samego 1X2 jest w ogóle dobrym instrumentem
    (STEP4_ENSEMBLE §11.10 A).

    ``ratio`` = ``lambda/mu`` bierzemy z odwrócenia 1X2 — rynek totali nie
    niesie informacji o tym, która drużyna strzeli. Szukamy wyłącznie
    poziomu, przy ustalonym podziale.

    Zwraca ``nan``, gdy ``q_over`` jest poza ``(0, 1)``, gdy ``ratio`` jest
    niedodatnie albo gdy rozwiązania nie da się zabracketować.
    """
    if not (0.0 < q_over < 1.0) or not np.isfinite(ratio) or ratio <= 0.0:
        return float("nan")

    def over_for_total(total: float) -> float:
        lam = total * ratio / (1.0 + ratio)
        mu = total / (1.0 + ratio)
        return over_probability(lam, mu, rho, line, max_goals=max_goals)

    # Zakres bracketu celowo wąski: suma 7 goli to już absurd piłkarski, a
    # szerszy przedział tylko zasypuje log ostrzeżeniami o masie poza
    # obcięciem macierzy. Poza zakresem zwracamy NaN, nie zgadujemy.
    low, high = 0.2, 7.0

    def shifted(total: float) -> float:
        return over_for_total(total) - q_over

    if not (shifted(low) < 0.0 < shifted(high)):
        return float("nan")
    try:
        root = brentq(shifted, low, high, xtol=1e-10, rtol=1e-12, maxiter=200)
    except (ValueError, RuntimeError):
        return float("nan")
    return float(root)


@dataclass(frozen=True)
class ClusteredSlope:
    """Nachylenie regresji z przedziałem z bootstrapu klastrowego.

    ``ci_low`` i ``ci_high`` są ``NaN``, gdy klastrów jest mniej niż
    ``MIN_CLUSTERS`` — wtedy przedział nie niesie informacji i nie wolno
    go wydrukować jako liczby.
    """

    slope: float
    intercept: float
    ci_low: float
    ci_high: float
    n: int
    n_clusters: int
    correlation: float
    sd_x: float
    sd_y: float

    @property
    def has_ci(self) -> bool:
        return bool(np.isfinite(self.ci_low) and np.isfinite(self.ci_high))

    @property
    def half_width(self) -> float:
        return (self.ci_high - self.ci_low) / 2.0 if self.has_ci else float("nan")

    def describe(self) -> str:
        if not self.has_ci:
            return (
                f"nachylenie={self.slope:.4f}  CI: n/d ({self.n_clusters} klastrów, "
                f"wymagane {MIN_CLUSTERS})  n={self.n}"
            )
        return (
            f"nachylenie={self.slope:.4f}  CI [{self.ci_low:.4f}, {self.ci_high:.4f}]  "
            f"polowa szerokosci={self.half_width:.4f}  n={self.n}  "
            f"r={self.correlation:.4f}"
        )


def clustered_slope(
    x: NDArray[np.float64],
    y: NDArray[np.float64],
    groups: NDArray[np.str_],
    *,
    n_boot: int = 4000,
    confidence: float = 0.95,
    seed: int = 0,
) -> ClusteredSlope:
    """Nachylenie ``y ~ x`` z bootstrapem losującym całe klastry.

    Klastrem jest sezon. Przy mniej niż ``MIN_CLUSTERS`` klastrach
    przedział to ``NaN`` — patrz ``MIN_CLUSTERS``.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y, groups = x[ok], y[ok], np.asarray(groups)[ok]
    if len(x) < 3:
        raise ValueError(f"za mało punktów do regresji: {len(x)}")

    fit = np.polyfit(x, y, 1)
    unique = np.unique(groups)
    index = {g: np.flatnonzero(groups == g) for g in unique}

    if len(unique) < MIN_CLUSTERS:
        low = high = float("nan")
    else:
        rng = np.random.default_rng(seed)
        draws = np.empty(n_boot, dtype=np.float64)
        for i in range(n_boot):
            pick = rng.integers(0, len(unique), size=len(unique))
            rows = np.concatenate([index[unique[j]] for j in pick])
            draws[i] = np.polyfit(x[rows], y[rows], 1)[0]
        alpha = (1.0 - confidence) / 2.0
        low, high = (float(v) for v in np.quantile(draws, [alpha, 1.0 - alpha]))

    return ClusteredSlope(
        slope=float(fit[0]),
        intercept=float(fit[1]),
        ci_low=low,
        ci_high=high,
        n=len(x),
        n_clusters=len(unique),
        correlation=float(np.corrcoef(x, y)[0, 1]),
        sd_x=float(np.std(x)),
        sd_y=float(np.std(y)),
    )


def market_goal_sums(
    predictions: pd.DataFrame, market: pd.DataFrame
) -> pd.DataFrame:
    """Dla każdego meczu: nasza suma goli i suma implikowana z rynku.

    ``predictions`` musi mieć ``match_id``, ``lambda_home``, ``mu_away``,
    ``rho``; ``market`` — ``match_id``, ``p_home``, ``p_draw``.

    Kolumna ``inverted`` mówi, czy odwrócenie się udało. Mecze nieodwrócone
    zostają w ramce z ``NaN``, żeby dało się je policzyć, a nie żeby
    zniknęły po cichu.
    """
    joined = predictions.merge(market, on="match_id", how="inner", validate="one_to_one")
    rates = [
        implied_goal_rates(float(qh), float(qd), float(rho))
        for qh, qd, rho in zip(
            joined["p_home"], joined["p_draw"], joined["rho"], strict=True
        )
    ]
    market_lam = np.array([r[0] for r in rates], dtype=np.float64)
    market_mu = np.array([r[1] for r in rates], dtype=np.float64)
    return joined.assign(
        market_lambda=market_lam,
        market_mu=market_mu,
        market_total=market_lam + market_mu,
        our_total=joined["lambda_home"].to_numpy() + joined["mu_away"].to_numpy(),
        inverted=np.isfinite(market_lam),
    )
