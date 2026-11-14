"""Runner kroku 5 (``scripts/run_backtest_fin.py``) — wyłącznie świat syntetyczny.

Nigdy na prawdziwych danych (wariant B, decyzja Pawła 2026-10-11): znana
odpowiedź, alarm D przy wymuszonym zysku, zapis tylko do katalogu raportu,
jedna ścieżka kodu (szpiedzy na funkcjach produkcyjnych, reguła 28).
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, file: str) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / file)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _runner() -> ModuleType:
    return _load("run_backtest_fin_under_test", "run_backtest_fin.py")


def _world(*, value: float, weeks: int = 12) -> Any:
    """Świat bramki z miękkim kursem value TYLKO na pierwszym wyniku rynku
    (``value / p``), reszta ``0.90 / p`` — booksum > 1, więc reguła (a) A4a-01
    przepuszcza; ten sam kurs u B365, BW, WH i w ``max``."""
    from valuebet.pricing.fair import MarketQuote

    et = _load("engine_tests_for_runner", "engine_tests.py")
    truth = et.synthetic_truth(weeks=weeks, per_week=6, seed=5)
    p_true = {t.match_id: t.p for t in truth}
    world = et.build_world(truth, seed=2, soft_factor=1.0)
    matches = []
    for m in world.matches:
        quotes = []
        for q in m.decision["bet365"]:
            p = p_true[m.match_id][q.market]
            odds = tuple((value if i == 0 else 0.90) / x for i, x in enumerate(p))
            quotes.append(MarketQuote(q.match_id, q.market, q.outcomes, odds, q.observed_at, q.line))
        books = {b: tuple(quotes) for b in ("bet365", "betandwin", "williamhill", "max")}
        matches.append(replace(m, decision={"pinnacle": m.decision["pinnacle"], **books}))
    return replace(world, matches=tuple(matches))


def _two_book_world(*, value: float, weeks: int = 12) -> Any:
    """Jak ``_world``, ale B365 i BW o RÓŻNYCH kursach 1X2: w każdej chwili decyzji
    mecze (po ``match_id``) na przemian — kurs value u bet365 albo u betandwin,
    u drugiego ``1.00 / p``; O/U tylko u bet365. Dublety C łączą więc nogi o
    różnym najlepszym bukmacherze (awaria oficjalnego przebiegu 2026-10-16)."""
    from valuebet.pricing.fair import MarketQuote

    et = _load("engine_tests_for_runner", "engine_tests.py")
    truth = et.synthetic_truth(weeks=weeks, per_week=6, seed=5)
    p_true = {t.match_id: t.p for t in truth}
    world = et.build_world(truth, seed=2, soft_factor=1.0)
    by_time: dict[Any, list[str]] = {}
    for m in world.matches:
        by_time.setdefault(m.decision_at, []).append(m.match_id)
    rank = {mid: i for ids in by_time.values() for i, mid in enumerate(sorted(ids))}

    def quotes(m: Any, top: float) -> tuple[Any, ...]:
        out = []
        for q in m.decision["bet365"]:
            p = p_true[m.match_id][q.market]
            first = value if q.market != "1x2" else top
            odds = tuple((first if i == 0 else 0.90) / x for i, x in enumerate(p))
            out.append(MarketQuote(q.match_id, q.market, q.outcomes, odds, q.observed_at, q.line))  # fmt: skip
        return tuple(out)

    matches = []
    for m in world.matches:
        b365_best = rank[m.match_id] % 2 == 0
        b365 = quotes(m, value if b365_best else 1.00)
        bw = tuple(q for q in quotes(m, 1.00 if b365_best else value) if q.market == "1x2")  # fmt: skip
        matches.append(replace(m, decision={"pinnacle": m.decision["pinnacle"], "bet365": b365, "betandwin": bw}))  # fmt: skip
    return replace(world, matches=tuple(matches))


def test_c_doubles_with_legs_from_different_books_get_one_label(tmp_path: Path) -> None:
    """Awaria 2026-10-16 (C-000008: „nogi różnią się polem bookmaker”): nogi
    dubletu C z najlepszym kursem u różnych bukmacherów. Kupon C to jedno konto
    Betclic — każda noga każdego kuponu ma etykietę ``C_BOOKMAKER``."""
    runner = _runner()
    (spec,) = _specs("C")
    run = runner.execute(spec, _two_book_world(value=1.025), out=tmp_path / "r", min_stake_pln=0.50)  # fmt: skip
    rows = [r for r in runner.BetJournal(journal_path=run.journal).read() if not r.is_settlement]  # fmt: skip
    assert any(r.n_legs == 2 for r in rows)
    assert rows and {r.bookmaker for r in rows} == {runner.C_BOOKMAKER}


def _specs(*names: str) -> list[Any]:
    runner = _runner()
    return [s for s in runner.run_specs(capital=10_000.0, with_f=False) if s.name in names]


def test_known_answer_every_a_bet_beats_the_close_by_e(tmp_path: Path) -> None:
    runner = _runner()
    payload, code = runner.run_all(_world(value=1.025), f_replay=None, out=tmp_path / "r", min_stake_pln=0.50,
                                   commit="test", observed_at_rule="x", specs=_specs("A", "C", "D", "E"))  # fmt: skip
    a = payload["summaries"]["A"]["aggregate"]
    assert a["n_coupons"] > 0
    assert a["clv"]["mean"] == pytest.approx(0.025, abs=1e-7)
    assert a["clv"]["ci_low"] == pytest.approx(0.025, abs=1e-7)  # każdy zakład = e
    c = payload["summaries"]["C"]
    assert any(k.startswith("multi") for k in c["tax_counts"])
    # CLV kuponu C: dublet (1+e)^2 - 1, singiel e (podatek 1.00) — średnia pomiędzy
    assert 0.025 - 1e-7 <= c["aggregate"]["clv"]["mean"] <= 1.025**2 - 1 + 1e-7
    assert payload["summaries"]["D"]["aggregate"]["clv"]["mean"] == pytest.approx(1.025 * 0.88 - 1, abs=1e-7)
    assert all(s["reconcile"]["ok"] for s in payload["summaries"].values())
    # Yield na ~150 kuponach to szum (dublety C: kursy ~4-5) — alarm 8% może
    # zadziałać i wtedy werdyktu NIE ma; ścieżka bez alarmu — test niżej.
    assert (payload["verdict"] is None) == bool(payload["alarms"]) == (code == 2)
    report = (tmp_path / "r" / "RAPORT.md").read_text(encoding="utf-8")
    assert "per liga" in report and "Przebiegi główne" in report


def test_alarm_d_fires_when_profit_is_forced(tmp_path: Path) -> None:
    """Kurs value 1.30/p: D (wybór 1.00, rozliczenie 0.88) zarabia → ALARM, kod 2, bez werdyktu."""
    runner = _runner()
    payload, code = runner.run_all(_world(value=1.30), f_replay=None, out=tmp_path / "r", min_stake_pln=0.50,
                                   commit="test", observed_at_rule="x", specs=_specs("A", "C", "D"))  # fmt: skip
    assert code == 2
    assert any(a.startswith("D: zysk") for a in payload["alarms"])
    assert any("> 8%" in a for a in payload["alarms"])
    assert payload["verdict"] is None
    assert "ALARM" in (tmp_path / "r" / "RAPORT.md").read_text(encoding="utf-8")


def test_runner_writes_only_into_its_report_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Nie dotyka data/raw ani data/bets/bets.csv — dzienniki per przebieg w katalogu raportu."""
    from valuebet.ingest.raw_store import RawStore

    def forbidden(*_a: Any, **_k: Any) -> None:
        raise AssertionError("runner pisze do data/raw")

    monkeypatch.setattr(RawStore, "write_raw", forbidden)
    live = ROOT / "data" / "bets" / "bets.csv"
    before = live.stat().st_mtime_ns if live.exists() else None
    runner = _runner()
    out = tmp_path / "r"
    runner.run_all(_world(value=1.025, weeks=8), f_replay=None, out=out, min_stake_pln=0.50, commit="test",
                   observed_at_rule="x", specs=_specs("A"))  # fmt: skip
    assert (live.stat().st_mtime_ns if live.exists() else None) == before
    journals = list(tmp_path.rglob("bets.csv"))
    assert journals and all(p.is_relative_to(out) for p in journals)


def test_runner_uses_the_production_functions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reguła 28/29: runner woła ``run_strategy`` / ``run_regime`` i przez nie te
    same funkcje co bramka §4 (``simulate``, Kelly, reżim ``pricing.ev``)."""
    import valuebet.backtest.financial as financial
    import valuebet.backtest.strategies as strategies
    import valuebet.backtest.strategy_c as strategy_c
    import valuebet.pricing.ev as ev
    import valuebet.pricing.kelly as kelly

    runner = _runner()
    assert runner.run_strategy is strategies.run_strategy
    assert runner.run_regime is strategy_c.run_regime
    assert runner.kelly_staker is financial.kelly_staker
    calls: dict[str, int] = {}

    def spy(owner: Any, attr: str) -> None:
        real = getattr(owner, attr)

        def wrapper(*a: Any, **k: Any) -> Any:
            calls[attr] = calls.get(attr, 0) + 1
            return real(*a, **k)

        monkeypatch.setattr(owner, attr, wrapper)

    spy(financial, "simulate")
    spy(strategy_c, "simulate")
    spy(ev.BetclicTaxRegime, "tax_for_multi")
    spy(financial, "fair_prices")
    real_from_journal = kelly.KellyPolicy.from_journal

    def from_journal(**kw: Any) -> Any:
        calls["from_journal"] = calls.get("from_journal", 0) + 1
        return real_from_journal(**kw)

    monkeypatch.setattr(kelly.KellyPolicy, "from_journal", staticmethod(from_journal))
    runner.run_all(_world(value=1.025, weeks=8), f_replay=None, out=tmp_path / "r", min_stake_pln=0.50,
                   commit="test", observed_at_rule="x", specs=_specs("A", "C"))  # fmt: skip
    for name in ("simulate", "tax_for_multi", "fair_prices", "from_journal"):
        assert calls.get(name, 0) > 0, name


def test_run_specs_follow_the_frozen_plan() -> None:
    runner = _runner()
    specs = runner.run_specs(capital=10_000.0, with_f=True)
    main = {s.name for s in specs if s.main}
    assert main == {"A", "A3", "B365", "B-BW", "B-WH", "C", "D", "E", "F"}
    names = {s.name for s in specs}
    assert {"C-udział-kupony", "A@1000zł", "C@1000zł", "A-bez-wyłącznika", "C-bez-wyłącznika"} <= names
    assert {f"A@θ{t:.2f}" for t in (0.01, 0.03, 0.05)} <= names
    assert all(s.theta == 0.02 for s in specs if s.main)
    small = [s for s in specs if s.name.endswith("1000zł")]
    assert all(s.capital == 1000.0 for s in small)


def test_verdict_and_recommendation_follow_section_six() -> None:
    runner = _runner()

    def summary(low: float | None, high: float | None, y: float) -> dict[str, Any]:
        return {"aggregate": {"yield_": y, "clv": {"ci_low": low, "ci_high": high}}}

    assert runner.clv_verdict(summary(0.001, 0.02, 0.01)) == "POTWIERDZONA"
    assert runner.clv_verdict(summary(-0.03, -0.001, 0.01)) == "OBALONA"
    assert runner.clv_verdict(summary(-0.01, 0.02, 0.05)) == "NIEPOTWIERDZONA"
    assert runner.clv_verdict(summary(None, None, 0.05)).startswith("NIEPOTWIERDZONA")
    assert runner.recommendation("POTWIERDZONA", "POTWIERDZONA").startswith("A i C POTWIERDZONE")
    assert "nieuzasadniony" in runner.recommendation("POTWIERDZONA", "NIEPOTWIERDZONA")


def test_without_alarms_the_report_has_the_three_part_verdict(tmp_path: Path) -> None:
    runner = _runner()

    def summary(name: str, *, profit: float, y: float, main: bool = True) -> dict[str, Any]:
        m = {"yield_": y, "profit": profit, "clv": {"ci_low": 0.001, "ci_high": 0.02}}
        return {"spec": {"main": main, "name": name, "strategy": name.split("@")[0], "alarm": name != "E" and main},
                "aggregate": m, "groups": {"najwyższe": m}, "reconcile": {"ok": True}}  # fmt: skip

    ok = {"A": summary("A", profit=10.0, y=0.03), "C": summary("C", profit=5.0, y=0.02),
          "D": summary("D", profit=-50.0, y=-0.09), "E": summary("E", profit=999.0, y=0.5)}  # fmt: skip
    assert runner.alarms(ok) == []  # E (Max) nie uruchamia alarmu
    bad_recon = {**ok, "A": {**ok["A"], "reconcile": {"ok": False}}}
    assert runner.alarms(bad_recon) == ["A: kapitał symulatora ≠ reconcile_bets.py"]
    sensitivity = {**ok, "A@θ0.01": summary("A@θ0.01", profit=1.0, y=0.5, main=False)}
    assert runner.alarms(sensitivity) == []  # przebieg bez flagi ``alarm`` — tylko raport


def test_run_spec_flags_are_required_and_alarm_follows_the_flag() -> None:
    """POWAŻNE 3 (reguła 30): ``main`` i ``alarm`` bez wartości domyślnej; alarm
    yieldu z flagi przebiegu, nie z białej listy nazw."""
    runner = _runner()
    with pytest.raises(TypeError):
        runner.RunSpec("A", "table", "A", 0.02, 10_000.0)

    def summary(name: str, *, y: float, main: bool, alarm: bool) -> dict[str, Any]:
        m = {"yield_": y, "profit": 1.0, "clv": {"ci_low": 0.0, "ci_high": 0.0}}
        return {"spec": {"main": main, "alarm": alarm, "name": name, "strategy": name},
                "aggregate": m, "groups": {}, "reconcile": {"ok": True}}  # fmt: skip

    assert runner.alarms({"Nowa": summary("Nowa", y=0.20, main=True, alarm=True)})
    assert runner.alarms({"E": summary("E", y=0.50, main=True, alarm=False)}) == []
    specs = runner.run_specs(capital=10_000.0, with_f=True)
    assert {s.name for s in specs if s.alarm} >= {"A", "A3", "B365", "B-BW", "B-WH", "C", "D", "F"}
    assert not next(s for s in specs if s.name == "E").alarm
