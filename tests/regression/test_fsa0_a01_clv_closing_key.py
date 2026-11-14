"""FSA0 A-01 — zamknięcie kluczowane wynikiem i rynkiem, nie samym meczem.

Ścieżka niebezpieczna: dwa zakłady na jeden mecz (1 w h2h i powyżej 2.5 w
totalach). Z kluczem ``match_id`` oba dostają to samo ``p_close`` — CLV
jednego z nich jest liczone z prawdopodobieństwa innego zdarzenia.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from helpers import assert_from_checkout, build
from valuebet.backtest.clv import clv_rows
from valuebet.live.bets import BetRecord

assert_from_checkout(__file__)

KO = datetime(2026, 3, 1, 18, 0, tzinfo=UTC)


def _bet(bet_id: str, market: str, outcome: str, line: float | None) -> Any:
    return build(
        BetRecord,
        bet_id=bet_id,
        placed_at=KO - timedelta(hours=5),
        mode="real",
        bookmaker="betclic",
        coupon_id=bet_id,
        coupon_type="single",
        n_legs=1,
        leg_index=0,
        match_id="m1",
        market=market,
        outcome=outcome,
        line=line,
        odds_taken=2.0,
        stake=10.0,
        tax_factor_applied=1.0,
        p_fair_at_bet=0.5,
        snapshot_observed_at=KO - timedelta(hours=6),
        price_available=True,
        ingested_at=KO - timedelta(hours=5),
        source="manual",
    )


def test_two_bets_on_one_match_get_their_own_closing() -> None:
    closing = {
        ("m1", "h2h", "home", None): (0.45, KO - timedelta(minutes=5)),
        ("m1", "totals", "over", 2.5): (0.58, KO - timedelta(minutes=5)),
    }
    rows = clv_rows(
        bets=[_bet("a", "h2h", "home", None), _bet("b", "totals", "over", 2.5)],
        closing=closing,
        kickoffs={"m1": KO},
        as_of=KO + timedelta(hours=3),
    )
    by_id = {r.bet_id: r for r in rows}
    assert by_id["a"].p_close == pytest.approx(0.45)
    assert by_id["b"].p_close == pytest.approx(0.58)
    assert by_id["a"].clv == pytest.approx(2.0 * 0.45 - 1)
    assert by_id["b"].clv == pytest.approx(2.0 * 0.58 - 1)


def test_bare_match_id_key_is_not_a_closing() -> None:
    """Stary format klucza nie może przejść po cichu — to byłby ten sam błąd."""
    rows = clv_rows(
        bets=[_bet("a", "h2h", "home", None)],
        closing={"m1": (0.45, KO - timedelta(minutes=5))},
        kickoffs={"m1": KO},
        as_of=KO + timedelta(hours=3),
    )
    assert rows[0].clv is None
