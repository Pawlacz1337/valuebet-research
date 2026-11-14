"""Scena kolektora dla testów regresji F0b/F0c: prawdziwy ``run_once``, fałszywy transport.

Odpowiedź ``/odds`` ustawia test (``Scene.events``) — The Odds API zwraca
mecze nadchodzące i trwające, więc test decyduje, co „widać” w danej chwili.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from helpers import fake_http
from valuebet.ingest.odds_api import OddsApiClient, OddsApiSettings
from valuebet.ingest.odds_collector import OddsCollector
from valuebet.ingest.raw_store import RawStore

H2H = {
    "key": "h2h",
    "outcomes": [
        {"name": "Home", "price": 2.10},
        {"name": "Away", "price": 3.40},
        {"name": "Draw", "price": 3.30},
    ],
}


def event(event_id: str, commence: datetime, *, pinnacle: bool = True) -> dict[str, Any]:
    books = [{"key": "pinnacle", "markets": [H2H]}] if pinnacle else []
    return {
        "id": event_id,
        "commence_time": commence.isoformat().replace("+00:00", "Z"),
        "home_team": f"H-{event_id}",
        "away_team": f"A-{event_id}",
        "bookmakers": books,
    }


@dataclass
class Scene:
    tmp_path: Path
    #: sport_key → lista zdarzeń zwracana przez ``/odds`` tej ligi.
    events: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    #: sport_key → terminarz z ``/events``; brak ligi = to samo co ``events``.
    listing: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    #: ścieżki ``/odds`` i ``/events`` w kolejności wywołań.
    odds_calls: list[str] = field(default_factory=list)

    def handler(self, request: httpx.Request) -> httpx.Response:
        headers = {"x-requests-used": "0", "x-requests-remaining": "500"}
        if request.url.path.endswith("/sports"):
            return httpx.Response(200, json=[], headers=headers)
        self.odds_calls.append(request.url.path)
        sport = request.url.path.split("/sports/")[1].split("/")[0]
        if request.url.path.endswith("/events"):
            body = self.listing.get(sport, self.events.get(sport, []))
            return httpx.Response(200, json=body, headers={**headers, "x-requests-last": "0"})
        return httpx.Response(200, json=self.events.get(sport, []), headers=headers)

    @property
    def paid_calls(self) -> list[str]:
        return [p for p in self.odds_calls if p.endswith("/odds")]

    def collector(self) -> OddsCollector:
        client = OddsApiClient(
            http=fake_http(self.handler), settings=OddsApiSettings(api_key="k" * 32)
        )
        return OddsCollector(
            client=client,
            store=RawStore(root=self.tmp_path / "raw", manifest=self.tmp_path / "manifest.jsonl"),
            state_root=self.tmp_path / "state",
        )
