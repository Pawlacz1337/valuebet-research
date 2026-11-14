"""Strategie Filaru 1 — definicje zamrożone przed wynikiem (BACKTEST_FIN_PLAN §3).

Decyzja Pawła 2026-10-08, dosłownie: „A = najlepszy z B365 i BW tylko dla
meczów z kompletem obu, reszta wyłączona z licznikiem per liga i sezon; WH
poza A; osobno A3 i B365-single.” O/U: w plikach jedynym miękkim jest B365
(§3) — O/U idzie przez B365 we wszystkich strategiach poza E.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from helpers.fin_world import WorldMatch, build_replay
from valuebet.backtest.financial import DecisionContext
from valuebet.backtest.replay import Replay
from valuebet.backtest.strategies import STRATEGIES, selector_for
from valuebet.pricing.fair import MarketQuote, fair_prices

P = (0.5, 0.3, 0.2)
OUTCOMES = ("home", "draw", "away")


def _world(books: dict[str, tuple[float, float, float]]) -> Replay:
    """Jeden mecz; ``books`` = kursy 1X2 miękkich bukmacherów (bez B365 → brak B365)."""
    base = build_replay([WorldMatch("m1", P, (1.01, 1.01, 1.01), 2, 0)])
    (match,) = base.matches
    decision = {"pinnacle": match.decision["pinnacle"]}
    for book, odds in books.items():
        decision[book] = (MarketQuote("m1", "1x2", OUTCOMES, odds, match.observed_at),)
    return replace(base, matches=(replace(match, decision=decision),))


def _pick(name: str, replay: Replay) -> tuple[list[tuple[str, str, float]], Counter[tuple[str, str, str]]]:
    (match,) = replay.matches
    t = match.decision_at
    pricing = fair_prices(match.decision["pinnacle"], decision_time=t, kickoffs={"m1": match.kickoff})
    excluded: Counter[tuple[str, str, str]] = Counter()
    select = selector_for(STRATEGIES[name], edge_threshold=0.02, excluded=excluded, rejected=Counter())
    picked = select(DecisionContext(t, replay.matches, pricing))
    return [(c.outcome, c.bookmaker, round(c.odds, 4)) for c in picked], excluded


def test_strategy_table_matches_the_decision() -> None:
    a = STRATEGIES["A"]
    assert a.books == {"1x2": ("bet365", "betandwin"), "over_under": ("bet365",)}
    assert a.require_complete is True
    assert (a.selection_tax, a.settlement_tax) == (1.0, 1.0)
    assert STRATEGIES["A3"].books["1x2"] == ("bet365", "betandwin", "williamhill")
    assert STRATEGIES["B365"].books == {"1x2": ("bet365",), "over_under": ("bet365",)}
    assert STRATEGIES["D"].books == a.books
    # Decyzja 2026-10-10 (audyt 4a): D = zakłady A rozliczone przy 0.88.
    assert (STRATEGIES["D"].selection_tax, STRATEGIES["D"].settlement_tax) == (1.0, 0.88)
    assert STRATEGIES["E"].margin_check is False
    assert all(s.margin_check for n, s in STRATEGIES.items() if n != "E")
    assert STRATEGIES["E"].books == {"1x2": ("max",), "over_under": ("max",)}


def test_a_takes_the_better_of_b365_and_bw() -> None:
    world = _world({"bet365": (2.06, 3.0, 4.5), "betandwin": (2.10, 3.0, 4.5)})
    picked, excluded = _pick("A", world)
    assert picked == [("home", "betandwin", 2.10)]
    assert not excluded


def test_a_excludes_match_without_both_books_and_counts_it() -> None:
    """BW bez kompletu → mecz poza A, nawet gdy B365 ma value; licznik per liga, sezon."""
    world = _world({"bet365": (2.20, 3.0, 4.5)})
    picked, excluded = _pick("A", world)
    assert picked == []
    assert excluded == Counter({("E0", "2324", "1x2: brak kompletu betandwin"): 1})
    # B365-single gra ten sam mecz.
    single, _ = _pick("B365", world)
    assert single == [("home", "bet365", 2.20)]


def test_williamhill_is_outside_a_but_inside_a3() -> None:
    world = _world({"bet365": (2.0, 3.0, 4.5), "betandwin": (2.0, 3.0, 4.5), "williamhill": (2.2, 3.0, 4.5)})
    a, _ = _pick("A", world)
    assert a == []
    a3, _ = _pick("A3", world)
    assert a3 == [("home", "williamhill", 2.2)]
    # A3 bez WH → wyłączony z licznikiem.
    no_wh = _world({"bet365": (2.2, 3.0, 4.5), "betandwin": (2.0, 3.0, 4.5)})
    picked, excluded = _pick("A3", no_wh)
    assert picked == []
    assert excluded[("E0", "2324", "1x2: brak kompletu williamhill")] == 1
