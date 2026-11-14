"""FSA #0b F0b-03 — ``tax_factor_applied`` z dziennika walidowany przed CLV.

Ścieżka niebezpieczna: dziennik live jest wpisywany ręcznie, więc literówka
(1.12 zamiast 0.88, 12 zamiast 1.2) jest realnym trybem awarii. Wartość 1.12
zmieniała CLV z -2.0% na +9.8% i ustawiała ``unlocks_gk``; walidacja
odpalała dopiero przy wypłacie wygranego kuponu — po CLV. Ten sam wzorzec co
F-05: walidacja na jednej ścieżce, brak na drugiej.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from helpers import assert_from_checkout, build
from valuebet.backtest.clv import clv_rows
from valuebet.live.bets import BETS_COLUMNS, BetJournal, BetRecord

assert_from_checkout(__file__)

KO = datetime(2026, 3, 1, 18, 0, tzinfo=UTC)
BAD_TAX = (1.12, 12.0, 0.12, 0.9, 0.0, -1.0, math.nan)


def _fields(tax: float) -> dict[str, Any]:
    return {
        "bet_id": "a",
        "placed_at": KO - timedelta(hours=5),
        "mode": "real",
        "bookmaker": "betclic",
        "coupon_id": "a",
        "coupon_type": "single",
        "n_legs": 1,
        "leg_index": 0,
        "match_id": "m1",
        "market": "h2h",
        "outcome": "home",
        "line": None,
        "odds_taken": 2.0,
        "stake": 10.0,
        "tax_factor_applied": tax,
        "p_fair_at_bet": 0.5,
        "snapshot_observed_at": KO - timedelta(hours=6),
        "price_available": True,
        "ingested_at": KO - timedelta(hours=5),
        "source": "manual",
    }


@pytest.mark.parametrize("tax", BAD_TAX)
def test_bet_record_rejects_tax_outside_domain(tax: float) -> None:
    with pytest.raises(ValueError, match="tax_factor"):
        build(BetRecord, **_fields(tax))


@pytest.mark.parametrize("tax", (1.12, 12.0))
def test_hand_edited_journal_row_is_rejected_on_read(tmp_path: Path, tax: float) -> None:
    """Wiersz wpisany ręcznie do CSV (z pominięciem ``add``) nie przechodzi odczytu."""
    path = tmp_path / "bets.csv"
    journal = build(BetJournal, journal_path=path, path=path)
    good = build(BetRecord, **_fields(1.0))
    journal.add(good)
    text = path.read_text(encoding="utf-8")
    header, row = text.strip().splitlines()
    cells = row.split(",")
    cells[list(BETS_COLUMNS).index("tax_factor_applied")] = str(tax)
    path.write_text(f"{header}\n{','.join(cells)}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="tax_factor"):
        journal.read()


def test_clv_validates_tax_even_if_record_bypassed_constructor() -> None:
    """CLV nie ufa rekordowi: druga ścieżka też waliduje (wzorzec F-05)."""
    record = build(BetRecord, **_fields(1.0))
    object.__setattr__(record, "tax_factor_applied", 1.12)
    closing = {("m1", "h2h", "home", None): (0.49, KO - timedelta(minutes=5))}
    with pytest.raises(ValueError, match="tax_factor"):
        clv_rows(
            bets=[record],
            closing=closing,
            kickoffs={"m1": KO},
            as_of=KO + timedelta(hours=3),
        )
