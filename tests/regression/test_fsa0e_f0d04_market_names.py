"""FSA #0d F0d-04 — jedna nazwa rynku wewnątrz systemu.

Ścieżka niebezpieczna: dziennik przyjmuje oba nazewnictwa (``1x2`` i ``h2h``,
``over_under`` i ``totals``), a ``closing_key`` budował klucz z surowego
napisu nogi. Zamknięcia z kolektora niosą klucze The Odds API — kupon wpisany
jako ``1x2`` nie znajdował zamknięcia i wypadał z CLV (``n_missing``).
Decyzja Pawła (2026-10-03, pkt 3): kanonizacja przez ``MARKET_ALIASES`` na
granicy dziennika; ``clv.py`` porównuje nazwy kanoniczne.
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


def _bet(market: str, outcome: str, line: float | None) -> Any:
    return build(
        BetRecord,
        bet_id="a",
        placed_at=KO - timedelta(hours=5),
        mode="real",
        bookmaker="betclic",
        coupon_id="a",
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


@pytest.mark.parametrize(
    ("journal", "closing", "outcome", "line"),
    [
        ("1x2", "h2h", "home", None),
        ("h2h", "1x2", "home", None),
        ("over_under", "totals", "over", 2.5),
        ("totals", "over_under", "over", 2.5),
    ],
)
def test_clv_finds_closing_across_market_names(
    journal: str, closing: str, outcome: str, line: float | None
) -> None:
    rows = clv_rows(
        bets=[_bet(journal, outcome, line)],
        closing={("m1", closing, outcome, line): (0.45, KO - timedelta(minutes=5))},
        kickoffs={"m1": KO},
        as_of=KO + timedelta(hours=3),
    )
    assert rows[0].clv == pytest.approx(2.0 * 0.45 - 1), rows[0]


def test_journal_stores_one_canonical_name() -> None:
    assert _bet("h2h", "home", None).market == _bet("1x2", "home", None).market
    assert _bet("totals", "over", 2.5).market == _bet("over_under", "over", 2.5).market
