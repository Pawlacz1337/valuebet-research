"""FSA #0 F-14 — stan kolektora nie leży w ``data/raw/``.

Ścieżka niebezpieczna: kolektor zbudowany z domyślnymi ścieżkami nadpisuje
``state.json`` (``write_text`` = truncate) i dopisuje ``heartbeat.jsonl``
w drzewie, które reguła 12 deklaruje jako niemodyfikowalne.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from helpers import assert_from_checkout, build
from valuebet.ingest.odds_collector import OddsCollector

assert_from_checkout(__file__)


class _NoClient:
    """Klient, którego test nie woła — kolektor bez kredytów."""


def _under_raw(path: Path) -> bool:
    return "data/raw" in path.as_posix()


@pytest.fixture
def collector(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> OddsCollector:
    # Domyślne ścieżki są względne — w katalogu tymczasowym nie dotykamy repo.
    monkeypatch.chdir(tmp_path)
    return build(OddsCollector, client=_NoClient())


def test_default_state_file_is_not_under_raw(collector: OddsCollector) -> None:
    assert not _under_raw(collector.state_file), collector.state_file


def test_default_heartbeat_is_not_under_raw(collector: OddsCollector) -> None:
    assert not _under_raw(collector.heartbeat_file), collector.heartbeat_file


def test_saving_state_writes_nothing_under_raw(
    collector: OddsCollector, tmp_path: Path
) -> None:
    collector._save_state({"done": ["a"], "kickoffs": {}, "last_usage": None})
    collector._heartbeat({"at": "x"})
    raw = tmp_path / "data" / "raw"
    written = [p for p in raw.rglob("*") if p.is_file()] if raw.exists() else []
    assert written == []
