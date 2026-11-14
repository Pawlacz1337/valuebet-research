"""FSA #0 F-24 — etykieta commita w raporcie musi dać się odtworzyć.

Ścieżki niebezpieczne:
- raport ``reports/*_<hash>.json`` deklaruje commit, w którego drzewie nie ma
  skryptu, który go wyprodukował (``lockbox_3433f2c.json``: ``run_lockbox.py``
  dodany dopiero w ``4b98818``);
- skrypt zapisujący raport z etykietą przy brudnym drzewie (zmiany w
  ``src/``, ``scripts/``, ``config/``, ``pyproject.toml``, ``uv.lock``,
  ``docs/promocje.md``) — liczby nie odpowiadają etykiecie.

``ImportError`` na starym kodzie jest tu dopuszczalnym czerwonym: znaleziskiem
jest brak mechanizmu (FSA0_NAPRAWY §1 pkt 2).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from helpers import assert_from_checkout
from valuebet.provenance import DirtyTreeError, frozen_commit

ROOT = assert_from_checkout(__file__)

#: Raporty sprzed ``frozen_commit`` — etykieta nieodtwarzalna; fakty w
#: pliku PROVENANCE obok. Lista nie może rosnąć.
#: Wyjątek: ``instrument_validation_aba1199.json`` — commit źródłowy istnieje
#: tylko w repo prywatnym; repo publiczne ma spłaszczoną historię.
LEGACY = {
    "reports/lockbox_3433f2c.json": "reports/lockbox_3433f2c.PROVENANCE.md",
    "reports/diag_313591a.json": "reports/diag_313591a.PROVENANCE.md",
    "reports/m2_313591a.json": "reports/m2_313591a.PROVENANCE.md",
    "reports/instrument_validation_aba1199.json": (
        "reports/instrument_validation_aba1199.PROVENANCE.md"
    ),
}
LABELLED = re.compile(r"^reports/(?:.+/)?[^/]+_([0-9a-f]{7,40})\.json$")


def _git(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)


def _labelled_reports() -> list[tuple[str, str]]:
    out = []
    for path in _git("ls-files", "reports").stdout.split():
        match = LABELLED.match(path)
        if match:
            out.append((path, match.group(1)))
    return out


def test_every_labelled_report_is_reproducible_or_documented() -> None:
    problems = []
    for path, commit in _labelled_reports():
        if path in LEGACY:
            if not (ROOT / LEGACY[path]).is_file():
                problems.append(f"{path}: brak {LEGACY[path]}")
            continue
        body = json.loads((ROOT / path).read_text(encoding="utf-8"))
        script = body.get("generated_by")
        if not script:
            problems.append(f"{path}: brak pola generated_by")
        elif _git("cat-file", "-e", f"{commit}:{script}").returncode != 0:
            problems.append(f"{path}: {script} nie istnieje w drzewie {commit}")
    assert problems == []


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "run_x.py").write_text("print(1)\n", encoding="utf-8")
    (repo / "src" / "m.py").write_text("x = 1\n", encoding="utf-8")
    for args in (
        ["init", "-q"],
        ["-c", "user.email=t@t", "-c", "user.name=t", "add", "src", "scripts"],
        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
    ):
        assert _git(*args, cwd=repo).returncode == 0
    return repo


def test_frozen_commit_refuses_dirty_tree(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    script = repo / "scripts" / "run_x.py"
    assert len(frozen_commit(script=script, root=repo)) >= 7
    (repo / "src" / "m.py").write_text("x = 2\n", encoding="utf-8")
    with pytest.raises(DirtyTreeError):
        frozen_commit(script=script, root=repo)


def test_frozen_commit_refuses_untracked_script(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    new = repo / "scripts" / "run_new.py"
    new.write_text("print(2)\n", encoding="utf-8")
    with pytest.raises(DirtyTreeError):
        frozen_commit(script=new, root=repo)
