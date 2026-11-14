"""Bramka §4 silnika — wersja szybka (sztuczny terminarz, kilka nasion).

Pełna bramka: ``scripts/engine_tests.py`` (200 nasion, terminarz E0/E1 z raw)
z raportem w ``reports/backtest_fin/<commit>/``. Tutaj te same funkcje, ale
wyłącznie punkty deterministyczne — statystyczne (1b, 2b, 3a) przy kilku
nasionach nie mają mocy i należą do skryptu.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATISTICAL = ("1b ", "2b ", "3a ", "1b-C", "2b-C", "3a-C")


def _script() -> ModuleType:
    name = "engine_tests_under_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "engine_tests.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclassy skryptu potrzebują modułu w sys.modules
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def checks(tmp_path_factory: pytest.TempPathFactory) -> list[Any]:
    script = _script()
    # 30 tygodni: świat pasma 3d-C potrzebuje dość migawek, żeby udział przeszedł przez próg
    truth = script.synthetic_truth(weeks=30, per_week=6, seed=7)
    work = tmp_path_factory.mktemp("engine")
    out: list[Any] = script.gate(truth, seeds=range(3), workdir=work)
    out.append(script.spy_check(truth, workdir=work))
    return out


def test_gate_covers_every_point_of_section_four(checks: list[Any]) -> None:
    names = [c.name for c in checks]
    for prefix in ("1a", "1b", "2a", "2b", "3a", "3b", "4a", "4b", "4c", "5 ", "6 ", "7 "):
        assert any(n.startswith(prefix) for n in names), prefix
    # wariant B (decyzja Pawła 2026-10-11): bramka obejmuje C, testy 1-7
    for prefix in ("1a-C", "1b-C", "2a-C", "2b-C", "3a-C", "3b-C", "3c-C", "3d-C", "4a-C", "4b-C", "4c-C", "5-C", "6-C"):
        assert any(n.startswith(prefix) for n in names), prefix
    spy = next(c for c in checks if c.name.startswith("7 "))
    assert "RegimePlanner.price" in spy.detail and "BetclicTaxRegime.tax_for_multi" in spy.detail


def test_deterministic_points_are_green(checks: list[Any]) -> None:
    red = [
        f"{c.name}: {c.detail}"
        for c in checks
        if not c.name.startswith(STATISTICAL) and not c.passed
    ]
    assert red == []


def test_totals_count_only_real_bets() -> None:
    """Po wyłączniku 25% zakłady idą jako paper: nie ruszają kasy, więc nie mogą
    wchodzić do obrotu ani do oczekiwanego zysku (incydent 2026-10-08, test 1b)."""
    from test_journal_cache import _record

    script = _script()
    real = _record(1, mode="real", stake=100.0, odds_taken=2.1, p_fair_at_bet=0.5)
    paper = _record(2, mode="paper", stake=50.0, odds_taken=2.1, p_fair_at_bet=0.5)
    turnover, expected = script.real_totals(bets=[real, paper])
    assert turnover == 100.0
    assert expected == 100.0 * (0.5 * 2.1 - 1)


def test_seed_refuses_to_run_below_the_free_space_floor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Twardy próg wolnego miejsca w KAŻDYM seedzie, nie tylko między fazami
    (incydent 2026-10-08: pagefile zjadł dysk w trakcie fazy)."""
    import shutil
    from collections import namedtuple

    script = _script()
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda _p: usage(100, 99, 1024**3))
    truth = script.synthetic_truth(weeks=1, per_week=2, seed=1)
    with pytest.raises(RuntimeError, match="< 3 GB"):
        script.run_seed(truth, strategy="A", seed=0, soft_factor=1.025, tax_factor=1.0, workdir=tmp_path)


# -- Poprawka 6 (bramka e66260a: 1092 „otwarta ekspozycja” w wymuszonym placebo) --


def _burst(tmp_path: Path, *, forced: bool, per_week: int = 32) -> tuple[Any, Any, list[Any]]:
    """Jedna migawka: ``per_week`` meczów; wymuszone placebo = 5 wyników x 10 zł."""
    from collections import Counter

    from valuebet.backtest.financial import (
        kelly_staker,
        run,
        tagged_selector,
        threshold_selector,
    )
    from valuebet.live.bets import BetJournal

    script = _script()
    truth = script.synthetic_truth(weeks=1, per_week=per_week, seed=3)
    world = script.build_world(truth, seed=0, soft_factor=0.95 if forced else 1.025)
    selector = tagged_selector(script._every_outcome, selection_tax=1.0) if forced else threshold_selector(
        books={"1x2": ("bet365",), "over_under": ("bet365",)}, tax_factor=1.0,
        edge_threshold=0.02, require_complete=True, excluded=Counter(), rejected=Counter(),
        margin_check=False,
    )  # fmt: skip
    path = tmp_path / "bets.csv"
    result = run(world, selector=selector, staker=script._flat if forced else kelly_staker,
                 selection_tax_factor=1.0, settlement_tax_factor=1.0, journal_path=path, run_id="t", start_capital=10_000.0,
                 ingested_at=script.INGESTED, min_stake_pln=script.MIN_STAKE_PLN)  # fmt: skip
    bets = [r for r in BetJournal(journal_path=path).read() if not r.is_settlement]
    return world, result, bets


def _exposure_errors(report: Any) -> list[str]:
    return [e for e in report.errors if "otwarta ekspozycja" in e]


def test_forced_placebo_is_exempt_from_kelly_limits_but_production_is_not(tmp_path: Path) -> None:
    script = _script()
    world, result, bets = _burst(tmp_path, forced=True)
    assert len(bets) == 160
    assert sum(b.stake for b in bets) == 1600.0
    exempt = script.invariant_errors(world, result, bets=bets, limits=script.FORCED_PLACEBO_NO_LIMITS)
    assert _exposure_errors(exempt) == []
    checked = script.invariant_errors(world, result, bets=bets, limits=script.PRODUCTION_LIMITS)
    assert _exposure_errors(checked)


def test_invariants_require_explicit_limits() -> None:
    script = _script()
    kwargs: dict[str, Any] = {"bets": []}
    with pytest.raises(TypeError, match="limits"):
        script.invariant_errors(None, None, **kwargs)


def test_checker_catches_an_engine_that_ignores_the_15_percent_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trucizna: silnik bez limitu 15% MUSI zaświecić test 6 na czerwono."""
    import valuebet.pricing.kelly as kelly

    script = _script()
    world, result, bets = _burst(tmp_path / "ok", forced=False, per_week=40)
    clean = script.invariant_errors(world, result, bets=bets, limits=script.PRODUCTION_LIMITS)
    assert not clean.errors
    assert clean.snapshots_checked > 0
    assert clean.max_open_exposure > 0.10
    monkeypatch.setattr(kelly, "MAX_OPEN_EXPOSURE", 1.0)
    world, result, bets = _burst(tmp_path / "bad", forced=False, per_week=40)
    broken = script.invariant_errors(world, result, bets=bets, limits=script.PRODUCTION_LIMITS)
    assert _exposure_errors(broken)


def test_time_order_violation_is_caught_in_both_modes(tmp_path: Path) -> None:
    from dataclasses import replace
    from datetime import timedelta

    script = _script()
    world, result, bets = _burst(tmp_path, forced=True, per_week=2)
    first = world.matches[0]
    early = replace(first, kickoff=bets[0].placed_at - timedelta(minutes=5))
    broken = replace(world, matches=(early, *world.matches[1:]))
    for limits in (script.FORCED_PLACEBO_NO_LIMITS, script.PRODUCTION_LIMITS):
        report = script.invariant_errors(broken, result, bets=bets, limits=limits)
        assert any("porządek czasu" in e for e in report.errors)


def test_check_six_fails_when_production_runs_checked_nothing() -> None:
    """Ochrona przed pustą zielenią: zero sprawdzonych migawek → test 6 czerwony."""
    script = _script()
    empty = script.InvariantReport(errors=(), snapshots_checked=0, max_open_exposure=0.0)
    assert script.check_six(production=[empty], other=[]).passed is False
    ok = script.InvariantReport(errors=(), snapshots_checked=5, max_open_exposure=0.12)
    assert script.check_six(production=[ok], other=[empty]).passed is True
    bad = script.InvariantReport(errors=("x: otwarta ekspozycja 1.00",), snapshots_checked=5,
                                 max_open_exposure=0.2)  # fmt: skip
    assert script.check_six(production=[ok], other=[bad]).passed is False


def test_checker_limits_are_independent_literals_equal_to_kelly() -> None:
    """Sprawdzarka ma WŁASNE literały limitów (CLAUDE.md reguły 21-23, TOR_S_PLAN §5);
    literówka w pricing/kelly.py (np. 0.02 → 0.2) nie może przejść bramki, bo sprawdzarka
    nie dzieli stałych z silnikiem. Zmiana jednej strony wywraca ten test."""
    import ast

    import valuebet.pricing.kelly as kelly

    script = _script()
    assert script.Limits(0.02, 0.03, 0.15) == script.CHECKER_LIMITS
    assert script.CHECKER_LIMITS.per_bet == kelly.MAX_FRACTION_PER_BET
    assert script.CHECKER_LIMITS.per_match == kelly.MAX_FRACTION_PER_MATCH
    assert script.CHECKER_LIMITS.open_exposure == kelly.MAX_OPEN_EXPOSURE
    tree = ast.parse((ROOT / "scripts" / "engine_tests.py").read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "valuebet.pricing.kelly"
        for alias in node.names
    }
    assert not imported & {"MAX_FRACTION_PER_BET", "MAX_FRACTION_PER_MATCH", "MAX_OPEN_EXPOSURE"}


def test_preflight_does_not_depend_on_a_local_collector_heartbeat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kolektor działa na VPS od 2026-10-10 (cutover): lokalny heartbeat stoi
    na zawsze, więc nie może zatrzymywać bramki. Wolne miejsce — nadal tak."""
    import json
    from datetime import UTC, datetime, timedelta

    script = _script()
    state = tmp_path / "data" / "state" / "odds_api"
    state.mkdir(parents=True)
    stale = datetime.now(UTC) - timedelta(days=2)
    (state / "heartbeat.jsonl").write_text(json.dumps({"at": stale.isoformat()}) + "\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(script, "_require_free_space", lambda _phase: None)
    script.preflight("start")  # nie przerywa


# -- reguła (a) A4a-01 w bramce: jawny znacznik, raport, przebieg produkcyjny ------


def test_gate_world_disables_rule_a_only_through_the_named_marker() -> None:
    """``run_seed`` wyłącza regułę (a) wyłącznie nazwanym znacznikiem (jak
    ``FORCED_PLACEBO_NO_LIMITS``), nie gołym literałem — grep znajduje każde użycie."""
    import ast

    tree = ast.parse((ROOT / "scripts" / "engine_tests.py").read_text(encoding="utf-8"))
    values = [
        kw.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "threshold_selector"
        for kw in node.keywords
        if kw.arg == "margin_check"
    ]
    assert values, "threshold_selector bez margin_check w skrypcie bramki"
    assert all(isinstance(v, ast.Name) and v.id == "GATE_WORLD_NO_MARGIN_CHECK" for v in values)
    script = _script()
    assert script.GATE_WORLD_NO_MARGIN_CHECK is False


def test_engine_report_states_that_rule_a_is_off_in_the_gate_world(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ENGINE_TESTS.md i .json mówią wprost, że reguła (a) jest w bramce wyłączona i dlaczego."""
    import json

    script = _script()

    class _Pool:
        def __init__(self, *a: Any, **k: Any) -> None: ...
        def __enter__(self) -> _Pool:
            return self
        def __exit__(self, *a: Any) -> None: ...

    monkeypatch.setattr(script, "ROOT", tmp_path)
    monkeypatch.setattr(script, "RawStore", lambda **_k: None)
    monkeypatch.setattr(script, "preflight_start", lambda: None)
    monkeypatch.setattr(script, "fixture_truth", lambda _store: script.synthetic_truth(weeks=1, per_week=1, seed=1))
    monkeypatch.setattr(script, "frozen_commit", lambda **_k: "testhash")
    monkeypatch.setattr(script, "generated_by", lambda **_k: "test")
    monkeypatch.setattr(script, "preflight", lambda _phase: None)
    monkeypatch.setattr(script, "_lower_priority", lambda: None)
    monkeypatch.setattr(script.multiprocessing, "Pool", _Pool)
    monkeypatch.setattr(script, "gate", lambda *_a, **_k: [script.Check("1a x", True, "ok")])
    monkeypatch.setattr(script, "spy_check", lambda *_a, **_k: script.Check("7 x", True, "ok"))
    assert script.main(["--seeds", "1", "--workers", "1"]) == 0
    out = tmp_path / "reports" / "backtest_fin" / "testhash"
    md = (out / "ENGINE_TESTS.md").read_text(encoding="utf-8")
    assert "GATE_WORLD_NO_MARGIN_CHECK" in md
    assert "reguła (a) A4a-01 WYŁĄCZONA" in md
    payload = json.loads((out / "ENGINE_TESTS.json").read_text(encoding="utf-8"))
    assert payload["margin_check"] is False


# -- wariant B: C w bramce, wyniki cząstkowe i --resume, PAPER, preflight ------------


def test_c_seed_places_doubles_with_regime_tax_checked_independently(tmp_path: Path) -> None:
    """Przebieg C na małym świecie c120: są dublety, podatek każdego kuponu = checker
    z literałów, CLV kuponu = (1+e)^n·tax - 1, stawki = wzór Kelly'ego (Π p, Π k)."""
    script = _script()
    truth = script.c120_truth(script.synthetic_truth(weeks=6, per_week=6, seed=7))
    run = script.run_seed(truth, strategy="C", seed=1, soft_factor=1.025, tax_factor=1.0,
                          detail=True, workdir=tmp_path)  # fmt: skip
    assert run.n_multi > 0
    assert run.tax_errors == ()
    assert run.clv_max_dev < script.SHIN_TOL
    assert run.kelly_mismatch == ()
    assert run.invariants.errors == ()
    assert run.reconcile_mismatches == 0


def test_reference_regime_catches_an_engine_that_ignores_the_share(tmp_path: Path,
                                                                  monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    """Trucizna checkera: silnik, który daje 1.00 każdemu singlowi, MUSI zaświecić 6-C."""
    import valuebet.pricing.ev as ev

    script = _script()
    # solo: same single, udział AKO 0 → poprawnie 0.94; zatruty silnik daje 1.00
    truth = script.solo_truth(script.synthetic_truth(weeks=12, per_week=3, seed=7))
    clean = script.run_seed(truth, strategy="C", seed=1, soft_factor=1.10, tax_factor=1.0, workdir=tmp_path / "ok")
    assert clean.n_coupons > 0 and clean.tax_errors == ()
    monkeypatch.setattr(ev.BetclicTaxRegime, "share_condition_met", lambda self, *, candidate: True)
    run = script.run_seed(truth, strategy="C", seed=1, soft_factor=1.10, tax_factor=1.0, workdir=tmp_path / "bad")
    assert run.tax_errors, "checker reżimu nie wykrył singli po 1.00 przy udziale < 50%"


def test_regime_transitions_are_green_and_catch_a_wrong_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    import valuebet.pricing.ev as ev

    script = _script()
    assert script.regime_transitions_check().passed
    monkeypatch.setattr(ev, "AKO_SHARE_THRESHOLD", 0.51)
    assert not script.regime_transitions_check().passed


def test_reconcile_is_independent_of_pricing() -> None:
    """Test 5 (C): reconcile_bets.py nie importuje ``valuebet`` — liczy wprost z CSV."""
    import ast

    tree = ast.parse((ROOT / "scripts" / "reconcile_bets.py").read_text(encoding="utf-8"))
    modules = {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    } | {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(m.startswith("valuebet") for m in modules), modules


def _small_gate(tmp_path: Path, *, partial: Path, resume: bool, stop_after: int | None = None) -> Any:
    script = _script()
    truth = script.synthetic_truth(weeks=4, per_week=4, seed=3)
    if stop_after is not None:
        original = script.run_item
        done = {"n": 0}

        def interrupted(*a: Any, **k: Any) -> Any:
            if done["n"] >= stop_after:
                raise KeyboardInterrupt("symulowane przerwanie")
            done["n"] += 1
            return original(*a, **k)

        script.run_item = interrupted
        try:
            return script.run_gate(truth, seeds=2, workdir=tmp_path, partial=partial, commit="abc1234",
                                   resume=resume, progress_every_s=0.0)  # fmt: skip
        finally:
            script.run_item = original
    return script.run_gate(truth, seeds=2, workdir=tmp_path, partial=partial, commit="abc1234",
                           resume=resume, progress_every_s=0.0)  # fmt: skip


def test_interrupted_and_resumed_gate_gives_the_same_report(tmp_path: Path) -> None:
    """Dopisek Pawła 2026-10-11: przerwany i wznowiony przebieg == przebieg bez przerwy."""
    full, _, _ = _small_gate(tmp_path / "w1", partial=tmp_path / "full", resume=False)
    with pytest.raises(KeyboardInterrupt):
        _small_gate(tmp_path / "w2", partial=tmp_path / "cut", resume=False, stop_after=7)
    assert len(list((tmp_path / "cut").glob("*.pkl"))) == 7
    resumed, store, progress = _small_gate(tmp_path / "w3", partial=tmp_path / "cut", resume=True)
    assert store.resumed and store.loaded == 7
    assert [(c.name, c.passed, c.detail) for c in resumed] == [(c.name, c.passed, c.detail) for c in full]
    assert progress.lines and "nasiono" in progress.lines[-1] and "GB wolne" in progress.lines[-1] and "RAM wolny" in progress.lines[-1]


def test_resume_refuses_other_commit_seeds_or_params_and_needs_the_flag(tmp_path: Path) -> None:
    script = _script()
    partial = tmp_path / "p"
    _small_gate(tmp_path / "w", partial=partial, resume=False)
    world = script.world_digest(script.synthetic_truth(weeks=4, per_week=4, seed=3))
    with pytest.raises(script.ResumeRefusedError, match="--resume"):
        script.PartialStore(partial, "abc1234", 2, False, world)
    with pytest.raises(script.ResumeRefusedError, match="commit"):
        script.PartialStore(partial, "fff0000", 2, True, world)
    with pytest.raises(script.ResumeRefusedError, match="nasion"):
        script.PartialStore(partial, "abc1234", 3, True, world)
    store = script.PartialStore(partial, "abc1234", 2, True, world)
    with pytest.raises(script.ResumeRefusedError, match="parametry"):
        store.get("1-A", {"strategy": "A", "seed": 0, "soft_factor": 9.9, "tax_factor": 1.0, "world": "full"})


def test_preflight_checks_repo_and_temp_disks_and_mid_run_message_mentions_resume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil
    from collections import namedtuple

    script = _script()
    usage = namedtuple("usage", "total used free")
    tmp = Path("D:/vb-tmp")
    monkeypatch.setattr(script, "temp_dir", lambda: tmp)
    gb = 1024**3

    def disks(repo: float, temp: float) -> None:
        monkeypatch.setattr(shutil, "disk_usage",
                            lambda p: usage(100, 99, int((temp if Path(p) == tmp else repo) * gb)))  # fmt: skip

    disks(6.0, 10.0)
    script.preflight_start()  # dopisek 3: 6 GB repo, 10 GB tymczasowy — wystarczy
    disks(5.9, 33.0)
    with pytest.raises(RuntimeError, match=r"repo.*< 6 GB"):
        script.preflight_start()
    disks(8.3, 9.9)
    with pytest.raises(RuntimeError, match=r"tymczasowy.*< 10 GB"):
        script.preflight_start()
    disks(2.9, 33.0)
    with pytest.raises(RuntimeError, match=r"repo.*--resume"):
        script.preflight("faza")
    disks(8.3, 2.9)
    with pytest.raises(RuntimeError, match=r"tymczasowy.*--resume"):
        script.preflight("faza")


def test_gate_reads_raw_only_through_the_given_root(tmp_path: Path) -> None:
    """--raw-root: odczyt z cudzego data/raw (worktree) — tylko ``latest`` i ``read_bytes``."""
    script = _script()
    store = script.RawStore(root=tmp_path / "raw")
    with pytest.raises(FileNotFoundError, match="raw"):
        script.fixture_truth(store)
    assert not (tmp_path / "raw").exists(), "odczyt nie może tworzyć katalogów w raw"


# -- audyt wariantu B (backtest-auditor 2026-10-11): POWAŻNE 1 i 2 ------------------


@pytest.mark.parametrize(("attr", "value"), [("AKO_SHARE_THRESHOLD", 0.45), ("AKO_WINDOW_MONTHS", 3)])
def test_band_world_catches_regime_mutations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, attr: str, value: float
) -> None:
    """POWAŻNE 1: w świecie pasma udziału ~50% (3d-C) zmutowany silnik (próg 0.45
    albo okno 3 miesiące zamiast 12) daje podatek ≠ niezależny checker."""
    import valuebet.pricing.ev as ev

    script = _script()
    truth = script.band_truth(script.synthetic_truth(weeks=40, per_week=6, seed=7))
    monkeypatch.setattr(ev, attr, value)
    run = script.run_seed(truth, strategy="C", seed=0, soft_factor=1.10, tax_factor=1.0, workdir=tmp_path)
    assert run.tax_errors, f"mutacja {attr}={value} nie wykryta"


def test_band_world_puts_coupons_near_the_share_threshold(tmp_path: Path) -> None:
    """Ochrona przed pustą zielenią: w świecie pasma część kuponów ma udział
    (z kandydatem, wg niezależnego checkera) w [0.40, 0.60]."""
    script = _script()
    truth = script.band_truth(script.synthetic_truth(weeks=40, per_week=6, seed=7))
    run = script.run_seed(truth, strategy="C", seed=0, soft_factor=1.10, tax_factor=1.0, workdir=tmp_path)
    assert run.share_band > 0
    assert run.tax_errors == ()


def test_resume_refuses_results_from_another_world(tmp_path: Path) -> None:
    """POWAŻNE 2: wyniki cząstkowe z innego świata (inne dane raw) — odmowa."""
    script = _script()
    a = script.synthetic_truth(weeks=4, per_week=4, seed=3)
    b = script.synthetic_truth(weeks=4, per_week=4, seed=4)
    script.run_gate(a, seeds=1, workdir=tmp_path / "w1", partial=tmp_path / "p", commit="abc1234",
                    resume=False, progress_every_s=0.0)  # fmt: skip
    with pytest.raises(script.ResumeRefusedError, match="świat"):
        script.run_gate(b, seeds=1, workdir=tmp_path / "w2", partial=tmp_path / "p", commit="abc1234",
                        resume=True, progress_every_s=0.0)  # fmt: skip
