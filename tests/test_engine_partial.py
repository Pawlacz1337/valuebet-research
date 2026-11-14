"""Tryb częściowy runnera bramki: ``--only 4b-C`` (decyzja Architekta 2026-10-15).

Rerun SAMEGO 4b-C po naprawie remisu zaokrąglenia — dopuszczalny tylko, gdy src/ i
config/ są bit-w-bit identyczne z bramką odniesienia 27ae469 (strażnik odmawia przy
niepustym ``git diff 27ae469..HEAD -- src config``). Raport do OSOBNYCH plików
``ENGINE_TESTS_4bC.*`` z nagłówkiem „CZĘŚCIOWY — NIE BRAMKA”.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from test_engine_gate import ROOT, _script


def _patch_main(script: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, diff: str) -> list[str]:
    """``main`` bez gita, danych i puli; zwraca listę wywołań runnera częściowego."""
    calls: list[str] = []

    class _Pool:
        def __init__(self, *a: Any, **k: Any) -> None: ...
        def __enter__(self) -> _Pool:
            return self
        def __exit__(self, *a: Any) -> None: ...

    def fake_partial(*_a: Any, **_k: Any) -> Any:
        calls.append("run_partial")
        store = script.PartialStore(tmp_path / "p", "testhash", 1, False, "w")
        return [script.Check("4b-C x", True, "ok")], store, script.Progress(total=0)

    monkeypatch.setattr(script, "ROOT", tmp_path)
    monkeypatch.setattr(script, "RawStore", lambda **_k: None)
    monkeypatch.setattr(script, "preflight_start", lambda: None)
    monkeypatch.setattr(script, "fixture_truth", lambda _store: script.synthetic_truth(weeks=1, per_week=1, seed=1))
    monkeypatch.setattr(script, "frozen_commit", lambda **_k: "testhash")
    monkeypatch.setattr(script, "generated_by", lambda **_k: "test")
    monkeypatch.setattr(script, "preflight", lambda _phase: None)
    monkeypatch.setattr(script, "_lower_priority", lambda: None)
    monkeypatch.setattr(script.multiprocessing, "Pool", _Pool)
    monkeypatch.setattr(script, "src_config_diff", lambda *_a, **_k: diff)
    monkeypatch.setattr(script, "run_partial", fake_partial)
    monkeypatch.setattr(script, "gate", lambda *_a, **_k: pytest.fail("--only nie może uruchamiać pełnej bramki"))
    monkeypatch.setattr(script, "spy_check", lambda *_a, **_k: pytest.fail("--only nie uruchamia szpiegów"))
    return calls


def test_guard_refuses_when_src_or_config_changed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ścieżka niebezpieczna: niepusty diff src/config → kod ≠ 0, nic nie policzone ani zapisane."""
    script = _script()
    calls = _patch_main(script, tmp_path, monkeypatch, diff="diff --git a/src/valuebet/pricing/kelly.py b/...\n")
    assert script.main(["--only", "4b-C", "--seeds", "1", "--workers", "1"]) != 0
    assert calls == []
    assert not (tmp_path / "reports").exists()


def test_guard_function_refuses_non_empty_diff() -> None:
    script = _script()
    with pytest.raises(script.PartialRunRefusedError, match="27ae469"):
        script.require_unchanged_src("diff --git a/config/strategy.yaml b/config/strategy.yaml\n")
    script.require_unchanged_src("")


def test_only_accepts_just_4b_c(capsys: pytest.CaptureFixture[str]) -> None:
    script = _script()
    with pytest.raises(SystemExit):
        script.main(["--only", "4a-C"])
    assert "invalid choice" in capsys.readouterr().err


def test_only_refuses_resume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = _script()
    calls = _patch_main(script, tmp_path, monkeypatch, diff="")
    with pytest.raises(SystemExit):
        script.main(["--only", "4b-C", "--resume"])
    assert calls == []


def test_partial_report_is_separate_and_labelled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = _script()
    calls = _patch_main(script, tmp_path, monkeypatch, diff="")
    assert script.main(["--only", "4b-C", "--seeds", "1", "--workers", "1"]) == 0
    assert calls == ["run_partial"]
    out = tmp_path / "reports" / "backtest_fin" / "testhash"
    assert not (out / "ENGINE_TESTS.md").exists() and not (out / "ENGINE_TESTS.json").exists()
    md = (out / "ENGINE_TESTS_4bC.md").read_text(encoding="utf-8")
    assert "CZĘŚCIOWY — NIE BRAMKA; uzupełnia bramkę 27ae469 (24/25 OK, 4b-C czerwone: remis zaokrąglenia)" in md
    assert "testhash" in md and "27ae469" in md
    payload = json.loads((out / "ENGINE_TESTS_4bC.json").read_text(encoding="utf-8"))
    assert payload["partial"] is True and payload["is_gate"] is False
    assert payload["commit"] == "testhash" and payload["reference_commit"] == "27ae469"
    assert payload["src_config_diff"] == ""
    assert [c["name"] for c in payload["checks"]] == ["4b-C x"]


def _many_calls(func: ast.FunctionDef) -> dict[str, str]:
    """``many("<id>", ...)`` w funkcji → id: tekst argumentów (bez id)."""
    out: dict[str, str] = {}
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "many":
            first = node.args[0]
            assert isinstance(first, ast.Constant)
            rest = [ast.unparse(a) for a in node.args[1:]]
            rest += sorted(f"{k.arg}={ast.unparse(k.value)}" for k in node.keywords)
            out[str(first.value)] = ", ".join(rest)
    return out


def test_partial_runs_exactly_the_4b_c_runs_of_the_full_gate() -> None:
    """Przebiegi trybu częściowego = 4-base-C i 4b-C z ``gate_c`` (świat, parametry) — bez kopii,
    która mogłaby się rozjechać z bramką."""
    tree = ast.parse((ROOT / "scripts" / "engine_tests.py").read_text(encoding="utf-8"))
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    full = _many_calls(funcs["gate_c"])
    partial = _many_calls(funcs["gate_4bc_only"])
    assert set(partial) == {"4-base-C", "4b-C"}
    assert {k: full[k] for k in partial} == partial
