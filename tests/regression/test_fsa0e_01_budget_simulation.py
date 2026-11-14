"""FSA #0e F0e-01 — kalkulator budżetu = symulacja prawdziwego kolektora.

Decyzja Pawła (2026-10-04, pkt 1): kalkulator nie ma własnej formuły, tylko
przechodzi prawdziwym ``due_calls`` co 5 min po terminarzu. Test: wynik
kalkulatora = liczba płatnych wywołań (i kredytów) prawdziwego ``run_once``
na fałszywym zegarze i transporcie, na tym samym terminarzu.

Ścieżka niebezpieczna z raportu audytora: kolektor robi migawkę decyzyjną
także w dniu PRZED pierwszym dniem kolejki (horyzont 48 h), a stara formuła
liczyła dni decyzji wyłącznie po dniach z meczem — plan zaniżony o ~31%
kredytów decyzji, realnie ~456 zamiast wydrukowanych 430.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest

from helpers import assert_from_checkout, build, fake_http
from valuebet.ingest.odds_api import OddsApiClient, OddsApiSettings
from valuebet.ingest.odds_collector import OddsCollector
from valuebet.ingest.raw_store import RawStore

ROOT = assert_from_checkout(__file__)

EKS = "soccer_poland_ekstraklasa"
EPL = "soccer_epl"
BUN = "soccer_germany_bundesliga"
STEP = timedelta(minutes=5)

#: Piątek 2026-11-27. Jedna pełna kolejka na ligę (9/10/9 meczów), więc
#: skala miesięczna kalkulatora jest dla każdej ligi ta sama: 4.3 / 1.
FRI = datetime(2026, 11, 27, tzinfo=UTC)


def _round(day: int, *hours: float) -> list[datetime]:
    return [FRI + timedelta(days=day, hours=h) for h in hours]


TERMINARZ: dict[str, list[datetime]] = {
    # Ekstraklasa: pt 17:30, 20:00; sb 12:15, 14:45, 17:30, 17:30; nd 14:45, 17:30; pn 19:00
    EKS: _round(0, 17.5, 20)
    + _round(1, 12.25, 14.75, 17.5, 17.5)
    + _round(2, 14.75, 17.5)
    + _round(3, 19),
    # Premier League: sb 12:30, 15:00 x4, 17:30; nd 14:00 x2, 16:30; pn 20:00
    EPL: _round(1, 12.5, 15, 15, 15, 15, 17.5) + _round(2, 14, 14, 16.5) + _round(3, 20),
    # Bundesliga: pt 19:30; sb 14:30 x5, 17:30; nd 14:30, 16:30
    BUN: _round(0, 19.5) + _round(1, 14.5, 14.5, 14.5, 14.5, 14.5, 17.5) + _round(2, 14.5, 16.5),
}
#: Początek symulacji: wtorek przed kolejką, równo na kroku 5 min.
START = FRI - timedelta(days=3)
END = FRI + timedelta(days=4)


def _event(sport: str, i: int, kickoff: datetime) -> dict[str, Any]:
    h2h = {
        "key": "h2h",
        "outcomes": [
            {"name": "H", "price": 2.1},
            {"name": "A", "price": 3.4},
            {"name": "D", "price": 3.3},
        ],
    }
    return {
        "id": f"{sport}-{i}",
        "sport_key": sport,
        "commence_time": kickoff.isoformat().replace("+00:00", "Z"),
        "home_team": f"H{i}",
        "away_team": f"A{i}",
        "bookmakers": [{"key": "pinnacle", "markets": [h2h]}],
    }


class _Transport:
    """Fałszywe The Odds API: terminarz z ``/events``, ceny z ``/odds``, licznik kredytów."""

    def __init__(self) -> None:
        self.now = START
        self.used = 0
        self.paid: list[tuple[str, int]] = []

    def _listing(self, sport: str) -> list[dict[str, Any]]:
        return [
            _event(sport, i, k) for i, k in enumerate(TERMINARZ.get(sport, [])) if k > self.now
        ]

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        base = {"x-requests-used": str(self.used), "x-requests-remaining": str(500 - self.used)}
        if path.endswith("/robots.txt"):
            return httpx.Response(404, text="")
        if path.endswith("/sports") or path.endswith("/sports/"):
            return httpx.Response(200, json=[], headers=base)
        sport = path.split("/sports/")[1].split("/")[0]
        if path.endswith("/events"):
            return httpx.Response(
                200, json=self._listing(sport), headers={**base, "x-requests-last": "0"}
            )
        markets = [m for m in request.url.params.get("markets", "").split(",") if m]
        self.used += len(markets)
        self.paid.append((sport, len(markets)))
        headers = {
            "x-requests-used": str(self.used),
            "x-requests-remaining": str(500 - self.used),
            "x-requests-last": str(len(markets)),
        }
        return httpx.Response(200, json=self._listing(sport), headers=headers)


def _real_collector_paid(tmp: Path) -> tuple[int, int]:
    """Prawdziwy ``run_once`` co 5 min od START do END: (płatne wywołania, kredyty)."""
    transport = _Transport()
    client = OddsApiClient(
        http=fake_http(transport.handler), settings=OddsApiSettings(api_key="k" * 32)
    )
    collector = build(
        OddsCollector,
        client=client,
        store=RawStore(root=tmp / "raw", manifest=tmp / "manifest.jsonl"),
        state_root=tmp / "state",
        free_bytes=lambda _path: 10 * 1024**3,
    )
    t = START
    while t <= END:
        transport.now = t
        collector.run_once(now=t)
        t += STEP
    return len(transport.paid), sum(cost for _, cost in transport.paid)


def _budget_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "odds_budget_f0e01", ROOT / "scripts" / "odds_budget.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_calculator_equals_real_collector_paid_credits(tmp_path: Path) -> None:
    calls, cost = _real_collector_paid(tmp_path)
    assert calls > 0
    module = _budget_module()
    result = build(module.plan, kickoffs=TERMINARZ, start=START, end=END)
    # Jedna kolejka na ligę → skala 4.3 dla każdej ligi; okno = cały cykl kolejki.
    assert result.total == pytest.approx(cost * module.ROUNDS_PER_MONTH), (
        f"kalkulator {result.total:.1f}/mies. ≠ kolektor {cost} kredytów x "
        f"{module.ROUNDS_PER_MONTH} = {cost * module.ROUNDS_PER_MONTH:.1f}"
    )
    assert result.window_calls == calls
    assert result.window_credits == cost
