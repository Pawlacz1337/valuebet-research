"""FSA #0 F-26 — jeden klient sieciowy z odstępem per host i robots.txt.

Ścieżki niebezpieczne:
- dwa zapytania do jednego hosta bez odstępu (``validate_instrument`` wysyłał
  sześć w 1-3 s; COLLECTOR_PLAN §2 pkt 6 wymaga ≥ max(10 s, Crawl-delay));
- ścieżka zabroniona przez robots.txt pobrana mimo to;
- ``httpx``/``requests``/``urllib.request`` użyte bezpośrednio poza klientem;
- sekret (``apiKey``, token Telegrama) w komunikacie wyjątku albo ``repr``.

``ImportError`` na starym kodzie jest tu dopuszczalnym czerwonym: znaleziskiem
jest brak mechanizmu (FSA0_NAPRAWY §1 pkt 2).
"""

from __future__ import annotations

import ast
import importlib.util
import itertools
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest

from helpers import assert_from_checkout
from valuebet.ingest.raw_store import RawStore
from valuebet.net.http import HttpClient, HttpError, RobotsDisallowedError

ROOT = assert_from_checkout(__file__)


class FakeClock:
    def __init__(self) -> None:
        self.t = 1_000_000.0

    def __call__(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


def _client(tmp_path: Path, handler: Any, clock: FakeClock) -> HttpClient:
    return HttpClient(
        clock=clock,
        sleep=clock.sleep,
        transport=httpx.MockTransport(handler),
        state_dir=tmp_path / "throttle",
        robots_dir=tmp_path / "robots",
    )


def test_two_requests_to_one_host_are_ten_seconds_apart(tmp_path: Path) -> None:
    clock = FakeClock()
    seen: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(clock())
        return httpx.Response(200, json=[])

    client = _client(tmp_path, handler, clock)
    client.get("https://api.the-odds-api.com/v4/sports", params={"apiKey": "x"})
    client.get("https://api.the-odds-api.com/v4/sports", params={"apiKey": "x"})
    assert len(seen) == 2
    assert seen[1] - seen[0] >= 10.0


def test_throttle_state_is_shared_between_clients(tmp_path: Path) -> None:
    clock = FakeClock()
    seen: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(clock())
        return httpx.Response(200, json=[])

    _client(tmp_path, handler, clock).get("https://api.telegram.org/x")
    _client(tmp_path, handler, clock).get("https://api.telegram.org/x")
    assert seen[1] - seen[0] >= 10.0


def _site(robots: str, *, status: int = 200) -> Any:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(status, text=robots)
        return httpx.Response(200, text="a,b\n")

    return handler


def test_crawl_delay_above_ten_seconds_is_respected(tmp_path: Path) -> None:
    clock = FakeClock()
    client = _client(tmp_path, _site("User-agent: *\nCrawl-delay: 20\n"), clock)
    client.get("https://example.org/a.csv")
    start = clock()
    client.get("https://example.org/b.csv")
    assert clock() - start >= 20.0


def test_disallowed_path_is_refused(tmp_path: Path) -> None:
    clock = FakeClock()
    client = _client(tmp_path, _site("User-agent: *\nDisallow: /private\n"), clock)
    with pytest.raises(RobotsDisallowedError):
        client.get("https://example.org/private/x.csv")


def test_unavailable_robots_is_refused(tmp_path: Path) -> None:
    clock = FakeClock()
    client = _client(tmp_path, _site("", status=503), clock)
    with pytest.raises(RobotsDisallowedError):
        client.get("https://example.org/a.csv")


def test_secrets_never_leak(tmp_path: Path) -> None:
    clock = FakeClock()

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"nie połączono z {request.url}")

    client = _client(tmp_path, boom, clock)
    with pytest.raises(HttpError) as info:
        client.get(
            "https://api.telegram.org/bot123456789:SEKRETTOKEN/sendMessage",
            params={"apiKey": "SEKRETKLUCZ"},
        )
    message = str(info.value) + repr(client)
    assert "SEKRETTOKEN" not in message
    assert "SEKRETKLUCZ" not in message


def _validate_instrument() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "validate_instrument", ROOT / "scripts" / "validate_instrument.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validate_instrument_download_loop_is_throttled(tmp_path: Path) -> None:
    clock = FakeClock()
    seen: list[float] = []
    header = "Date,HomeTeam,AwayTeam,FTHG,FTAG,PSCH,PSCD,PSCA,PC>2.5,PC<2.5\n"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        seen.append(clock())
        return httpx.Response(200, text=header)

    module = _validate_instrument()
    store = RawStore(root=tmp_path / "raw", manifest=tmp_path / "manifest.jsonl")
    module.load_or_fetch(
        _client(tmp_path, handler, clock),
        store,
        now=lambda: datetime.fromtimestamp(clock(), tz=UTC),
    )
    assert len(seen) == len(module.SEASONS)
    gaps = [b - a for a, b in itertools.pairwise(seen)]
    assert min(gaps) >= 10.0


NET_ROOTS = {"httpx", "requests", "urllib3", "aiohttp"}
NET_MODULES = {"urllib.request", "http.client"}
#: Moduły do usunięcia w późniejszej naprawie — pusty po F-28.
PENDING_REMOVAL: dict[str, str] = {}
READERS = {"read_csv", "read_json", "read_parquet", "read_html"}
SUBPROCESS = {"run", "Popen", "call", "check_output", "check_call"}


def _violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            if name in NET_MODULES or name.split(".")[0] in NET_ROOTS:
                found.append(f"import {name}")
        if isinstance(node, ast.Call):
            func = node.func
            attr = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            literals = [
                a.value
                for a in node.args
                if isinstance(a, ast.Constant) and isinstance(a.value, str)
            ]
            if attr in READERS and any(v.startswith("http") for v in literals):
                found.append(f"{attr} z adresem http")
            if attr in SUBPROCESS:
                flat = " ".join(ast.unparse(a) for a in node.args)
                if "curl" in flat or "wget" in flat:
                    found.append("subprocess curl/wget")
    return found


def test_no_network_outside_the_client() -> None:
    bad = {}
    for base in ("src", "scripts"):
        for path in sorted((ROOT / base).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if rel == "src/valuebet/net/http.py" or rel in PENDING_REMOVAL:
                continue
            found = _violations(path)
            if found:
                bad[rel] = found
    assert bad == {}
