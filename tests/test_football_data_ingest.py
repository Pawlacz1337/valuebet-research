"""Ingest Filaru 1 (``BACKTEST_FIN_PLAN.md`` §1, §7 krok 2) — na fałszywym transporcie.

Co ma być prawdą:

- 22 ligi x 7 sezonów, dokładnie z listy planu;
- każde zapytanie przez ``HttpClient`` (odstęp ≥ 10 s, robots.txt);
- surowe bajty do raw przez ``RawStore`` (manifest sum kontrolnych) — po
  każdym pliku, nie na końcu;
- ponowne uruchomienie pomija pliki zweryfikowane sumą kontrolną i nie
  wychodzi po nie do sieci; plik w raw niezgodny z manifestem albo bez
  wpisu → głośny błąd, nigdy nadpisanie ani ciche pobranie od nowa;
- 404 → „brak pliku” w dzienniku, nic w raw; HTML zamiast CSV → nic w raw.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from helpers import FakeClock, fake_http
from valuebet.ingest.football_data_main import (
    FIN_LEAGUES,
    FIN_SEASONS,
    RAW_SUBDIR,
    IngestOutcome,
    MainLeagueFile,
    RawIntegrityError,
    column_report,
    fin_files,
    ingest_files,
    ingest_notes,
)
from valuebet.ingest.raw_store import RawStore, read_manifest
from valuebet.net.http import MIN_INTERVAL_S, RobotsDisallowedError

T0 = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)

HEADER = "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,PSH,PSD,PSA,PSCH,PSCD,PSCA\n"


def _csv(league: str, extra: str = "") -> bytes:
    row = f"{league},17/08/2024,15:00,Arsenal,Chelsea,2,1,H,1.9,3.6,4.2,1.95,3.5,4.1\n"
    return (HEADER + row + extra).encode("latin-1")


class Server:
    """Fałszywy football-data: CSV dla każdej pary, chyba że ustawiono inaczej."""

    def __init__(self) -> None:
        self.csv_requests: list[str] = []
        self.overrides: dict[str, Callable[[], httpx.Response]] = {}
        self.robots = "User-agent: *\nDisallow:\n"

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/robots.txt":
            return httpx.Response(200, text=self.robots)
        self.csv_requests.append(path)
        if path in self.overrides:
            return self.overrides[path]()
        league = path.rsplit("/", 1)[-1].removesuffix(".csv")
        return httpx.Response(200, content=_csv(league))


def _store(tmp_path: Path) -> RawStore:
    return RawStore(
        root=tmp_path / "raw",
        manifest=tmp_path / "manifest" / "raw_sha256.jsonl",
        artifacts_manifest=tmp_path / "manifest" / "artifacts_sha256.jsonl",
    )


def _clock_now(clock: FakeClock) -> Callable[[], datetime]:
    start = clock()
    return lambda: T0 + timedelta(seconds=clock() - start)


FILES = (
    MainLeagueFile(league="E0", season="2324"),
    MainLeagueFile(league="E0", season="2425"),
    MainLeagueFile(league="SC1", season="2425"),
)


def _run(
    tmp_path: Path, server: Server, files: tuple[MainLeagueFile, ...] = FILES
) -> tuple[list[IngestOutcome], FakeClock]:
    clock = FakeClock()
    with fake_http(server, clock) as http:
        out = ingest_files(
            files,
            client=http,
            store=_store(tmp_path),
            progress=tmp_path / "state" / "ingest.jsonl",
            now=_clock_now(clock),
        )
    return list(out), clock


def test_plan_lists_22_leagues_and_7_seasons() -> None:
    assert FIN_LEAGUES == (
        "E0", "E1", "E2", "E3", "EC",
        "SC0", "SC1", "SC2", "SC3",
        "D1", "D2", "I1", "I2", "SP1", "SP2", "F1", "F2",
        "N1", "B1", "P1", "T1", "G1",
    )  # fmt: skip
    assert FIN_SEASONS == ("1920", "2021", "2122", "2223", "2324", "2425", "2526")
    files = fin_files()
    assert len(files) == 154
    assert len(set(files)) == 154


def test_fetches_through_client_and_records_manifest_after_each_file(tmp_path: Path) -> None:
    server = Server()
    outcomes, clock = _run(tmp_path, server)
    store = _store(tmp_path)
    assert [o.status for o in outcomes] == ["fetched"] * 3
    assert store.verify() == []
    entries = read_manifest(store.manifest)
    assert len(entries) == 3
    # Bajty w raw dokładnie te z odpowiedzi (bez dekodowania i ponownego kodowania).
    for outcome, file in zip(outcomes, FILES, strict=True):
        assert outcome.path.read_bytes() == _csv(file.league)
    # Jeden host, trzy pliki + robots.txt → co najmniej trzy odstępy po 10 s.
    assert clock.slept >= 3 * MIN_INTERVAL_S
    progress = (tmp_path / "state" / "ingest.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["status"] for line in progress] == ["fetched"] * 3


def test_rerun_skips_verified_files_without_network(tmp_path: Path) -> None:
    _run(tmp_path, Server())
    again = Server()
    outcomes, _ = _run(tmp_path, again)
    assert again.csv_requests == []
    assert [o.status for o in outcomes] == ["verified"] * 3
    assert len(read_manifest(_store(tmp_path).manifest)) == 3


def test_resume_after_failure_fetches_only_the_rest(tmp_path: Path) -> None:
    broken = Server()
    broken.overrides["/mmz4281/2425/SC1.csv"] = lambda: httpx.Response(503)
    with pytest.raises(RuntimeError, match="HTTP 503"):
        _run(tmp_path, broken)
    # Dwa pierwsze pliki już są w raw z manifestem — mimo przerwania.
    assert len(read_manifest(_store(tmp_path).manifest)) == 2
    resumed = Server()
    outcomes, _ = _run(tmp_path, resumed)
    assert resumed.csv_requests == ["/mmz4281/2425/SC1.csv"]
    assert [o.status for o in outcomes] == ["verified", "verified", "fetched"]
    assert _store(tmp_path).verify() == []


def test_tampered_raw_file_is_a_loud_error_and_is_not_refetched(tmp_path: Path) -> None:
    outcomes, _ = _run(tmp_path, Server())
    victim = outcomes[1].path
    victim.write_bytes(b"Div,zmienione\n")
    again = Server()
    with pytest.raises(RawIntegrityError, match="hash"):
        _run(tmp_path, again)
    assert victim.read_bytes() == b"Div,zmienione\n"
    assert "/mmz4281/2425/E0.csv" not in again.csv_requests


def test_orphan_without_manifest_entry_is_a_loud_error(tmp_path: Path) -> None:
    store = _store(tmp_path)
    orphan = store.root / RAW_SUBDIR / "E0-2324.20261008T110000000000Z.deadbeef.csv"
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(_csv("E0"))
    with pytest.raises(RawIntegrityError, match="bez wpisu"):
        _run(tmp_path, Server())


def test_missing_file_is_recorded_and_nothing_is_written(tmp_path: Path) -> None:
    server = Server()
    server.overrides["/mmz4281/2425/SC1.csv"] = lambda: httpx.Response(404)
    outcomes, _ = _run(tmp_path, server)
    assert [o.status for o in outcomes] == ["fetched", "fetched", "missing"]
    assert len(read_manifest(_store(tmp_path).manifest)) == 2
    last = (tmp_path / "state" / "ingest.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    assert json.loads(last) | {"at": None} == {
        "at": None,
        "league": "SC1",
        "season": "2425",
        "url": "https://www.football-data.co.uk/mmz4281/2425/SC1.csv",
        "status": "missing",
        "http_status": 404,
        "path": None,
        "sha256": None,
        "bytes": None,
    }


def test_html_instead_of_csv_is_not_written(tmp_path: Path) -> None:
    server = Server()
    server.overrides["/mmz4281/2425/SC1.csv"] = lambda: httpx.Response(
        200, text="<!DOCTYPE html><html><body>Not found</body></html>"
    )
    with pytest.raises(RuntimeError, match="nie wygląda na CSV"):
        _run(tmp_path, server)
    assert len(read_manifest(_store(tmp_path).manifest)) == 2


def test_robots_disallow_stops_before_any_file(tmp_path: Path) -> None:
    server = Server()
    server.robots = "User-agent: *\nDisallow: /mmz4281/\n"
    with pytest.raises(RobotsDisallowedError):
        _run(tmp_path, server)
    assert server.csv_requests == []
    assert read_manifest(_store(tmp_path).manifest) == []


def test_ingest_requires_now_keyword(tmp_path: Path) -> None:
    """Reguła 30: zegar podaje punkt wejścia — bez ``now`` nie ma przebiegu."""
    kwargs: dict[str, object] = {"store": _store(tmp_path), "progress": tmp_path / "p.jsonl"}
    with fake_http(Server()) as http, pytest.raises(TypeError, match="now"):
        ingest_files(FILES, client=http, **kwargs)


def test_column_report_measures_presence_and_coverage() -> None:
    header = (
        "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,"
        "PSH,PSD,PSA,PSCH,PSCD,PSCA,B365H,B365D,B365A,B365>2.5,B365<2.5\n"
    )
    rows = (
        "E1,10/08/2024,15:00,A,B,1,0,2.0,3.4,3.9,2.1,3.3,3.8,1.9,3.3,4.0,1.8,2.0\n"
        "E1,10/08/2024,,C,D,0,0,2.2,3.2,3.5,,,,1.9,3.3,4.0,1.0,2.0\n"
    )
    report = column_report(
        (header + rows).encode("latin-1"), file=MainLeagueFile(league="E1", season="2425")
    )
    assert report["n_rows"] == 2
    groups = report["groups"]
    assert groups["PS_pre"] == 1.0
    assert groups["PS_close"] == 0.5
    assert groups["B365_pre"] == 1.0
    assert groups["B365_close"] is None  # brak kolumn w nagłówku
    # Kurs 1.0 to nie kurs — wiersz nie liczy się do pokrycia.
    assert groups["B365_ou_pre"] == 0.5
    assert report["time_coverage"] == 0.5


NOTES = b"Notes for Football Data\nBetting odds for weekend games are collected Friday afternoons\n"


def test_notes_go_to_raw_once_and_are_verified_on_rerun(tmp_path: Path) -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        requests.append(request.url.path)
        return httpx.Response(200, content=NOTES)

    for expected in ("fetched", "verified"):
        clock = FakeClock()
        with fake_http(handler, clock) as http:
            status, path, _ = ingest_notes(
                client=http,
                store=_store(tmp_path),
                progress=tmp_path / "p.jsonl",
                now=_clock_now(clock),
            )
        assert status == expected
        assert path.read_bytes() == NOTES
    assert requests == ["/notes.txt"]
    assert _store(tmp_path).verify() == []


def test_notes_without_the_collection_rule_are_rejected(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>inna strona</html>")

    with fake_http(handler) as http, pytest.raises(RuntimeError, match="momencie"):
        ingest_notes(
            client=http, store=_store(tmp_path), progress=tmp_path / "p.jsonl", now=lambda: T0
        )
    assert read_manifest(_store(tmp_path).manifest) == []
