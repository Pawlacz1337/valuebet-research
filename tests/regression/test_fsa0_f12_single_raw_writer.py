"""FSA #0 F-12 — do ``data/raw`` pisze wyłącznie ``ingest/raw_store.py``.

Ścieżka niebezpieczna: nowy albo stary moduł zapisuje plik w raw
bezpośrednio (``open(..., "w")``, ``write_text``, ``to_parquet``…), z
pominięciem manifestu — i reguła 12 znów staje się niesprawdzalna.

Test statyczny: **każde** miejsce zapisu pliku w ``src/`` i ``scripts/`` musi
być w rejestrze ``WRITERS_OUTSIDE_RAW`` z uzasadnieniem, że cel leży poza
``data/raw``. Nowe miejsce zapisu czerwieni test, dopóki ktoś go nie obejrzy.
Wyjątek ma tylko ``raw_store.py``. Drugi test sprawdza dynamicznie, że
zapisy surowe kolektora lądują w manifeście.
"""

from __future__ import annotations

import ast

from helpers import assert_from_checkout

ROOT = assert_from_checkout(__file__)

WRITE_ATTRS = {"write_text", "write_bytes", "to_csv", "to_parquet", "to_json"}

#: ``plik::funkcja::wywołanie`` → dlaczego cel NIE leży w ``data/raw``.
WRITERS_OUTSIDE_RAW: dict[str, str] = {
    "src/valuebet/fsutil.py::write_atomic::tmp.open": "zapis atomowy stanu (data/state)",
    "src/valuebet/ingest/football_data.py::write_interim::result.matches.to_parquet": "data/interim",
    "src/valuebet/ingest/football_data.py::write_interim::result.closing_odds.to_parquet": "data/interim",
    "src/valuebet/ingest/odds_collector.py::_heartbeat::self.heartbeat_file.open": "data/state/odds_api",
    "src/valuebet/ingest/odds_collector.py::_usage_line::self.usage_file.open": "data/state/odds_api",
    "src/valuebet/ingest/odds_collector.py::_report_missed::self.missed_file.open": "data/state/odds_api",
    "src/valuebet/ingest/team_mapping.py::to_yaml::Path(path).write_text": "słownik aliasów",
    "src/valuebet/live/bets.py::_ensure_header::self.journal_path.open": "data/bets — dziennik",
    "src/valuebet/live/bets.py::_append::self.journal_path.open": "data/bets — dziennik",
    "src/valuebet/live/digest.py::send_digest::path.write_text": "reports/digest",
    "scripts/run_diagnostics.py::flush::self.path.write_text": "reports/diag_*.json",
    "scripts/run_diagnostics.py::main::dev.to_parquet": "reports/dev_*.parquet",
    "scripts/run_lockbox.py::flush::out.write_text": "reports/lockbox_*.json",
    "scripts/run_lockbox.py::main::out.write_text": "reports/lockbox_*.json",
    "scripts/run_m2.py::main::out_path.write_text": "reports/m2_*.json",
    "scripts/validate_instrument.py::main::out.write_text": "reports/instrument_validation*.json",
    "src/valuebet/ingest/football_data_main.py::_log_progress::progress.open": "data/state/ingest",
    "scripts/ingest_football_data.py::main::(out_dir / 'columns.json').write_text": (
        "reports/ingest/<commit>/columns.json"
    ),
    "scripts/ingest_football_data.py::write_markdown::out.write_text": (
        "reports/ingest/<commit>/COLUMNS.md"
    ),
    "scripts/engine_tests.py::main::(out / 'ENGINE_TESTS.json').write_text": (
        "reports/backtest_fin/<commit>/ENGINE_TESTS.json"
    ),
    "scripts/engine_tests.py::write_report::path.write_text": (
        "reports/backtest_fin/<commit>/ENGINE_TESTS.md"
    ),
    # FSA1-D03 (2026-11-13): raport trybu --only 4b-C (main_partial, od 737a111).
    "scripts/engine_tests.py::main_partial::(out / 'ENGINE_TESTS_4bC.json').write_text": (
        "reports/backtest_fin/<commit>/ENGINE_TESTS_4bC.json"
    ),
    "scripts/engine_tests.py::main_partial::(out / 'ENGINE_TESTS_4bC.md').write_text": (
        "reports/backtest_fin/<commit>/ENGINE_TESTS_4bC.md"
    ),
    "scripts/run_backtest_fin.py::execute::(folder / 'equity.csv').open": (
        "reports/backtest_fin/<commit>/strategie/<przebieg>/equity.csv"
    ),
    "scripts/run_backtest_fin.py::run_all::(out / 'RAPORT.json').write_text": (
        "reports/backtest_fin/<commit>/strategie/RAPORT.json"
    ),
    "scripts/run_backtest_fin.py::write_report::(out / 'RAPORT.md').write_text": (
        "reports/backtest_fin/<commit>/strategie/RAPORT.md"
    ),
}

EXEMPT_FILES = {"src/valuebet/ingest/raw_store.py"}


def _mode(call: ast.Call, *, is_builtin: bool) -> str | None:
    candidates = call.args[1:2] if is_builtin else call.args[:1]
    for arg in candidates:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    for keyword in call.keywords:
        if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
            return str(keyword.value.value)
    return None


def _write_sites() -> set[str]:
    sites: set[str] = set()
    for base in ("src", "scripts"):
        for file in sorted((ROOT / base).rglob("*.py")):
            rel = file.relative_to(ROOT).as_posix()
            if rel in EXEMPT_FILES:
                continue
            tree = ast.parse(file.read_text(encoding="utf-8"))
            for func in ast.walk(tree):
                if not isinstance(func, ast.FunctionDef | ast.AsyncFunctionDef):
                    continue
                for node in ast.walk(func):
                    if not isinstance(node, ast.Call):
                        continue
                    target = node.func
                    writes = False
                    if isinstance(target, ast.Attribute) and target.attr in WRITE_ATTRS:
                        writes = True
                    builtin = isinstance(target, ast.Name) and target.id == "open"
                    method = isinstance(target, ast.Attribute) and target.attr == "open"
                    if builtin or method:
                        mode = _mode(node, is_builtin=builtin)
                        writes = writes or bool(mode and set(mode) & set("wax+"))
                    if writes:
                        what = (
                            ast.unparse(node.args[0]) if builtin and node.args
                            else ast.unparse(target)
                        )
                        sites.add(f"{rel}::{func.name}::{what}")
    return sites


def test_every_write_site_is_registered_outside_raw() -> None:
    unregistered = sorted(_write_sites() - set(WRITERS_OUTSIDE_RAW))
    assert unregistered == [], (
        "zapis pliku poza rejestrem — jeśli cel jest w data/raw, użyj "
        f"raw_store.RawStore.write_raw: {unregistered}"
    )


def test_registry_has_no_stale_entries() -> None:
    stale = sorted(set(WRITERS_OUTSIDE_RAW) - _write_sites())
    assert stale == [], f"wpisy rejestru bez miejsca zapisu: {stale}"
