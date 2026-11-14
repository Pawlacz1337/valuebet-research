"""FSA #0 F-15 + F-16 — budżet 450 kredytów i tryb „tylko zamknięcia” w kodzie.

Ścieżki niebezpieczne (fałszywy transport, zero prawdziwych kredytów):
- ``used = 449``, wywołanie za 2 kredyty — dziś idzie (jedyny bezpiecznik to
  ``remaining < 10``, czyli stop po 490, nie po 450);
- ``used = 395`` (zapas 55 < 60) — migawka decyzyjna dziś idzie, a w trybie
  oszczędnym wolno już tylko zamknięcia;
- ``credits_spent`` zawsze 3, niezależnie od liczby rynków (F-16).

Prawdą o zużyciu są nagłówki dostawcy, odświeżane bezpłatnym ``/sports`` na
początku przebiegu — nie stary stan z pliku.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from helpers import assert_from_checkout, build, fake_http
from valuebet.ingest.odds_api import OddsApiClient, OddsApiSettings
from valuebet.ingest.odds_collector import OddsCollector, decision_window_utc
from valuebet.ingest.raw_store import RawStore

assert_from_checkout(__file__)

EPL = "soccer_epl"
KICKOFF = datetime(2026, 10, 24, 17, 0, tzinfo=UTC)


def _event(commence: datetime) -> dict[str, Any]:
    return {
        "id": "e1",
        "sport_key": EPL,
        "commence_time": commence.isoformat().replace("+00:00", "Z"),
        "home_team": "A",
        "away_team": "B",
        "bookmakers": [],
    }


def _world(tmp_path: Path, *, used: int) -> tuple[Any, list[str]]:
    paths: list[str] = []
    headers = {
        "x-requests-used": str(used),
        "x-requests-remaining": str(500 - used),
        "x-requests-last": "0",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/sports"):
            return httpx.Response(200, json=[], headers=headers)
        if request.url.path.endswith("/events"):
            # Terminarz (od rundy 0e) — bezpłatny, x-requests-last: 0.
            return httpx.Response(200, json=[_event(KICKOFF)], headers=headers)
        return httpx.Response(
            200,
            json=[_event(KICKOFF)],
            headers={**headers, "x-requests-last": "2"},
        )

    client = build(
        OddsApiClient,
        settings=OddsApiSettings(api_key="k" * 32),
        http=fake_http(handler),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    collector = build(
        OddsCollector,
        client=client,
        store=RawStore(root=tmp_path / "raw", manifest=tmp_path / "manifest.jsonl"),
        state_root=tmp_path / "state",
    )
    collector._save_state(
        {
            "done": [],
            "kickoffs": {EPL: [KICKOFF.isoformat()]},
            # Stary stan z pliku twierdzi, że budżet jest pełny — prawdą są nagłówki.
            "last_usage": {"remaining": 500, "used": 0},
        }
    )
    return collector, paths


def _run(collector: Any, now: datetime) -> dict[str, Any]:
    return dict(build(collector.run_once, now=now))


def test_call_over_450_is_skipped(tmp_path: Path) -> None:
    collector, paths = _world(tmp_path, used=449)
    entry = _run(collector, KICKOFF - timedelta(minutes=5))
    assert not any(p.endswith("/odds") for p in paths), "449 + 2 > 450 — kredyt nie może pójść"
    assert entry.get("budget_skip"), entry


def test_saving_mode_allows_only_closings(tmp_path: Path) -> None:
    collector, paths = _world(tmp_path, used=395)
    start, _ = build(decision_window_utc, now=KICKOFF - timedelta(hours=10))
    entry = _run(collector, start + timedelta(minutes=5))
    assert not any(p.endswith("/odds") for p in paths), "zapas 55 < 60 — tylko zamknięcia"
    assert entry.get("budget_skip"), entry


def test_closing_still_goes_in_saving_mode(tmp_path: Path) -> None:
    collector, paths = _world(tmp_path, used=395)
    entry = _run(collector, KICKOFF - timedelta(minutes=5))
    assert any(p.endswith("/odds") for p in paths), entry


def test_credits_spent_comes_from_provider_header(tmp_path: Path) -> None:
    collector, _ = _world(tmp_path, used=100)
    _run(collector, KICKOFF - timedelta(minutes=5))
    usage = tmp_path / "state" / "usage.jsonl"
    assert usage.exists(), "nagłówki dostawcy mają trafiać do usage.jsonl"
    text = usage.read_text(encoding="utf-8")
    assert '"last": 2' in text
