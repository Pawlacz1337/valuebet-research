"""FSA #0 F-20 — wycena wymaga gwizdka; po gwizdku i bez gwizdka nie ma ceny.

Ścieżka niebezpieczna: ``fair_prices`` bez ``kickoffs``. Migawka sprzed
godziny z meczu, który trwa od dwóch godzin, zostaje wyceniona jako
przedmeczowa — kurs live niesie wynik, więc w odtwarzaniu historycznym daje
dowolnie dużą pozorną przewagę.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from helpers import assert_from_checkout
from valuebet.pricing.fair import MarketQuote, fair_prices

assert_from_checkout(__file__)

KICKOFF = datetime(2026, 10, 24, 15, 0, tzinfo=UTC)
DECISION = KICKOFF + timedelta(hours=2)
QUOTE = MarketQuote(
    match_id="m1",
    market="h2h",
    outcomes=("home", "draw", "away"),
    odds=(1.95, 3.60, 4.20),
    observed_at=DECISION - timedelta(hours=1),
)


def _prices(result: Any) -> list[Any]:
    return list(getattr(result, "prices", result))


def test_pricing_without_kickoffs_is_refused() -> None:
    with pytest.raises(TypeError):
        fair_prices([QUOTE], decision_time=DECISION)


def test_match_without_known_kickoff_is_not_priced() -> None:
    result = fair_prices([QUOTE], decision_time=DECISION, kickoffs={})
    assert _prices(result) == []
    assert getattr(result, "skipped", {}).get("brak gwizdka") == 1


def test_live_match_is_not_priced() -> None:
    result = fair_prices([QUOTE], decision_time=DECISION, kickoffs={"m1": KICKOFF})
    assert _prices(result) == []
    assert getattr(result, "skipped", {}).get("po gwizdku") == 1


def test_decision_exactly_at_kickoff_is_not_priced() -> None:
    quote = MarketQuote(
        match_id="m1",
        market="h2h",
        outcomes=("home", "draw", "away"),
        odds=(1.95, 3.60, 4.20),
        observed_at=KICKOFF - timedelta(hours=1),
    )
    result = fair_prices([quote], decision_time=KICKOFF, kickoffs={"m1": KICKOFF})
    assert _prices(result) == []
