"""Zapis atomowy i blokada pliku (``valuebet.fsutil``)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from valuebet import fsutil
from valuebet.fsutil import LockTimeoutError, file_lock, write_atomic


def test_write_atomic_replaces_whole_file(tmp_path: Path) -> None:
    target = tmp_path / "s" / "state.json"
    write_atomic(target, b"pierwszy")
    write_atomic(target, b"drugi")
    assert target.read_bytes() == b"drugi"
    assert [p.name for p in target.parent.iterdir()] == ["state.json"]


def test_write_atomic_retries_permission_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows: antywirus trzyma plik przez chwilę — ponowienie, nie awaria."""
    calls = {"n": 0}
    original = Path.replace

    def flaky(self: Path, target: Path) -> Path:
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError("zajęty")
        return original(self, target)

    monkeypatch.setattr(Path, "replace", flaky)
    monkeypatch.setattr(fsutil, "_REPLACE_PAUSE_S", 0.0)
    write_atomic(tmp_path / "a.json", b"x")
    assert (tmp_path / "a.json").read_bytes() == b"x"
    assert calls["n"] == 3


def test_write_atomic_gives_up_and_cleans_tmp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def always(self: Path, target: Path) -> Path:
        raise PermissionError("zajęty")

    monkeypatch.setattr(Path, "replace", always)
    monkeypatch.setattr(fsutil, "_REPLACE_PAUSE_S", 0.0)
    with pytest.raises(PermissionError):
        write_atomic(tmp_path / "a.json", b"x")
    assert list(tmp_path.iterdir()) == []


def test_lock_is_exclusive(tmp_path: Path) -> None:
    target = tmp_path / "manifest.jsonl"
    with (
        file_lock(target),
        pytest.raises(LockTimeoutError),
        file_lock(target, wait_s=0.1),
    ):
        pass
    assert not (tmp_path / "manifest.jsonl.lock").exists()


def test_stale_lock_is_taken_over(tmp_path: Path) -> None:
    target = tmp_path / "manifest.jsonl"
    lock = tmp_path / "manifest.jsonl.lock"
    lock.write_text("123", encoding="utf-8")
    old = time.time() - fsutil.LOCK_STALE_AFTER_S - 5
    os.utime(lock, (old, old))
    with file_lock(target, wait_s=0.1):
        assert lock.exists()
    assert not lock.exists()
