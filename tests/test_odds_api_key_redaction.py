"""Klucz The Odds API nie trafia na dysk ani do logów — ścieżka kolektora od końca do końca.

Kontekst (alarm 2026-10-12): „klucz w URL w plikach raw 16/16”. Testy
przechodzą przez prawdziwy ``OddsCollector.run_once`` z fałszywym transportem
i sprawdzają ścieżki niebezpieczne (reguła 30): udane wywołanie, HTTP 401 z
URL-em zapytania w treści błędu i zerwane połączenie z URL-em w komunikacie
wyjątku ``httpx``. Klucz testowy nigdy nie może się pojawić w żadnym bajcie
zapisanym pod ``tmp_path`` ani w logach.
"""

from __future__ import annotations

import hashlib
import json
import logging
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from helpers import FakeClock, assert_from_checkout
from helpers.collector_scene import event
from valuebet.ingest.odds_api import (
    OddsApiClient,
    OddsApiError,
    OddsApiSettings,
    UsageGuard,
    redact_api_key,
)
from valuebet.ingest.odds_collector import OddsCollector
from valuebet.ingest.raw_store import RawStore
from valuebet.net.http import HttpClient

assert_from_checkout(__file__)

KEY = "TESTKEY0123456789abcdef"
EPL = "soccer_epl"
KICKOFF = datetime(2026, 10, 24, 14, 0, tzinfo=UTC)
#: Rano w dniu meczu — należna migawka decyzyjna (jak w testach F0c).
MORNING = datetime(2026, 10, 24, 6, 40, tzinfo=UTC)
#: W oknie zamknięcia — błąd tu daje wpis ``closing_missed``.
CLOSING = datetime(2026, 10, 24, 13, 55, tzinfo=UTC)
HEADERS = {
    "x-requests-used": "10",
    "x-requests-remaining": "490",
    "x-requests-last": "0",
}

Handler = Callable[[httpx.Request], httpx.Response]


def _ok(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/sports"):
        return httpx.Response(200, json=[], headers=HEADERS)
    return httpx.Response(200, json=[event("m1", KICKOFF)], headers=HEADERS)


def _unauthorized(request: httpx.Request) -> httpx.Response:
    """401 z URL-em zapytania (z kluczem) w treści — tak bywa u dostawców."""
    if request.url.path.endswith("/sports") or request.url.path.endswith("/events"):
        return _ok(request)
    body = {"message": "bad key", "url": str(request.url)}
    return httpx.Response(401, json=body, headers=HEADERS)


def _connection_error(request: httpx.Request) -> httpx.Response:
    """Zerwane połączenie; komunikat ``httpx`` niesie pełny URL z kluczem."""
    if request.url.path.endswith("/sports") or request.url.path.endswith("/events"):
        return _ok(request)
    raise httpx.ConnectError(f"nie połączono z {request.url}", request=request)


def _http(tmp_path: Path, handler: Handler) -> HttpClient:
    clock = FakeClock()
    return HttpClient(
        clock=clock,
        sleep=clock.sleep,
        transport=httpx.MockTransport(handler),
        state_dir=tmp_path / "http" / "throttle",
        robots_dir=tmp_path / "http" / "robots",
    )


def _collector(tmp_path: Path, handler: Handler) -> OddsCollector:
    client = OddsApiClient(
        http=_http(tmp_path, handler), settings=OddsApiSettings(api_key=KEY)
    )
    return OddsCollector(
        client=client,
        store=RawStore(root=tmp_path / "raw", manifest=tmp_path / "manifest.jsonl"),
        state_root=tmp_path / "state",
    )


def _run(tmp_path: Path, handler: Handler) -> OddsCollector:
    collector = _collector(tmp_path, handler)
    collector.run_once(now=MORNING)
    collector.run_once(now=CLOSING)
    return collector


def _files_with_key(root: Path) -> list[Path]:
    return [
        p for p in root.rglob("*") if p.is_file() and KEY.encode() in p.read_bytes()
    ]


def _raw_files(tmp_path: Path) -> list[Path]:
    return sorted((tmp_path / "raw").rglob("*.json"))


# -- 1. plik surowy ------------------------------------------------------------


def test_raw_file_has_redacted_url_and_no_key(tmp_path: Path) -> None:
    _run(tmp_path, _ok)
    raws = _raw_files(tmp_path)
    assert raws, "scena nie wywołała płatnego /odds — test byłby pusty"
    for path in raws:
        data = path.read_bytes()
        assert KEY.encode() not in data, f"klucz w pliku surowym {path.name}"
        url = json.loads(data)["requested_url"]
        assert "apiKey=REDACTED" in url
        assert "/odds" in url, "zredagowany URL ma nadal mówić, o co pytaliśmy"


# -- 2. logi -------------------------------------------------------------------


@pytest.mark.parametrize("handler", [_ok, _unauthorized, _connection_error])
def test_logs_never_contain_key(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, handler: Handler
) -> None:
    caplog.set_level(logging.DEBUG)
    _run(tmp_path, handler)
    assert caplog.records, "kolektor nic nie zalogował — test byłby pusty"
    assert KEY not in caplog.text
    for record in caplog.records:
        assert KEY not in record.getMessage()
        if record.exc_info:
            assert KEY not in "".join(traceback.format_exception(*record.exc_info))


# -- 3. wyjątki warstwy HTTP ----------------------------------------------------


@pytest.mark.parametrize("handler", [_unauthorized, _connection_error])
def test_http_failure_exception_never_carries_key(
    tmp_path: Path, handler: Handler
) -> None:
    client = OddsApiClient(
        http=_http(tmp_path, handler), settings=OddsApiSettings(api_key=KEY)
    )
    with pytest.raises(OddsApiError) as info:
        client.fetch_odds(
            sport_key=EPL,
            markets=("h2h",),
            usage_guard=UsageGuard(used=0),
            closing=False,
        )
    exc = info.value
    assert KEY not in str(exc)
    assert KEY not in repr(exc)
    # Pełny traceback, tak jak wypisałby go ``log.exception`` albo interpreter.
    assert KEY not in "".join(traceback.format_exception(exc))


@pytest.mark.parametrize("handler", [_unauthorized, _connection_error])
def test_collector_records_failure_without_key(
    tmp_path: Path, handler: Handler
) -> None:
    _run(tmp_path, handler)
    heartbeat = (tmp_path / "state" / "heartbeat.jsonl").read_text(encoding="utf-8")
    assert '"errors": ["' in heartbeat, (
        "błąd nie trafił do heartbeatu — test byłby pusty"
    )
    assert KEY not in heartbeat
    missed = tmp_path / "state" / "closing_missed.jsonl"
    if missed.exists():
        assert KEY not in missed.read_text(encoding="utf-8")


# -- 4. każdy plik, który kolektor zapisuje --------------------------------------


@pytest.mark.parametrize("handler", [_ok, _unauthorized, _connection_error])
def test_no_written_file_contains_key(tmp_path: Path, handler: Handler) -> None:
    """state.json, heartbeat, usage, closing_missed, throttle, robots, manifest, raw."""
    _run(tmp_path, handler)
    written = [p for p in tmp_path.rglob("*") if p.is_file()]
    names = {p.name for p in written}
    assert {"state.json", "heartbeat.jsonl"} <= names
    assert any(p.parent.name == "throttle" for p in written), "brak pliku tempa"
    assert _files_with_key(tmp_path) == []


# -- 5. hash pliku surowego -------------------------------------------------------


def test_raw_hash_is_of_redacted_bytes(tmp_path: Path) -> None:
    _run(tmp_path, _ok)
    raws = _raw_files(tmp_path)
    assert raws
    manifest = [
        json.loads(line)
        for line in (tmp_path / "manifest.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    by_name = {Path(entry["path"]).name: entry for entry in manifest}
    for path in raws:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert by_name[path.name]["sha256"] == digest
        # Prefiks hasha w nazwie pliku: ``<kotwica>.<znacznik>.<sha256[:8]>.json``.
        assert path.name.split(".")[-2] == digest[:8]


# -- redact_api_key: kolejność parametrów i kodowanie ------------------------------


@pytest.mark.parametrize(
    "query",
    [
        f"apiKey={KEY}&regions=eu&markets=h2h",
        f"regions=eu&apiKey={KEY}&markets=h2h",
        f"regions=eu&markets=h2h&apiKey={KEY}",
    ],
)
def test_redact_any_parameter_position(query: str) -> None:
    out = redact_api_key(f"https://api.the-odds-api.com/v4/sports/{EPL}/odds?{query}")
    assert KEY not in out
    assert "apiKey=REDACTED" in out
    assert "regions=eu" in out


def test_redact_percent_encoded_value() -> None:
    raw = "KEY+/=0123456789abcdef"
    url = str(
        httpx.URL("https://api.the-odds-api.com/v4/sports", params={"apiKey": raw})
    )
    assert raw not in url, "warunek testu: wartość ma być zakodowana w URL-u"
    out = redact_api_key(url)
    assert "apiKey=REDACTED" in out
    assert "0123456789abcdef" not in out
