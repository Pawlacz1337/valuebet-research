"""FSA #0c F0c-02 — kolektor nie milknie, gdy miną wszystkie znane gwizdki.

Ścieżka niebezpieczna (prawdziwy ``run_once``, krok 5 min): ostatni znany mecz
PL to B 24.10 16:30, odpowiedzi ``/odds`` nie zawierają jeszcze następnej
kolejki (przerwa reprezentacyjna, zimowa — Ekstraklasa listowana ~8 dni
naprzód). Terminarz odświeżał się wyłącznie z należnych wywołań → po B nic
nie było należne → zero wywołań na zawsze, heartbeat „nic nienależne”,
``errors = []``; pokrycie (0, 0) zamiast 0 z 2.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from helpers import assert_from_checkout
from helpers.collector_scene import Scene, event
from valuebet.ingest.odds_collector import closing_coverage

assert_from_checkout(__file__)

EPL = "soccer_epl"
B = datetime(2026, 10, 24, 16, 30, tzinfo=UTC)
N1 = datetime(2026, 11, 7, 15, 0, tzinfo=UTC)
N2 = datetime(2026, 11, 8, 14, 0, tzinfo=UTC)
LISTED_FROM = datetime(2026, 11, 1, 0, 0, tzinfo=UTC)


def _walk(scene: Scene, start: datetime, end: datetime) -> None:
    collector = scene.collector()
    now = start
    while now <= end:
        # Następna kolejka pojawia się w API dopiero od 1.11.
        upcoming = [event("n1", N1), event("n2", N2)] if now >= LISTED_FROM else []
        scene.events[EPL] = [e for e in upcoming if datetime.fromisoformat(
            e["commence_time"].replace("Z", "+00:00")) > now]
        collector.run_once(now=now)
        now += timedelta(minutes=5)


def _initial(scene: Scene) -> None:
    scene.collector()._save_state(
        {"done": [], "kickoffs": {EPL: [B.isoformat()]}, "last_usage": None}
    )


def test_collector_keeps_asking_after_last_known_kickoff(tmp_path: Path) -> None:
    scene = Scene(tmp_path)
    _initial(scene)
    _walk(scene, B + timedelta(minutes=5), N2 + timedelta(hours=3))
    epl_calls = [p for p in scene.odds_calls if EPL in p]
    assert epl_calls, "zero wywołań PL po ostatnim znanym meczu — kolektor zamilkł"
    cov = closing_coverage(scene.collector()._load_state(), now=N2 + timedelta(hours=3))
    assert cov["premier_league"] == (2, 2), cov


def test_schedule_costs_nothing_and_is_refreshed_hourly(tmp_path: Path) -> None:
    """Terminarz z bezpłatnego ``/events`` co ≤ 60 min; bez meczów — zero płatnych wywołań.

    Do rundy 0e test ograniczał koszt płatnej sondy terminarza (≤ 1/dobę).
    Decyzja Pawła (2026-10-03) usunęła płatną sondę w całości: terminarz
    wyłącznie z ``/events``, odświeżany bezwarunkowo co 60 min.
    """
    scene = Scene(tmp_path)
    _initial(scene)
    _walk(scene, B + timedelta(minutes=5), B + timedelta(days=3))
    epl_paid = [p for p in scene.paid_calls if EPL in p]
    epl_events = [p for p in scene.odds_calls if EPL in p and p.endswith("/events")]
    assert epl_paid == [], "bez meczów nie ma płatnych wywołań"
    assert len(epl_events) >= 3 * 24, len(epl_events)


def test_heartbeat_names_leagues_without_known_fixtures(tmp_path: Path) -> None:
    scene = Scene(tmp_path)
    _initial(scene)
    scene.collector().run_once(now=B + timedelta(hours=1))
    lines = (tmp_path / "state" / "heartbeat.jsonl").read_text(encoding="utf-8").splitlines()
    last = json.loads(lines[-1])
    assert "premier_league" in last.get("schedule_empty", []), last
