"""``BetJournal`` — odczyt raz, potem pamięć; zmiana pliku z zewnątrz wykrywana.

Backtest finansowy (Filar 1) dopisuje dziesiątki tysięcy kuponów przez TEN
SAM dziennik co live (reguła 28). Pełne parsowanie CSV przy każdym
``add_coupon`` i ``settle`` dawało koszt kwadratowy. Zachowanie ma zostać
identyczne: append-only, wykrycie powtórzonego ``bet_id``, wypłata singla.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from valuebet.live import bets as bets_module
from valuebet.live.bets import BetJournal, BetRecord

T0 = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def _record(n: int, **kwargs: Any) -> BetRecord:
    base: dict[str, Any] = {
        "bet_id": f"b{n}",
        "placed_at": T0,
        "mode": "paper",
        "bookmaker": "bet365",
        "coupon_id": f"c{n}",
        "coupon_type": "single",
        "n_legs": 1,
        "leg_index": 0,
        "match_id": f"m{n}",
        "market": "1x2",
        "outcome": "home",
        "line": None,
        "odds_taken": 2.10,
        "stake": 50.0,
        "tax_factor_applied": 1.00,
        "p_fair_at_bet": 0.52,
        "snapshot_observed_at": T0 - timedelta(hours=1),
        "price_available": True,
        "ingested_at": T0,
        "source": "backtest:test",
    }
    base.update(kwargs)
    return BetRecord(**base)


class _Counter:
    def __init__(self) -> None:
        self.calls = 0
        self.real = csv.DictReader

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        return self.real(*args, **kwargs)


def test_many_adds_and_settles_parse_the_file_at_most_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    counter = _Counter()
    monkeypatch.setattr(bets_module.csv, "DictReader", counter)
    journal = BetJournal(journal_path=tmp_path / "bets.csv")
    for n in range(50):
        journal.add(_record(n))
    for n in range(50):
        journal.settle(f"b{n}", "won", now=T0 + timedelta(hours=3))
    rows = journal.read()
    assert len(rows) == 100
    assert counter.calls <= 1


def test_external_append_is_seen(tmp_path: Path) -> None:
    path = tmp_path / "bets.csv"
    first = BetJournal(journal_path=path)
    first.add(_record(1))
    assert len(first.read()) == 1
    BetJournal(journal_path=path).add(_record(2))
    assert {r.bet_id for r in first.read()} == {"b1", "b2"}
    # Powtórzenie wykryte także dla wiersza dopisanego przez inną instancję.
    with pytest.raises(ValueError, match="append-only"):
        first.add(_record(2))


def test_cached_state_equals_fresh_read(tmp_path: Path) -> None:
    path = tmp_path / "bets.csv"
    journal = BetJournal(journal_path=path)
    for n in range(5):
        journal.add(_record(n, mode="real"))
    journal.settle("b0", "won", now=T0 + timedelta(hours=3))
    journal.settle("b1", "lost", now=T0 + timedelta(hours=3))
    journal.settle("b2", "void", now=T0 + timedelta(hours=3))
    assert journal.read() == BetJournal(journal_path=path).read()
    payouts = {r.bet_id: r.payout for r in journal.read() if r.is_settlement}
    assert payouts == {"b0#settle": 105.0, "b1#settle": 0.0, "b2#settle": 50.0}
    with pytest.raises(ValueError, match="już rozliczona"):
        journal.settle("b0", "won", now=T0 + timedelta(hours=4))


def test_returned_rows_cannot_corrupt_the_cache(tmp_path: Path) -> None:
    journal = BetJournal(journal_path=tmp_path / "bets.csv")
    journal.add(_record(1))
    journal.read().clear()
    assert len(journal.read()) == 1
