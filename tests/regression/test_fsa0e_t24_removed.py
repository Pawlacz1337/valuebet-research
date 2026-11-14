"""Decyzja Pawła 2026-10-04 (pkt 1) — kotwica T-24h Ekstraklasy usunięta.

T-24h dubluje poranne migawki decyzyjne (TOR_S_PLAN §2), a z nią plan
kredytów przekraczał 450 (F0e-01: ~456/mies.). Oś ``bet_lead_time`` to
odtąd migawki decyzyjne (ok. 4-40 h do gwizdka) kontra zamknięcie, z CLV w
przedziałach czasu do gwizdka (COLLECTOR_PLAN §3.3).

Ścieżka niebezpieczna: płatne wywołanie T-24h nadal należne i nadal w
planie. Cel decyzji: plan z symulacji prawdziwego ``due_calls`` ≤ 420.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

from helpers import assert_from_checkout, build
from valuebet.ingest.odds_collector import LEAGUES, due_calls

ROOT = assert_from_checkout(__file__)

#: Cel z decyzji Pawła 2026-10-04 — nie budżet (450) ani próg trybu oszczędnego.
TARGET = 420
KICKOFF = datetime(2026, 10, 24, 17, 0, tzinfo=UTC)


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_no_league_has_a_t24_anchor() -> None:
    names = {(lg.label, a.name) for lg in LEAGUES for a in lg.anchors}
    assert not [n for n in names if n[1] == "t24"], names


def test_nothing_paid_is_due_a_day_before_kickoff() -> None:
    """Godzinę wokół KO-24 h (poza oknem decyzji) nic płatnego nie jest należne."""
    kickoffs = {lg.sport_key: [KICKOFF] for lg in LEAGUES}
    for minutes in range(-30, 50, 5):
        now = KICKOFF - timedelta(hours=24) + timedelta(minutes=minutes)
        due = due_calls(now=now, kickoffs=kickoffs, done=set())
        assert due == [], (now, [(c.league.label, c.anchor.name) for c in due])


def test_budget_plan_from_simulation_meets_target() -> None:
    """Terminarz kolejki z testu F0e-01 (kalkulator = prawdziwy kolektor)."""
    sim = _load(
        "fsa0e_01_terminarz", ROOT / "tests" / "regression" / "test_fsa0e_01_budget_simulation.py"
    )
    budget = _load("odds_budget_t24", ROOT / "scripts" / "odds_budget.py")
    result = build(budget.plan, kickoffs=sim.TERMINARZ, start=sim.START, end=sim.END)
    kinds = {anchor for (_, anchor) in result.by_kind}
    assert "t24" not in kinds, result.by_kind
    assert result.total <= TARGET, (
        f"plan {result.total:.1f}/mies. > {TARGET}: "
        + ", ".join(f"{lg}/{a} {v:.1f}" for (lg, a), v in result.by_kind.items())
    )
