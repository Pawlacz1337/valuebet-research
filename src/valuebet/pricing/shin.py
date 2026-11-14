"""Usuwanie marży bukmacherskiej metodą Shina (1992, 1993).

Dlaczego nie normalizacja proporcjonalna
----------------------------------------
Najprostsza metoda odjęcia marży to podzielenie surowych prawdopodobieństw
implikowanych ``pi_i = 1/k_i`` przez ich sumę (booksum). Zakłada to, że
bukmacher rozkłada marżę proporcjonalnie na wszystkie wyniki. Empirycznie
to nieprawda: marża jest przeciążona na longshotach (favourite-longshot
bias). Metoda proporcjonalna systematycznie **zawyża** odzyskane
prawdopodobieństwo outsiderów, co produkuje fałszywe +EV na wysokich
kursach — dokładnie tam, gdzie wariancja jest największa.

Model Shina
-----------
Shin zakłada, że na rynku jest frakcja ``z`` graczy poinformowanych
(insiderów). Bukmacher podnosi marżę, żeby się przed nimi zabezpieczyć, i
robi to nieproporcjonalnie — mocniej tam, gdzie insider ma większą
przewagę. Przy danym ``z`` prawdziwe prawdopodobieństwo to:

    p_i = ( sqrt( z^2 + 4(1-z) * pi_i^2 / P ) - z ) / ( 2(1-z) )

gdzie ``pi_i = 1/k_i`` a ``P = sum(pi_i)`` to booksum. Parametr ``z``
dobierany jest tak, aby ``sum(p_i) == 1``.

Referencje
----------
- Shin, H.S. (1993), "Measuring the Incidence of Insider Trading in a
  Market for State-Contingent Claims", Economic Journal 103, 1141-1153.
- Štrumbelj, E. (2014), "On determining probability forecasts from betting
  odds", International Journal of Forecasting 30(4), 934-943.
  (Pokazuje, że Shin bije normalizację proporcjonalną na danych piłkarskich.)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import brentq

__all__ = [
    "ShinNotConvergedError",
    "ShinResult",
    "booksum",
    "implied_probabilities",
    "overround",
    "shin_forward",
    "shin_probabilities",
]

# Poniżej tej wartości używamy granicy analitycznej wzoru Shina przy
# z -> 0 (patrz _apply_shin), żeby uniknąć dzielenia 0/0.
_Z_EPS = 1e-10
_MAX_ITER = 200
_TOL = 1e-12


@dataclass(frozen=True)
class ShinResult:
    """Wynik usunięcia marży metodą Shina.

    Attributes
    ----------
    probabilities:
        Odzyskane prawdopodobieństwa, sumujące się do 1.
    z:
        Oszacowana frakcja insider tradingu. Typowo 0.01-0.06 na rynkach
        piłkarskich 1X2; wyższe wartości sugerują rynek niepłynny albo
        problem z danymi wejściowymi.
    booksum:
        Suma surowych prawdopodobieństw implikowanych (1 + overround).
    iterations:
        Liczba iteracji do zbieżności.
    converged:
        Czy iteracja zbiegła w granicach tolerancji.
    """

    probabilities: NDArray[np.float64]
    z: float
    booksum: float
    iterations: int
    converged: bool
    #: Czym policzono prawdopodobieństwa: ``"shin"`` albo ``"none"`` (brak
    #: zbieżności — prawdopodobieństwa NaN). Normalizacji proporcjonalnej
    #: (reguła 16) ta funkcja nie zwraca nigdy (FSA0 A-03); konsumenci wołają
    #: wariant ``strict=True``.
    method: str = "shin"

    @property
    def overround(self) -> float:
        """Marża bukmachera jako ułamek (0.06 == 6%)."""
        return self.booksum - 1.0

    @property
    def fair_odds(self) -> NDArray[np.float64]:
        """Kursy sprawiedliwe (bez marży) odpowiadające odzyskanym p."""
        return 1.0 / self.probabilities


def implied_probabilities(odds: ArrayLike) -> NDArray[np.float64]:
    """Surowe prawdopodobieństwa implikowane 1/k. NIE sumują się do 1."""
    arr = np.asarray(odds, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"oczekiwano tablicy 1-D, dostano ndim={arr.ndim}")
    if arr.size < 2:
        raise ValueError("potrzeba co najmniej 2 wyników na rynku")
    if not np.all(np.isfinite(arr)):
        raise ValueError("kursy zawierają NaN lub inf")
    if np.any(arr <= 1.0):
        raise ValueError(
            f"kursy dziesiętne muszą być > 1.0, dostano min={arr.min()}"
        )
    return 1.0 / arr


def booksum(odds: ArrayLike) -> float:
    """Suma 1/k. Wartość > 1 to marża, < 1 to arbitraż (albo błąd danych)."""
    return float(implied_probabilities(odds).sum())


def overround(odds: ArrayLike) -> float:
    """Marża bukmachera jako ułamek: booksum - 1."""
    return booksum(odds) - 1.0


def shin_probabilities(
    odds: ArrayLike,
    *,
    max_iter: int = _MAX_ITER,
    tol: float = _TOL,
    allow_underround: bool = False,
    strict: bool = False,
) -> ShinResult:
    """Usuwa marżę bukmachera metodą Shina.

    Parameters
    ----------
    odds:
        Kursy dziesiętne dla WSZYSTKICH wzajemnie wykluczających się i
        wyczerpujących wyników rynku. Dla 1X2 podaj trzy kursy. Podanie
        niepełnego rynku daje wynik bez sensu — booksum nie ma wtedy
        interpretacji marży.
    max_iter, tol:
        Parametry solvera (Brent).
    allow_underround:
        Jeśli False (domyślnie), booksum < 1 podnosi wyjątek. Underround u
        pojedynczego bukmachera prawie zawsze oznacza błąd danych albo
        niepełny rynek, nie prawdziwy arbitraż.

    Returns
    -------
    ShinResult

    Notes
    -----
    ``z`` znajdujemy metodą Brenta na g(z) = sum(p_i(z)) - 1. Klasyczna
    iteracja punktu stałego z literatury nie zbiega dla małych z i nie
    istnieje dla rynku dwustronnego — szczegóły w ``_solve_z``.
    """
    pi = implied_probabilities(odds)
    bsum = float(pi.sum())

    if not allow_underround and bsum < 1.0:
        raise ValueError(
            f"booksum = {bsum:.6f} < 1 (underround). Prawdopodobnie niepełny "
            "rynek albo błąd danych. Użyj allow_underround=True, jeśli "
            "świadomie podajesz zagregowane kursy z wielu bukmacherów."
        )

    # Bez marży nie ma czego usuwać.
    if abs(bsum - 1.0) < tol:
        return ShinResult(
            method="shin",
            probabilities=pi.copy(),
            z=0.0,
            booksum=bsum,
            iterations=0,
            converged=True,
        )

    z, iterations, converged = _solve_z(pi, bsum, max_iter, tol)
    probs = _apply_shin(pi, bsum, z)

    # Iteracja jest zbieżna, ale renormalizujemy dla pewności numerycznej —
    # bez tego sum(p) potrafi odjechać o ~1e-15 i psuć porównania.
    probs = probs / probs.sum()

    if not converged:
        # Przy braku zbieżności z = 0, a _apply_shin przy z < eps daje
        # pi/sqrt(P), co po renormalizacji JEST normalizacją proporcjonalną
        # — zakazaną w kodzie produkcyjnym (reguła 16). Nie zwracamy jej:
        # NaN nie da się użyć bez zauważenia, a ``strict`` podnosi wyjątek
        # (FSA0 A-03). Wcześniej chroniła tylko dyscyplina konsumenta.
        if strict:
            raise ShinNotConvergedError(
                f"Shin nie zbiegł (booksum {bsum:.6f}) — brak wyceny, nie "
                "normalizacja proporcjonalna (reguła 16)"
            )
        return ShinResult(
            probabilities=np.full_like(pi, np.nan),
            z=float("nan"),
            booksum=bsum,
            iterations=iterations,
            converged=False,
            method="none",
        )

    return ShinResult(
        probabilities=probs,
        z=float(z),
        booksum=bsum,
        iterations=iterations,
        converged=True,
        method="shin",
    )


class ShinNotConvergedError(ValueError):
    """Shin nie zbiegł — wariant ``strict``. Podklasa ``ValueError``."""


def _solve_z(
    pi: NDArray[np.float64], bsum: float, max_iter: int, tol: float
) -> tuple[float, int, bool]:
    """Znajduje z takie, że sum(p_i(z)) == 1.

    Używamy Brenta zamiast iteracji punktu stałego z literatury
    (z_{n+1} = (sum(root) - 2) / (n - 2)). Powód jest praktyczny: tamta
    iteracja nie zbiega dla małych z i nie istnieje dla rynku dwustronnego
    (zero w mianowniku). Brent działa jednolicie dla każdego n i jest
    odporny numerycznie.

    Funkcja celu g(z) = sum(p_i(z)) - 1 jest monotonicznie malejąca:
      - g(0)   = sqrt(P) - 1 > 0  dla książki z marżą
      - g(1^-) = sum(pi_i^2)/P - 1 < 0
    więc pierwiastek jest zawsze zabracketowany na [0, 1).
    """

    def g(z: float) -> float:
        return float(_apply_shin(pi, bsum, z).sum()) - 1.0

    lo, hi = 0.0, 1.0 - 1e-12

    g_lo = g(lo)
    if abs(g_lo) < tol:
        return 0.0, 0, True

    g_hi = g(hi)
    if g_lo * g_hi > 0.0:
        # Nie powinno się zdarzyć dla poprawnej książki z marżą; jeśli
        # jednak się zdarzy, nie zgadujemy — schodzimy na proporcjonalną
        # i sygnalizujemy brak zbieżności.
        return 0.0, 0, False

    z = float(
        brentq(g, lo, hi, xtol=tol, rtol=max(tol, 1e-15), maxiter=max_iter)
    )
    return z, max_iter, True


def _apply_shin(
    pi: NDArray[np.float64], bsum: float, z: float
) -> NDArray[np.float64]:
    """Wzór Shina przy zadanym z.

    Uwaga na granicę z -> 0: NIE jest nią normalizacja proporcjonalna.

        lim_{z->0} ( sqrt(z^2 + 4(1-z) pi_i^2 / P) - z ) / (2(1-z))
            = sqrt(4 pi_i^2 / P) / 2
            = pi_i / sqrt(P)

    czyli suma dąży do sqrt(P), a nie do 1. To nie jest błąd — to właśnie
    jest funkcja celu, której pierwiastka szukamy: g(0) = sqrt(P) - 1 > 0.
    Wstawienie tu pi/P (proporcjonalnej) zeruje g w punkcie 0 i solver
    zwraca z = 0 dla każdej książki.
    """
    if z < _Z_EPS:
        return np.asarray(pi / np.sqrt(bsum), dtype=np.float64)
    root = np.sqrt(z * z + 4.0 * (1.0 - z) * (pi**2) / bsum)
    return np.asarray((root - z) / (2.0 * (1.0 - z)), dtype=np.float64)


def shin_forward(
    probabilities: ArrayLike, z: float, *, margin: float = 0.0
) -> NDArray[np.float64]:
    """Model odwrotny: z prawdziwych p i z generuje kursy bukmachera.

    Używane wyłącznie w testach (round-trip) i w symulacjach Monte Carlo
    backtestu. Odwraca ``shin_probabilities``:

        pi_i = sqrt(P) * sqrt( p_i * ( (1-z) * p_i + z ) )
        sqrt(P) = sum_i sqrt( p_i * ( (1-z) * p_i + z ) )

    Parameters
    ----------
    probabilities:
        Prawdziwe prawdopodobieństwa, muszą sumować się do 1.
    z:
        Frakcja insider tradingu w [0, 1).
    margin:
        Opcjonalna dodatkowa marża proporcjonalna nałożona NA WIERZCH
        marży wynikającej z z. Model czysty Shina przy z=0 daje booksum=1,
        co nie odpowiada rzeczywistości — realne książki mają marżę z obu
        źródeł. Użyj margin, żeby symulować to drugie.
    """
    p = np.asarray(probabilities, dtype=np.float64)
    if not np.isclose(p.sum(), 1.0, atol=1e-9):
        raise ValueError(f"prawdopodobieństwa muszą sumować się do 1, jest {p.sum()}")
    if not 0.0 <= z < 1.0:
        raise ValueError(f"z musi być w [0, 1), jest {z}")
    if margin < 0.0:
        raise ValueError("margin nie może być ujemny")

    inner = np.sqrt(p * ((1.0 - z) * p + z))
    sqrt_p = float(inner.sum())
    pi = sqrt_p * inner * (1.0 + margin)
    return np.asarray(1.0 / pi, dtype=np.float64)
