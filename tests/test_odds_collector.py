"""Testy kolektora The Odds API (S1). Zegar sztuczny, sieć zamockowana."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from helpers import fake_http
from valuebet.ingest.odds_api import OddsApiClient, OddsApiSettings
from valuebet.ingest.odds_collector import (
    CLOSING,
    CLOSING_BACKUP,
    DECISION,
    LEAGUES,
    OddsCollector,
    due_calls,
    migrate_done_keys,
)
from valuebet.ingest.raw_store import RawStore

KICKOFF = datetime(2026, 10, 24, 17, 0, tzinfo=UTC)
EKSTRAKLASA = "soccer_poland_ekstraklasa"
EPL = "soccer_epl"


def _event(commence: datetime, home: str = "Legia", away: str = "Lech") -> dict:
    return {
        "id": f"{home}-{away}-{commence.isoformat()}",
        "commence_time": commence.isoformat().replace("+00:00", "Z"),
        "home_team": home,
        "away_team": away,
        "bookmakers": [{"key": "pinnacle", "markets": [{"key": "h2h", "outcomes": [
            {"name": "H", "price": 2.1}, {"name": "A", "price": 3.4},
            {"name": "D", "price": 3.3}]}]}],
    }


#: Odległy przyszły mecz w każdej lidze — tło dla testów „spokojnego” przebiegu.
FAR = KICKOFF + timedelta(days=60)


def _far_schedule(**extra: list[dict]) -> dict[str, list[dict]]:
    out = {lg.sport_key: [_event(FAR, "Far", lg.label)] for lg in LEAGUES}
    for key, values in extra.items():
        out[key] = [*values, *out[key]]
    return out


def _collector(
    tmp_path: Path,
    handler,
    remaining: int = 400,
    schedule: dict[str, list[dict]] | None = None,
) -> tuple[OddsCollector, list[httpx.Request]]:
    """Kolektor na fałszywym transporcie; ``seen`` = wyłącznie płatne ``/odds``.

    Terminarz pochodzi WYŁĄCZNIE z bezpłatnego ``/events`` (decyzja Pawła
    2026-10-03, F0d-01) — test podaje go w ``schedule``; ``/events`` ma
    ``x-requests-last: 0`` jak w dokumentacji v4.
    """
    seen: list[httpx.Request] = []
    listing = schedule or {}

    def wrapped(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/events"):
            sport = request.url.path.split("/sports/")[1].split("/")[0]
            return httpx.Response(
                200,
                json=listing.get(sport, []),
                headers={"x-requests-used": "0", "x-requests-remaining": "500", "x-requests-last": "0"},
            )
        if request.url.path.endswith("/sports"):
            # Bezpłatne odświeżenie licznika (F-15). Test podaje własny licznik
            # w nagłówku odpowiedzi albo dostaje pusty budżet z zapasem.
            response = handler(request)
            if "x-requests-used" in response.headers:
                return response
            return httpx.Response(
                200, json=[], headers={"x-requests-used": "0", "x-requests-remaining": "500"}
            )
        seen.append(request)
        return handler(request)

    client = OddsApiClient(
        http=fake_http(wrapped), settings=OddsApiSettings(api_key="k" * 32)
    )
    return OddsCollector(
        client=client,
        store=RawStore(root=tmp_path / "raw", manifest=tmp_path / "manifest.jsonl"),
        state_root=tmp_path / "state",
    ), seen


# ---------------------------------------------------------------------------
# Planowanie kotwic — czysta funkcja, sztuczny zegar
# ---------------------------------------------------------------------------


def _due(now: datetime, kickoffs: dict, done: set[str] | None = None) -> list:
    return due_calls(now=now, kickoffs=kickoffs, done=done or set())


def test_closing_fires_in_last_seven_minutes() -> None:
    kickoffs = {EKSTRAKLASA: [KICKOFF]}
    assert [c.anchor.name for c in _due(KICKOFF - timedelta(minutes=5), kickoffs)] == [
        "closing"
    ]
    # Zapasowe tylko PL i Bundesliga (budżet, F-13).
    assert _due(KICKOFF - timedelta(minutes=10), kickoffs) == []
    assert [c.anchor.name for c in _due(KICKOFF - timedelta(minutes=10), {EPL: [KICKOFF]})] == [
        "closing_backup"
    ]


def test_closing_does_not_fire_hours_early() -> None:
    assert _due(KICKOFF - timedelta(hours=3), {EKSTRAKLASA: [KICKOFF]}) == []


def test_closing_does_not_fire_after_kickoff() -> None:
    assert _due(KICKOFF + timedelta(minutes=5), {EKSTRAKLASA: [KICKOFF]}) == []


def test_no_t24_anchor_a_day_before_kickoff() -> None:
    """Żadna liga nie ma T-24h (decyzja Pawła 2026-10-04 — dubluje migawki decyzyjne).

    Do 2026-10-04 test oczekiwał ``[("ekstraklasa", "t24")]`` — zmiana
    specyfikacji, wpis w FIX_LOG_F0.md.
    """
    when = KICKOFF - timedelta(hours=24)
    due = _due(when, {EKSTRAKLASA: [KICKOFF], EPL: [KICKOFF]})
    assert [(c.league.label, c.anchor.name) for c in due] == []


def test_windows_cover_the_closing_tolerance_at_five_minute_step() -> None:
    """Zapasowa + główna = [KO-30, KO); przy kroku 5 min każda ma przebieg (F-13)."""
    assert CLOSING_BACKUP.before == timedelta(minutes=30)
    assert CLOSING_BACKUP.before - CLOSING_BACKUP.window == CLOSING.before
    assert min(CLOSING.window, CLOSING.before) > timedelta(minutes=5)
    assert DECISION.window > timedelta(minutes=5)


def test_same_kickoff_matches_share_one_call() -> None:
    """Jedno wywołanie zwraca całą ligę — mecze z jednym gwizdkiem dzielą zapytanie."""
    kickoffs = {EKSTRAKLASA: [KICKOFF, KICKOFF, KICKOFF + timedelta(minutes=30)]}
    due = _due(KICKOFF - timedelta(minutes=5), kickoffs)
    assert len(due) == 1


def test_different_kickoffs_are_separate_events() -> None:
    kickoffs = {EKSTRAKLASA: [KICKOFF, KICKOFF + timedelta(minutes=30)]}
    first = _due(KICKOFF - timedelta(minutes=5), kickoffs)
    later = _due(KICKOFF + timedelta(minutes=25), kickoffs, {first[0].key})
    assert len(first) == len(later) == 1
    assert later[0].reference != first[0].reference


def test_already_done_is_not_repeated() -> None:
    kickoffs = {EKSTRAKLASA: [KICKOFF]}
    first = _due(KICKOFF - timedelta(minutes=6), kickoffs)
    assert _due(KICKOFF - timedelta(minutes=2), kickoffs, {first[0].key}) == []


def test_old_slot_keys_are_migrated_without_refetch() -> None:
    late = KICKOFF + timedelta(minutes=30)
    kickoffs = {EKSTRAKLASA: [KICKOFF, late]}
    old = {f"ekstraklasa|closing|{KICKOFF.isoformat()}", "ekstraklasa|decision|2026-10-24"}
    new = migrate_done_keys(old, kickoffs=kickoffs)
    assert f"ekstraklasa|closing|{late.isoformat()}" in new
    assert "ekstraklasa|decision|2026-10-24" in new
    assert _due(late - timedelta(minutes=5), kickoffs, new) == []
    assert migrate_done_keys(new, kickoffs=kickoffs) == new


def test_markets_match_the_league_plan() -> None:
    by_label = {lg.label: lg for lg in LEAGUES}
    # spreads Ekstraklasy zdjęte dla budżetu 450 (F-13, TOR_S_PLAN §2).
    assert by_label["ekstraklasa"].markets == ("h2h", "totals")
    assert by_label["ekstraklasa"].credits_per_call == 2
    assert CLOSING_BACKUP not in by_label["ekstraklasa"].anchors
    assert CLOSING_BACKUP in by_label["premier_league"].anchors
    assert by_label["premier_league"].markets == ("h2h", "totals")
    assert by_label["bundesliga"].credits_per_call == 2


# ---------------------------------------------------------------------------
# Przebieg
# ---------------------------------------------------------------------------


def test_quiet_run_costs_nothing_but_still_beats(tmp_path: Path) -> None:
    """Luka jest daną: heartbeat leci TAKŻE gdy nic się nie należało."""
    collector, seen = _collector(
        tmp_path, lambda r: httpx.Response(200, json=[]), schedule=_far_schedule()
    )
    entry = collector.run_once(now=KICKOFF - timedelta(days=5))
    assert seen == [], "spokojny przebieg nie może kosztować kredytu"
    assert entry["fetched"] == []
    lines = collector.heartbeat_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["note"] == "nic nienależne"


def test_raw_response_is_written_with_provenance(tmp_path: Path) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=[_event(KICKOFF)], headers={"x-requests-remaining": "390"}
        )

    collector, seen = _collector(tmp_path, handler, schedule={EKSTRAKLASA: [_event(KICKOFF)]})
    now = KICKOFF - timedelta(minutes=5)
    entry = collector.run_once(now=now)

    assert len(seen) == 1
    assert len(entry["fetched"]) == 1
    files = list((collector.root / "ekstraklasa").glob("*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    # Reguła 14.
    assert payload["ingested_at"]
    assert payload["source"] == "the-odds-api-v4"
    assert payload["anchor"] == "closing"
    assert payload["markets"] == ["h2h", "totals"]
    assert payload["events"]
    assert "apiKey=REDACTED" in payload["requested_url"]
    assert "k" * 32 not in json.dumps(payload)


def test_raw_files_are_never_overwritten(tmp_path: Path) -> None:
    """``data/raw/`` jest niemodyfikowalne (reguła 12).

    Ten sam zapis w tej samej chwili (stan wyczyszczony, ta sama odpowiedź)
    trafia na tę samą nazwę — ma być błędem w heartbeacie, a pierwszy plik
    zostaje nietknięty.
    """

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[_event(KICKOFF)])

    collector, _ = _collector(tmp_path, handler, schedule={EKSTRAKLASA: [_event(KICKOFF)]})
    now = KICKOFF - timedelta(minutes=5)
    first = collector.run_once(now=now)
    state = collector._load_state()
    state["done"] = []
    assert first["fetched"] and not first["errors"]
    folder = collector.root / "ekstraklasa"
    (only,) = list(folder.glob("*.json"))
    before = only.read_bytes()

    collector._save_state(state)
    entry = collector.run_once(now=now)
    assert entry["errors"], "nadpisanie pliku w raw ma być błędem, nie cichym zapisem"
    assert list(folder.glob("*.json")) == [only]
    assert only.read_bytes() == before
    assert collector.store.verify() == []


def test_schedule_comes_only_from_events(tmp_path: Path) -> None:
    """Terminarz WYŁĄCZNIE z ``/events``; płatna odpowiedź go nie zasila (F0d-01).

    Do rundy 0e terminarz żył z odpowiedzi płatnych wywołań — i milkł, gdy
    nic nie było należne. Mecz obecny tylko w odpowiedzi ``/odds`` nie
    trafia do terminarza; mecz z ``/events`` — trafia.
    """
    later = KICKOFF + timedelta(days=7)
    only_paid = KICKOFF + timedelta(days=9)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[_event(KICKOFF), _event(only_paid, "X", "Y")])

    collector, _ = _collector(
        tmp_path, handler, schedule={EKSTRAKLASA: [_event(KICKOFF), _event(later)]}
    )
    entry = collector.run_once(now=KICKOFF - timedelta(minutes=5))
    assert entry["fetched"], entry
    seen = collector._load_state()["events_seen"][EKSTRAKLASA]
    assert _event(later)["id"] in seen
    assert _event(only_paid, "X", "Y")["id"] not in seen


def test_budget_guard_stops_the_run(tmp_path: Path) -> None:
    """Licznik z /sports mówi 449 użytych — płatne /odds nie idzie (F-15)."""
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200, json=[_event(KICKOFF)], headers={"x-requests-used": "449"}
        )

    collector, _ = _collector(tmp_path, handler, schedule={EKSTRAKLASA: [_event(KICKOFF)]})
    collector._save_state({"done": [], "last_usage": {"remaining": 496, "used": 4}})
    entry = collector.run_once(now=KICKOFF - timedelta(minutes=5))
    assert [c.url.path.rsplit("/", 1)[-1] for c in calls] == ["sports"], "płatne /odds nie poszło"
    assert entry["budget_skip"]


def test_failed_call_is_recorded_not_swallowed(tmp_path: Path) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="chwilowo niedostepne")

    collector, _ = _collector(tmp_path, handler, schedule={EKSTRAKLASA: [_event(KICKOFF)]})
    entry = collector.run_once(now=KICKOFF - timedelta(minutes=5))
    assert entry["fetched"] == []
    assert entry["errors"]
    # Nieudane wywołanie nie może zostać oznaczone jako zrobione.
    assert collector._load_state()["done"] == []


def test_done_marker_prevents_double_spend(tmp_path: Path) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=[_event(KICKOFF)], headers={"x-requests-remaining": "390"}
        )

    collector, seen = _collector(
        tmp_path, handler, schedule=_far_schedule(**{EKSTRAKLASA: [_event(KICKOFF)]})
    )
    collector.run_once(now=KICKOFF - timedelta(minutes=6))
    collector.run_once(now=KICKOFF - timedelta(minutes=3))
    assert len(seen) == 1, "ta sama kotwica nie może być opłacona dwa razy"


@pytest.mark.parametrize("remaining", [400, 59, 11])
def test_usage_is_carried_between_runs(tmp_path: Path, remaining: int) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[_event(KICKOFF)],
            headers={"x-requests-remaining": str(remaining)},
        )

    collector, _ = _collector(tmp_path, handler, schedule={EKSTRAKLASA: [_event(KICKOFF)]})
    collector.run_once(now=KICKOFF - timedelta(minutes=5))
    assert collector._load_state()["last_usage"]["remaining"] == remaining


# ---------------------------------------------------------------------------
# Migawka decyzyjna (TOR_S_PLAN §2)
# ---------------------------------------------------------------------------


def test_decision_window_follows_warsaw_wall_clock() -> None:
    """Godzina ścienna, nie offset — po zmianie czasu ma się przesunąć.

    2026-10-25 to koniec czasu letniego w Polsce. 08:30 warszawskie to
    06:30 UTC przed zmianą i 07:30 UTC po niej.
    """
    from valuebet.ingest.odds_collector import decision_window_utc

    before, _ = decision_window_utc(now=datetime(2026, 10, 24, 12, 0, tzinfo=UTC))
    after, _ = decision_window_utc(now=datetime(2026, 10, 26, 12, 0, tzinfo=UTC))
    assert (before.hour, before.minute) == (6, 30)
    assert (after.hour, after.minute) == (7, 30)


def test_decision_due_only_inside_window_and_only_if_league_plays() -> None:
    from valuebet.ingest.odds_collector import decision_due, decision_window_utc

    day = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    start, _ = decision_window_utc(now=day)
    soon = [start + timedelta(hours=10)]
    far = [start + timedelta(days=5)]

    def due(now: datetime, games: list[datetime]) -> bool:
        return decision_due(now=now, kickoffs=games, done=set(), label="ekstraklasa")

    assert due(start + timedelta(minutes=5), soon)
    assert not due(start - timedelta(hours=1), soon)
    assert not due(start + timedelta(hours=3), soon)
    assert not due(start + timedelta(minutes=5), far)


def test_decision_is_once_per_day_per_league() -> None:
    from valuebet.ingest.odds_collector import decision_window_utc

    day = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    start, _ = decision_window_utc(now=day)
    kickoffs = {EKSTRAKLASA: [start + timedelta(hours=10)]}
    first = _due(start + timedelta(minutes=5), kickoffs)
    decision = [c for c in first if c.anchor.name == "decision"]
    assert len(decision) == 1
    again = _due(start + timedelta(minutes=20), kickoffs, {decision[0].key})
    assert [c for c in again if c.anchor.name == "decision"] == []


def test_decision_uses_two_markets_not_three() -> None:
    """Trzeci rynek kosztowałby 50% więcej, a progów 1X2 i totali nie zmienia."""
    from valuebet.ingest.odds_collector import DECISION_MARKETS, decision_window_utc

    day = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    start, _ = decision_window_utc(now=day)
    kickoffs = {EKSTRAKLASA: [start + timedelta(hours=10)]}
    decision = next(
        c
        for c in _due(start + timedelta(minutes=5), kickoffs)
        if c.anchor.name == "decision"
    )
    assert decision.effective_markets == DECISION_MARKETS == ("h2h", "totals")
    assert decision.credits == 2
    assert decision.league.credits_per_call == 2


# ---------------------------------------------------------------------------
# Zamknięcia przegapione i pokrycie (FSA #0 F-13)
# ---------------------------------------------------------------------------


def test_missed_closing_is_recorded_once(tmp_path: Path) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    collector, _ = _collector(tmp_path, handler, schedule={EPL: [_event(KICKOFF)]})
    collector.run_once(now=KICKOFF + timedelta(hours=1))
    collector.run_once(now=KICKOFF + timedelta(hours=2))
    lines = collector.missed_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["league"] == "premier_league"


def test_weekly_closing_coverage(tmp_path: Path) -> None:
    """Stan z prawdziwego ``run_once``: zamknięcie pierwszego meczu zebrane, drugiego nie.

    Wcześniej stan był budowany ręcznie, a zebrane = klucz w ``done`` — tak
    liczyła błędna miara (F0c-04: zapis bez kursu Pinnacle = zebrane).
    """
    from valuebet.ingest.odds_collector import closing_coverage

    second = KICKOFF + timedelta(hours=2)
    both = [_event(KICKOFF), _event(second, "B", "C")]
    collector, _ = _collector(
        tmp_path, lambda r: httpx.Response(200, json=both), schedule={EPL: both}
    )
    collector.run_once(now=KICKOFF - timedelta(minutes=5))
    state = collector._load_state()
    cov = closing_coverage(state, now=KICKOFF + timedelta(days=1))
    assert cov["premier_league"] == (1, 2)
    assert cov["ekstraklasa"] == (0, 0)


def test_pick_closing_takes_latest_within_tolerance() -> None:
    from valuebet.closing import pick_closing

    snaps = [
        (KICKOFF - timedelta(minutes=40), "za wczesna"),
        (KICKOFF - timedelta(minutes=25), "zapasowa"),
        (KICKOFF - timedelta(minutes=4), "główna"),
        (KICKOFF + timedelta(minutes=1), "live"),
    ]
    assert pick_closing(snaps, kickoff=KICKOFF) == (KICKOFF - timedelta(minutes=4), "główna")
    assert pick_closing(snaps[:1], kickoff=KICKOFF) is None
