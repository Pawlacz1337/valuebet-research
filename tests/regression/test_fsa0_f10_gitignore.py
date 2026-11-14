"""FSA #0 F-09/F-10 — artefakty i stan lokalny poza gitem.

Ścieżka niebezpieczna: plik stanu, dziennik zakładów albo manifest trafia
do repozytorium przy pierwszym ``git add`` katalogu, bo ``.gitignore`` go
nie wyklucza (2026-10-01: tak wypadł ``.env.example``, tylko w drugą stronę).
"""

from __future__ import annotations

import subprocess

import pytest

from helpers import assert_from_checkout

ROOT = assert_from_checkout(__file__)

#: Ścieżki, które MUSZĄ być ignorowane. Pliki nie muszą istnieć —
#: ``git check-ignore --no-index`` sprawdza reguły, nie dysk.
MUST_BE_IGNORED = (
    ".env",
    ".coverage",
    "htmlcov/index.html",
    "data/bets/bets.csv",
    "data/bets/archive/bets_pre_F02.csv",
    "data/state/odds_api/state.json",
    "data/state/throttle/example.org.json",
    "data/manifest/raw_sha256.jsonl",
    "config/bookmakers.local.yaml",
    "data/raw/x.csv",
)

#: Jedyny śledzony plik w ``data/`` poza ``.gitkeep``: słownik aliasów
#: drużyn (reguła 15). To ręcznie pisana konfiguracja, nie dane, a jego
#: ścieżkę podaje zamrożony ``COLLECTOR_PLAN.md`` (FSA0_NAPRAWY §8).
TRACKED_DATA_EXCEPTIONS = {"data/team_aliases.yaml"}


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )


@pytest.mark.parametrize("path", MUST_BE_IGNORED)
def test_local_state_is_ignored(path: str) -> None:
    result = _git("check-ignore", "--no-index", "-q", path)
    assert result.returncode == 0, f"{path} nie jest ignorowany przez .gitignore"


def test_env_listed_once() -> None:
    lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert lines.count(".env") == 1


def test_nothing_but_gitkeep_tracked_in_data() -> None:
    tracked = _git("ls-files", "data/").stdout.split()
    extra = [
        p
        for p in tracked
        if not p.endswith("/.gitkeep") and p not in TRACKED_DATA_EXCEPTIONS
    ]
    assert extra == []
