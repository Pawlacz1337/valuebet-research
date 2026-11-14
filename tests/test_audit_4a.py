"""Regresje audytu 4a (``reports/backtest_fin/5831a92/AUDIT_4a.md``), decyzje 2026-10-10.

- A4a-01: kurs miękki bez kontroli wiarygodności — reguła (a) booksum
  bukmachera < 1.00 → bukmacher poza best-of (bez E/``max``), reguła (b)
  EV przy 1.00 względem Pinnacle > 0.50 → zakład odrzucony. Progi zamrożone
  2026-10-10, przed jakimkolwiek wynikiem; tylko migawka decyzyjna.
- FSA4a-01: podatek strategii z jednego obiektu; niezgodna para selektor/run
  → wyjątek. D = zakłady A rozliczone przy 0.88 (kontrola podatku).
- FSA4a-02: trucizny 4b/4c porównują listy POSTAWIONYCH zakładów.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from helpers.fin_world import WorldMatch, build_replay
from valuebet.backtest.financial import (
    MAX_PLAUSIBLE_EV,
    MIN_SOFT_BOOKSUM,
    REJECT_BOOKSUM,
    REJECT_EV,
    DecisionContext,
    kelly_staker,
    run,
    threshold_selector,
)
from valuebet.backtest.replay import Replay
from valuebet.pricing.fair import FairPrice, FairPricing, MarketQuote

INGESTED = datetime(2026, 10, 10, 22, 0, tzinfo=UTC)
OUTCOMES = ("home", "draw", "away")
B365 = {"1x2": ("bet365",)}
A_BOOKS = {"1x2": ("bet365", "betandwin")}


def _replay(books: dict[str, tuple[float, float, float]], *, home: int = 1, away: int = 0) -> Replay:
    """Jeden mecz E0; ``books`` = kursy 1X2 miękkich bukmacherów w migawce decyzyjnej."""
    base = build_replay([WorldMatch("m1", (0.5, 0.3, 0.2), (1.01, 1.01, 1.01), home, away)])
    (match,) = base.matches
    decision = {"pinnacle": match.decision["pinnacle"]}
    for book, odds in books.items():
        decision[book] = (MarketQuote("m1", "1x2", OUTCOMES, odds, match.observed_at),)
    return replace(base, matches=(replace(match, decision=decision),))


def _ctx(replay: Replay, p: tuple[float, float, float] = (0.5, 0.3, 0.2)) -> DecisionContext:
    """Kontekst z DOKŁADNYMI ``p`` (bez rundy Shina) — granice reguł co do bitu."""
    (match,) = replay.matches
    prices = [
        FairPrice("m1", "1x2", outcome, prob, match.observed_at)
        for outcome, prob in zip(OUTCOMES, p, strict=True)
    ]
    return DecisionContext(match.decision_at, replay.matches, FairPricing(prices=prices, skipped=Counter()))


def _select(
    books: dict[str, tuple[str, ...]],
    ctx: DecisionContext,
    *,
    rejected: Counter[tuple[str, str, str]] | None = None,
    margin_check: bool = True,
) -> list[tuple[str, str, float]]:
    select = threshold_selector(
        books=books, tax_factor=1.0, edge_threshold=0.02, require_complete=True,
        excluded=Counter(), rejected=Counter() if rejected is None else rejected,
        margin_check=margin_check,
    )  # fmt: skip
    return [(c.outcome, c.bookmaker, c.odds) for c in select(ctx)]


# -- A4a-01 ------------------------------------------------------------------


def test_a4a01_typo_15_instead_of_1_50_is_rejected() -> None:
    """Literówka ``B365H`` 15.0 zamiast 1.50 (repro audytora): EV +875% nie jest okazją."""
    p = (0.65, 0.2, 0.15)
    fair = tuple(0.97 / x for x in p)
    typo = (15.0, fair[1], fair[2])
    ctx = _ctx(_replay({"bet365": typo}), p)
    rejected: Counter[tuple[str, str, str]] = Counter()
    assert _select(B365, ctx, rejected=rejected) == []
    assert rejected == Counter({("E0", "2324", REJECT_BOOKSUM): 1})
    # Bez reguły (a) (jak E) literówkę zatrzymuje reguła (b): EV +875% > 0.50.
    rejected_b: Counter[tuple[str, str, str]] = Counter()
    assert _select(B365, ctx, rejected=rejected_b, margin_check=False) == []
    assert rejected_b == Counter({("E0", "2324", REJECT_EV): 1})


def test_a4a01_bookmaker_with_booksum_098_drops_out_of_best_of() -> None:
    """B365 z ujemną marżą (booksum ≈ 0.975) wypada; najlepszy kurs bierze się z BW."""
    b365 = (2.12, 3.3, 5.0)  # booksum 0.9747, home EV +6%
    bw = (2.06, 3.2, 4.6)  # booksum 1.0154, home EV +3%
    assert sum(1 / k for k in b365) < 1.0 < sum(1 / k for k in bw)
    ctx = _ctx(_replay({"bet365": b365, "betandwin": bw}))
    rejected: Counter[tuple[str, str, str]] = Counter()
    assert _select(A_BOOKS, ctx, rejected=rejected) == [("home", "betandwin", 2.06)]
    # Raz na mecz i regułę, choć selektor ogląda trzy wyniki rynku.
    assert rejected == Counter({("E0", "2324", REJECT_BOOKSUM): 1})
    # Jedyny bukmacher odrzucony → brak zakładu.
    assert _select(B365, _ctx(_replay({"bet365": b365}))) == []


def test_a4a01_ev_030_passes_and_ev_055_is_rejected() -> None:
    ok = (2.6, 2.5, 4.6)  # home EV +30%, booksum 1.002
    bad = (3.1, 2.0, 5.0)  # home EV +55%, booksum 1.023
    assert sum(1 / k for k in ok) >= 1.0 and sum(1 / k for k in bad) >= 1.0
    assert _select(B365, _ctx(_replay({"bet365": ok}))) == [("home", "bet365", 2.6)]
    rejected: Counter[tuple[str, str, str]] = Counter()
    assert _select(B365, _ctx(_replay({"bet365": bad})), rejected=rejected) == []
    assert rejected == Counter({("E0", "2324", REJECT_EV): 1})


def test_a4a01_boundaries_are_inclusive_exactly() -> None:
    """booksum dokładnie 1.00 zostaje; EV dokładnie 0.50 zostaje (reguły: < 1.00, > 0.50)."""
    edge = (2.0, 4.0, 4.0)  # 0.5 + 0.25 + 0.25 == 1.0; draw EV = 0.3·4 - 1 = 0.2
    assert sum(1 / k for k in edge) == 1.0
    assert _select(B365, _ctx(_replay({"bet365": edge}))) == [("draw", "bet365", 4.0)]
    fifty = (3.0, 2.0, 5.0)  # home EV = 0.5·3 - 1 == 0.5 dokładnie; booksum 1.033
    assert 0.5 * 3.0 - 1 == 0.5
    assert _select(B365, _ctx(_replay({"bet365": fifty}))) == [("home", "bet365", 3.0)]
    assert MIN_SOFT_BOOKSUM == 1.00 and MAX_PLAUSIBLE_EV == 0.50  # zamrożone 2026-10-10


def test_a4a01_e_max_column_skips_rule_a_but_not_rule_b() -> None:
    """E (``max``): kolumna Max to nie kwotowanie jednego bukmachera — bez reguły (a)."""
    from valuebet.backtest.strategies import STRATEGIES, selector_for

    max_odds = (2.12, 3.3, 5.0)  # booksum 0.975 — normalne dla maksimum rynku
    ctx = _ctx(_replay({"max": max_odds}))
    rejected: Counter[tuple[str, str, str]] = Counter()
    select = selector_for(STRATEGIES["E"], edge_threshold=0.02, excluded=Counter(), rejected=rejected)
    assert [(c.outcome, c.odds) for c in select(ctx)] == [("home", 2.12)]
    assert not rejected
    bad = _ctx(_replay({"max": (3.1, 2.0, 5.0)}))
    assert select(bad) == []
    assert rejected == Counter({("E0", "2324", REJECT_EV): 1})


def test_a4a01_rules_use_only_the_decision_snapshot() -> None:
    """Trucizna: inne zamknięcie i inny wynik → te same odrzucenia i ci sami kandydaci."""
    books = {"bet365": (2.12, 3.3, 5.0), "betandwin": (3.1, 2.0, 5.0)}
    base = _replay(books, home=1, away=0)
    (match,) = base.matches
    noisy_close = {"pinnacle": (MarketQuote("m1", "1x2", OUTCOMES, (9.0, 1.2, 9.0), match.closing_at),)}
    poisoned = replace(
        base,
        matches=(replace(match, closing=noisy_close),),
        results={"m1": replace(base.results["m1"], home_goals=0, away_goals=3)},
    )
    out = []
    for replay in (base, poisoned):
        rejected: Counter[tuple[str, str, str]] = Counter()
        out.append((_select(A_BOOKS, _ctx(replay), rejected=rejected), rejected))
    assert out[0] == out[1]
    assert out[0][1] == Counter({("E0", "2324", REJECT_BOOKSUM): 1, ("E0", "2324", REJECT_EV): 1})


# -- FSA4a-01 ----------------------------------------------------------------


def test_fsa4a01_mismatched_selector_and_settlement_tax_raise(tmp_path: Path) -> None:
    """Selektor przy 1.00 i rozliczenie przy 0.88 bez deklaracji strategii → błąd."""
    replay = _replay({"bet365": (2.2, 3.0, 4.5)})
    select = threshold_selector(books=B365, tax_factor=1.0, edge_threshold=0.02,
                                require_complete=True, excluded=Counter(),
                                rejected=Counter(), margin_check=True)  # fmt: skip
    with pytest.raises(ValueError, match="podatek"):
        run(replay, selector=select, staker=kelly_staker, selection_tax_factor=0.88,
            settlement_tax_factor=0.88, journal_path=tmp_path / "b.csv", run_id="x",
            start_capital=10_000.0, ingested_at=INGESTED, min_stake_pln=0.50)  # fmt: skip
    # C: nogi value wybiera się przy 1.00 — selektor przy 0.88 to błąd.
    from valuebet.backtest.strategy_c import counterfactual_regime_config, run_regime

    taxed = threshold_selector(books=B365, tax_factor=0.88, edge_threshold=0.02,
                               require_complete=True, excluded=Counter(),
                               rejected=Counter(), margin_check=True)  # fmt: skip
    (match,) = replay.matches
    with pytest.raises(ValueError, match="podatku"):
        run_regime(replay, selector=taxed, staker=kelly_staker,
                   regime_config=counterfactual_regime_config(start=match.decision_at, share_basis="stakes", min_stake_pln=0.50),
                   edge_threshold=0.02, single_mode="production", journal_path=tmp_path / "c.csv",
                   run_id="c", start_capital=10_000.0, ingested_at=INGESTED, min_stake_pln=0.50)  # fmt: skip


def test_fsa4a01_d_selects_the_same_bets_as_a() -> None:
    """Decyzja 2026-10-10: D = zakłady wybrane przy 1.00 (te same co A), rozliczone przy 0.88."""
    from valuebet.backtest.strategies import STRATEGIES, selector_for

    ctx = _ctx(_replay({"bet365": (2.12, 3.0, 4.5), "betandwin": (2.10, 3.0, 4.5)}))
    picks = {}
    for name in ("A", "D"):
        select = selector_for(STRATEGIES[name], edge_threshold=0.02, excluded=Counter(), rejected=Counter())
        picks[name] = [(c.outcome, c.bookmaker, c.odds) for c in select(ctx)]
    assert picks["A"] == [("home", "bet365", 2.12)]
    assert picks["D"] == picks["A"]


def test_fsa4a01_run_strategy_d_places_a_bets_and_settles_them_at_088(tmp_path: Path) -> None:
    """D przez ``run_strategy``: te same zakłady i stawki co A, w dzienniku 0.88, wypłata x0.88."""
    from valuebet.backtest.strategies import STRATEGIES, run_strategy
    from valuebet.live.bets import BetJournal

    replay = _replay({"bet365": (2.12, 3.0, 4.5), "betandwin": (2.10, 3.0, 4.5)})
    out = {}
    for name in ("A", "D"):
        result = run_strategy(
            replay, strategy=STRATEGIES[name], staker=kelly_staker, edge_threshold=0.02,
            excluded=Counter(), rejected=Counter(), journal_path=tmp_path / f"{name}.csv",
            run_id=name, start_capital=10_000.0, ingested_at=INGESTED, min_stake_pln=0.50,
        )  # fmt: skip
        (bet,) = [r for r in BetJournal(journal_path=tmp_path / f"{name}.csv").read() if not r.is_settlement]
        out[name] = (bet, result)
    (a, ra), (d, rd) = out["A"], out["D"]
    assert (d.match_id, d.outcome, d.odds_taken, d.stake) == (a.match_id, a.outcome, a.odds_taken, a.stake)
    assert (a.tax_factor_applied, d.tax_factor_applied) == (1.0, 0.88)
    # home wygrywa: A dostaje stawka·k, D stawka·k·0.88.
    assert ra.cash == pytest.approx(10_000 - a.stake + round(a.stake * 2.12, 2))
    assert rd.cash == pytest.approx(10_000 - d.stake + round(d.stake * 2.12 * 0.88, 2))
    # Stawka D liczona przy podatku wyboru (1.00) — zapis dla sprawdzarki Kelly'ego.
    assert rd.stake_inputs[d.coupon_id][3] == 1.0


# -- FSA4a-02 ----------------------------------------------------------------


def _gate_with_broken_staker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, broken: Any) -> dict[str, Any]:
    """Szybka bramka (sztuczny terminarz) z silnikiem, który pomija kandydatów wg ``broken``."""
    from test_engine_gate import _script
    from valuebet.pricing.kelly import StakeDecision

    script = _script()
    worlds: list[Any] = []
    real_build = script.build_world

    def capture(*args: Any, **kwargs: Any) -> Any:
        world = real_build(*args, **kwargs)
        worlds.append(world)
        return world

    def staker(ctx: Any) -> StakeDecision:
        decision = kelly_staker(ctx)
        if broken(ctx.candidate, worlds[-1]):
            return replace(decision, stake=0.0, fraction=0.0)
        return decision

    monkeypatch.setattr(script, "build_world", capture)
    monkeypatch.setattr(script, "kelly_staker", staker)
    truth = script.synthetic_truth(weeks=8, per_week=6, seed=11)
    checks = script.gate(truth, seeds=range(2), workdir=tmp_path)
    # klucz do spacji: "4b" (A) i "4b-C" (C) to różne testy (wariant B, 2026-10-11)
    return {c.name.split(" ")[0]: c for c in checks}


def test_fsa4a02_engine_skipping_losing_longshots_turns_4b_red(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mutacja M6 audytora: kupon przy k ≥ 3, który przegra, nie jest stawiany."""
    from valuebet.backtest.financial import leg_result

    def by_result(c: Any, world: Any) -> bool:
        if c.odds < 3.0 or "+" in c.match_id:  # widok dubletu C ("a+b") — mutacja dotyczy singli
            return False
        result = world.results[c.match_id]
        return leg_result(market=c.market, outcome=c.outcome, line=c.line, result=result) == "lost"

    checks = _gate_with_broken_staker(tmp_path, monkeypatch, by_result)
    assert not checks["4b"].passed, checks["4b"].detail


def test_fsa4a02_engine_that_bets_differently_with_the_future_turns_4c_red(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Silnik, który w PEŁNYM przebiegu pomija kandydatów (bo widzi mecze po D),
    a w uciętym nie: decyzje do D różnią się w obie strony — 4c ma to zobaczyć."""
    full: dict[str, int] = {}

    def by_future(c: Any, world: Any) -> bool:
        n = len(world.matches)
        full["max"] = max(full.get("max", 0), n)
        return n == full["max"] and c.outcome == "draw"

    checks = _gate_with_broken_staker(tmp_path, monkeypatch, by_future)
    assert not checks["4c"].passed, checks["4c"].detail


def test_a4a01_run_strategy_has_rule_a_on_in_production(tmp_path: Path) -> None:
    """Przebieg produkcyjny (``run_strategy``) ma regułę (a) włączoną: B365 z ujemną
    marżą i value nie daje zakładu w B365-single, a w A wypada z best-of (BW zostaje);
    E (``max``) — reguła (a) wyłączona z tabeli."""
    from valuebet.backtest.strategies import STRATEGIES, run_strategy
    from valuebet.live.bets import BetJournal

    b365 = (2.12, 3.3, 5.0)  # booksum 0.975, home EV +6%
    bw = (2.06, 3.2, 4.6)  # booksum 1.015, home EV +3%
    cases = {
        "B365": (_replay({"bet365": b365}), []),
        "A": (_replay({"bet365": b365, "betandwin": bw}), [("home", "betandwin", 2.06)]),
        "E": (_replay({"max": b365}), [("home", "max", 2.12)]),
    }
    for name, (replay, expected) in cases.items():
        rejected: Counter[tuple[str, str, str]] = Counter()
        path = tmp_path / f"{name}.csv"
        run_strategy(
            replay, strategy=STRATEGIES[name], staker=kelly_staker, edge_threshold=0.02,
            excluded=Counter(), rejected=rejected, journal_path=path, run_id=name,
            start_capital=10_000.0, ingested_at=INGESTED, min_stake_pln=0.50,
        )  # fmt: skip
        bets = [r for r in BetJournal(journal_path=path).read() if not r.is_settlement] if path.exists() else []
        assert [(b.outcome, b.bookmaker, b.odds_taken) for b in bets] == expected, name
        assert rejected == (Counter() if name == "E" else Counter({("E0", "2324", REJECT_BOOKSUM): 1})), name
