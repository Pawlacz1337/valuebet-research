"""Magazyn raw z manifestem i ``scripts/verify_raw.py`` (reguła 12, FSA #0 F-12)."""

from __future__ import annotations

import importlib.util
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

import pandas as pd
import pytest

from valuebet.ingest import raw_store
from valuebet.ingest.raw_store import (
    RawStore,
    manifest_anchor,
    parquet_bytes,
    read_manifest,
)

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[1]


def _verify_raw() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "verify_raw", ROOT / "scripts" / "verify_raw.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def store(tmp_path: Path) -> RawStore:
    return RawStore(
        root=tmp_path / "raw",
        manifest=tmp_path / "manifest" / "raw.jsonl",
        artifacts_manifest=tmp_path / "manifest" / "artifacts.jsonl",
    )


def test_manifest_paths_are_relative_with_slashes(store: RawStore) -> None:
    store.write_raw("a/b", "x", ".json", b"{}", now=NOW)
    (entry,) = read_manifest(store.manifest)
    assert entry.path.startswith("a/b/x.")
    assert "\\" not in entry.path
    assert entry.bytes == 2
    assert entry.recorded_by == "write_raw"


@pytest.mark.parametrize(
    ("subdir", "stem", "suffix"),
    [("../poza", "x", ".csv"), ("a", "a/b", ".csv"), ("a", "x", "csv"), ("a", "", ".csv")],
)
def test_invalid_names_are_rejected(
    store: RawStore, subdir: str, stem: str, suffix: str
) -> None:
    with pytest.raises(ValueError):
        store.write_raw(subdir, stem, suffix, b"1", now=NOW)


def test_naive_now_is_rejected(store: RawStore) -> None:
    with pytest.raises(ValueError, match="timezone"):
        store.write_raw("a", "x", ".csv", b"1", now=NOW.replace(tzinfo=None))


def test_incoming_is_skipped_by_verify(store: RawStore) -> None:
    (store.root / ".incoming").mkdir(parents=True)
    (store.root / ".incoming" / "half.part").write_bytes(b"x")
    (store.root / ".gitkeep").write_bytes(b"")
    assert store.verify() == []
    assert store.files() == []


def test_duplicate_manifest_entries_are_reported(store: RawStore) -> None:
    store.write_raw("a", "x", ".csv", b"1", now=NOW)
    line = store.manifest.read_text(encoding="utf-8")
    store.manifest.write_text(line + line, encoding="utf-8")
    assert any("dwa wpisy" in p for p in store.verify())


def test_manifest_without_field_is_an_error(store: RawStore) -> None:
    store.manifest.parent.mkdir(parents=True)
    store.manifest.write_text(json.dumps({"path": "x"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="brak pola"):
        read_manifest(store.manifest)


def test_anchor_is_a_prefix_hash(store: RawStore) -> None:
    assert manifest_anchor(store.manifest)[0] == 0
    store.write_raw("a", "x", ".csv", b"1", now=NOW)
    n1, h1 = manifest_anchor(store.manifest)
    store.write_raw("a", "y", ".csv", b"2", now=NOW)
    n2, _ = manifest_anchor(store.manifest)
    assert (n1, n2) == (1, 2)
    first_line = store.manifest.read_bytes().splitlines(keepends=True)[0]
    import hashlib

    assert h1 == hashlib.sha256(first_line).hexdigest()


def test_adopt_refuses_known_and_missing(store: RawStore) -> None:
    path = store.write_raw("a", "x", ".csv", b"1", now=NOW)
    with pytest.raises(ValueError, match="ma już wpis"):
        store.adopt(path, now=NOW, recorded_by="adopted-x")
    with pytest.raises(FileNotFoundError):
        store.adopt(Path("a/nie_ma.csv"), now=NOW, recorded_by="adopted-x")


def test_artifacts_verified_by_latest_entry(
    store: RawStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    artifact = Path("reports") / "dev_x.parquet"
    artifact.parent.mkdir()
    artifact.write_bytes(parquet_bytes(pd.DataFrame({"a": [1, 2]})))
    store.record_artifacts([artifact], now=NOW, recorded_by="artifact-test")
    assert store.verify_artifacts() == []
    artifact.write_bytes(b"inne")
    assert any("niezgodny" in p for p in store.verify_artifacts())
    artifact.unlink()
    assert any("bez pliku" in p for p in store.verify_artifacts())


def test_link_failure_falls_back_without_overwrite(
    store: RawStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_links(src: object, dst: object) -> None:
        raise OSError("system plików bez dowiązań")

    monkeypatch.setattr(os, "link", no_links)
    path = store.write_raw("a", "x", ".csv", b"1", now=NOW)
    assert path.read_bytes() == b"1"
    with pytest.raises(FileExistsError):
        store.write_raw("a", "x", ".csv", b"1", now=NOW)
    assert not any((store.root / raw_store.INCOMING).iterdir())


def test_verify_raw_cli_codes(store: RawStore, tmp_path: Path) -> None:
    module = _verify_raw()
    assert module.main([], store=store) == 0
    path = store.write_raw("a", "x", ".csv", b"1", now=NOW)
    assert module.main([], store=store) == 0
    path.write_bytes(b"2")
    assert module.main([], store=store) == 1


def test_baseline_once_and_adoption(store: RawStore) -> None:
    module = _verify_raw()
    old = store.root / "football_data" / "POL-20260921T133212Z-27bb0df3.parquet"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"stary plik sprzed manifestu")
    assert module.main([], store=store) == 1
    assert module.main(["--init-baseline"], store=store) == 0
    (entry,) = read_manifest(store.manifest)
    assert entry.recorded_by.startswith("baseline-")
    assert module.main(["--init-baseline"], store=store) == 1

    orphan = store.root / "x" / "sierota.json"
    orphan.parent.mkdir()
    orphan.write_bytes(b"{}")
    assert module.main([], store=store) == 1
    assert module.main(["--adopt-orphan", "x/sierota.json"], store=store) == 0
    assert read_manifest(store.manifest)[-1].recorded_by.startswith("adopted-")


def test_record_artifacts_cli(
    store: RawStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _verify_raw()
    monkeypatch.chdir(tmp_path)
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "dev_a.parquet").write_bytes(b"pq")
    assert module.main(["--record-artifacts"], store=store) == 0
    assert module.main(["--record-artifacts"], store=store) == 0
    assert len(read_manifest(store.artifacts_manifest)) == 1


def test_names_differ_by_microsecond(store: RawStore) -> None:
    a = store.write_raw("a", "E0-2425", ".csv", b"1", now=NOW)
    b = store.write_raw("a", "E0-2425", ".csv", b"1", now=NOW + timedelta(microseconds=1))
    assert a != b


def test_baseline_with_relative_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Domyślny magazyn ma ścieżki względne (``data/raw``) — baseline też musi działać."""
    monkeypatch.chdir(tmp_path)
    store = RawStore(
        root=Path("data/raw"),
        manifest=Path("data/manifest/raw.jsonl"),
        artifacts_manifest=Path("data/manifest/a.jsonl"),
    )
    old = Path("data/raw/football_data_main/E0-1920-20261001T155704Z.csv")
    old.parent.mkdir(parents=True)
    old.write_bytes(b"x")
    assert _verify_raw().main(["--init-baseline"], store=store) == 0
    assert [e.path for e in read_manifest(store.manifest)] == [
        "football_data_main/E0-1920-20261001T155704Z.csv"
    ]


def test_latest_understands_both_name_formats(store: RawStore) -> None:
    folder = store.root / "football_data_main"
    folder.mkdir(parents=True)
    old = folder / "E0-2425-20261001T155704Z.csv"
    old.write_bytes(b"stary")
    (folder / "E0-24250-20261001T155704Z.csv").write_bytes(b"inny stem")
    (folder / "E0-2425.bez-znacznika.csv").write_bytes(b"x")
    assert store.latest("football_data_main", "E0-2425", ".csv") == old
    new = store.write_raw("football_data_main", "E0-2425", ".csv", b"nowy", now=NOW)
    assert store.latest("football_data_main", "E0-2425", ".csv") == new
    assert store.latest("brak", "E0-2425", ".csv") is None
