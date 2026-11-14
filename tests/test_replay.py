"""``backtest/replay.py`` — wiersz football-data → migawka decyzyjna, zamknięcie, wynik.

Co ma być prawdą (BACKTEST_FIN_PLAN §2, §4 pkt 6):

- ``observed_at < decision_at < kickoff < settled_at`` dla każdego meczu;
- ``observed_at`` z reguły ``config/strategy.yaml`` (piątek/wtorek London),
  mecz z gwizdkiem ≤ ``observed_at`` wypada z licznikiem per liga i sezon;
- migawka decyzyjna to kolumny SPRZED meczu, zamknięcie to kolumny ``C``;
- wynik nie jest częścią meczu — leży osobno, z ``settled_at`` po gwizdku;
- rynek niekompletny u bukmachera → brak notowania (reguła 17), z licznikiem.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from valuebet.backtest.replay import (
    CLOSING_BEFORE_KICKOFF,
    DECISION_LAG,
    SETTLE_AFTER,
    Replay,
    ReplayMatch,
    replay_csv,
)
from valuebet.ingest.football_data_main import ObservedAtRule

A = ObservedAtRule.AFTERNOON_1800
HEADER = (
    "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,"
    "PSH,PSD,PSA,B365H,B365D,B365A,BWH,BWD,BWA,MaxH,MaxD,MaxA,"
    "P>2.5,P<2.5,B365>2.5,B365<2.5,"
    "PSCH,PSCD,PSCA,PC>2.5,PC<2.5,B365CH,B365CD,B365CA\n"
)
# Sobota 17.08.2024 15:00 BST (14:00 UTC): obserwacja piątek 16.08 18:00 BST.
ROW_SAT = (
    "E0,17/08/2024,15:00,Arsenal,Wolves,2,0,"
    "1.30,6.00,10.0,1.28,5.75,10.5,1.29,5.8,9.5,1.33,6.3,11.0,"
    "1.70,2.25,1.66,2.20,"
    "1.25,6.50,12.0,1.75,2.15,1.25,6.0,12.0\n"
)
# Piątek 23.08.2024 17:00 BST — przed końcem „afternoon”: wypada.
ROW_FRI_EARLY = (
    "E0,23/08/2024,17:00,Brighton,Man United,2,1,"
    "2.40,3.60,2.90,2.35,3.50,2.90,2.3,3.5,2.9,2.5,3.7,3.0,"
    "1.60,2.40,1.57,2.37,"
    "2.30,3.70,3.00,1.62,2.35,2.30,3.6,3.0\n"
)
# Bet&Win bez kursu remisu — rynek niekompletny tylko u niego.
ROW_INCOMPLETE = (
    "E0,24/08/2024,12:30,Brighton,Arsenal,1,1,"
    "3.10,3.50,2.30,3.00,3.40,2.30,3.0,,2.3,3.2,3.6,2.4,"
    "1.80,2.05,1.80,2.00,"
    "3.20,3.40,2.30,1.85,2.00,3.10,3.4,2.25\n"
)


def _replay(*rows: str, rule: ObservedAtRule = A) -> Replay:
    return replay_csv(
        (HEADER + "".join(rows)).encode("latin-1"), league="E0", season="2425", rule=rule
    )


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def test_row_becomes_match_with_time_order() -> None:
    replay = _replay(ROW_SAT)
    (match,) = replay.matches
    assert isinstance(match, ReplayMatch)
    assert match.kickoff == _utc(2024, 8, 17, 14, 0)
    assert match.observed_at == _utc(2024, 8, 16, 17, 0)
    assert match.decision_at == match.observed_at + DECISION_LAG
    assert match.closing_at == match.kickoff - CLOSING_BEFORE_KICKOFF
    assert match.observed_at < match.decision_at < match.kickoff
    result = replay.results[match.match_id]
    assert result.settled_at == match.kickoff + SETTLE_AFTER
    assert (result.home_goals, result.away_goals) == (2, 0)


def test_decision_snapshot_uses_pre_match_columns_and_closing_the_c_columns() -> None:
    (match,) = _replay(ROW_SAT).matches
    pin = {q.market: q for q in match.decision["pinnacle"]}
    assert pin["1x2"].outcomes == ("home", "draw", "away")
    assert pin["1x2"].odds == (1.30, 6.00, 10.0)
    assert pin["1x2"].observed_at == match.observed_at
    assert pin["over_under"].line == 2.5
    assert pin["over_under"].outcomes == ("over", "under")
    assert pin["over_under"].odds == (1.70, 2.25)
    close = {q.market: q for q in match.closing["pinnacle"]}
    assert close["1x2"].odds == (1.25, 6.50, 12.0)
    assert close["1x2"].observed_at == match.closing_at
    assert close["over_under"].odds == (1.75, 2.15)
    soft = {q.market: q for q in match.decision["bet365"]}
    assert soft["1x2"].odds == (1.28, 5.75, 10.5)
    assert soft["over_under"].odds == (1.66, 2.20)


def test_match_carries_no_result() -> None:
    """Trucizna (KRYT 2): wynik dostępny wyłącznie przez ``results`` po gwizdku."""
    (match,) = _replay(ROW_SAT).matches
    fields = set(vars(match))
    assert not fields & {"home_goals", "away_goals", "result", "settled_at"}


def test_kickoff_not_after_observed_at_is_counted_per_league_and_season() -> None:
    replay = _replay(ROW_SAT, ROW_FRI_EARLY)
    assert len(replay.matches) == 1
    assert replay.skipped[("E0", "2425", "gwizdek ≤ observed_at")] == 1
    # Wariant 23:59: piątek 17:00 też wypada, sobota zostaje.
    late = _replay(ROW_SAT, ROW_FRI_EARLY, rule=ObservedAtRule.END_OF_DAY_2359)
    (match,) = late.matches
    assert match.observed_at == _utc(2024, 8, 16, 22, 59)


def test_incomplete_book_market_is_not_quoted() -> None:
    replay = _replay(ROW_INCOMPLETE)
    (match,) = replay.matches
    assert "1x2" not in {q.market for q in match.decision.get("betandwin", ())}
    assert "1x2" in {q.market for q in match.decision["bet365"]}
    assert replay.skipped[("E0", "2425", "niekompletny betandwin 1x2")] == 1


def test_duplicate_match_is_an_error() -> None:
    with pytest.raises(ValueError, match="powtórzony"):
        _replay(ROW_SAT, ROW_SAT)


def test_missing_result_is_kept_and_marked_void() -> None:
    """Mecz bez wyniku nie znika z replayu (odrzucenie po wyniku to selekcja z przyszłości)."""
    row = ROW_SAT.replace(",2,0,", ",,,", 1)
    replay = _replay(row)
    (match,) = replay.matches
    result = replay.results[match.match_id]
    assert result.home_goals is None
    assert result.void is True
    assert replay.skipped[("E0", "2425", "brak wyniku → void")] == 1


def test_settle_after_and_lag_are_conservative() -> None:
    assert timedelta(0) < DECISION_LAG
    assert timedelta(hours=2) <= SETTLE_AFTER
    assert timedelta(0) < CLOSING_BEFORE_KICKOFF <= timedelta(minutes=30)


def test_ekstraklasa_closing_replay_is_closing_vs_closing() -> None:
    """F (report-only, decyzja Pawła 2026-10-08): migawka „decyzyjna” = zamknięcie;
    B365C vs PSC; tylko mecze z kompletem obu; reszta z licznikiem."""
    import pandas as pd

    from valuebet.backtest.replay import replay_pol_closing

    frame = pd.DataFrame(
        {
            "Season": ["2025/2026", "2025/2026", "2024/2025"],
            "Date": ["16/08/2025", "17/08/2025", "10/08/2024"],
            "Time": ["17:30", "15:00", "17:30"],
            "Home": ["Legia", "Lech Poznan", "Rakow"],
            "Away": ["Rakow", "Pogon", "Legia"],
            "HG": ["2", "1", "0"],
            "AG": ["1", "1", "0"],
            "PSCH": ["2.0", "", "2.1"],
            "PSCD": ["3.5", "", "3.4"],
            "PSCA": ["3.9", "", "3.6"],
            "B365CH": ["2.05", "1.9", ""],
            "B365CD": ["3.4", "3.5", ""],
            "B365CA": ["3.8", "4.0", ""],
        }
    )
    replay = replay_pol_closing(frame, seasons=("2025/2026",))
    (match,) = replay.matches
    assert match.league == "POL"
    assert match.observed_at < match.decision_at < match.kickoff
    assert {q.market for q in match.decision["pinnacle"]} == {"1x2"}
    assert match.decision["bet365"][0].odds == (2.05, 3.4, 3.8)
    # Zamknięcie Pinnacle = ta sama migawka co decyzja (zamknięcie vs zamknięcie).
    assert match.closing["pinnacle"][0].odds == match.decision["pinnacle"][0].odds
    assert replay.skipped[("POL", "2025/2026", "brak kompletu PSC/B365C")] == 1
    assert replay.results[match.match_id].home_goals == 2
