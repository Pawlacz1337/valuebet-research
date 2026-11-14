"""Etykieta commita w raporcie — fakt, nie deklaracja (FSA #0 F-24).

``reports/lockbox_3433f2c.json`` deklarował commit, w którego drzewie nie
było skryptu, który go wyprodukował — liczb nie dało się odtworzyć z
etykiety. :func:`frozen_commit` zwraca hash HEAD **tylko** wtedy, gdy kod,
konfiguracja i sam skrypt są zacommitowane; inaczej podnosi wyjątek.

Woła go każdy skrypt zapisujący ``reports/*_<commit>.*`` i dopisuje do
raportu pole ``generated_by`` (ścieżkę skryptu) — test proweniencji sprawdza,
że skrypt istnieje w drzewie zadeklarowanego commita.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Final

__all__ = ["FROZEN_PATHS", "DirtyTreeError", "frozen_commit", "generated_by"]

#: Co musi być zacommitowane, żeby liczba odpowiadała etykiecie.
FROZEN_PATHS: Final = (
    "src",
    "scripts",
    "config",
    "pyproject.toml",
    "uv.lock",
    "docs/promocje.md",
)


class DirtyTreeError(RuntimeError):
    """Drzewo robocze ma zmiany, które zmieniłyby liczby raportu."""


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


def frozen_commit(*, script: Path, root: Path) -> str:
    """Krótki hash HEAD, jeśli ``FROZEN_PATHS`` i ``script`` są czyste i śledzone."""
    rel_script = script.resolve().relative_to(root.resolve()).as_posix()
    paths = [p for p in FROZEN_PATHS if (root / p).exists()]
    dirty = _git(root, "status", "--porcelain", "--untracked-files=all", "--", *paths, rel_script)
    if dirty:
        raise DirtyTreeError(
            "niezacommitowane zmiany — etykieta commita nie opisywałaby liczb:\n" + dirty
        )
    if not _git(root, "ls-files", "--", rel_script):
        raise DirtyTreeError(f"{rel_script} nie jest śledzony przez gita")
    return _git(root, "rev-parse", "--short", "HEAD")


def generated_by(*, script: Path, root: Path) -> str:
    """Ścieżka skryptu względem repozytorium — wartość pola ``generated_by``."""
    return script.resolve().relative_to(root.resolve()).as_posix()
