"""FSA #0 F-13 — kotwica zamknięcia nie ginie przy zmierzonych lukach harmonogramu.

Ścieżki niebezpieczne:
- przebiegi o zmierzonym wzorcu odstępów (heartbeat 2026-10-01: luki 30, 45,
  60 min): przebieg 28 min przed gwizdkiem, następny po gwizdku — okno 25 min
  ``[KO-25, KO)`` jest puste i zamknięcie przepada bezpowrotnie, choć migawka
  sprzed 28 min mieści się w tolerancji CLV (30 min);
- migawka główna ma lądować w ``[KO-7, KO)`` — dziś ląduje na pierwszym
  przebiegu po ``KO-25``, czyli zwykle 12-25 min przed gwizdkiem.

Planowanie sprawdzane czystą funkcją ``due_calls`` na sztucznym zegarze —
zero kredytów.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from helpers import accepts, assert_from_checkout
from valuebet.ingest import odds_collector
from valuebet.ingest.odds_collector import due_calls

assert_from_checkout(__file__)

EPL = "soccer_epl"
KO = datetime(2026, 10, 24, 15, 0, tzinfo=UTC)


def _due(now: datetime, done: set[str]) -> list[Any]:
    kickoffs = {EPL: [KO]}
    if accepts(due_calls, "now") and not _positional():
        return list(due_calls(now=now, kickoffs=kickoffs, done=done))
    return list(due_calls(now, kickoffs, done))


def _positional() -> bool:
    import inspect

    param = inspect.signature(due_calls).parameters["now"]
    return param.kind is not inspect.Parameter.KEYWORD_ONLY


def _simulate(offsets_min: list[int]) -> list[tuple[int, str]]:
    """Przebiegi o podanych przesunięciach od gwizdka; zwraca (przesunięcie, kotwica)."""
    done: set[str] = set()
    fetched: list[tuple[int, str]] = []
    for offset in offsets_min:
        now = KO + timedelta(minutes=offset)
        for call in _due(now, done):
            if call.league.sport_key != EPL or call.anchor.name == "decision":
                continue
            done.add(call.key)
            fetched.append((offset, call.anchor.name))
    return fetched


def test_measured_gap_pattern_still_yields_a_closing() -> None:
    # Odstępy 30 min (zmierzone): -58, -28, +2. Okno 25 min nie ma przebiegu.
    fetched = _simulate([-58, -28, 2])
    in_tolerance = [o for o, _ in fetched if -30 <= o < 0]
    assert in_tolerance, f"zamknięcie przepadło przy luce 30 min: {fetched}"


def test_main_closing_lands_in_last_seven_minutes() -> None:
    # Krok 5 min, bez luk.
    fetched = _simulate(list(range(-60, 1, 5)))
    main = [o for o, name in fetched if name == "closing"]
    assert main, fetched
    assert all(-7 <= o < 0 for o in main), f"migawka główna poza [KO-7, KO): {main}"


def test_closing_is_never_after_kickoff() -> None:
    fetched = _simulate(list(range(-60, 30, 5)))
    assert all(o < 0 for o, _ in fetched), fetched


def test_tolerance_and_target_are_two_constants_in_one_module() -> None:
    from valuebet import closing

    assert timedelta(minutes=30) == closing.CLOSING_TOLERANCE
    assert timedelta(minutes=7) == closing.CLOSING_TARGET
    assert odds_collector.CLOSING.before == closing.CLOSING_TARGET
