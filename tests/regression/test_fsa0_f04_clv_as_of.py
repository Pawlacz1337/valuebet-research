"""FSA #0 F-04 — CLV bez granicy czasu nie istnieje.

Ścieżka niebezpieczna: ``clv_rows`` wywołane bez ``as_of``. Do agregatu
wchodzą mecze jeszcze nierozegrane, a ich wysokie CLV podnosi CI i — przez
``ClvReport.unlocks_gk`` — ułamek Kelly'ego. Zmierzone w FSA #0: CLV -1.0%
zamienia się w +9.5%, ``unlocks_gk`` z False na True.

Poza agregatem (liczone osobno jako ``excluded_future``): zakład po
``as_of``, mecz bez gwizdka, gwizdek po ``as_of``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from helpers import assert_from_checkout, build
from valuebet.backtest.clv import clv_report, clv_rows
from valuebet.live.bets import BetRecord

assert_from_checkout(__file__)

T0 = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
P_CLOSE = 0.5


def _bet(bet_id: str, match_id: str, kickoff: datetime, odds: float) -> Any:
    return build(
        BetRecord,
        bet_id=bet_id,
        placed_at=kickoff - timedelta(hours=6),
        mode="real",
        bookmaker="betclic",
        coupon_id=bet_id,
        coupon_type="single",
        n_legs=1,
        leg_index=0,
        match_id=match_id,
        market="h2h",
        outcome="home",
        line=None,
        odds_taken=odds,
        stake=10.0,
        tax_factor_applied=1.0,
        p_fair_at_bet=0.5,
        snapshot_observed_at=kickoff - timedelta(hours=7),
        price_available=True,
        ingested_at=kickoff - timedelta(hours=6),
        source="manual",
    )


def _world() -> tuple[list[Any], dict[Any, tuple[float, datetime]], dict[str, datetime]]:
    bets, closing, kickoffs = [], {}, {}
    for i in range(40):
        # 10 przeszłych kolejek, CLV = 1.98 * 0.5 - 1 = -0.01
        ko = T0 - timedelta(weeks=10 - i // 4)
        mid = f"past{i}"
        bets.append(_bet(f"p{i}", mid, ko, 1.98))
        kickoffs[mid] = ko
        for key in (mid, (mid, "h2h", "home", None)):
            closing[key] = (P_CLOSE, ko - timedelta(minutes=5))
    for i in range(40):
        # mecze PO chwili decyzji, CLV = 2.40 * 0.5 - 1 = +0.20
        ko = T0 + timedelta(weeks=1 + i // 4)
        mid = f"future{i}"
        bets.append(_bet(f"f{i}", mid, ko, 2.40))
        kickoffs[mid] = ko
        for key in (mid, (mid, "h2h", "home", None)):
            closing[key] = (P_CLOSE, ko - timedelta(minutes=5))
    return bets, closing, kickoffs


def test_clv_without_as_of_is_refused() -> None:
    bets, closing, kickoffs = _world()
    with pytest.raises(TypeError):
        clv_rows(bets=bets, closing=closing, kickoffs=kickoffs)


def test_future_matches_are_excluded_and_counted() -> None:
    bets, closing, kickoffs = _world()
    rows = clv_rows(bets=bets, closing=closing, kickoffs=kickoffs, as_of=T0)
    report = clv_report(rows)
    assert report.mean == pytest.approx(-0.01, abs=1e-9)
    assert not report.unlocks_gk
    assert getattr(report, "n_excluded_future", None) == 40


def test_match_without_kickoff_is_excluded() -> None:
    bets, closing, kickoffs = _world()
    del kickoffs["past0"]
    rows = clv_rows(bets=bets, closing=closing, kickoffs=kickoffs, as_of=T0)
    report = clv_report(rows)
    assert report.n_total == 39
    assert getattr(report, "n_excluded_future", None) == 41


def test_naive_as_of_is_rejected() -> None:
    bets, closing, kickoffs = _world()
    with pytest.raises(ValueError, match="timezone"):
        clv_rows(bets=bets, closing=closing, kickoffs=kickoffs, as_of=T0.replace(tzinfo=None))
