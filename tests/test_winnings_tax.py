"""Podatek od wygranej (promocje.md T13) — czynnik ``winnings_factor``."""

from __future__ import annotations

import math

import pytest

from valuebet.pricing.ev import (
    WINNINGS_TAX_THRESHOLD,
    ev,
    min_odds,
    settlement_payout,
    validate_winnings_factor,
    winnings_factor_for,
)
from valuebet.pricing.kelly import kelly_fraction


def test_threshold_is_strict_and_on_gross_after_turnover_tax() -> None:
    assert winnings_factor_for(stake=1140.0, odds=2.0, tax_factor=1.0) == 1.00
    assert winnings_factor_for(stake=1140.01, odds=2.0, tax_factor=1.0) == 0.90
    # 1250 · 2.0 · 0.88 = 2200 < 2280 — podatek obrotowy obniża wypłatę.
    assert winnings_factor_for(stake=1250.0, odds=2.0, tax_factor=0.88) == 1.00
    assert WINNINGS_TAX_THRESHOLD == 2280.0


def test_payout_taxed_on_whole_amount() -> None:
    assert settlement_payout(stake=1250.0, odds=2.0, tax_factor=1.0) == pytest.approx(2250.0)
    assert settlement_payout(stake=100.0, odds=2.0, tax_factor=0.94) == pytest.approx(188.0)


@pytest.mark.parametrize("w", [0.95, 1.1, 0.0, math.nan, True])
def test_winnings_factor_domain(w: float) -> None:
    with pytest.raises(ValueError, match="winnings_factor"):
        validate_winnings_factor(winnings_factor=w)
    with pytest.raises(ValueError, match="winnings_factor"):
        ev(0.5, 2.1, tax_factor=1.0, winnings_factor=w)


def test_ev_threshold_and_kelly_include_w() -> None:
    assert ev(0.6, 2.0, tax_factor=1.0, winnings_factor=0.9) == pytest.approx(0.08)
    assert min_odds(0.5, tax_factor=1.0, winnings_factor=0.9, edge_threshold=0.02) == (
        pytest.approx(1.02 / 0.45)
    )
    # k_eff = 2.0 · 0.9 = 1.8; f* = (0.6·1.8 - 1)/(1.8 - 1) = 0.1
    assert kelly_fraction(0.6, 2.0, tax_factor=1.0, winnings_factor=0.9) == pytest.approx(0.1)
