"""FSA #0e F0e-03 — klucz zamknięcia CLV: wynik kanoniczny, kolizje bez kolejności, nieznany rynek.

Decyzja Pawła 2026-10-04 (pkt 5, krok 1a): „wynik kanonizowany tak jak rynek,
kolizje kluczy bez zależności od kolejności słownika, nieznany rynek
odrzucany już przy zapisie do dziennika”.

Ścieżki niebezpieczne z raportu audytora (``probes/p_clv_keys.py``):
(a) dziennik ``Home``/``draw``, zamknięcie ``home``/``Draw`` → n/d;
(b) ``h2h`` i ``1x2`` tego samego wyniku zlewają się w jeden klucz, a CLV
zależy od kolejności wstawiania (-10% albo -20%);
(c) jeden klucz z nieznanym rynkiem w mapie zamknięć wywraca cały raport.
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
AS_OF = KO + timedelta(hours=3)


def _bet(market: str, outcome: str, line: float | None, bet_id: str = "a") -> Any:
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


@pytest.mark.parametrize(
    ("journal", "closing", "market", "line"),
    [
        ("Home", "home", "1x2", None),
        ("draw", "Draw", "h2h", None),
        ("over", "Over", "totals", 2.5),
        ("UNDER", "under", "over_under", 2.5),
    ],
)
def test_outcome_is_canonical_on_both_sides(
    journal: str, closing: str, market: str, line: float | None
) -> None:
    rows = clv_rows(
        bets=[_bet(market, journal, line)],
        closing={("m1", market, closing, line): (0.45, KO - timedelta(minutes=5))},
        kickoffs={"m1": KO},
        as_of=AS_OF,
    )
    assert rows[0].clv == pytest.approx(2.0 * 0.45 - 1), rows[0]


def test_journal_stores_canonical_outcome() -> None:
    assert _bet("1x2", "Home", None).outcome == "home"
    assert _bet("totals", "Over", 2.5).outcome == "over"


@pytest.mark.parametrize(
    ("market", "outcome", "line"),
    [("1x2", "Arsenal", None), ("1x2", "over", None), ("totals", "home", 2.5)],
)
def test_journal_rejects_outcome_outside_market(
    market: str, outcome: str, line: float | None
) -> None:
    """Nazwa drużyny albo wynik z innego rynku — błąd przy zapisie, nie n/d w CLV."""
    with pytest.raises(ValueError, match="outcome"):
        _bet(market, outcome, line)


def test_journal_rejects_unknown_market() -> None:
    with pytest.raises(ValueError, match="market"):
        _bet("h2h_lay", "home", None)


@pytest.mark.parametrize("order", ["h2h-pierwszy", "1x2-pierwszy"])
def test_colliding_keys_take_latest_snapshot_regardless_of_order(order: str) -> None:
    """Dwa wpisy tego samego wyniku pod ``h2h`` i ``1x2`` — wygrywa późniejsza migawka."""
    early = (("m1", "h2h", "home", None), (0.40, KO - timedelta(minutes=25)))
    late = (("m1", "1x2", "home", None), (0.45, KO - timedelta(minutes=2)))
    items = [early, late] if order == "h2h-pierwszy" else [late, early]
    rows = clv_rows(
        bets=[_bet("1x2", "home", None)],
        closing=dict(items),
        kickoffs={"m1": KO},
        as_of=AS_OF,
    )
    assert rows[0].clv == pytest.approx(2.0 * 0.45 - 1), rows[0]


def test_unknown_market_in_closing_map_does_not_break_the_report() -> None:
    """Klucz spoza słownika odpada; pozostałe kupony dostają CLV."""
    rows = clv_rows(
        bets=[_bet("1x2", "home", None)],
        closing={
            ("m1", "1x2", "home", None): (0.45, KO - timedelta(minutes=5)),
            ("m1", "h2h_lay", "home", None): (0.50, KO - timedelta(minutes=5)),
        },
        kickoffs={"m1": KO},
        as_of=AS_OF,
    )
    assert rows[0].clv == pytest.approx(2.0 * 0.45 - 1), rows[0]


def test_collision_prefers_snapshot_inside_closing_window() -> None:
    """Migawka in-play (po gwizdku) nie wypiera zamknięcia z okna (backtest-auditor, 2026-10-07)."""
    rows = clv_rows(
        bets=[_bet("1x2", "home", None)],
        closing={
            ("m1", "1x2", "home", None): (0.45, KO - timedelta(minutes=5)),
            ("m1", "h2h", "home", None): (0.60, KO + timedelta(minutes=30)),
        },
        kickoffs={"m1": KO},
        as_of=AS_OF,
    )
    assert rows[0].clv == pytest.approx(2.0 * 0.45 - 1), rows[0]
