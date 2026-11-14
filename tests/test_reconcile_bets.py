"""``scripts/reconcile_bets.py`` — niezależne podwójne księgowanie (BACKTEST_FIN_PLAN §2, §4 pkt 5).

Skrypt nie importuje modułów wyceny: kapitał liczy wprost ze ``stake``,
``odds_taken``, ``tax_factor_applied`` i wyniku. Po każdym rozliczeniu musi
się zgadzać z symulatorem (tolerancja 1e-9).
"""

from __future__ import annotations

import ast
import importlib.util
from collections import Counter
from datetime import timedelta
from pathlib import Path
from types import ModuleType

import pytest

from helpers.fin_world import T0, WorldMatch, build_replay
from valuebet.backtest.financial import kelly_staker, run, threshold_selector
from valuebet.live.bets import BetJournal

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "reconcile_bets.py"


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("reconcile_bets_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_imports_no_pricing_or_valuebet_module() -> None:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not {m for m in imported if m.split(".")[0] == "valuebet"}
    assert len(SCRIPT.read_text(encoding="utf-8").splitlines()) <= 150


def _world() -> list[WorldMatch]:
    p = (0.5, 0.3, 0.2)
    soft = (1.05 / 0.5, 0.9 / 0.3, 1.04 / 0.2)
    out = []
    for i, goals in enumerate([(2, 0), (0, 1), (1, 1), (None, None), (3, 1), (0, 2)]):
        at = T0 + timedelta(days=3 * i)
        out.append(
            WorldMatch(f"m{i}", p, soft, goals[0], goals[1], observed_at=at,
                       kickoff=at + timedelta(hours=20))
        )  # fmt: skip
    return out


def test_reconciled_cash_matches_simulator_after_every_settlement(tmp_path: Path) -> None:
    journal_path = tmp_path / "bets.csv"
    result = run(
        build_replay(_world()),
        selector=threshold_selector(
            books={"1x2": ("bet365",)}, tax_factor=1.0, edge_threshold=0.02,
            require_complete=True, excluded=Counter(), rejected=Counter(), margin_check=False,
        ),
        staker=kelly_staker,
        selection_tax_factor=1.0,
        settlement_tax_factor=1.0,
        journal_path=journal_path,
        run_id="r",
        start_capital=10_000.0,
        ingested_at=T0,
        min_stake_pln=0.50,
    )
    ledger = _script().reconcile(journal_path, start_capital=10_000.0)
    simulated = [(p.event, p.cash) for p in result.equity if p.event != "decision"]
    assert len(ledger) == len(simulated) > 0
    for (coupon_id, _at, cents), (event, sim_cash) in zip(ledger, simulated, strict=True):
        assert coupon_id == event
        assert cents == round(sim_cash * 100)  # dokładnie, w groszach
    assert ledger[-1][2] == round(result.cash * 100)


def test_winnings_tax_and_void_by_hand(tmp_path: Path) -> None:
    """Wypłata > 2280 zł → x0.90 (T13); zwrot = stawka · tax; paper nie rusza kasy."""
    from test_journal_cache import T0 as JOURNAL_T0
    from test_journal_cache import _record

    path = tmp_path / "bets.csv"
    journal = BetJournal(journal_path=path)
    journal.add(_record(1, mode="real", stake=1000.0, odds_taken=3.0))
    journal.add(_record(2, mode="real", stake=100.0, odds_taken=2.0))
    journal.add(_record(3, mode="paper", stake=100.0, odds_taken=2.0))
    settle = JOURNAL_T0 + timedelta(hours=3)
    journal.settle("b1", "won", now=settle)
    journal.settle("b2", "void", now=settle)
    journal.settle("b3", "won", now=settle)
    ledger = _script().reconcile(path, start_capital=5000.0)
    # 5000 - 1000 - 100 (paper nic) → c1: +3000·0.9 = 2700 → c2: +100 → c3 (paper): bez zmian
    assert [(cid, cents) for cid, _, cents in ledger] == [
        ("c1", 660_000),
        ("c2", 670_000),
        ("c3", 670_000),
    ]


# -- Poprawka 5 (bramka e66260a: |symulator - reconcile| = 1.06e-9 przy tolerancji 1e-9) --


def _engine() -> ModuleType:
    import sys

    name = "engine_tests_for_reconcile"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "engine_tests.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_float_noise_never_changes_the_grosz_count(tmp_path: Path, seed: int) -> None:
    """Własność: 20 000 przepływów w skali 1e5 zł — szum zmiennoprzecinkowy symulatora
    (gotówka przyrostowo w kolejności zdarzeń) nie może dać różnicy w groszach."""
    import numpy as np

    from test_journal_cache import T0 as JOURNAL_T0
    from test_journal_cache import _record

    rng = np.random.default_rng(seed)
    path = tmp_path / "bets.csv"
    journal = BetJournal(journal_path=path)
    n = 10_000
    stakes = (rng.integers(1, 200_000, size=n) / 100).tolist()
    odds = (rng.integers(120, 800, size=n) / 100).tolist()
    for i in range(n):
        journal.add(_record(i, mode="real", stake=stakes[i], odds_taken=odds[i]))
    results = rng.choice(["won", "lost", "void"], size=n, p=[0.45, 0.5, 0.05]).tolist()
    for i in range(n):
        journal.settle(f"b{i}", results[i], now=JOURNAL_T0 + timedelta(hours=3, seconds=i))
    start = 100_000.0
    cash = start
    for s in stakes:
        cash -= s
    sim: list[float] = []
    for row in BetJournal(journal_path=path).read():
        if row.is_settlement:
            cash += row.payout or 0.0
            sim.append(cash)
    ledger = _script().reconcile(path, start_capital=start)
    assert all(isinstance(cents, int) for _, _, cents in ledger)
    assert _engine().cash_mismatches(ledger, sim) == []


def test_one_grosz_error_is_detected() -> None:
    """Trucizna: błąd 1 grosza w jednym przepływie MUSI zostać wykryty."""
    from datetime import UTC, datetime

    at = datetime(2026, 10, 9, tzinfo=UTC)
    ledger = [("c1", at, 1_000_000), ("c2", at, 1_002_150)]
    assert _engine().cash_mismatches(ledger, [10_000.0, 10_021.5]) == []
    assert _engine().cash_mismatches(ledger, [10_000.0, 10_021.51]) != []


def test_flow_not_a_multiple_of_a_grosz_is_a_precondition_error() -> None:
    engine = _engine()
    engine.require_grosz(10.01, what="stawka")
    with pytest.raises(ValueError, match="wielokrotno"):
        engine.require_grosz(10.005, what="stawka")
