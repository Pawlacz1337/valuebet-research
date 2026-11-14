"""Kupony w dzienniku (FSA #0 F-02): status, wypłata, CLV, spójność nóg."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from valuebet.backtest.clv import clv_report, clv_rows
from valuebet.live.bets import BetJournal, BetRecord, coupons, live_coupons

T0 = datetime(2026, 11, 7, 10, 0, tzinfo=UTC)
KO = T0 + timedelta(hours=6)


def _leg(i: int, n: int, *, coupon: str = "K", odds: float = 1.5, **kw: Any) -> BetRecord:
    base: dict[str, Any] = {
        "bet_id": f"{coupon}-{i}",
        "placed_at": T0,
        "mode": "real",
        "bookmaker": "betclic",
        "coupon_id": coupon,
        "coupon_type": "multi" if n > 1 else "single",
        "n_legs": n,
        "leg_index": i,
        "match_id": f"m{i}",
        "market": "h2h",
        "outcome": "home",
        "line": None,
        "odds_taken": odds,
        "stake": 100.0,
        "tax_factor_applied": 1.0,
        "p_fair_at_bet": 0.6,
        "snapshot_observed_at": T0 - timedelta(hours=1),
        "price_available": True,
        "ingested_at": T0,
        "source": "manual",
    }
    base.update(kw)
    return BetRecord(**base)


def _journal(tmp_path: Path) -> BetJournal:
    return BetJournal(journal_path=tmp_path / "bets.csv")


def test_double_status_and_payout(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    journal.add_coupon([_leg(0, 2), _leg(1, 2, odds=2.0)])
    s1, s2 = KO + timedelta(hours=2), KO + timedelta(hours=3)
    journal.settle("K-0", "won", now=s1)
    journal.settle("K-1", "won", now=s2)
    rows = journal.read()
    (open_coupon,) = coupons(rows, now=s1 + timedelta(minutes=1))
    assert open_coupon.status == "open" and open_coupon.payout is None
    (done,) = coupons(rows, now=s2)
    assert done.status == "won"
    assert done.payout == pytest.approx(100.0 * 1.5 * 2.0)
    assert done.settled_at == s2
    assert done.ako_at_placement


def test_void_leg_drops_out_of_odds_and_ako(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    journal.add_coupon([_leg(0, 2), _leg(1, 2, odds=2.0)])
    journal.settle("K-0", "void", now=KO + timedelta(hours=2))
    journal.settle("K-1", "won", now=KO + timedelta(hours=2))
    (coupon,) = coupons(journal.read(), now=KO + timedelta(hours=3))
    assert coupon.payout == pytest.approx(200.0)
    assert coupon.ako_at_placement
    assert not coupon.to_placed_bet().qualifies_as_ako, "T6: noga zwrócona się nie liczy"


def test_lost_leg_settles_the_coupon_and_all_void_refunds(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    journal.add_coupon([_leg(0, 2), _leg(1, 2)])
    journal.add_coupon([_leg(0, 1, coupon="S", tax_factor_applied=0.94)])
    journal.settle("K-0", "lost", now=KO + timedelta(hours=2))
    journal.settle("S-0", "void", now=KO + timedelta(hours=2))
    found = {c.coupon_id: c for c in coupons(journal.read(), now=KO + timedelta(hours=3))}
    assert found["K"].status == "lost" and found["K"].payout == 0.0
    assert found["K"].settled_at == KO + timedelta(hours=2)
    assert found["S"].status == "void" and found["S"].payout == pytest.approx(94.0)


def test_coupon_after_now_does_not_exist(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    journal.add_coupon([_leg(0, 1)])
    assert coupons(journal.read(), now=T0 - timedelta(seconds=1)) == []
    with pytest.raises(ValueError, match="timezone"):
        coupons(journal.read(), now=T0.replace(tzinfo=None))


@pytest.mark.parametrize(
    "legs",
    [
        [_leg(0, 2)],
        [_leg(0, 2), _leg(0, 2, bet_id="dup")],
        [_leg(0, 2), _leg(1, 2, stake=50.0)],
        [_leg(0, 2), _leg(1, 2, placed_at=T0 + timedelta(seconds=1))],
        [_leg(0, 2), _leg(1, 2, coupon_id="INNY")],
    ],
)
def test_inconsistent_coupon_is_rejected(tmp_path: Path, legs: list[BetRecord]) -> None:
    with pytest.raises(ValueError):
        _journal(tmp_path).add_coupon(legs)


def test_journal_is_append_only_per_coupon(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    journal.add_coupon([_leg(0, 1)])
    with pytest.raises(ValueError, match="append-only"):
        journal.add_coupon([_leg(0, 1)])
    with pytest.raises(ValueError):
        journal.add_coupon([])
    journal.settle("K-0", "won", now=KO)
    with pytest.raises(ValueError, match="już rozliczona"):
        journal.settle("K-0", "won", now=KO)
    with pytest.raises(ValueError, match="nieznany"):
        journal.settle("K-0", "half_won", now=KO)
    with pytest.raises(ValueError, match="nie ma zakładu"):
        journal.settle("brak", "won", now=KO)


def test_stored_ako_flag_must_match(tmp_path: Path) -> None:
    rows = [
        replace(_leg(0, 2), ako_at_placement=False),
        replace(_leg(1, 2), ako_at_placement=False),
    ]
    with pytest.raises(ValueError, match="rozjechały"):
        coupons(rows, now=KO)


def test_record_validation() -> None:
    with pytest.raises(ValueError):
        _leg(0, 1, coupon_type="multi")
    with pytest.raises(ValueError):
        _leg(2, 2)
    with pytest.raises(ValueError, match="source"):
        _leg(0, 1, source="ręcznie")
    with pytest.raises(ValueError, match="settled_at"):
        _leg(0, 1, settled="won")


def test_live_reader_accepts_manual(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    journal.add_coupon([_leg(0, 1)])
    assert len(live_coupons(tmp_path / "bets.csv", now=KO)) == 1


def test_clv_of_a_double_is_one_observation(tmp_path: Path) -> None:
    rows = [_leg(0, 2), _leg(1, 2, odds=2.0)]
    closing = {
        ("m0", "h2h", "home", None): (0.7, KO - timedelta(minutes=5)),
        ("m1", "h2h", "home", None): (0.55, KO - timedelta(minutes=5)),
    }
    out = clv_rows(
        bets=rows,
        closing=closing,
        kickoffs={"m0": KO, "m1": KO},
        as_of=KO + timedelta(hours=3),
    )
    assert len(out) == 1
    assert out[0].clv == pytest.approx(1.5 * 0.7 * 2.0 * 0.55 - 1.0)
    missing_leg = clv_rows(
        bets=rows,
        closing={("m0", "h2h", "home", None): closing[("m0", "h2h", "home", None)]},
        kickoffs={"m0": KO, "m1": KO},
        as_of=KO + timedelta(hours=3),
    )
    assert missing_leg[0].clv is None
    report = clv_report(missing_leg)
    assert report.n_missing == 1
    after = clv_rows(
        bets=rows,
        closing=closing,
        kickoffs={"m0": KO, "m1": T0 - timedelta(minutes=1)},
        as_of=KO + timedelta(hours=3),
    )
    assert "po gwizdku" in after[0].reason
    late = clv_rows(
        bets=rows,
        closing={k: (p, KO + timedelta(hours=1)) for k, (p, _) in closing.items()},
        kickoffs={"m0": KO, "m1": KO},
        as_of=KO + timedelta(minutes=30),
    )
    assert "po as_of" in late[0].reason
