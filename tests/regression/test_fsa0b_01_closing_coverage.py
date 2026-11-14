"""FSA #0b F0b-01 — tygodniowe pokrycie zamknięć liczone ze stanu, który kolektor naprawdę tworzy.

Ścieżka niebezpieczna: prawdziwy ``run_once`` na fałszywym transporcie.
Premier League, mecz A 11:30 — komputer spał, zamknięcie przegapione; mecz B
16:30 — zapasowe i główne zebrane. The Odds API zwraca tylko mecze
nadchodzące i trwające, więc odpowiedź ``/odds`` zawiera B i przyszły C.
``run_once`` nadpisywał terminarz każdą odpowiedzią — A znikał ze stanu, a
``closing_coverage`` dawało (1, 1) = 100% zamiast 1 z 2 = 50%. Ta liczba
decyduje o bramkach G-S i G-K (≥ 95%, ROADMAP §8). Stary test budował stan
ręcznie — taki, jakiego kolektor nigdy nie wytwarza.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from helpers import assert_from_checkout, fake_http
from valuebet.ingest.odds_api import OddsApiClient, OddsApiSettings
from valuebet.ingest.odds_collector import OddsCollector, closing_coverage
from valuebet.ingest.raw_store import RawStore

assert_from_checkout(__file__)

EPL = "soccer_epl"
A = datetime(2026, 10, 24, 11, 30, tzinfo=UTC)
B = datetime(2026, 10, 24, 16, 30, tzinfo=UTC)
C = datetime(2026, 10, 31, 16, 30, tzinfo=UTC)


def _event(commence: datetime) -> dict[str, Any]:
    return {
        "id": f"ev-{commence.isoformat()}",
        "commence_time": commence.isoformat().replace("+00:00", "Z"),
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "bookmakers": [{"key": "pinnacle", "markets": [{"key": "h2h", "outcomes": [
            {"name": "H", "price": 2.1}, {"name": "A", "price": 3.4},
            {"name": "D", "price": 3.3}]}]}],
    }


#: Co lista ligi pokazuje „teraz” — rano A, B, C; po gwizdku A tylko B i C.
_LISTED: list[datetime] = [A, B, C]


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/sports"):
        return httpx.Response(
            200, json=[], headers={"x-requests-used": "0", "x-requests-remaining": "500"}
        )
    if EPL in request.url.path:
        return httpx.Response(
            200,
            json=[_event(k) for k in _LISTED],
            headers={"x-requests-used": "1", "x-requests-remaining": "499"},
        )
    return httpx.Response(
        200, json=[], headers={"x-requests-used": "1", "x-requests-remaining": "499"}
    )


def _collector(tmp_path: Path) -> OddsCollector:
    client = OddsApiClient(http=fake_http(_handler), settings=OddsApiSettings(api_key="k" * 32))
    return OddsCollector(
        client=client,
        store=RawStore(root=tmp_path / "raw", manifest=tmp_path / "manifest.jsonl"),
        state_root=tmp_path / "state",
    )


def _run_day(collector: OddsCollector) -> dict[str, Any]:
    collector._save_state(
        {"done": [], "kickoffs": {EPL: [A.isoformat(), B.isoformat(), C.isoformat()]},
         "last_usage": None}
    )
    # Rano kolektor widzi A, B, C (od rundy 0e terminarz jest z /events).
    _LISTED[:] = [A, B, C]
    collector.run_once(now=A - timedelta(hours=2))
    # Komputer śpi przez całe okno zamknięcia A; budzi się przed B, A zszedł z listy.
    _LISTED[:] = [B, C]
    collector.run_once(now=B - timedelta(minutes=25))
    collector.run_once(now=B - timedelta(minutes=5))
    return collector._load_state()


def test_closing_for_b_was_collected_and_a_was_missed(tmp_path: Path) -> None:
    """Warunek sceny: B zebrane, A nie — inaczej test niczego nie mierzy."""
    state = _run_day(_collector(tmp_path))
    done = set(state["done"])
    assert f"premier_league|closing|{B.isoformat()}" in done
    assert f"premier_league|closing|{A.isoformat()}" not in done


def test_coverage_counts_the_missed_match(tmp_path: Path) -> None:
    state = _run_day(_collector(tmp_path))
    cov = closing_coverage(state, now=B + timedelta(hours=3))
    assert cov["premier_league"] == (1, 2), "przegapione A zniknęło z mianownika"


def test_coverage_survives_later_calls(tmp_path: Path) -> None:
    """Kolejne wywołania ligi (tu: tydzień później, zamknięcie C) nie gubią A ani B."""
    collector = _collector(tmp_path)
    _run_day(collector)
    collector.run_once(now=C - timedelta(minutes=5))
    cov = closing_coverage(collector._load_state(), now=C + timedelta(hours=3), days=8)
    assert cov["premier_league"] == (2, 3)
