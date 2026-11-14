"""FSA0 A-02 — podatek 10% od wygranej powyżej 2280 zł z jednego kuponu.

Ścieżki niebezpieczne (dziś niemodelowane nigdzie):
- rozliczenie kuponu z wypłatą brutto 2500 zł księguje 2500, a na konto
  wpływa 2250 (``docs/promocje.md`` T13, wariant pesymistyczny: 0.90 na
  całej wypłacie);
- EV kandydata, którego wypłata przy wyliczonej stawce przekracza 2280 zł,
  liczone bez czynnika 0.90 — zawyżone o 10% wypłaty.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from helpers import accepts, assert_from_checkout, build
from valuebet.backtest.clv import clv_report
from valuebet.live import bets as bets_module
from valuebet.live.bets import BetJournal, BetRecord
from valuebet.pricing.kelly import KellyPolicy

assert_from_checkout(__file__)

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


def _record(**kw: Any) -> Any:
    base: dict[str, Any] = {
        "bet_id": "b1",
        "placed_at": T0,
        "mode": "real",
        "bookmaker": "betclic",
        "coupon_id": "c1",
        "coupon_type": "single",
        "n_legs": 1,
        "leg_index": 0,
        "match_id": "m1",
        "market": "h2h",
        "outcome": "home",
        "line": None,
        "odds_taken": 2.0,
        "stake": 1250.0,
        "tax_factor_applied": 1.0,
        "p_fair_at_bet": 0.55,
        "snapshot_observed_at": T0 - timedelta(hours=1),
        "price_available": True,
        "ingested_at": T0,
        "source": "manual",
    }
    base.update(kw)
    return build(BetRecord, **base)


def _journal(tmp_path: Path) -> Any:
    path = tmp_path / "bets.csv"
    return build(BetJournal, journal_path=path, path=path)


def _net_payout(journal: Any, now: datetime) -> float:
    coupons = getattr(bets_module, "coupons", None)
    if coupons is not None:
        (coupon,) = coupons(journal.read(), now=now)
        return float(coupon.payout)
    settled = [r for r in journal.read() if r.settled]
    return float(settled[0].payout)


def test_settlement_above_threshold_pays_ninety_percent(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    add = getattr(journal, "add_coupon", None)
    if add is not None:
        add([_record()])
    else:
        journal.add(_record())
    later = T0 + timedelta(hours=4)
    settle = journal.settle
    if accepts(settle, "payout"):
        settle("b1", "won", 2500.0)
    else:
        settle("b1", "won", now=later)
    assert _net_payout(journal, later) == pytest.approx(2250.0)


def test_settlement_below_threshold_is_untaxed(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    add = getattr(journal, "add_coupon", None)
    record = _record(stake=1000.0)
    if add is not None:
        add([record])
    else:
        journal.add(record)
    later = T0 + timedelta(hours=4)
    if accepts(journal.settle, "payout"):
        journal.settle("b1", "won", 2000.0)
    else:
        journal.settle("b1", "won", now=later)
    assert _net_payout(journal, later) == pytest.approx(2000.0)


def test_candidate_ev_uses_winnings_factor_at_computed_stake() -> None:
    policy = KellyPolicy.from_journal(
        bankroll=200_000.0,
        peak_bankroll=200_000.0,
        clv_report=clv_report([]),
        n_real_bets=0,
        open_exposure=0.0,
        match_exposure=0.0,
    )
    decision = policy.stake(0.60, 2.0, tax_factor=1.0)
    # stawka 2% z 200 000 = 4000 zł, wypłata 8000 > 2280 -> w = 0.90
    assert getattr(decision, "winnings_factor", None) == 0.90
    assert getattr(decision, "ev", None) == pytest.approx(0.60 * 2.0 * 1.0 * 0.90 - 1.0)
