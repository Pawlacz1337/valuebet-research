"""Testy kontraktu danych — głównie wymuszania UTC i kompletności rynków."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from valuebet.schema import (
    MarketType,
    Match,
    MatchStatus,
    OddsSnapshot,
    Outcome,
    Selection,
    make_match_id,
)

KICKOFF = datetime(2026, 4, 12, 17, 30, tzinfo=UTC)


def _match(**over: object) -> Match:
    base: dict[str, object] = {
        "match_id": "abc123",
        "competition": "Ekstraklasa",
        "season": "2025/26",
        "kickoff_utc": KICKOFF,
        "home_team_id": "lech-poznan",
        "away_team_id": "legia-warszawa",
    }
    return Match(**(base | over))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Czas
# ---------------------------------------------------------------------------


def test_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError, match="tz-aware"):
        _match(kickoff_utc=datetime(2026, 4, 12, 17, 30))  # noqa: DTZ001


def test_normalises_other_timezone_to_utc() -> None:
    warsaw = timezone(timedelta(hours=2))
    m = _match(kickoff_utc=datetime(2026, 4, 12, 19, 30, tzinfo=warsaw))
    assert m.kickoff_utc == KICKOFF
    assert m.kickoff_utc.tzinfo is UTC


def test_observed_at_must_be_aware() -> None:
    with pytest.raises(ValidationError, match="tz-aware"):
        OddsSnapshot(
            match_id="abc123",
            bookmaker="betclic",
            market=MarketType.ONE_X_TWO,
            outcome=Outcome.HOME,
            odds=2.10,
            observed_at=datetime(2026, 4, 12, 15, 0),  # noqa: DTZ001
        )


# ---------------------------------------------------------------------------
# match_id
# ---------------------------------------------------------------------------


def test_match_id_is_deterministic() -> None:
    a = make_match_id("Ekstraklasa", KICKOFF, "lech-poznan", "legia-warszawa")
    b = make_match_id("Ekstraklasa", KICKOFF, "lech-poznan", "legia-warszawa")
    assert a == b


def test_match_id_ignores_time_within_day() -> None:
    """Źródła podają godziny różniące się o minuty — ID musi być stabilne."""
    a = make_match_id("Ekstraklasa", KICKOFF, "lech-poznan", "legia-warszawa")
    b = make_match_id(
        "Ekstraklasa",
        KICKOFF + timedelta(minutes=15),
        "lech-poznan",
        "legia-warszawa",
    )
    assert a == b


def test_match_id_is_order_sensitive() -> None:
    """Mecz u siebie i na wyjeździe to dwa różne spotkania."""
    home = make_match_id("Ekstraklasa", KICKOFF, "lech-poznan", "legia-warszawa")
    away = make_match_id("Ekstraklasa", KICKOFF, "legia-warszawa", "lech-poznan")
    assert home != away


def test_match_id_normalises_competition_diacritics() -> None:
    a = make_match_id("1. Liga", KICKOFF, "a", "b")
    b = make_match_id("1. LIGA", KICKOFF, "a", "b")
    assert a == b


def test_match_id_rejects_naive() -> None:
    with pytest.raises(ValueError, match="tz-aware"):
        make_match_id("Ekstraklasa", datetime(2026, 4, 12), "a", "b")  # noqa: DTZ001


# ---------------------------------------------------------------------------
# Match
# ---------------------------------------------------------------------------


def test_team_cannot_play_itself() -> None:
    with pytest.raises(ValidationError, match="sama ze sobą"):
        _match(away_team_id="lech-poznan")


def test_finished_match_needs_result() -> None:
    with pytest.raises(ValidationError, match="oba wyniki"):
        _match(status=MatchStatus.FINISHED)


def test_partial_result_rejected() -> None:
    with pytest.raises(ValidationError, match="kompletny albo pusty"):
        _match(home_goals=2)


def test_scheduled_match_has_no_result() -> None:
    m = _match()
    assert m.has_result is False


def test_finished_match_has_result() -> None:
    m = _match(status=MatchStatus.FINISHED, home_goals=2, away_goals=1)
    assert m.has_result is True


def test_extra_field_accepts_arbitrary_payload() -> None:
    """Miejsce na przyszłe cechy bez migracji schematu."""
    m = _match(extra={"attendance": 41_000, "referee": "Szymon Marciniak"})
    assert m.extra["attendance"] == 41_000


def test_unknown_top_level_field_rejected() -> None:
    """extra='forbid' — literówka w nazwie pola ma boleć od razu."""
    with pytest.raises(ValidationError):
        _match(home_goalz=2)


def test_match_is_frozen() -> None:
    m = _match()
    with pytest.raises(ValidationError):
        m.home_goals = 3  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def test_selection_rejects_outcome_not_in_market() -> None:
    with pytest.raises(ValidationError, match="nie należy do rynku"):
        Selection(
            match_id="abc123", market=MarketType.ONE_X_TWO, outcome=Outcome.OVER
        )


def test_over_under_requires_line() -> None:
    with pytest.raises(ValidationError, match="wymaga podania line"):
        Selection(match_id="abc123", market=MarketType.OVER_UNDER, outcome=Outcome.OVER)


def test_one_x_two_rejects_line() -> None:
    with pytest.raises(ValidationError, match="nie przyjmuje line"):
        Selection(
            match_id="abc123",
            market=MarketType.ONE_X_TWO,
            outcome=Outcome.HOME,
            line=2.5,
        )


def test_selection_key_is_stable_and_distinct() -> None:
    a = Selection(
        match_id="abc123", market=MarketType.OVER_UNDER, outcome=Outcome.OVER, line=2.5
    )
    b = Selection(
        match_id="abc123", market=MarketType.OVER_UNDER, outcome=Outcome.OVER, line=3.5
    )
    assert a.selection_key == "abc123:over_under:over@2.5"
    assert a.selection_key != b.selection_key


# ---------------------------------------------------------------------------
# OddsSnapshot
# ---------------------------------------------------------------------------


def _odds(**over: object) -> OddsSnapshot:
    base: dict[str, object] = {
        "match_id": "abc123",
        "bookmaker": "betclic",
        "market": MarketType.ONE_X_TWO,
        "outcome": Outcome.HOME,
        "odds": 2.10,
        "observed_at": KICKOFF,
    }
    return OddsSnapshot(**(base | over))  # type: ignore[arg-type]


def test_odds_must_exceed_one() -> None:
    with pytest.raises(ValidationError):
        _odds(odds=1.0)


def test_tax_factor_defaults_to_polish_standard() -> None:
    assert _odds().tax_factor == pytest.approx(0.88)


@pytest.mark.parametrize(
    ("tax", "expected"),
    [(1.00, 2.10), (0.94, 1.974), (0.88, 1.848)],
)
def test_effective_odds_applies_tax(tax: float, expected: float) -> None:
    """Podatek od stawki działa jak mnożnik kursu."""
    assert _odds(tax_factor=tax).effective_odds == pytest.approx(expected)


def test_effective_odds_shows_break_even_threshold() -> None:
    """Kurs 2.10 przy standardowym podatku jest poniżej progu 1/p dla p=0.5."""
    assert _odds(tax_factor=0.88).effective_odds < 2.0


def test_selection_key_matches_between_selection_and_snapshot() -> None:
    """Klucze muszą się zgadzać, inaczej join kursów z typami milcząco pada."""
    sel = Selection(
        match_id="abc123", market=MarketType.OVER_UNDER, outcome=Outcome.OVER, line=2.5
    )
    snap = _odds(market=MarketType.OVER_UNDER, outcome=Outcome.OVER, line=2.5)
    assert sel.selection_key == snap.selection_key
