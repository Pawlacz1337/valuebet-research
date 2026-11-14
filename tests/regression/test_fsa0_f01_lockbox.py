"""FSA #0 F-01 + F-21 + W.8 — lockbox nie otwiera się po cichu.

Ścieżki niebezpieczne:
- etykieta sezonu w innym zapisie (``2025-26``, ``2025/2026``…), ``NaN``,
  etykieta nie do sparsowania — ``assert_no_lockbox`` przechodził bez błędu,
  bo porównywał literały tekstowe (F-01);
- skrypt woła producenta liczb toru M bez ``assert_no_lockbox``
  (``validate_instrument.py`` — deklaracja z ``eac437c`` nieprawdziwa, F-21;
  baseline'y bez bramki, W.8);
- ``run_lockbox.py`` uruchomiony drugi raz — nic nie liczyło obejrzeń (W.8).

Test ``run_lockbox.main()`` **nie może obejrzeć lockboxa** także na starym
kodzie: ładowanie danych i ewaluacja są podmienione na wartownika.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import logging
import math
from pathlib import Path
from types import ModuleType

import pandas as pd
import pytest

from helpers import assert_from_checkout
from valuebet.backtest.lockbox import assert_no_lockbox

ROOT = assert_from_checkout(__file__)

PRODUCERS = {"run_elo_baseline", "run_dixon_coles_baseline", "clustered_slope"}


class LockboxViewAttemptedError(AssertionError):
    """Test próbował obejrzeć lockbox — to jest właśnie błąd, którego szukamy."""


@pytest.mark.parametrize("label", ["2025-26", "2025/2026", "2025-2026", "2026-27"])
def test_other_spelling_of_lockbox_season_is_caught(label: str) -> None:
    frame = pd.DataFrame({"season": ["2023/24", label]})
    with pytest.raises(RuntimeError, match="lockbox"):
        assert_no_lockbox(frame, what="test")


@pytest.mark.parametrize("label", [math.nan, None, "25/26", "2025/27", "sezon"])
def test_unreadable_season_is_an_error(label: object) -> None:
    frame = pd.DataFrame({"season": ["2023/24", label]})
    with pytest.raises(ValueError):
        assert_no_lockbox(frame, what="test")


def test_frame_without_season_is_an_error() -> None:
    with pytest.raises(ValueError):
        assert_no_lockbox(pd.DataFrame({"x": [1]}), what="test")


def _load_script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_lockbox_refuses_second_view(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_lockbox = _load_script("run_lockbox")
    # Stary main() konfiguruje logi przed czymkolwiek — nie może to wyciec
    # do innych testów.
    dc_logger = logging.getLogger("valuebet.models.dixon_coles")
    monkeypatch.setattr(dc_logger, "level", dc_logger.level)
    monkeypatch.setattr(logging.root, "handlers", list(logging.root.handlers))

    def sentinel(*_: object, **__: object) -> None:
        raise LockboxViewAttemptedError("run_lockbox sięgnął po dane lockboxa")

    for name in ("run_elo_baseline", "run_dixon_coles_baseline"):
        monkeypatch.setattr(run_lockbox, name, sentinel)
    monkeypatch.setattr(run_lockbox.pd, "read_parquet", sentinel)
    # git nie jest „oglądaniem” — wyłączony, żeby test nie zależał od stanu drzewa.
    for name in ("_assert_frozen", "frozen_commit"):
        if hasattr(run_lockbox, name):
            monkeypatch.setattr(run_lockbox, name, lambda *a, **k: "abc1234")
    monkeypatch.setattr(run_lockbox, "_commit", lambda: "abc1234", raising=False)
    monkeypatch.chdir(tmp_path)
    registry = tmp_path / "reports" / "lockbox_views.jsonl"
    registry.parent.mkdir()
    registry.write_text(
        json.dumps({"date": "2026-10-01", "report": "reports/lockbox_3433f2c.json"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="obejrzany"):
        run_lockbox.main()


def _calls(tree: ast.AST) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            out.add(func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", ""))
    return out


def _entry_points() -> list[Path]:
    points = sorted((ROOT / "scripts").glob("*.py"))
    for path in sorted((ROOT / "src" / "valuebet").rglob("*.py")):
        if '__name__ == "__main__"' in path.read_text(encoding="utf-8"):
            points.append(path)
    return points


def test_every_tor_m_entry_point_guards_the_lockbox() -> None:
    unguarded = []
    for path in _entry_points():
        if path.name == "run_lockbox.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls = _calls(tree)
        if calls & PRODUCERS and "assert_no_lockbox" not in calls:
            unguarded.append(path.relative_to(ROOT).as_posix())
    assert unguarded == [], f"producenci liczb toru M bez assert_no_lockbox: {unguarded}"


TOR_M_FILES = (
    *sorted((ROOT / "scripts").glob("run_*.py")),
    ROOT / "scripts" / "validate_instrument.py",
    ROOT / "src" / "valuebet" / "backtest" / "elo_baseline.py",
    ROOT / "src" / "valuebet" / "backtest" / "dixon_coles_baseline.py",
    ROOT / "src" / "valuebet" / "backtest" / "market_benchmark.py",
)


@pytest.mark.parametrize("path", TOR_M_FILES, ids=lambda p: p.name)
def test_lockbox_labels_live_only_in_lockbox_module(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert "2025/26" not in text and "2026/27" not in text
