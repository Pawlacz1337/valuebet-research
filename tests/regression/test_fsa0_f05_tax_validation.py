"""FSA #0 F-05 — każda funkcja wyceny waliduje ``tax_factor`` i próg.

Ścieżka niebezpieczna: ``min_odds`` (jedyna funkcja wyceny w przeglądzie
dnia) przyjmuje dowolny podatek — przy ``tax = -1`` próg jest ujemny i każdy
kurs wygląda na value; przy pomyłce 1.00 zamiast 0.94 EV +2.5% jest w
rzeczywistości -3.65%. Tak samo ``kelly_fraction`` i ``double_ev``.
Wywołania z nazwanymi argumentami — działają na starej i nowej sygnaturze.
"""

from __future__ import annotations

import math

import pytest

from helpers import assert_from_checkout, build
from valuebet.backtest.clv import clv_report
from valuebet.pricing.ev import double_ev, evaluate, min_odds
from valuebet.pricing.kelly import KellyPolicy, kelly_fraction

assert_from_checkout(__file__)

BAD_TAX = (0.5, 1.5, -1.0, 0.0, 0.9, math.nan)
LEGS = (("m1", 0.55, 2.0), ("m2", 0.60, 1.9))


@pytest.mark.parametrize("tax", BAD_TAX)
def test_min_odds_rejects_tax_outside_domain(tax: float) -> None:
    with pytest.raises(ValueError, match="tax_factor"):
        build(min_odds, 0.5, tax_factor=tax, edge_threshold=0.02, winnings_factor=1.0)


@pytest.mark.parametrize("tax", BAD_TAX)
def test_kelly_fraction_rejects_tax_outside_domain(tax: float) -> None:
    with pytest.raises(ValueError, match="tax_factor"):
        build(kelly_fraction, 0.55, 2.10, tax_factor=tax, winnings_factor=1.0)


@pytest.mark.parametrize("tax", BAD_TAX)
def test_double_ev_rejects_tax_outside_domain(tax: float) -> None:
    with pytest.raises(ValueError, match="tax_factor"):
        build(double_ev, LEGS, tax_factor=tax, winnings_factor=1.0)


def test_kelly_stake_rejects_tax_outside_domain() -> None:
    policy = KellyPolicy.from_journal(
        bankroll=10_000.0,
        peak_bankroll=10_000.0,
        clv_report=clv_report([]),
        n_real_bets=0,
        open_exposure=0.0,
        match_exposure=0.0,
    )
    with pytest.raises(ValueError, match="tax_factor"):
        policy.stake(0.55, 2.10, tax_factor=1.25)


@pytest.mark.parametrize("threshold", [-0.01, math.nan, math.inf])
def test_edge_threshold_must_be_finite_and_nonnegative(threshold: float) -> None:
    with pytest.raises(ValueError, match=r"próg|edge_threshold"):
        build(min_odds, 0.5, tax_factor=1.0, edge_threshold=threshold, winnings_factor=1.0)
    with pytest.raises(ValueError, match=r"próg|edge_threshold"):
        build(evaluate, 0.5, 2.1, tax_factor=1.0, edge_threshold=threshold, winnings_factor=1.0)


def test_valid_values_still_work() -> None:
    assert build(min_odds, 0.5, tax_factor=1.0, edge_threshold=0.02, winnings_factor=1.0) == pytest.approx(2.04)
    assert build(kelly_fraction, 0.55, 2.10, tax_factor=1.0, winnings_factor=1.0) > 0.0
