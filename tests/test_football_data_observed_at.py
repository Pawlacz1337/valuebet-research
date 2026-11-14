"""Reguła ``observed_at`` kursów sprzed meczu football-data i godzina gwizdka w UTC.

notes.txt (raw, 2026-10-08): „Betting odds for weekend games are collected
Friday afternoons, and on Tuesday afternoons for midweek games.” Decyzja
Pawła 2026-10-08: gwizdek Pt-Pn → piątek, Wt-Czw → wtorek; koniec
„afternoon” = 18:00 Europe/London (wariant wrażliwości: 23:59); mecz z
gwizdkiem ≤ ``observed_at`` wypada ze strategii przedmeczowych.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from valuebet.ingest.football_data_main import (
    ObservedAtRule,
    kickoff_utc,
    pre_match_observed_at,
)

A = ObservedAtRule.AFTERNOON_1800
E = ObservedAtRule.END_OF_DAY_2359


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def test_kickoff_time_is_london_local_summer_and_winter() -> None:
    # Bayern-Hertha 16.08.2019, 20:30 CEST = 18:30 UTC; w pliku 19:30 (BST).
    assert kickoff_utc("16/08/2019", "19:30") == _utc(2019, 8, 16, 18, 30)
    # RB Leipzig-Bayern 20.01.2023, 20:30 CET = 19:30 UTC; w pliku 19:30 (GMT).
    assert kickoff_utc("20/01/2023", "19:30") == _utc(2023, 1, 20, 19, 30)
    # Dwucyfrowy rok (notes.txt: dd/mm/yy).
    assert kickoff_utc("16/08/19", "19:30") == _utc(2019, 8, 16, 18, 30)


@pytest.mark.parametrize("time", ["", "nan", "25:00", "19.30"])
def test_missing_or_malformed_time_is_an_error(time: str) -> None:
    """Data bez godziny to nie godzina odcięcia (reguła 2)."""
    with pytest.raises(ValueError):
        kickoff_utc("16/08/2019", time)


@pytest.mark.parametrize(
    ("kickoff", "expected"),
    [
        # sobota 15:00 BST → piątek 18:00 BST = 17:00 UTC
        (_utc(2024, 8, 17, 14, 0), _utc(2024, 8, 16, 17, 0)),
        # niedziela, zima → piątek 18:00 GMT
        (_utc(2024, 1, 21, 16, 30), _utc(2024, 1, 19, 18, 0)),
        # poniedziałek 20:00 → poprzedni piątek
        (_utc(2024, 1, 22, 20, 0), _utc(2024, 1, 19, 18, 0)),
        # piątek 20:00 GMT → ten sam piątek 18:00
        (_utc(2024, 1, 19, 20, 0), _utc(2024, 1, 19, 18, 0)),
        # środa → wtorek tego tygodnia
        (_utc(2024, 1, 24, 19, 45), _utc(2024, 1, 23, 18, 0)),
        # czwartek → wtorek
        (_utc(2024, 1, 25, 19, 45), _utc(2024, 1, 23, 18, 0)),
        # wtorek 19:45 → ten sam wtorek 18:00
        (_utc(2024, 1, 23, 19, 45), _utc(2024, 1, 23, 18, 0)),
    ],
)
def test_afternoon_rule(kickoff: datetime, expected: datetime) -> None:
    assert pre_match_observed_at(kickoff, rule=A) == expected


@pytest.mark.parametrize(
    "kickoff",
    [
        _utc(2024, 1, 19, 17, 0),  # piątek 17:00 GMT — przed końcem „afternoon”
        _utc(2024, 1, 19, 18, 0),  # równo 18:00 — ≤ observed_at też wypada
        _utc(2024, 1, 23, 17, 45),  # wtorek 17:45
        _utc(2024, 8, 16, 16, 30),  # piątek 17:30 BST
    ],
)
def test_kickoff_not_after_observed_at_is_excluded(kickoff: datetime) -> None:
    assert pre_match_observed_at(kickoff, rule=A) is None


def test_end_of_day_variant_is_later_and_excludes_evening_games() -> None:
    saturday = _utc(2024, 1, 20, 15, 0)
    assert pre_match_observed_at(saturday, rule=E) == _utc(2024, 1, 19, 23, 59)
    # Piątkowy wieczór: przy 18:00 zostaje, przy 23:59 wypada.
    friday_evening = _utc(2024, 1, 19, 20, 0)
    assert pre_match_observed_at(friday_evening, rule=A) is not None
    assert pre_match_observed_at(friday_evening, rule=E) is None


def test_rule_requires_aware_kickoff_and_explicit_rule() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        pre_match_observed_at(datetime.fromisoformat("2024-01-20T15:00"), rule=A)
    kwargs: dict[str, object] = {}
    with pytest.raises(TypeError, match="rule"):
        pre_match_observed_at(_utc(2024, 1, 20, 15, 0), **kwargs)


def test_rule_values_are_the_config_vocabulary() -> None:
    assert {r.value for r in ObservedAtRule} == {
        "friday_tuesday_1800_london",
        "friday_tuesday_2359_london",
    }
