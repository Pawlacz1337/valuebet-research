"""FSA #0 F-12 + F-17 — manifest sum kontrolnych i jeden zapis do ``data/raw``.

Ścieżki niebezpieczne:
- bajt pliku w raw zmieniony po zapisie — dziś nic tego nie wykrywa, bo
  manifestu nie ma (reguła 12 niesprawdzalna);
- drugi zapis pod tę samą nazwę — musi być wyjątkiem, nie nadpisaniem;
- plik w raw bez wpisu i wpis bez pliku — oba to błąd weryfikacji.

``ImportError`` na starym kodzie jest tu dopuszczalnym czerwonym: znaleziskiem
jest **brak mechanizmu** (FSA0_NAPRAWY §1 pkt 2).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from helpers import assert_from_checkout

assert_from_checkout(__file__)

NOW = datetime(2026, 10, 2, 12, 0, 0, 123456, tzinfo=UTC)


@pytest.fixture
def store(tmp_path: Path) -> Any:
    from valuebet.ingest.raw_store import RawStore

    return RawStore(root=tmp_path / "raw", manifest=tmp_path / "m" / "raw.jsonl")


def test_changed_byte_is_detected(store: Any) -> None:
    path = store.write_raw("football_data_main", "E0-2425", ".csv", b"a,b\n1,2\n", now=NOW)
    assert store.verify() == []
    data = bytearray(path.read_bytes())
    data[0] ^= 0x01
    path.write_bytes(bytes(data))
    problems = store.verify()
    assert any("hash" in p for p in problems), problems


def test_second_write_under_same_name_raises(store: Any) -> None:
    store.write_raw("x", "same", ".bin", b"payload", now=NOW)
    with pytest.raises(FileExistsError):
        store.write_raw("x", "same", ".bin", b"payload", now=NOW)


def test_file_without_entry_is_an_error(store: Any) -> None:
    store.write_raw("x", "ok", ".bin", b"1", now=NOW)
    orphan = store.root / "x" / "orphan.bin"
    orphan.write_bytes(b"2")
    assert any("bez wpisu" in p for p in store.verify())


def test_entry_without_file_is_an_error(store: Any) -> None:
    path = store.write_raw("x", "gone", ".bin", b"1", now=NOW)
    path.unlink()
    assert any("bez pliku" in p for p in store.verify())


def test_name_is_generated_and_ntfs_safe(store: Any) -> None:
    path = store.write_raw("x", "E0-2425", ".csv", b"abc", now=NOW)
    assert ":" not in path.name
    assert path.name.startswith("E0-2425.20261002T120000123456Z.")
    assert path.suffix == ".csv"
    assert not any((store.root / ".incoming").iterdir())
