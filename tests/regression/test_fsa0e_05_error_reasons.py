"""FSA #0e F0e-05 / F0e-02 — powód ``closing_missed`` wyprowadzony z rodzaju błędu HTTP.

Decyzje Pawła: 2026-10-04 pkt 2 („błąd API dostawcy” wyłącznie dla 5xx,
timeoutu i zerwanego połączenia, z kodem HTTP we wpisie; 401, 403 i
pozostałe 4xx → errors w heartbeacie; 429 → budżet) i 2026-10-07 (szósty
powód dla 4xx poza 429; wpis z kodem HTTP i ``collector_gap = false``;
heartbeat nadal zapisuje błąd — wpis jest dodatkiem, nie zamiennikiem;
5xx/timeout nadal „błąd API dostawcy”, nie szósty).

Ścieżka niebezpieczna: każdy błąd ``/odds`` przy zamknięciu ląduje dziś pod
jednym powodem „błąd API dostawcy” — 403 z powodu złego klucza wygląda jak
awaria dostawcy, 429 (limit) jak awaria, a wpis nie mówi, co się stało.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from helpers import assert_from_checkout, build, fake_http
from valuebet.ingest.odds_api import OddsApiClient, OddsApiSettings
from valuebet.ingest.odds_collector import MISSED_REASONS, OddsCollector
from valuebet.ingest.raw_store import RawStore

assert_from_checkout(__file__)

EKS = "soccer_poland_ekstraklasa"
KICKOFF = datetime(2026, 11, 28, 17, 0, tzinfo=UTC)

REASON_API = "błąd API dostawcy"
REASON_BUDGET = "budżet > 450"
#: Szósty powód (decyzja Pawła 2026-10-07): odpowiedź HTTP 4xx poza 429.
REASON_CLIENT = "błąd kolektora (HTTP 4xx)"


def _event() -> dict[str, Any]:
    return {
        "id": "m1",
        "sport_key": EKS,
        "commence_time": KICKOFF.isoformat().replace("+00:00", "Z"),
        "home_team": "Legia",
        "away_team": "Lech",
        "bookmakers": [],
    }


def _failing(odds: Callable[[httpx.Request], httpx.Response]) -> Callable[..., httpx.Response]:
    """``/events`` i ``/sports`` działają; ``/odds`` zachowuje się wg ``odds``."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        base = {"x-requests-used": "10", "x-requests-remaining": "490"}
        if path.endswith("/robots.txt"):
            return httpx.Response(404, text="")
        if path.endswith("/sports") or path.endswith("/sports/"):
            return httpx.Response(200, json=[], headers=base)
        if path.endswith("/events"):
            return httpx.Response(200, json=[_event()], headers={**base, "x-requests-last": "0"})
        return odds(request)

    return handler


def _status(code: int) -> Callable[[httpx.Request], httpx.Response]:
    return lambda _r: httpx.Response(code, text=f"blad {code}")


def _raise(exc: type[httpx.TransportError]) -> Callable[[httpx.Request], httpx.Response]:
    def odds(request: httpx.Request) -> httpx.Response:
        raise exc("symulacja", request=request)

    return odds


def _missed_after_closing(
    tmp: Path, odds: Callable[[httpx.Request], httpx.Response]
) -> tuple[list[dict[str, Any]], list[str]]:
    client = OddsApiClient(
        http=fake_http(_failing(odds)), settings=OddsApiSettings(api_key="k" * 32)
    )
    collector = build(
        OddsCollector,
        client=client,
        store=RawStore(root=tmp / "raw", manifest=tmp / "manifest.jsonl"),
        state_root=tmp / "state",
        free_bytes=lambda _path: 10 * 1024**3,
    )
    errors: list[str] = []
    t = KICKOFF - timedelta(hours=2)
    while t <= KICKOFF + timedelta(minutes=30):
        entry = collector.run_once(now=t)
        errors.extend(entry["errors"])
        t += timedelta(minutes=5)
    lines = collector.missed_file.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line], errors


@pytest.mark.parametrize(
    ("odds", "status"),
    [
        (_status(500), 500),
        (_status(502), 502),
        (_status(503), 503),
        (_raise(httpx.ReadTimeout), None),
        (_raise(httpx.ConnectError), None),
    ],
    ids=["500", "502", "503", "timeout", "zerwane-polaczenie"],
)
def test_provider_failure_is_api_reason_with_http_code(
    tmp_path: Path, odds: Callable[[httpx.Request], httpx.Response], status: int | None
) -> None:
    """5xx, timeout, zerwane połączenie → „błąd API dostawcy”, NIE szósty powód (warunek e)."""
    missed, _ = _missed_after_closing(tmp_path, odds)
    (entry,) = missed
    assert entry["reason"] == REASON_API
    assert entry["collector_gap"] is False
    assert "http_status" in entry, entry
    assert entry["http_status"] == status
    if status is None:
        assert entry.get("error_kind") in {"timeout", "connection"}, entry


@pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
def test_client_error_is_sixth_reason_and_stays_in_heartbeat(tmp_path: Path, code: int) -> None:
    """4xx poza 429 → szósty powód z kodem, ``collector_gap = false``, błąd w heartbeacie (a-c)."""
    missed, errors = _missed_after_closing(tmp_path, _status(code))
    (entry,) = missed
    assert entry["reason"] == REASON_CLIENT
    assert entry["http_status"] == code
    assert entry["collector_gap"] is False
    assert any(f"HTTP {code}" in e for e in errors), errors


def test_rate_limit_429_is_budget_not_api(tmp_path: Path) -> None:
    """429 → budżet (decyzja 2026-10-04: „429 → budżet”)."""
    missed, _ = _missed_after_closing(tmp_path, _status(429))
    (entry,) = missed
    assert entry["reason"] == REASON_BUDGET
    assert entry["http_status"] == 429
    assert entry["collector_gap"] is False


def test_sixth_reason_is_on_the_closed_list() -> None:
    assert REASON_CLIENT in MISSED_REASONS
    assert len(MISSED_REASONS) == 7


# ---------------------------------------------------------------------------
# Decyzje Architekta 2026-10-07 ~22:10: nieznany licznik i błąd kontraktu
# ---------------------------------------------------------------------------

REASON_CONTRACT = "błąd kontraktu API"
REASON_OFFLINE = "komputer nie działał"
REASON_NO_PINNACLE = "brak rynku Pinnacle"
REASON_STORAGE = "brak miejsca / błąd zapisu"


def _run_scene(
    tmp: Path,
    *,
    sports: Callable[[httpx.Request], httpx.Response] | None = None,
    odds: Callable[[httpx.Request], httpx.Response] | None = None,
    free: int = 10 * 1024**3,
    start: timedelta = timedelta(hours=2),
) -> tuple[list[dict[str, Any]], list[str], int]:
    """Scena zamknięcia: (wpisy closing_missed, błędy heartbeatu, liczba płatnych /odds)."""
    paid = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal paid
        path = request.url.path
        base = {"x-requests-used": "10", "x-requests-remaining": "490"}
        if path.endswith("/robots.txt"):
            return httpx.Response(404, text="")
        if path.endswith("/sports") or path.endswith("/sports/"):
            if sports is not None:
                return sports(request)
            return httpx.Response(200, json=[], headers=base)
        if path.endswith("/events"):
            return httpx.Response(200, json=[_event()], headers={**base, "x-requests-last": "0"})
        paid += 1
        if odds is not None:
            return odds(request)
        return httpx.Response(200, json=[_event()], headers={**base, "x-requests-last": "2"})

    client = OddsApiClient(http=fake_http(handler), settings=OddsApiSettings(api_key="k" * 32))
    collector = build(
        OddsCollector,
        client=client,
        store=RawStore(root=tmp / "raw", manifest=tmp / "manifest.jsonl"),
        state_root=tmp / "state",
        free_bytes=lambda _path: free,
    )
    errors: list[str] = []
    t = KICKOFF - start
    while t <= KICKOFF + timedelta(minutes=30):
        entry = collector.run_once(now=t)
        errors.extend(entry["errors"])
        t += timedelta(minutes=5)
    path = collector.missed_file
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    return [json.loads(line) for line in lines if line], errors, paid


@pytest.mark.parametrize(
    ("sports", "reason", "status"),
    [
        (_status(503), REASON_API, 503),
        (_raise(httpx.ReadTimeout), REASON_API, None),
        (_status(401), REASON_CLIENT, 401),
        (_status(429), REASON_BUDGET, 429),
    ],
    ids=["503", "timeout", "401", "429"],
)
def test_unknown_counter_is_classified_and_spends_nothing(
    tmp_path: Path,
    sports: Callable[[httpx.Request], httpx.Response],
    reason: str,
    status: int | None,
) -> None:
    """``/sports`` padło → licznik nieznany: zero płatnych ``/odds``, wpis z kodem z ``/sports``."""
    missed, errors, paid = _run_scene(tmp_path, sports=sports)
    assert paid == 0, "przy nieznanym liczniku kolektor nie może wydać kredytu"
    (entry,) = missed
    assert entry["reason"] == reason, entry
    assert entry["http_status"] == status, entry
    assert entry["collector_gap"] is False
    assert errors, "błąd /sports ma być w heartbeacie"


@pytest.mark.parametrize(
    "odds",
    [
        lambda _r: httpx.Response(200, text="<html>nie json</html>"),
        lambda _r: httpx.Response(200, json={"message": "zly ksztalt"}),
        lambda _r: httpx.Response(200, json=[{"bookmakers": []}]),
    ],
    ids=["zly-json", "nie-lista", "brak-pol"],
)
def test_contract_error_is_its_own_reason(
    tmp_path: Path, odds: Callable[[httpx.Request], httpx.Response]
) -> None:
    """HTTP 200 ze złą treścią → „błąd kontraktu API”, ``http_status`` 200, nie API i nie 4xx."""
    missed, errors, _ = _run_scene(tmp_path, odds=odds)
    (entry,) = missed
    assert entry["reason"] == REASON_CONTRACT, entry
    assert entry["http_status"] == 200
    assert entry["collector_gap"] is False
    assert errors


def test_every_reason_has_a_real_path_in_the_code(tmp_path: Path) -> None:
    """Każdy powód z ``MISSED_REASONS`` powstaje z prawdziwego ``run_once`` — żaden martwy."""
    no_pinnacle = {**_event(), "bookmakers": []}
    scenes: dict[str, dict[str, Any]] = {
        REASON_OFFLINE: {"start": timedelta(minutes=-10)},
        REASON_BUDGET: {"odds": _status(429)},
        REASON_NO_PINNACLE: {"odds": lambda _r: httpx.Response(200, json=[no_pinnacle])},
        REASON_STORAGE: {"free": 1024},
        REASON_API: {"odds": _status(503)},
        REASON_CLIENT: {"odds": _status(403)},
        REASON_CONTRACT: {"odds": lambda _r: httpx.Response(200, json={"x": 1})},
    }
    assert set(scenes) == set(MISSED_REASONS)
    for i, (reason, kwargs) in enumerate(scenes.items()):
        # OFFLINE: pierwszy przebieg 10 min PO gwizdku — mecz znany z /events,
        # w godzinie przed gwizdkiem żadnego przebiegu.
        missed, _, _ = _run_scene(tmp_path / str(i), **kwargs)
        assert [e["reason"] for e in missed] == [reason], (reason, missed)
