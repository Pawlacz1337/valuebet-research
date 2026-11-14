"""FSA #0c F0c-01 + F0c-04 — pokrycie zamknięć liczone per MECZ i per kurs Pinnacle.

Ścieżki niebezpieczne (prawdziwy ``run_once``):

- F0c-01: mianownik był zbiorem godzin gwizdka. Sobotni slot 14:00 z pięcioma
  meczami przegapiony (komputer śpi), slot 16:30 z jednym meczem zebrany →
  (1, 2) = 50%, prawda 1 z 6. Na miesiącu PL audytor zmierzył 95.8% przy
  prawdziwych 87.5% — po złej stronie progu 95% (ROADMAP §8).
- F0c-04: zamknięcie liczone jako zebrane po samym zapisie odpowiedzi, także
  gdy w odpowiedzi nie ma meczu albo kursu Pinnacle → (1, 1) przy zerze kursów.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from helpers import assert_from_checkout
from helpers.collector_scene import Scene, event
from valuebet.ingest.odds_collector import closing_coverage

assert_from_checkout(__file__)

EPL = "soccer_epl"
S1 = datetime(2026, 10, 24, 14, 0, tzinfo=UTC)
S2 = datetime(2026, 10, 24, 16, 30, tzinfo=UTC)
NEXT = datetime(2026, 10, 31, 14, 0, tzinfo=UTC)
FIVE = [event(f"s1-{i}", S1) for i in range(5)]


def _state(scene: Scene) -> dict[str, object]:
    return scene.collector()._load_state()


def test_five_match_slot_missed_counts_five(tmp_path: Path) -> None:
    scene = Scene(tmp_path)
    collector = scene.collector()
    # Migawka decyzyjna rano poznaje wszystkie mecze dnia (z identyfikatorami).
    scene.events[EPL] = [*FIVE, event("s2", S2), event("n", NEXT)]
    collector._save_state(
        {"done": [], "kickoffs": {EPL: [S1.isoformat()] * 5 + [S2.isoformat()]},
         "last_usage": None}
    )
    collector.run_once(now=datetime(2026, 10, 24, 6, 40, tzinfo=UTC))
    # Komputer śpi przez okno zamknięcia S1; po gwizdku S1 lista go nie ma.
    scene.events[EPL] = [event("s2", S2), event("n", NEXT)]
    collector.run_once(now=S2 - timedelta(minutes=25))
    collector.run_once(now=S2 - timedelta(minutes=5))
    cov = closing_coverage(_state(scene), now=S2 + timedelta(hours=3))
    assert cov["premier_league"] == (1, 6), "pięć meczów slotu liczonych jako jeden"


def test_five_match_slot_listed_by_events_counts_five(tmp_path: Path) -> None:
    """Pięć meczów jednego slotu poznanych z ``/events`` (nie ze stanu) — pięć pozycji.

    Do rundy 0e ten test sprawdzał migrację stanu „same godziny” na wpisy
    ``legacy:``. Decyzja Pawła (2026-10-03) zrobiła ``/events`` jedynym źródłem
    terminarza: stary terminarz z płatnych odpowiedzi jest odrzucany przy
    migracji, więc krotność bierze się z identyfikatorów ``/events``.
    """
    scene = Scene(tmp_path)
    collector = scene.collector()
    collector._save_state(
        {"done": [], "kickoffs": {EPL: [S1.isoformat()] * 5 + [S2.isoformat()]},
         "last_usage": None}
    )
    scene.events[EPL] = [*FIVE, event("s2", S2), event("n", NEXT)]
    collector.run_once(now=S1 - timedelta(hours=2))
    scene.events[EPL] = [event("s2", S2), event("n", NEXT)]
    collector.run_once(now=S2 - timedelta(minutes=25))
    collector.run_once(now=S2 - timedelta(minutes=5))
    state = _state(scene)
    assert "kickoffs" not in state, "terminarz z płatnych odpowiedzi ma zniknąć ze stanu"
    cov = closing_coverage(state, now=S2 + timedelta(hours=3))
    assert cov["premier_league"] == (1, 6)


def test_closing_without_pinnacle_price_is_not_collected(tmp_path: Path) -> None:
    scene = Scene(tmp_path)
    collector = scene.collector()
    collector._save_state(
        {"done": [], "kickoffs": {EPL: [S2.isoformat()]}, "last_usage": None}
    )
    scene.events[EPL] = [event("s2", S2, pinnacle=False), event("n", NEXT)]
    collector.run_once(now=S2 - timedelta(minutes=5))
    cov = closing_coverage(_state(scene), now=S2 + timedelta(hours=3))
    assert cov["premier_league"] == (0, 1), "zamknięcie bez kursu Pinnacle liczone jako zebrane"


def test_closing_response_without_the_match_is_not_collected(tmp_path: Path) -> None:
    scene = Scene(tmp_path)
    collector = scene.collector()
    collector._save_state(
        {"done": [], "kickoffs": {EPL: [S2.isoformat()]}, "last_usage": None}
    )
    scene.listing[EPL] = [event("s2", S2), event("n", NEXT)]
    scene.events[EPL] = [event("n", NEXT)]
    collector.run_once(now=S2 - timedelta(minutes=5))
    cov = closing_coverage(_state(scene), now=S2 + timedelta(hours=3))
    assert cov["premier_league"] == (0, 1)
