"""FSA #0 F-02 + F-03 + F-31 — kupon w dzienniku, jedna implementacja obrotu.

Ścieżki niebezpieczne:
- dublet AKO (dwie nogi po 100 zł stawki kuponu) + singiel 50 zł: dziennik
  zamieniał każdy wiersz w osobny „singiel”, więc udział AKO był
  strukturalnie 0, a obrót 250 zamiast 150 (F-02);
- ``BetJournal.real_turnover`` — druga implementacja obrotu bez odcięcia
  czasowego (F-03, reguła 28);
- dziennik bez ``ingested_at`` i ``source`` (F-31, reguła 14); wiersze spoza
  ``manual`` w dzienniku live przechodziły po cichu.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from helpers import assert_from_checkout, build
from valuebet.live import bets as bets_module
from valuebet.live.bets import BetJournal, BetRecord
from valuebet.pricing import ev

ROOT = assert_from_checkout(__file__)
T0 = datetime(2026, 11, 7, 10, 0, tzinfo=UTC)


def _row(bet_id: str, coupon: str, match_id: str, odds: float, stake: float, **kw: Any) -> Any:
    base: dict[str, Any] = {
        "bet_id": bet_id,
        "placed_at": T0,
        "mode": "real",
        "bookmaker": "betclic",
        "coupon_id": coupon,
        "coupon_type": "single",
        "n_legs": 1,
        "leg_index": 0,
        "match_id": match_id,
        "market": "h2h",
        "outcome": "home",
        "line": None,
        "odds_taken": odds,
        "stake": stake,
        "tax_factor_applied": 1.0,
        "p_fair_at_bet": 0.5,
        "snapshot_observed_at": T0 - timedelta(hours=1),
        "price_available": True,
        "ingested_at": T0,
        "source": "manual",
    }
    base.update(kw)
    return build(BetRecord, **base)


def _journal(tmp_path: Path) -> Any:
    path = tmp_path / "bets.csv"
    journal = build(BetJournal, journal_path=path, path=path)
    double = [
        _row("d1", "K1", "m1", 1.5, 100.0, coupon_type="multi", n_legs=2, leg_index=0),
        _row("d2", "K1", "m2", 1.6, 100.0, coupon_type="multi", n_legs=2, leg_index=1),
    ]
    single = [_row("s1", "K2", "m3", 2.0, 50.0)]
    if hasattr(journal, "add_coupon"):
        journal.add_coupon(double)
        journal.add_coupon(single)
    else:
        for record in [*double, *single]:
            journal.add(record)
    return journal


def _placed(journal: Any, now: datetime) -> list[Any]:
    coupons = getattr(bets_module, "coupons", None)
    if coupons is not None:
        return [c.to_placed_bet() for c in coupons(journal.read(), now=now)]
    return list(ev.placed_bets_from_journal(journal.read()))


def _config() -> Any:
    cls = getattr(ev, "RegimeConfig", None)
    return cls(
        promo_active=True,
        promo_valid_from=T0 - timedelta(days=30),
        join_date=T0 - timedelta(days=30),
        external_turnover_pln=0.0,
        external_coupons=0,
        share_condition_known=True,
        min_stake_pln=0.0,
        excluded_markets=frozenset(),
        share_basis="stakes",
    )


def test_double_is_one_coupon_with_two_legs(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    now = T0 + timedelta(minutes=1)
    regime = build(ev.BetclicTaxRegime, now=now, bets=_placed(journal, now), regime_config=_config())
    assert regime.real_turnover == pytest.approx(150.0)
    by_stake, _ = regime.ako_shares(candidate=None)
    assert by_stake == pytest.approx(100.0 / 150.0)


def test_every_consumer_counts_coupon_stake_once(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    now = T0 + timedelta(minutes=1)
    coupons = bets_module.coupons(journal.read(), now=now)
    assert len(coupons) == 2
    assert bets_module.open_stake(coupons) == pytest.approx(150.0)
    assert bets_module.match_open_stake(coupons, "m1") == pytest.approx(100.0)
    assert bets_module.real_coupon_count(coupons) == 2


def test_turnover_has_one_implementation() -> None:
    owners = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.FunctionDef) and node.name == "real_turnover":
                owners.append(path.relative_to(ROOT).as_posix())
    assert set(owners) == {"src/valuebet/pricing/ev.py"}, owners


def test_journal_carries_provenance(tmp_path: Path) -> None:
    _journal(tmp_path)
    header = (tmp_path / "bets.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
    for column in ("ingested_at", "source", "coupon_type", "n_legs", "leg_index"):
        assert column in header


def test_live_reader_rejects_non_manual_rows(tmp_path: Path) -> None:
    path = tmp_path / "bets.csv"
    journal = build(BetJournal, journal_path=path, path=path)
    row = _row("x1", "KX", "m9", 2.0, 10.0, source="backtest:abc")
    if hasattr(journal, "add_coupon"):
        journal.add_coupon([row])
    else:
        journal.add(row)
    reader = getattr(bets_module, "live_coupons", None)
    assert reader is not None, "brak czytnika dziennika live z kontrolą source"
    with pytest.raises(ValueError, match="manual"):
        reader(path, now=T0 + timedelta(minutes=1))
