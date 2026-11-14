"""Wspólne zabezpieczenia testów.

Zero sieci w testach (COLLECTOR_PLAN §3.9). Test, który spróbuje wyjść do
internetu, ma się wywalić — a nie przejść raz u mnie i paść w CI, albo
zacząć cicho zużywać kredyty The Odds API.

Blokada siedzi na ``httpx.HTTPTransport``, czyli na transporcie
**sieciowym**. ``httpx.MockTransport`` jest osobną klasą, więc testy, które
wstrzykują własny transport, działają normalnie. To celowe: blokujemy
wyjście na zewnątrz, nie samo użycie ``httpx``.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest


class NetworkAccessInTestError(RuntimeError):
    """Test sięgnął do sieci. Sufiks ``Error`` wymaga ruff N818."""


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    def blocked(self: httpx.HTTPTransport, request: httpx.Request) -> httpx.Response:
        raise NetworkAccessInTestError(
            f"test próbował wyjść do sieci: {request.method} {request.url.host}"
            f"{request.url.path} — użyj httpx.MockTransport"
        )

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    yield


# Pomocnicy testów regresji (``tests/helpers``) jako zwykły import
# ``helpers`` — także po skopiowaniu testu do worktree rewersu.
sys.path.insert(0, str(Path(__file__).resolve().parent))
