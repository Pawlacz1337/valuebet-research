"""``valuebet.provenance`` — ścieżka ``generated_by`` i drzewo repozytorium."""

from __future__ import annotations

from pathlib import Path

from valuebet.provenance import frozen_commit, generated_by

ROOT = Path(__file__).resolve().parents[1]


def test_generated_by_is_repo_relative_posix() -> None:
    assert generated_by(script=ROOT / "scripts" / "run_lockbox.py", root=ROOT) == (
        "scripts/run_lockbox.py"
    )


def test_frozen_commit_returns_head_hash_when_clean_or_refuses() -> None:
    """W repo projektu: albo hash HEAD, albo odmowa — nigdy etykieta brudnego drzewa."""
    from valuebet.provenance import DirtyTreeError

    try:
        commit = frozen_commit(script=ROOT / "scripts" / "run_lockbox.py", root=ROOT)
    except DirtyTreeError:
        return
    assert len(commit) >= 7


def test_ignored_script_is_refused(tmp_path: Path) -> None:
    import subprocess

    import pytest

    from valuebet.provenance import DirtyTreeError

    repo = tmp_path / "r"
    (repo / "scripts").mkdir(parents=True)
    (repo / ".gitignore").write_text("scripts/ukryty.py\n", encoding="utf-8")
    (repo / "scripts" / "ukryty.py").write_text("print(1)\n", encoding="utf-8")
    for args in (
        ["init", "-q"],
        ["add", ".gitignore"],
        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
    ):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    with pytest.raises(DirtyTreeError, match="nie jest śledzony"):
        frozen_commit(script=repo / "scripts" / "ukryty.py", root=repo)
