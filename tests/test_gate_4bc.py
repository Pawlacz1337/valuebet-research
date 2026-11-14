"""Kryterium 4b-C dla strategii zależnej od ścieżki i czystość planisty C (naprawa
4b-C, 2026-10-12; BACKTEST_FIN_PLAN §4).

Zmiana kryterium po czerwonym 4b-C na świecie syntetycznym bramki 2624fff (przed
jakimkolwiek wynikiem na prawdziwych danych) jest dopuszczalna tylko z testami
czułości: kryterium MUSI złapać przeciek (planista patrzący w wynik) i fałszywe
wyjaśnienie (przyczyna odrzucenia niezgodna z księgą).
"""

from __future__ import annotations

import ast
import inspect
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from test_engine_gate import _script

ROOT = Path(__file__).resolve().parents[1]
#: Jedyne nazwy, które planista może dostać (stan decyzji — bez wyników, rozliczeń, P&L).
PLANNER_ARGS = {"self", "t", "current", "candidates", "legs", "stake_at", "coupon"}
FORBIDDEN = ("result", "results", "settle", "profit", "pnl", "replay", "world", "goals")


# -- krok 5 (a): strukturalny ----------------------------------------------------


def test_planner_methods_cannot_receive_results() -> None:
    """Sygnatury begin/groups/price/placed (protokół, A, C) bez wyniku/rozliczenia/P&L."""
    from valuebet.backtest import financial, strategy_c

    for owner in (financial.Planner, financial.ConstantTaxPlanner, strategy_c.RegimePlanner):
        for name in ("begin", "groups", "price", "placed"):
            sig = inspect.signature(getattr(owner, name))
            assert set(sig.parameters) <= PLANNER_ARGS, (owner.__name__, name, sig)
            text = str(sig).lower()
            assert not any(word in text for word in ("matchresult", "replay")), (owner.__name__, name, sig)


def test_the_event_loop_passes_no_results_to_the_planner() -> None:
    """``simulate`` woła planistę wyłącznie stanem decyzji — w argumentach ani śladu wyników."""
    tree = ast.parse((ROOT / "src" / "valuebet" / "backtest" / "financial.py").read_text(encoding="utf-8"))
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name) and node.func.value.id == "planner"
    ]  # fmt: skip
    assert {c.func.attr for c in calls if isinstance(c.func, ast.Attribute)} == {"begin", "groups", "price", "placed"}
    for call in calls:
        assert {k.arg for k in call.keywords} <= PLANNER_ARGS
        names = {n.id for arg in [*call.args, *(k.value for k in call.keywords)] for n in ast.walk(arg)
                 if isinstance(n, ast.Name)}  # fmt: skip
        assert not any(word in name.lower() for name in names for word in FORBIDDEN), names


# -- krok 5 (b): behawioralny ----------------------------------------------------


def _snapshot_inputs(tmp_path: Path) -> dict[str, Any]:
    """Stan wejściowy z prawdziwego przebiegu C na małym świecie: historia kuponów do t,
    kandydaci migawek t (z OBU światów: wyniki oryginalne i spermutowane)."""
    from valuebet.backtest.financial import DecisionContext
    from valuebet.live.bets import BetJournal, coupons
    from valuebet.pricing.fair import fair_prices

    script = _script()
    truth = script.c120_truth(script.synthetic_truth(weeks=8, per_week=6, seed=5))
    script.run_seed(truth, strategy="C", seed=1, soft_factor=1.025, tax_factor=1.0, workdir=tmp_path)
    worlds = {perm: script.build_world(truth, seed=1, soft_factor=1.025, permute_results=perm) for perm in (False, True)}
    # historia: dziennik pełnego przebiegu bazowego (odtworzony jeszcze raz, z detail)
    path = tmp_path / "hist.csv"
    world = worlds[False]
    script.run_regime(world, selector=_selector(script), staker=script.kelly_staker,
                      regime_config=script.counterfactual_regime_config(
                          start=script.c_regime_start(world), share_basis="stakes", min_stake_pln=0.50),
                      edge_threshold=0.02, single_mode="production", journal_path=path, run_id="h",
                      start_capital=10_000.0, ingested_at=script.INGESTED, min_stake_pln=0.50)  # fmt: skip
    rows = BetJournal(journal_path=path).read()
    times = sorted({m.decision_at for m in world.matches})
    chosen = [times[2], times[len(times) // 2], times[-2]]
    out: dict[str, Any] = {"worlds": worlds, "snapshots": []}
    for t in chosen:
        cands = {}
        for perm, w in worlds.items():
            matches = tuple(m for m in w.matches if m.decision_at == t)
            quotes = [q for m in matches for q in m.decision["pinnacle"]]
            pricing = fair_prices(quotes, decision_time=t, kickoffs={m.match_id: m.kickoff for m in w.matches})
            cands[perm] = sorted(_selector(script)(DecisionContext(t, matches, pricing)),
                                 key=lambda c: (-(c.p * c.odds), c.match_id, c.market, c.outcome))  # fmt: skip
        out["snapshots"].append((t, coupons(rows, now=t), cands))
    return out


def _selector(script: Any) -> Any:
    from valuebet.backtest.financial import threshold_selector

    return threshold_selector(books={"1x2": ("bet365",), "over_under": ("bet365",)}, tax_factor=1.0,
                              edge_threshold=0.02, require_complete=True, excluded=Counter(), rejected=Counter(),
                              margin_check=False)  # fmt: skip


def _stake_at(capital: float) -> Callable[[Any], Callable[[float], Any]]:
    from valuebet.backtest.clv import clv_report
    from valuebet.backtest.financial import StakeContext, kelly_staker

    def for_group(view: Any) -> Callable[[float], Any]:
        def stake_at(tax: float) -> Any:
            return kelly_staker(StakeContext(candidate=view, bankroll=capital, peak_bankroll=capital,
                                             clv_report=clv_report([]), n_real_bets=0, open_exposure=0.0,
                                             match_exposure=0.0, tax_factor=tax))  # fmt: skip
        return stake_at

    return for_group


def _outputs(planner_factory: Callable[[Any], Any], inputs: dict[str, Any], capital: float) -> dict[bool, list[Any]]:
    """Wyjście planisty (grupy, podatek, stawka) dla obu światów przy IDENTYCZNYM stanie."""
    import math
    from dataclasses import replace

    out: dict[bool, list[Any]] = {}
    for perm, world in inputs["worlds"].items():
        rows: list[Any] = []
        for t, current, cands in inputs["snapshots"]:
            planner = planner_factory(world)
            planner.begin(t=t, current=current)
            for group in planner.groups(cands[perm]):
                view = replace(group[0], match_id="+".join(c.match_id for c in group),
                               p=math.prod(c.p for c in group), odds=math.prod(c.odds for c in group))  # fmt: skip
                priced = planner.price(group, stake_at=_stake_at(capital)(view))
                rows.append((t, tuple((c.match_id, c.outcome) for c in group),
                             None if priced is None else (priced[0], priced[1].stake)))  # fmt: skip
        out[perm] = rows
    return out


def _real_planner(_world: Any) -> Any:
    from valuebet.backtest.strategy_c import RegimePlanner, counterfactual_regime_config

    script = _script()
    start = script.c_regime_start(_world)
    return RegimePlanner(counterfactual_regime_config(start=start, share_basis="stakes", min_stake_pln=0.50),
                         0.02, "production")  # fmt: skip


def _peeking_planner(world: Any) -> Any:
    """MUTACJA: planista zaglądający do wyniku pierwszej nogi (przeciek)."""
    from valuebet.backtest.financial import leg_result

    base = _real_planner(world)

    class Peeking(type(base)):
        def price(self, legs: Any, *, stake_at: Any) -> Any:
            first = legs[0]
            res = world.results[first.match_id]
            if leg_result(market=first.market, outcome=first.outcome, line=first.line, result=res) == "lost":
                return None
            return super().price(legs, stake_at=stake_at)

    return Peeking(base.regime_config, base.edge_threshold, base.single_mode)


def test_planner_is_pure_and_the_purity_test_catches_a_peeking_planner(tmp_path: Path) -> None:
    """Krok 5 (b): identyczny stan (kapitał, historia, okno), dwa zestawy wyników świata →
    identyczne grupy, podatki i stawki na 3 migawkach, przy kapitale, dla którego stawka
    najdłuższego dubletu jest tuż NAD i tuż POD 0,50 zł. Mutacja zaglądająca do wyniku → różnica."""
    inputs = _snapshot_inputs(tmp_path)
    probe = _outputs(_real_planner, inputs, 10_000.0)[False]  # bez T13 (1 mln zł → x0.90, EV < 0)
    smallest = min(stake for *_, out in probe if out is not None and (stake := out[1]) > 0)
    for capital in (10_000.0 * 0.505 / smallest, 10_000.0 * 0.485 / smallest):
        real = _outputs(_real_planner, inputs, capital)
        assert real[False] == real[True]
        assert len({t for t, *_ in real[False]}) == 3
    above = _outputs(_real_planner, inputs, 10_000.0 * 0.505 / smallest)[False]
    below = _outputs(_real_planner, inputs, 10_000.0 * 0.485 / smallest)[False]
    assert above != below, "kapitał nie przeprowadził stawki przez 0,50 zł — test bez mocy"
    mutant = _outputs(_peeking_planner, inputs, 10_000.0 * 0.505 / smallest)
    assert mutant[False] != mutant[True], "test czystości nie wykrył planisty zaglądającego do wyniku"


# -- krok 6: czułość kryterium 4b-C ---------------------------------------------


def _pair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, leak: bool, fake_reason: bool) -> Any:
    """(bazowy, spermutowany) przebieg C na małym świecie + ``check_4b_c``."""
    import valuebet.backtest.financial as financial
    import valuebet.backtest.strategy_c as strategy_c
    from valuebet.backtest.financial import leg_result

    script = _script()
    truth = script.c120_truth(script.synthetic_truth(weeks=16, per_week=6, seed=5))
    worlds: list[Any] = []
    real_build = script.build_world

    def capture(*a: Any, **k: Any) -> Any:
        worlds.append(real_build(*a, **k))
        return worlds[-1]

    monkeypatch.setattr(script, "build_world", capture)
    if leak:
        real_price = strategy_c.RegimePlanner.price

        def peeking(self: Any, legs: Any, *, stake_at: Any) -> Any:
            first = legs[0]
            if leg_result(market=first.market, outcome=first.outcome, line=first.line,
                          result=worlds[-1].results[first.match_id]) == "lost" and first.odds > 3.0:  # fmt: skip
                return None
            return real_price(self, legs, stake_at=stake_at)

        monkeypatch.setattr(strategy_c.RegimePlanner, "price", peeking)
    if fake_reason:
        monkeypatch.setattr(financial, "DROP_EV", financial.DROP_BELOW_MIN_STAKE)
    base = script.run_seed(truth, strategy="C", seed=1, soft_factor=1.025, tax_factor=1.0, detail=True,
                           workdir=tmp_path / "b")  # fmt: skip
    perm = script.run_seed(truth, strategy="C", seed=1, soft_factor=1.025, tax_factor=1.0, detail=True,
                           permute_results=True, workdir=tmp_path / "p")  # fmt: skip
    return script.check_4b_c({1: base}, [perm])


def test_4bc_criterion_is_green_on_an_honest_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    check = _pair(tmp_path, monkeypatch, leak=False, fake_reason=False)
    assert check.passed, check.detail
    assert "niewyjaśnionych: 0" in check.detail


def test_4bc_criterion_catches_a_leaking_planner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Krok 6 (a): planista pomija grupy, których pierwsza noga przegrywa → CZERWONY."""
    check = _pair(tmp_path, monkeypatch, leak=True, fake_reason=False)
    assert not check.passed
    assert "niewyjaśnionych: 0" not in check.detail, check.detail


def test_4bc_criterion_catches_a_false_explanation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Krok 6 (b): odrzucenie podpisane STAWKA_PONIZEJ_MINIMUM, a z księgi stawka ≥ 0,50 zł → CZERWONY."""
    check = _pair(tmp_path, monkeypatch, leak=True, fake_reason=True)
    assert not check.passed
    assert "STAWKA_PONIZEJ_MINIMUM niepotwierdzona" in check.detail, check.detail
