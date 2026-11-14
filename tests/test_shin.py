"""Testy usuwania marży metodą Shina.

Najważniejszy test to `test_roundtrip_*`: generujemy kursy z prawdziwych
prawdopodobieństw modelem odwrotnym, po czym sprawdzamy, czy Shin je
odzyskuje. Jeśli ten test przechodzi, implementacja jest poprawna
matematycznie, a nie tylko "daje liczby sumujące się do 1".
"""

from __future__ import annotations

import numpy as np
import pytest

from valuebet.pricing.shin import (
    ShinResult,
    booksum,
    implied_probabilities,
    overround,
    shin_forward,
    shin_probabilities,
)

# --------------------------------------------------------------------------
# Podstawy
# --------------------------------------------------------------------------


def test_implied_probabilities_basic() -> None:
    np.testing.assert_allclose(
        implied_probabilities([2.0, 4.0, 4.0]), [0.5, 0.25, 0.25]
    )


def test_booksum_and_overround() -> None:
    odds = [2.0, 4.0, 4.0]
    assert booksum(odds) == pytest.approx(1.0)
    assert overround(odds) == pytest.approx(0.0)

    # Typowa polska książka 1X2 z marżą ~4.8%.
    odds = [2.10, 3.40, 3.60]
    assert overround(odds) == pytest.approx(0.0481, abs=1e-3)


@pytest.mark.parametrize(
    "bad",
    [
        [1.0, 3.0],  # kurs == 1.0
        [0.5, 3.0],  # kurs < 1.0
        [2.0],  # jeden wynik
        [2.0, np.nan],  # NaN
        [2.0, np.inf],  # inf
    ],
)
def test_rejects_invalid_odds(bad: list[float]) -> None:
    with pytest.raises(ValueError):
        implied_probabilities(bad)


def test_rejects_underround_by_default() -> None:
    # booksum < 1 => arbitraż. U jednego bukmachera to błąd danych.
    with pytest.raises(ValueError, match="underround"):
        shin_probabilities([2.5, 3.0, 4.0])


def test_allows_underround_when_explicit() -> None:
    """Dopuszczone wejście, ale bez marży do usunięcia Shin nie zbiega — NaN (A-03)."""
    res = shin_probabilities([2.5, 3.0, 4.0], allow_underround=True)
    assert not res.converged
    assert np.isnan(res.probabilities).all()


# --------------------------------------------------------------------------
# Niezmienniki
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "odds",
    [
        [2.10, 3.40, 3.60],  # 1X2, marża ~7%
        [1.85, 1.95],  # dwustronny, marża ~5%
        [1.30, 5.50, 9.00],  # mocny faworyt
        [1.05, 15.0, 34.0],  # skrajny faworyt
        [4.20, 3.60, 1.95],  # marża ~9%
        [2.50, 3.10, 2.90, 6.00],  # rynek 4-wynikowy
        [1.91, 1.91],  # symetryczny handicap
    ],
)
def test_probabilities_sum_to_one(odds: list[float]) -> None:
    res = shin_probabilities(odds)
    assert res.probabilities.sum() == pytest.approx(1.0, abs=1e-12)
    assert np.all(res.probabilities > 0.0)
    assert res.converged


@pytest.mark.parametrize(
    "odds",
    [
        [2.10, 3.40, 3.60],
        [1.30, 5.50, 9.00],
        [1.05, 15.0, 34.0],
        [2.50, 3.10, 2.90, 6.00],
    ],
)
def test_preserves_ordering(odds: list[float]) -> None:
    """Usuwanie marży nie może zmieniać kolejności wyników."""
    pi = implied_probabilities(odds)
    p = shin_probabilities(odds).probabilities
    np.testing.assert_array_equal(np.argsort(pi), np.argsort(p))


def test_zero_margin_is_identity() -> None:
    """Przy booksum == 1 nie ma czego usuwać."""
    odds = [2.0, 4.0, 4.0]
    res = shin_probabilities(odds)
    np.testing.assert_allclose(res.probabilities, [0.5, 0.25, 0.25], atol=1e-12)
    assert res.z == 0.0


def test_z_in_valid_range() -> None:
    for odds in ([2.10, 3.40, 3.60], [1.30, 5.50, 9.00], [1.85, 1.95]):
        res = shin_probabilities(odds)
        assert 0.0 <= res.z < 1.0


def test_result_helpers() -> None:
    res = shin_probabilities([2.10, 3.40, 3.60])
    assert isinstance(res, ShinResult)
    assert res.overround == pytest.approx(res.booksum - 1.0)
    np.testing.assert_allclose(res.fair_odds, 1.0 / res.probabilities)
    # Kursy sprawiedliwe muszą być wyższe niż oferowane — to jest cała marża.
    assert np.all(res.fair_odds > np.array([2.10, 3.40, 3.60]))


# --------------------------------------------------------------------------
# Round-trip: najważniejszy test poprawności
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "true_p",
    [
        [0.50, 0.25, 0.25],
        [0.45, 0.28, 0.27],
        [0.75, 0.15, 0.10],
        [0.88, 0.08, 0.04],  # skrajny faworyt
        [0.34, 0.33, 0.33],
        [0.60, 0.40],  # dwustronny
        [0.30, 0.25, 0.25, 0.20],  # cztery wyniki
    ],
)
@pytest.mark.parametrize("z", [0.01, 0.03, 0.05, 0.10])
def test_roundtrip_recovers_true_probabilities(
    true_p: list[float], z: float
) -> None:
    """Generujemy kursy modelem odwrotnym, Shin musi odzyskać wejście."""
    odds = shin_forward(true_p, z=z)
    res = shin_probabilities(odds)

    np.testing.assert_allclose(res.probabilities, true_p, atol=1e-8)
    assert res.z == pytest.approx(z, abs=1e-6)
    assert res.converged


def test_roundtrip_forward_produces_overround() -> None:
    """Model odwrotny z z > 0 musi dawać książkę z marżą."""
    odds = shin_forward([0.5, 0.3, 0.2], z=0.05)
    assert booksum(odds) > 1.0


# --------------------------------------------------------------------------
# Przewaga nad normalizacją proporcjonalną
# --------------------------------------------------------------------------


def test_shin_beats_proportional_on_longshots() -> None:
    """Sedno całego modułu.

    Przy prawdziwym insider tradingu normalizacja proporcjonalna zawyża
    longshoty. Ten test weryfikuje, że Shin odzyskuje longshota poprawnie,
    a metoda proporcjonalna go przeszacowuje — czyli dokładnie ten błąd,
    który produkuje fałszywe +EV na wysokich kursach.
    """
    true_p = np.array([0.80, 0.14, 0.06])
    odds = shin_forward(true_p, z=0.06)

    shin_p = shin_probabilities(odds).probabilities
    pi = implied_probabilities(odds)
    proportional_p = pi / pi.sum()

    longshot = 2  # indeks najmniej prawdopodobnego wyniku

    shin_err = abs(shin_p[longshot] - true_p[longshot])
    prop_err = abs(proportional_p[longshot] - true_p[longshot])

    assert shin_err < prop_err, (
        f"Shin err={shin_err:.6f} nie jest lepszy niż proporcjonalny "
        f"err={prop_err:.6f}"
    )
    # Proporcjonalna musi ZAWYŻAĆ longshota, nie zaniżać.
    assert proportional_p[longshot] > true_p[longshot]
    # A Shin musi trafić praktycznie idealnie.
    assert shin_err < 1e-8


def test_proportional_would_create_false_value() -> None:
    """Pokazuje konkretny koszt złej metody w złotówkach EV.

    Bierzemy uczciwą książkę (zero prawdziwego value). Metoda proporcjonalna
    'znajduje' value na longshocie, którego tam nie ma.
    """
    true_p = np.array([0.78, 0.15, 0.07])
    odds = shin_forward(true_p, z=0.06)

    pi = implied_probabilities(odds)
    proportional_p = pi / pi.sum()

    longshot = 2
    # EV liczone błędną metodą — wygląda na dodatnie...
    ev_proportional = proportional_p[longshot] * odds[longshot] - 1.0
    # ...a prawdziwe EV jest ujemne (to marża bukmachera).
    ev_true = true_p[longshot] * odds[longshot] - 1.0

    assert ev_proportional > ev_true
    assert ev_true < 0.0, "kontrola: uczciwa książka nie może mieć +EV"


# --------------------------------------------------------------------------
# Odporność numeryczna
# --------------------------------------------------------------------------


def test_extreme_favourite_is_stable() -> None:
    res = shin_probabilities([1.01, 34.0, 67.0])
    assert res.probabilities.sum() == pytest.approx(1.0)
    assert np.all(np.isfinite(res.probabilities))
    assert res.converged


def test_high_margin_book_is_stable() -> None:
    """Niższe ligi potrafią mieć marżę 15%+."""
    odds = [1.80, 3.20, 3.20]
    assert overround(odds) > 0.12
    res = shin_probabilities(odds)
    assert res.probabilities.sum() == pytest.approx(1.0)
    assert res.converged


def test_many_outcomes_market() -> None:
    """Rynek typu 'dokładny wynik' — wiele wyników, duża marża."""
    odds = [5.0, 6.0, 7.0, 8.0, 9.0, 11.0, 13.0, 16.0, 20.0, 28.0]
    assert booksum(odds) > 1.0
    res = shin_probabilities(odds)
    assert res.probabilities.sum() == pytest.approx(1.0)
    assert res.converged


def test_accepts_numpy_input() -> None:
    res = shin_probabilities(np.array([2.10, 3.40, 3.60]))
    assert res.probabilities.sum() == pytest.approx(1.0)


def test_forward_rejects_bad_input() -> None:
    with pytest.raises(ValueError, match="sumować"):
        shin_forward([0.5, 0.4], z=0.05)
    with pytest.raises(ValueError, match="z musi"):
        shin_forward([0.5, 0.5], z=1.0)
