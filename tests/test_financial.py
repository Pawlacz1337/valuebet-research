"""``backtest/financial.py`` — pętla zdarzeń na modułach live, liczby policzone ręcznie."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from helpers.fin_world import T0, WorldMatch, build_replay
from valuebet.backtest.financial import (
    Candidate,
    DecisionContext,
    RunResult,
    Selector,
    StakeContext,
    Staker,
    kelly_staker,
    leg_result,
    run,
    tagged_selector,
    threshold_selector,
)
from valuebet.backtest.replay import MatchResult
from valuebet.live.bets import BetJournal
from valuebet.pricing.kelly import StakeDecision

INGESTED = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
B365 = {"1x2": ("bet365",), "over_under": ("bet365",)}
P = (0.5, 0.3, 0.2)
#: home value (EV +5%), draw i away poniżej progu.
SOFT = (1.05 / 0.5, 0.9 / 0.3, 0.9 / 0.2)


def _run(
    tmp_path: Path,
    world: list[WorldMatch],
    *,
    selector: Selector | None = None,
    staker: Staker = kelly_staker,
) -> RunResult:
    return run(
        build_replay(world),
        selector=selector
        or threshold_selector(books=B365, tax_factor=1.0, edge_threshold=0.02, require_complete=True, excluded=Counter(), rejected=Counter(), margin_check=False),
        staker=staker,
        selection_tax_factor=1.0,
        settlement_tax_factor=1.0,
        journal_path=tmp_path / "bets.csv",
        run_id="t",
        start_capital=10_000.0,
        ingested_at=INGESTED,
        min_stake_pln=0.50,
    )


@pytest.mark.parametrize(
    ("market", "outcome", "goals", "expected"),
    [
        ("1x2", "home", (2, 0), "won"),
        ("1x2", "draw", (2, 0), "lost"),
        ("1x2", "draw", (1, 1), "won"),
        ("1x2", "away", (0, 3), "won"),
        ("over_under", "over", (2, 1), "won"),
        ("over_under", "under", (2, 1), "lost"),
        ("over_under", "under", (1, 1), "won"),
        ("1x2", "home", (None, None), "void"),
    ],
)
def test_leg_result(
    market: str, outcome: str, goals: tuple[int | None, int | None], expected: str
) -> None:
    result = MatchResult("m", goals[0], goals[1], T0)
    line = 2.5 if market == "over_under" else None
    assert leg_result(market=market, outcome=outcome, line=line, result=result) == expected


def test_single_value_bet_by_hand(tmp_path: Path) -> None:
    result = _run(tmp_path, [WorldMatch("m1", P, SOFT, 2, 0)])
    rows = BetJournal(journal_path=tmp_path / "bets.csv").read()
    bets = [r for r in rows if not r.is_settlement]
    assert [(b.match_id, b.outcome) for b in bets] == [("m1", "home")]
    bet = bets[0]
    # f* = (0.5·2.1 - 1)/(2.1 - 1) = 0.0454…; c = ¼ → 1.136% < 2%.
    assert bet.stake == pytest.approx(113.64)
    assert bet.mode == "real"
    assert bet.placed_at == T0 + timedelta(minutes=1)
    assert bet.snapshot_observed_at == T0
    assert bet.source == "backtest:t"
    assert bet.p_fair_at_bet == pytest.approx(0.5, abs=1e-9)
    # Wygrana: 10000 - 113.64 + round(113.64 · 2.1, 2).
    assert result.cash == pytest.approx(10_000 - 113.64 + 238.64)
    assert result.n_coupons == 1
    # CLV = k · p_close - 1 = 2.1 · 0.5 - 1 (zamknięcie = p_true).
    assert result.clv.mean == pytest.approx(0.05, abs=1e-6)


def test_lost_and_void_bets_move_cash_correctly(tmp_path: Path) -> None:
    lost = _run(tmp_path / "a", [WorldMatch("m1", P, SOFT, 0, 1)])
    assert lost.cash == pytest.approx(10_000 - 113.64)
    void = _run(tmp_path / "b", [WorldMatch("m1", P, SOFT, None, None)])
    assert void.cash == pytest.approx(10_000.0)


def test_match_limit_binds_across_outcomes_of_one_match(tmp_path: Path) -> None:
    """Dwa wyniki jednego meczu z dużą przewagą: 2% + reszta do 3% na mecz."""
    p = (0.4, 0.3, 0.3)
    # EV 45%, nie 50%: reguła (b) A4a-01 odrzuca EV > 0.50, a 1.5/0.4 po rundzie Shina wychodzi tuż ponad próg.
    soft = (1.45 / 0.4, 1.4 / 0.3, 0.9 / 0.3)
    _run(tmp_path, [WorldMatch("m1", p, soft, 1, 0)])
    bets = [r for r in BetJournal(journal_path=tmp_path / "bets.csv").read() if not r.is_settlement]
    stakes = sorted(b.stake for b in bets)
    assert stakes == pytest.approx([100.0, 200.0])


def test_settlement_before_next_decision_feeds_capital(tmp_path: Path) -> None:
    later = T0 + timedelta(days=4)
    world = [
        WorldMatch("m1", P, SOFT, 2, 0),
        WorldMatch("m2", P, SOFT, 2, 0, observed_at=later, kickoff=later + timedelta(hours=2)),
    ]
    _run(tmp_path, world)
    bets = [r for r in BetJournal(journal_path=tmp_path / "bets.csv").read() if not r.is_settlement]
    # Druga stawka liczona od 10125.00, nie od 10000.
    assert bets[1].stake == pytest.approx(round(0.25 * 0.05 / 1.1 * 10_125.0, 2))


def test_placebo_selector_and_flat_stake_are_injectable(tmp_path: Path) -> None:
    def every(ctx: DecisionContext) -> list[Candidate]:
        soft = {m.match_id: m.decision["bet365"][0] for m in ctx.matches}
        return [
            Candidate(p.match_id, p.market, p.outcome, p.line, p.p,
                      soft[p.match_id].odds[soft[p.match_id].outcomes.index(p.outcome)],
                      "bet365", p.observed_at)
            for p in ctx.fair.prices
        ]  # fmt: skip

    def flat(ctx: StakeContext) -> StakeDecision:
        return StakeDecision(
            fraction=0.01, stake=10.0, mode="real", kelly_full=0.0, c=0.25, reasons=(),
            gk_would_unlock=False, winnings_factor=1.0, ev=0.0,
        )  # fmt: skip

    result = _run(tmp_path, [WorldMatch("m1", P, SOFT, 2, 0)], selector=tagged_selector(every, selection_tax=1.0), staker=flat)
    assert result.n_coupons == 3
    assert result.cash == pytest.approx(10_000 - 30 + 21.0)


def test_run_requires_selector_staker_and_a_fresh_journal(tmp_path: Path) -> None:
    replay = build_replay([WorldMatch("m1", P, SOFT, 2, 0)])
    kwargs: dict[str, object] = {
        "staker": kelly_staker, "selection_tax_factor": 1.0, "settlement_tax_factor": 1.0, "journal_path": tmp_path / "x.csv",
        "run_id": "t", "start_capital": 1.0, "ingested_at": INGESTED, "min_stake_pln": 0.50,
    }  # fmt: skip
    with pytest.raises(TypeError, match="selector"):
        run(replay, **kwargs)
    # min. stawka — wymagana, bez wartości domyślnej (reguła 30, decyzja 2026-10-11)
    no_min = {k: v for k, v in kwargs.items() if k != "min_stake_pln"}
    with pytest.raises(TypeError, match="min_stake_pln"):
        run(replay, selector=tagged_selector(lambda _c: [], selection_tax=1.0), **no_min)
    _run(tmp_path, [WorldMatch("m1", P, SOFT, 2, 0)])
    with pytest.raises(ValueError, match="nowy"):
        _run(tmp_path, [WorldMatch("m1", P, SOFT, 2, 0)])


def test_threshold_selector_keeps_only_odds_at_or_above_k_min() -> None:
    """EV dodatnie, ale poniżej θ, NIE przechodzi — progu nie zastępuje zerowa stawka Kelly'ego."""
    from valuebet.pricing.fair import fair_prices

    # home: EV +1% (< θ = 2%) → odpada; away: EV +3% → zostaje.
    soft = (1.01 / 0.5, 0.9 / 0.3, 1.03 / 0.2)
    replay = build_replay([WorldMatch("m1", P, soft, 2, 0)])
    (match,) = replay.matches
    t = match.decision_at
    pricing = fair_prices(match.decision["pinnacle"], decision_time=t, kickoffs={"m1": match.kickoff})
    select = threshold_selector(books=B365, tax_factor=1.0, edge_threshold=0.02, require_complete=True, excluded=Counter(), rejected=Counter(), margin_check=False)
    picked = select(DecisionContext(t, replay.matches, pricing))
    assert [(c.outcome, round(c.odds, 4)) for c in picked] == [("away", 5.15)]
    # Przy podatku 0.88 nic nie przechodzi.
    taxed = threshold_selector(books=B365, tax_factor=0.88, edge_threshold=0.02, require_complete=True, excluded=Counter(), rejected=Counter(), margin_check=False)
    assert taxed(DecisionContext(t, replay.matches, pricing)) == []


def test_limits_bind_paper_bets_after_the_drawdown_switch(tmp_path: Path) -> None:
    """Po wyłączniku 25% kupony paper też podlegają limitom 3%/15% (jak w live:
    ``open_stake`` liczy wszystkie otwarte kupony). Regresja z bramki §4
    2026-10-08: 285 naruszeń „mecz > 3%” po przełączeniu w paper."""
    p = (0.4, 0.3, 0.3)
    # EV 45%, nie 50%: reguła (b) A4a-01 odrzuca EV > 0.50, a 1.5/0.4 po rundzie Shina wychodzi tuż ponad próg.
    soft = (1.45 / 0.4, 1.4 / 0.3, 0.9 / 0.3)  # home i draw z dużą przewagą
    world = []
    for week in range(2):  # dwa tygodnie przegranych: 15% + 15% kapitału
        at = T0 + timedelta(days=7 * week)
        for i in range(6):
            world.append(WorldMatch(f"w{week}-{i}", p, soft, 0, 2, observed_at=at,
                                    kickoff=at + timedelta(hours=20)))  # fmt: skip
    at = T0 + timedelta(days=14)
    world.append(WorldMatch("paper", p, soft, 0, 2, observed_at=at, kickoff=at + timedelta(hours=20)))
    result = _run(tmp_path, world)
    bets = [r for r in BetJournal(journal_path=tmp_path / "bets.csv").read() if not r.is_settlement]
    last = [b for b in bets if b.match_id == "paper"]
    assert last and all(b.mode == "paper" for b in last)
    capital = result.bankroll_at[last[0].bet_id]
    assert sum(b.stake for b in last) <= 0.03 * capital + 0.01


def _flat_at(amount: float) -> Staker:
    def flat(_ctx: StakeContext) -> StakeDecision:
        return StakeDecision(
            fraction=0.0, stake=amount, mode="real", kelly_full=0.0, c=0.25, reasons=(),
            gk_would_unlock=False, winnings_factor=1.0, ev=0.0,
        )  # fmt: skip

    return flat


def test_stake_below_min_stake_is_skipped_with_a_counter_never_rounded_up(tmp_path: Path) -> None:
    """Decyzja Pawła 2026-10-11 (T12, Betclic pkt 3.1): stawka < 0,50 zł → zakład
    POMINIĘTY z licznikiem, nie zaokrąglony w górę — we wszystkich strategiach."""
    from valuebet.backtest.financial import SKIP_BELOW_MIN_STAKE

    world = [WorldMatch("m1", P, SOFT, 2, 0)]
    low = _run(tmp_path / "low", world, staker=_flat_at(0.49))
    assert low.n_coupons == 0
    assert low.skipped[SKIP_BELOW_MIN_STAKE] == 1
    assert not (tmp_path / "low" / "bets.csv").exists() or not [
        r for r in BetJournal(journal_path=tmp_path / "low" / "bets.csv").read() if not r.is_settlement
    ]
    ok = _run(tmp_path / "ok", world, staker=_flat_at(0.50))
    (bet,) = [r for r in BetJournal(journal_path=tmp_path / "ok" / "bets.csv").read() if not r.is_settlement]
    assert bet.stake == 0.50
    assert ok.skipped[SKIP_BELOW_MIN_STAKE] == 0


def test_min_stake_check_is_one_function_for_live_and_backtest() -> None:
    """Reguła 28: jedno porównanie z min. stawką w ``pricing.kelly`` (live i backtest)."""
    from valuebet.pricing.kelly import meets_min_stake

    assert meets_min_stake(0.50, min_stake_pln=0.50)
    assert not meets_min_stake(0.49, min_stake_pln=0.50)
    for bad in (0.0, -1.0, float("nan")):
        with pytest.raises(ValueError, match="min_stake_pln"):
            meets_min_stake(1.0, min_stake_pln=bad)


def _paper_world() -> list[WorldMatch]:
    """Jak w teście limitów po wyłączniku: dwa tygodnie przegranych, potem kupony paper."""
    p = (0.4, 0.3, 0.3)
    soft = (1.45 / 0.4, 1.4 / 0.3, 0.9 / 0.3)
    world = []
    for week in range(3):
        at = T0 + timedelta(days=7 * week)
        for i in range(6):
            world.append(WorldMatch(f"w{week}-{i}", p, soft, 0, 2, observed_at=at,
                                    kickoff=at + timedelta(hours=20)))  # fmt: skip
    return world


def test_paper_message_is_logged_once_per_run_with_a_counter(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Dopisek Pawła 2026-10-11 (2.5 c): „tryb PAPER” raz na przebieg (było: przy
    każdej stawce, tysiące linii w bramce 17a0759) + licznik w ``RunResult``.
    Logowanie nie zmienia wyników: ten sam przebieg przy DEBUG i przy ERROR."""
    import logging

    with caplog.at_level(logging.DEBUG):
        loud = _run(tmp_path / "a", _paper_world())
    warnings = [r for r in caplog.records if "tryb PAPER" in r.getMessage() and r.levelno >= logging.WARNING]
    assert loud.paper_coupons > 1
    assert len(warnings) == 1
    caplog.clear()
    with caplog.at_level(logging.ERROR):
        quiet = _run(tmp_path / "b", _paper_world())
    assert (quiet.cash, quiet.n_coupons, quiet.paper_coupons) == (loud.cash, loud.n_coupons, loud.paper_coupons)
    rows = [(r.bet_id, r.stake, r.mode) for r in BetJournal(journal_path=tmp_path / "a" / "bets.csv").read()]
    assert rows == [(r.bet_id, r.stake, r.mode) for r in BetJournal(journal_path=tmp_path / "b" / "bets.csv").read()]


def test_ab9_every_dropped_group_has_a_named_reason_from_the_closed_list(tmp_path: Path) -> None:
    """AB-9: odrzucona grupa ma wpis w ``RunResult.dropped_groups`` (przyczyna z listy
    zamkniętej, kapitał i stawka w chwili decyzji, tryb). A: licznik bez zmian."""
    from valuebet.backtest.financial import (
        DROP_BELOW_MIN_STAKE,
        DROP_REASONS,
        SKIP_BELOW_MIN_STAKE,
    )

    low = _run(tmp_path, [WorldMatch("m1", P, SOFT, 2, 0)], staker=_flat_at(0.49))
    (drop,) = low.dropped_groups
    assert drop.reason == DROP_BELOW_MIN_STAKE and drop.reason in DROP_REASONS
    assert (drop.stake, drop.capital, drop.mode, drop.placed_before) == (0.49, 10_000.0, "real", 0)
    assert drop.legs == (("m1", "1x2", "home", SOFT[0]),)
    assert low.skipped[SKIP_BELOW_MIN_STAKE] == 1
