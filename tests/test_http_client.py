"""``valuebet.net.http`` — cache robots.txt, błędy sieci, kontekst."""

from __future__ import annotations

import httpx
import pytest

from helpers import FakeClock, fake_http
from valuebet.net.http import ROBOTS_TTL_S, RobotsDisallowedError, redact


def test_robots_is_cached_for_a_day_then_refetched() -> None:
    clock = FakeClock()
    robots_calls: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            robots_calls.append(clock())
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, text="ok")

    with fake_http(handler, clock) as http:
        http.get("https://example.org/a")
        http.get("https://example.org/b")
        assert len(robots_calls) == 1
        clock.sleep(ROBOTS_TTL_S + 1)
        http.get("https://example.org/c")
    assert len(robots_calls) == 2


def test_robots_network_error_is_a_refusal() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("brak sieci")

    with pytest.raises(RobotsDisallowedError, match="niedostępny"):
        fake_http(handler).get("https://example.org/a")


def test_missing_robots_allows_with_minimum_interval() -> None:
    clock = FakeClock()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404 if request.url.path == "/robots.txt" else 200)

    http = fake_http(handler, clock)
    assert http.interval_for("https://example.org/a") == 10.0
    http.post("https://api.telegram.org/x", json_body={"a": 1})


def test_redact_handles_text_and_urls() -> None:
    assert "SEKRET" not in redact("blad apiKey=SEKRET&x=1")
    assert "SEKRET" not in redact("https://h/v4?apiKey=SEKRET")
    assert redact("https://api.telegram.org/bot1:SEKRET/send") == (
        "https://api.telegram.org/botREDACTED/send"
    )
