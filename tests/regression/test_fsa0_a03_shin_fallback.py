"""FSA0 A-03 (W.6) — ścieżka awaryjna Shina nie zwraca normalizacji proporcjonalnej.

Ścieżka niebezpieczna: ``shin_probabilities`` bez zbieżności zwracało
``pi / sum(pi)`` — normalizację zakazaną regułą 16 (zawyża longshoty, daje
fałszywe +EV). Chroniła tylko dyscyplina konsumenta, który musiał pamiętać o
``converged``. Teraz wynik bez zbieżności nie nadaje się do użycia bez
jawnego sprawdzenia (NaN), a wariant ``strict`` podnosi wyjątek.
"""

from __future__ import annotations

import numpy as np
import pytest

from helpers import assert_from_checkout, build
from valuebet.pricing.shin import shin_probabilities

assert_from_checkout(__file__)

UNDERROUND = [2.5, 3.0, 4.0]


def test_failed_fit_is_not_proportional_normalisation() -> None:
    bad = shin_probabilities(UNDERROUND, allow_underround=True)
    assert not bad.converged
    pi = 1.0 / np.array(UNDERROUND)
    assert not np.allclose(bad.probabilities, pi / pi.sum(), equal_nan=False)
    assert np.isnan(bad.probabilities).all()


def test_strict_variant_raises() -> None:
    with pytest.raises(ValueError, match="zbieg"):
        build(shin_probabilities, UNDERROUND, allow_underround=True, strict=True)
