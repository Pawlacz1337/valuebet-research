"""Testy poprawności silnika finansowego — bramka §4 BACKTEST_FIN_PLAN (pkt 1-7).

Uruchamiane **przed** pierwszym przebiegiem strategii. Czerwone → STOP,
bez oglądania wyników strategii. Każdy test idzie przez prawdziwy
``backtest.financial`` — te same moduły co live (reguła 28): strategia A
przez ``run``, strategia C przez ``strategy_c.run_regime`` (wariant B,
decyzja Pawła 2026-10-11: bramka obejmuje C, testy 1-7).

Świat znanej odpowiedzi (§4 pkt 1): prawdziwy terminarz E0 i E1 2022/23-
2023/24 (gwizdki i ``observed_at`` z raw), ``p_true`` = Shin z zamknięcia
Pinnacle (1X2 i O/U 2.5), liczony raz na mecz i wspólny dla nasion. Kursy
Pinnacle w obu migawkach odtworzone z ``p_true`` przez ``shin_forward``
(marża ~2.5%), więc Shin zwraca ``p_true``; wyniki losowane z ``p_true``
(rynki niezależnie — każdy zakład wygrywa z prawdopodobieństwem ``p_true``);
kurs miękki ``(1 + e) / p_true``.

Światy C (``WORLDS``): ``c120`` — mecze, w których każdy kurs miękki przy
``e = 0.025`` jest ≥ 1.20 (każda noga może wejść do dubletu, T6); ``solo`` —
jeden mecz na migawkę decyzyjną, więc dubletów nie ma z konstrukcji
(udział AKO = 0, single po 0.94 — test podatku C).

Wyniki cząstkowe i wznowienie (dopisek Pawła 2026-10-11, po awarii bramki
17a0759): każdy przebieg nasiona zapisywany atomowo do
``reports/backtest_fin/<commit>/partial/``; ``--resume`` pomija gotowe
nasiona tylko przy tym samym commicie, liczbie nasion i parametrach testu.

Użycie::

    uv run python scripts/engine_tests.py --workers 3 --raw-root <repo>/data/raw
    uv run python scripts/engine_tests.py --workers 3 --raw-root <...> --resume
    uv run python scripts/engine_tests.py --seeds 20   # szybciej, NIE jest bramką

Raport: ``reports/backtest_fin/<commit>/ENGINE_TESTS.md`` + ``.json``.
"""

from __future__ import annotations

import argparse
import bisect
import calendar
import itertools
import json
import logging
import math
import multiprocessing
import pickle
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

from valuebet.backtest import financial, strategy_c
from valuebet.backtest.financial import (
    Candidate,
    DecisionContext,
    RunResult,
    StakeContext,
    kelly_staker,
    run,
    tagged_selector,
    threshold_selector,
)
from valuebet.backtest.replay import (
    CLOSING_BEFORE_KICKOFF,
    DECISION_LAG,
    SETTLE_AFTER,
    MatchResult,
    Replay,
    ReplayMatch,
    merge_replays,
    replay_csv,
)
from valuebet.backtest.strategy_c import counterfactual_regime_config, run_regime
from valuebet.config import STRATEGY_PATH, load_strategy
from valuebet.fsutil import write_atomic
from valuebet.ingest.football_data_main import RAW_SUBDIR
from valuebet.ingest.raw_store import RAW_ROOT, RawStore
from valuebet.live.bets import BetJournal, BetRecord, Coupon, coupons
from valuebet.pricing.ev import SHARE_BY_STAKES
from valuebet.pricing.fair import MarketQuote
from valuebet.pricing.kelly import StakeDecision
from valuebet.pricing.shin import (
    ShinNotConvergedError,
    shin_forward,
    shin_probabilities,
)
from valuebet.provenance import frozen_commit, generated_by

log = logging.getLogger("engine_tests")

SCRIPT = Path(__file__)
ROOT = SCRIPT.resolve().parents[1]
FIXTURE_FILES = (("E0", "2223"), ("E0", "2324"), ("E1", "2223"), ("E1", "2324"))
EDGE = 0.025
Z = 0.025
START = 10_000.0
THETA = 0.02
SOFT = "bet365"
INGESTED = datetime(2026, 10, 8, 0, 0, tzinfo=UTC)
#: Minimalna stawka we wszystkich strategiach — ta sama liczba co przebieg
#: produkcyjny (config/strategy.yaml, decyzja Pawła 2026-10-11, T12).
_STRATEGY = load_strategy(ROOT / STRATEGY_PATH)
MIN_STAKE_PLN = _STRATEGY.min_stake_pln
#: Dokładność Shina na round-tripie (``_TOL`` solvera ~1e-12; zapas).
SHIN_TOL = 1e-7
#: Granica „bez granicy” do składania kuponów po zakończeniu przebiegu.
_END = datetime.max.replace(tzinfo=UTC)
MARKETS = (("1x2", ("home", "draw", "away"), None), ("over_under", ("over", "under"), 2.5))

# ---------------------------------------------------------------------------
# NIEZALEŻNY checker reżimu Betclica (test 6 C, 3c C) — WŁASNE literały z
# regulaminu (docs/promocje.md T2-T9, §3 ust. 3-12), celowo bez importu stałych
# ani funkcji reżimu z ``pricing.ev``: literówka w silniku nie może przejść
# bramki dlatego, że sprawdzarka dzieli z nim kod (jak ``CHECKER_LIMITS``).
# ---------------------------------------------------------------------------
REF_LIMIT_PLN = 1000.0  # §3 ust. 3
REF_SHARE = 0.50  # §3 ust. 12: „co najmniej 50%”
REF_MIN_LEG_ODDS = 1.20  # §3 ust. 9
REF_WINDOW_BETS = 5000  # §3 ust. 8
REF_WINDOW_MONTHS = 12  # §3 ust. 8, miesiące kalendarzowe
REF_COUNTERFACTUAL_EXTERNAL = 1000.0  # promocje.md, wariant kontrfaktyczny
_WARSAW = ZoneInfo("Europe/Warsaw")


@dataclass(frozen=True)
class TrueMatch:
    match_id: str
    league: str
    season: str
    kickoff: datetime
    observed_at: datetime
    #: market → p_true (kolejność jak w ``MARKETS``).
    p: dict[str, tuple[float, ...]]


def _shin(odds: Sequence[float]) -> tuple[float, ...] | None:
    try:
        return tuple(float(x) for x in shin_probabilities(list(odds), strict=True).probabilities)
    except (ShinNotConvergedError, ValueError):
        return None


def truth_from_replay(replay: Replay) -> list[TrueMatch]:
    """``p_true`` = Shin z zamknięcia Pinnacle; mecze bez kompletu obu rynków odpadają."""
    out: list[TrueMatch] = []
    for m in replay.matches:
        closing = {q.market: q for q in m.closing.get("pinnacle", ())}
        p = {k: _shin(closing[k].odds) for k, _, _ in MARKETS if k in closing}
        if len(p) == len(MARKETS) and all(v is not None for v in p.values()):
            out.append(TrueMatch(m.match_id, m.league, m.season, m.kickoff, m.observed_at,
                                 {k: v for k, v in p.items() if v is not None}))  # fmt: skip
    return out


def synthetic_truth(*, weeks: int, per_week: int, seed: int) -> list[TrueMatch]:
    """Terminarz zastępczy do szybkich testów pytest (bez raw)."""
    rng = np.random.default_rng(seed)
    start = datetime(2023, 8, 11, 17, 0, tzinfo=UTC)
    out = []
    for w in range(weeks):
        observed = start + timedelta(days=7 * w)
        for i in range(per_week):
            home = float(rng.uniform(0.25, 0.65))
            draw = float(rng.uniform(0.2, 0.3)) * (1 - home) / 0.75
            over = float(rng.uniform(0.4, 0.65))
            out.append(TrueMatch(f"s{w:03d}-{i:02d}", "E0", "2324",
                                 observed + timedelta(hours=21 + (i % 3)), observed,
                                 {"1x2": (home, draw, 1 - home - draw), "over_under": (over, 1 - over)}))  # fmt: skip
    return out


def c120_truth(truth: Sequence[TrueMatch]) -> list[TrueMatch]:
    """Świat C: każdy kurs miękki ``(1 + e)/p`` ≥ 1.20 — każda noga może wejść do dubletu."""
    cap = (1 + EDGE) / REF_MIN_LEG_ODDS
    return [t for t in truth if all(x <= cap for v in t.p.values() for x in v)]


def solo_truth(truth: Sequence[TrueMatch]) -> list[TrueMatch]:
    """Jeden mecz na migawkę decyzyjną (najmniejszy ``match_id``) — dubletów brak z konstrukcji."""
    first: dict[datetime, TrueMatch] = {}
    for t in sorted(truth, key=lambda t: (t.observed_at, t.match_id)):
        first.setdefault(t.observed_at, t)
    return list(first.values())


def band_truth(truth: Sequence[TrueMatch]) -> list[TrueMatch]:
    """Świat pasma udziału ~50% (audyt wariantu B, POWAŻNE 1): migawki na przemian
    z jednym meczem (same single — udział AKO spada) i z czterema meczami, których
    nogi ≥ 1.20 (dublety — udział rośnie; proporcja dobrana na świecie
    syntetycznym tak, by single dostawały i 1.00, i 0.94). Przy e = 0.10 single po 0.94 też
    przechodzą ``k_min``, więc udział krąży wokół progu i podatek singla zmienia
    się w trakcie przebiegu — tam działa niezależny checker (3d-C)."""
    cap = 1.10 / REF_MIN_LEG_ODDS
    by_snapshot: dict[datetime, list[TrueMatch]] = {}
    for t in sorted(truth, key=lambda t: (t.observed_at, t.match_id)):
        by_snapshot.setdefault(t.observed_at, []).append(t)
    out: list[TrueMatch] = []
    for i, (_, group) in enumerate(sorted(by_snapshot.items())):
        pairable = [t for t in group if all(x <= cap for v in t.p.values() for x in v)]
        out += group[:1] if i % 2 == 0 else pairable[:4]
    return out


def truncation_cut(truth: Sequence[TrueMatch]) -> datetime:
    ordered = sorted(truth, key=lambda t: t.observed_at)
    return ordered[len(ordered) // 2].observed_at + DECISION_LAG


def early_truth(truth: Sequence[TrueMatch]) -> list[TrueMatch]:
    """4c: D na osi INFORMACJI — usuwamy mecze, których migawka pojawia się po D."""
    cut = truncation_cut(truth)
    return [t for t in truth if t.observed_at + DECISION_LAG <= cut]


def build_worlds(truth: Sequence[TrueMatch]) -> dict[str, list[TrueMatch]]:
    c120 = c120_truth(truth)
    return {
        "full": list(truth), "early": early_truth(truth),
        "c120": c120, "c120-early": early_truth(c120), "solo": solo_truth(truth),
        "band": band_truth(truth),
    }  # fmt: skip


def _goals(rng: np.random.Generator, p: dict[str, tuple[float, ...]]) -> tuple[int, int]:
    """Wynik zgodny z niezależnie wylosowanym 1X2 i O/U 2.5."""
    side = int(rng.choice(3, p=np.asarray(p["1x2"]) / sum(p["1x2"])))
    over = bool(rng.random() < p["over_under"][0])
    return {
        (0, True): (3, 0), (0, False): (1, 0),
        (1, True): (2, 2), (1, False): (1, 1),
        (2, True): (0, 3), (2, False): (0, 1),
    }[(side, over)]  # fmt: skip


def build_world(
    truth: Sequence[TrueMatch],
    *,
    seed: int,
    soft_factor: float,
    closing_noise: bool = False,
    permute_results: bool = False,
) -> Replay:
    """Replay świata: Pinnacle z ``shin_forward(p_true)``, kurs miękki ``soft_factor / p_true``."""
    rng = np.random.default_rng(seed)
    goals = [_goals(rng, t.p) for t in truth]
    if permute_results:
        order = np.random.default_rng(seed + 10_000).permutation(len(goals))
        goals = [goals[i] for i in order]
    noise = np.random.default_rng(seed + 20_000)
    matches: list[ReplayMatch] = []
    results: dict[str, MatchResult] = {}
    for t, (h, a) in zip(truth, goals, strict=True):
        closing_at = t.kickoff - CLOSING_BEFORE_KICKOFF
        decision: dict[str, list[MarketQuote]] = {"pinnacle": [], SOFT: []}
        closing: dict[str, list[MarketQuote]] = {"pinnacle": []}
        for market, outcomes, line in MARKETS:
            p = np.asarray(t.p[market])
            pin = tuple(float(k) for k in shin_forward(p, Z))
            decision["pinnacle"].append(MarketQuote(t.match_id, market, outcomes, pin, t.observed_at, line))
            soft = tuple(float(soft_factor / x) for x in p)
            decision[SOFT].append(MarketQuote(t.match_id, market, outcomes, soft, t.observed_at, line))
            p_close = noise.dirichlet(np.ones(len(p)) * 5) if closing_noise else p
            close = tuple(float(k) for k in shin_forward(p_close / p_close.sum(), Z))
            closing["pinnacle"].append(MarketQuote(t.match_id, market, outcomes, close, closing_at, line))
        matches.append(ReplayMatch(
            match_id=t.match_id, league=t.league, season=t.season,
            home_team=f"{t.match_id}-h", away_team=f"{t.match_id}-a",
            kickoff=t.kickoff, observed_at=t.observed_at,
            decision_at=t.observed_at + DECISION_LAG, closing_at=closing_at,
            decision={b: tuple(q) for b, q in decision.items()},
            closing={b: tuple(q) for b, q in closing.items()},
        ))  # fmt: skip
        results[t.match_id] = MatchResult(t.match_id, h, a, t.kickoff + SETTLE_AFTER)
    matches.sort(key=lambda m: (m.decision_at, m.match_id))
    return Replay(matches=tuple(matches), results=results)


def _every_outcome(ctx: DecisionContext) -> list[Candidate]:
    """Placebo: wymuszony zakład na każdy wycenione wynik (§4 pkt 2)."""
    by = {m.match_id: m for m in ctx.matches}
    out = []
    for p in ctx.fair.prices:
        quote = next(q for q in by[p.match_id].decision[SOFT] if q.market == p.market)
        out.append(Candidate(p.match_id, p.market, p.outcome, p.line, p.p,
                             quote.odds[quote.outcomes.index(p.outcome)], SOFT, p.observed_at))  # fmt: skip
    return out


def _flat(_ctx: StakeContext) -> StakeDecision:
    return StakeDecision(fraction=0.0, stake=10.0, mode="real", kelly_full=0.0, c=0.25,
                         reasons=("płaska",), gk_would_unlock=False, winnings_factor=1.0, ev=0.0)  # fmt: skip


#: Kupon w formie do porównań trucizn C: (chwila, nogi (mecz, rynek, wynik, kurs), stawka).
CouponKey = tuple[str, tuple[tuple[str, str, str, float], ...], float]


@dataclass(frozen=True)
class SeedRun:
    seed: int
    n_bets: int
    profit: float
    turnover: float
    expected_profit: float
    clv_max_dev: float
    #: Rozliczenia, w których gotówka symulatora ≠ księga (w groszach, dokładnie).
    reconcile_mismatches: int
    invariants: InvariantReport
    #: Pełne listy tylko przy ``detail=True`` (nasiona testu trucizny) — 200
    #: nasion z pełnymi listami obciążało proces nadrzędny (incydent 2026-10-08).
    decisions: tuple[tuple[str, str, str, float, float, str], ...]
    stakes: tuple[float, ...]
    clv_values: tuple[float, ...]
    candidates: tuple[tuple[str, str, str, str, float, float], ...]
    #: Kupony, których stawka ≠ niezależny wzór Kelly'ego (reguła 22, ¼, limity, T13).
    kelly_mismatch: tuple[str, ...]
    strategy: str = "A"
    #: Kupony (od 1) w kolejności postawienia — tylko przy ``detail=True``.
    coupon_list: tuple[CouponKey, ...] = ()
    n_coupons: int = 0
    n_multi: int = 0
    #: (rodzaj kuponu, podatek) → liczba; rodzaj: ``single`` / ``multi``.
    tax_counts: tuple[tuple[str, float, int], ...] = ()
    #: Kupony C, których podatek ≠ niezależny checker reżimu (błąd).
    tax_errors: tuple[str, ...] = ()
    #: Single C rozliczone NIŻEJ niż checker przy zapisanej stawce — cykl podatek
    #: ↔ stawka rozstrzygnięty pesymistycznie (``RegimePlanner._single``); raport.
    tax_pessimistic: int = 0
    #: Kupony postawione w trybie PAPER (po wyłączniku 25%).
    paper_coupons: int = 0
    #: Kupony C, przy których udział AKO z kandydatem (checker) leży w [0.40, 0.60]
    #: — dowód, że bramka sprawdziła reżim przy progu (audyt wariantu B, POWAŻNE 1).
    share_band: int = 0
    #: Tryb (real/paper) kuponów w kolejności ``coupon_list`` — tylko przy ``detail``.
    coupon_modes: tuple[str, ...] = ()
    #: Audyt ścieżki C z księgi przebiegu (naprawa 4b-C, 2026-10-12): kupony, których
    #: stawka ≠ wzór Kelly'ego albo tryb ≠ obsunięcie 25% — liczone niezależnie.
    path_errors: tuple[str, ...] = ()
    #: Grupy odrzucone przez pętlę (``RunResult.dropped_groups``) z NIEZALEŻNYM
    #: potwierdzeniem przyczyny: (chwila, nogi, przyczyna, potwierdzona, uwaga).
    dropped: tuple[tuple[str, tuple[tuple[str, str, str, float], ...], str, bool, str], ...] = ()
    #: Statystyki audytu stawek z księgi (naprawa 4b-C #2, 2026-10-15): (sprawdzonych
    #: kuponów, remisów, zaakceptowanych dzięki regule remisu, odrzuconych, max |Δ kapitału|).
    path_stats: tuple[int, int, int, int, float] | tuple[()] = ()


def c_regime_start(world: Replay) -> datetime:
    """Start akcji w wariancie kontrfaktycznym = pierwsza migawka decyzyjna świata."""
    return min(m.decision_at for m in world.matches)


def run_seed(
    truth: Sequence[TrueMatch],
    *,
    strategy: str,
    seed: int,
    soft_factor: float,
    tax_factor: float,
    forced: bool = False,
    closing_noise: bool = False,
    permute_results: bool = False,
    detail: bool = False,
    workdir: Path,
) -> SeedRun:
    """Jeden przebieg nasiona. ``strategy`` wymagane: ``"A"`` (``run``) albo ``"C"``
    (``run_regime``: nogi value przy 1.00, reżim Betclica, ``single_mode``
    ``production``; wymuszone placebo — ``literal``, bo w produkcji singiel
    poniżej ``k_min`` odpada, a wymuszenie ma przejść przez planistę C)."""
    if strategy not in ("A", "C"):
        raise ValueError(f"strategy {strategy!r} spoza (A, C)")
    _require_free_space(f"{strategy} seed {seed}")
    world = build_world(truth, seed=seed, soft_factor=soft_factor,
                        closing_noise=closing_noise, permute_results=permute_results)  # fmt: skip
    path = workdir / f"bets-{strategy}-{seed}-{soft_factor}-{tax_factor}-{forced}-{closing_noise}-{permute_results}-{len(truth)}.csv"
    # Reguła (a) A4a-01 wyłączona wyłącznie znacznikiem GATE_WORLD_NO_MARGIN_CHECK.
    selector = tagged_selector(_every_outcome, selection_tax=tax_factor) if forced else threshold_selector(
        books={"1x2": (SOFT,), "over_under": (SOFT,)}, tax_factor=tax_factor,
        edge_threshold=THETA, require_complete=True, excluded=Counter(), rejected=Counter(),
        margin_check=GATE_WORLD_NO_MARGIN_CHECK,
    )
    staker = _flat if forced else kelly_staker
    start: datetime | None = None
    if strategy == "A":
        result = run(world, selector=selector, staker=staker,
                     selection_tax_factor=tax_factor, settlement_tax_factor=tax_factor,
                     journal_path=path, run_id=f"s{seed}",
                     start_capital=START, ingested_at=INGESTED, min_stake_pln=MIN_STAKE_PLN)  # fmt: skip
    else:
        if tax_factor != 1.0:
            raise ValueError("C: nogi value wybiera się przy 1.00 (plan §3)")
        start = c_regime_start(world)
        result = run_regime(world, selector=selector, staker=staker,
                            regime_config=counterfactual_regime_config(
                                start=start, share_basis=SHARE_BY_STAKES, min_stake_pln=MIN_STAKE_PLN),
                            edge_threshold=THETA, single_mode="literal" if forced else "production",
                            journal_path=path, run_id=f"c{seed}", start_capital=START,
                            ingested_at=INGESTED, min_stake_pln=MIN_STAKE_PLN)  # fmt: skip
    rows = BetJournal(journal_path=path).read() if path.exists() else []
    bets = [r for r in rows if not r.is_settlement]
    placed = sorted(coupons(rows, now=_END), key=lambda c: c.coupon_id)
    # Wymuszone placebo stawkuje płasko, poza Kelly'm — limity go nie dotyczą.
    invariants = invariant_errors(
        world, result, bets=bets, limits=FORCED_PLACEBO_NO_LIMITS if forced else PRODUCTION_LIMITS
    )
    clv_by_coupon = {r.bet_id: r.clv for r in clv_rows_of(world, rows) if r.clv is not None}
    shape = {c.coupon_id: (len(c.legs), c.tax_factor_applied) for c in placed}
    # CLV kuponu = Π(k_i · p_close_i) · tax - 1; w świecie bramki k·p_close = soft_factor.
    clv_dev = max((abs(v - (soft_factor ** shape[cid][0] * shape[cid][1] - 1)) for cid, v in clv_by_coupon.items()),
                  default=0.0)  # fmt: skip
    # Warunek wstępny (bramka e66260a, test 5): każdy przepływ symulatora to pełne
    # grosze — inaczej porównanie w groszach mogłoby ukryć błąd.
    for b in bets:
        require_grosz(b.stake, what=f"stawka {b.bet_id}")
    for c in placed:
        if c.is_real and c.payout is not None:
            require_grosz(c.payout, what=f"wypłata {c.coupon_id}")
    ledger = _reconcile(path)
    sim = [p.cash for p in result.equity if p.event != "decision"]
    recon_bad = len(cash_mismatches(ledger, sim))
    turnover, expected = real_totals(bets=bets) if strategy == "A" else coupon_totals(placed)
    tax_errors: list[str] = []
    pessimistic = 0
    band = 0
    path_errors: list[str] = []
    dropped: list[tuple[str, tuple[tuple[str, str, str, float], ...], str, bool, str]] = []
    path_stats: tuple[int, int, int, int, float] | tuple[()] = ()
    if strategy == "C":
        assert start is not None
        tax_errors, pessimistic, band = regime_tax_errors(placed, start=start, stake_inputs=result.stake_inputs)
        if detail:
            path_errors, dropped, stats = path_audit(rows, result, start=start)
            path_stats = (stats.checked, stats.ties, stats.tie_accepted, stats.rejected, stats.max_dcap)
    path.unlink(missing_ok=True)
    counts = Counter(("multi" if len(c.legs) > 1 else "single", c.tax_factor_applied) for c in placed)
    return SeedRun(
        seed=seed, n_bets=len(bets), profit=result.cash - START,
        turnover=turnover, expected_profit=expected, clv_max_dev=clv_dev,
        reconcile_mismatches=recon_bad, invariants=invariants,
        decisions=tuple((b.match_id, b.market, b.outcome, b.odds_taken, b.p_fair_at_bet,
                         b.placed_at.isoformat()) for b in bets) if detail else (),
        stakes=tuple(b.stake for b in bets) if detail else (),
        clv_values=tuple(clv_by_coupon[c.coupon_id] for c in placed if c.coupon_id in clv_by_coupon)
        if detail else (),
        candidates=tuple((t.isoformat(), m, mk, o, k, pp) for t, m, mk, o, k, pp in result.candidates)
        if detail else (),
        kelly_mismatch=tuple(kelly_mismatches(placed=placed, result=result)),
        strategy=strategy,
        coupon_list=tuple(coupon_key(c) for c in placed) if detail else (),
        n_coupons=len(placed), n_multi=sum(1 for c in placed if len(c.legs) > 1),
        tax_counts=tuple(sorted((kind, tax, n) for (kind, tax), n in counts.items())),
        tax_errors=tuple(tax_errors), tax_pessimistic=pessimistic,
        paper_coupons=result.paper_coupons, share_band=band,
        coupon_modes=tuple(c.mode for c in placed) if detail else (),
        path_errors=tuple(path_errors), dropped=tuple(dropped), path_stats=path_stats,
    )  # fmt: skip


def coupon_key(c: Coupon) -> CouponKey:
    legs = tuple((g.record.match_id, g.record.market, g.record.outcome, g.record.odds_taken) for g in c.legs)
    return (c.placed_at.isoformat(), legs, c.stake)


def kelly_expected_stake(
    p: float, odds: float, *, tax: float, capital: float, open_exposure: float, match_exposure: float
) -> float:
    """Stawka z NIEZALEŻNEGO wzoru (nie z ``pricing.kelly``): reguła 22, c = ¼,
    limity 2% / 3% na mecz / 15% otwartej ekspozycji, T13 (x0.90 przy wypłacie
    brutto > 2280 zł — jedno przeliczenie, stawka nie rośnie), do grosza."""
    def fraction(w: float) -> float:
        eff = odds * tax * w
        full = (p * eff - 1) / (eff - 1) if eff > 1 and p * eff > 1 else 0.0
        return max(0.0, min(0.25 * full, CHECKER_LIMITS.per_bet,
                            CHECKER_LIMITS.per_match - match_exposure,
                            CHECKER_LIMITS.open_exposure - open_exposure))  # fmt: skip

    f = fraction(1.0)
    if round(f * capital, 2) * odds * tax > 2280.0:
        f = min(f, fraction(0.9))
    return round(f * capital, 2)


def kelly_mismatches(*, placed: Sequence[Coupon], result: RunResult) -> list[str]:
    """Stawka każdego kuponu vs wzór — kupon wielonożny przy ``p = Π p``, ``k = Π k`` (plan §3 C)."""
    out = []
    for c in placed:
        capital, open_e, match_e, tax = result.stake_inputs[c.coupon_id]
        p = math.prod(g.record.p_fair_at_bet for g in c.legs)
        odds = math.prod(g.record.odds_taken for g in c.legs)
        expected = kelly_expected_stake(p, odds, tax=tax, capital=capital,
                                        open_exposure=open_e, match_exposure=match_e)  # fmt: skip
        if abs(expected - c.stake) > 1e-9:
            out.append(f"{c.coupon_id}: stawka {c.stake} vs wzór {expected}")
    return out


def real_totals(*, bets: Sequence[BetRecord]) -> tuple[float, float]:
    """(obrót, oczekiwany zysk ``Σ stawka·(p·k·tax - 1)``) — **tylko zakłady prawdziwe**.

    Paper (po wyłączniku 25%) nie rusza kasy, więc nie może wchodzić do
    porównania z zyskiem zrealizowanym (incydent 2026-10-08, test 1b).
    """
    real = [b for b in bets if b.mode == "real"]
    turnover = sum(b.stake for b in real)
    expected = sum(b.stake * (b.p_fair_at_bet * b.odds_taken * b.tax_factor_applied - 1) for b in real)
    return turnover, expected


def coupon_totals(placed: Sequence[Coupon]) -> tuple[float, float]:
    """C: (obrót, ``Σ stawka·(Π p · Π k · tax · w - 1)``) po kuponach prawdziwych.

    ``w`` (T13) z własnych literałów: 0.90 przy wypłacie brutto > 2280 zł —
    dublety mają kursy do kilkudziesięciu, więc bez ``w`` oczekiwanie byłoby
    zawyżone. Gdy noga przegrywa, kupon przegrywa — ``Π p`` jest szansą wygranej
    (nogi z różnych meczów, wyniki niezależne)."""
    turnover = 0.0
    expected = 0.0
    for c in placed:
        if not c.is_real:
            continue
        p = math.prod(g.record.p_fair_at_bet for g in c.legs)
        odds = math.prod(g.record.odds_taken for g in c.legs)
        w = 0.90 if c.stake * odds * c.tax_factor_applied > 2280.0 else 1.0
        turnover += c.stake
        expected += c.stake * (p * odds * c.tax_factor_applied * w - 1)
    return turnover, expected


def clv_rows_of(world: Replay, rows: list[BetRecord]) -> list[Any]:
    from valuebet.backtest.clv import clv_rows

    kickoffs = {m.match_id: m.kickoff for m in world.matches}
    end = max((r.settled_at for r in rows if r.settled_at), default=INGESTED)
    return clv_rows(bets=rows, closing=financial.closing_map(world), kickoffs=kickoffs, as_of=end)


def require_grosz(amount: float, *, what: str) -> None:
    """Przepływ pieniężny musi być wielokrotnością 0,01 zł (|x·100 - round| < 1e-6)."""
    if abs(amount * 100 - round(amount * 100)) >= 1e-6:
        raise ValueError(f"{what}: {amount!r} nie jest wielokrotnością grosza")


def cash_mismatches(ledger: Sequence[tuple[str, datetime, int]], sim: Sequence[float]) -> list[str]:
    """Dokładne porównanie w groszach: ``round(gotówka_symulatora·100) == grosze_księgi``.

    Dlaczego zaokrąglenie nie ukrywa błędu: symulator sumuje n przepływów float
    (każdy pełny grosz — :func:`require_grosz`), więc błąd zaokrągleń
    |Δ| ≤ n·u·Σ|x|, u = 2^-53 ≈ 1.1e-16. Bramka: n ≈ 18 000, Σ|x| ≈ 1.8e5 zł →
    |Δ| ≤ ~3.6e-7 zł ≪ 0.005 zł (pół grosza). Każda różnica ≥ 1 grosza to błąd
    księgowy, nie szum. Bez tolerancji.
    """
    if len(ledger) != len(sim):
        return [f"liczba rozliczeń: księga {len(ledger)}, symulator {len(sim)}"]
    return [
        f"{cid} {at}: księga {cents} gr, symulator {round(cash * 100)} gr"
        for (cid, at, cents), cash in zip(ledger, sim, strict=True)
        if round(cash * 100) != cents
    ]


_RECONCILE: dict[str, Any] = {}


def _reconcile_module() -> Any:
    """``scripts/reconcile_bets.py`` — niezależne księgowanie (bez ``valuebet``)."""
    import importlib.util

    if "module" not in _RECONCILE:
        spec = importlib.util.spec_from_file_location("reconcile_bets", ROOT / "scripts" / "reconcile_bets.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _RECONCILE["module"] = module
    return _RECONCILE["module"]


def _reconcile(path: Path) -> list[tuple[str, datetime, int]]:
    if not path.exists():
        return []  # zero zakładów — dziennik nie powstał
    out: list[tuple[str, datetime, int]] = _reconcile_module().reconcile(path, start_capital=START)
    return out


# -- niezależny checker reżimu Betclica (C) ------------------------------------


@dataclass(frozen=True)
class RefCoupon:
    """Kupon w zakresie checkera: chwila, stawka, nogi (mecz, kurs), prawdziwy."""

    placed_at: datetime
    stake: float
    legs: tuple[tuple[str, float], ...]
    real: bool


def ref_is_ako(legs: Sequence[tuple[str, float]]) -> bool:
    """§3 ust. 9 + T6 (wariant pesymistyczny): ≥ 2 nogi z różnych meczów, każda ≥ 1.20."""
    matches = [m for m, _ in legs]
    return len(legs) >= 2 and len(set(matches)) == len(matches) and all(k >= REF_MIN_LEG_ODDS for _, k in legs)


def ref_months_back(moment: datetime, months: int) -> datetime:
    """Ta sama godzina ścienna w Warszawie ``months`` miesięcy kalendarzowych wcześniej."""
    local = moment.astimezone(_WARSAW)
    year, month0 = divmod(local.year * 12 + local.month - 1 - months, 12)
    day = min(local.day, calendar.monthrange(year, month0 + 1)[1])
    return local.replace(year=year, month=month0 + 1, day=day).astimezone(UTC)


class RefRegime:
    """Reżim z literałów regulaminu, przyrostowo po kuponach w kolejności postawienia.

    ``tax(...)`` — podatek kandydata z historią dotychczas dodanych kuponów
    (``add``). Udział po stawkach, kandydat wliczony (T3), okno T7 (12 miesięcy
    kalendarzowych od ``now`` po upływie 12 miesięcy od przystąpienia, potem
    ostatnie 5000), obrót spoza dziennika jako nie-AKO (T2)."""

    def __init__(self, *, start: datetime, external_pln: float, min_stake_pln: float) -> None:
        self.start = start
        self.external = external_pln
        self.min_stake = min_stake_pln
        self.times: list[datetime] = []
        self.cum_stake = [0.0]
        self.cum_ako = [0.0]

    def add(self, c: RefCoupon) -> None:
        if not c.real:
            return  # T11: paper poza obrotem i udziałem
        if self.times and c.placed_at < self.times[-1]:
            raise ValueError("checker: kupony poza kolejnością czasu")
        self.times.append(c.placed_at)
        self.cum_stake.append(self.cum_stake[-1] + c.stake)
        self.cum_ako.append(self.cum_ako[-1] + (c.stake if ref_is_ako(c.legs) else 0.0))

    def tax(self, *, now: datetime, stake: float, legs: Sequence[tuple[str, float]]) -> float:
        return self.evaluate(now=now, stake=stake, legs=legs)[0]

    def evaluate(self, *, now: datetime, stake: float, legs: Sequence[tuple[str, float]]) -> tuple[float, float | None]:
        """(podatek, udział AKO po stawkach z kandydatem — gdy o podatku decyduje udział)."""
        if now < self.start or stake < self.min_stake:
            return 0.88, None  # T1, T12
        hi = bisect.bisect_right(self.times, now)
        lo_start = bisect.bisect_left(self.times, self.start)
        used = self.external + self.cum_stake[hi] - self.cum_stake[lo_start]
        if used < REF_LIMIT_PLN:
            return 1.00, None  # §3 ust. 4: przed zakładem zostaje jakakolwiek kwota
        if len(legs) > 1 and ref_is_ako(legs):
            return 1.00, None  # §3 ust. 11.2
        lo = lo_start  # join = start akcji (wariant kontrfaktyczny)
        cutoff = ref_months_back(now, REF_WINDOW_MONTHS)
        if cutoff >= self.start:
            lo = max(lo, bisect.bisect_left(self.times, cutoff))
        lo = max(lo, hi - REF_WINDOW_BETS)
        stakes = self.cum_stake[hi] - self.cum_stake[lo] + stake + self.external
        share = (self.cum_ako[hi] - self.cum_ako[lo]) / stakes
        return (1.00 if share >= REF_SHARE else 0.94), share  # §3 ust. 11.1, 12


def regime_tax_errors(
    placed: Sequence[Coupon], *, start: datetime, stake_inputs: dict[str, tuple[float, float, float, float]]
) -> tuple[list[str], int, int]:
    """Test 6 C: podatek każdego kuponu vs :class:`RefRegime` (kupony w kolejności numerów).

    Singiel zapisany NIŻEJ niż checker przy zapisanej stawce jest dopuszczalny
    tylko jako cykl podatek ↔ stawka (``RegimePlanner._single``): checker przy
    stawce liczonej przy 1.00 (niezależny wzór Kelly'ego) daje wtedy 0.94. Inaczej
    to błąd — tolerancja nie może ukrywać błędów w dół (audyt wariantu B, DROBNE 8).

    Zwraca (błędy, single rozstrzygnięte pesymistycznie, kupony z udziałem w [0.40, 0.60])."""
    ref = RefRegime(start=start, external_pln=REF_COUNTERFACTUAL_EXTERNAL, min_stake_pln=MIN_STAKE_PLN)
    errors: list[str] = []
    pessimistic = 0
    band = 0
    for c in placed:
        if any(g.status == "void" for g in c.legs):
            errors.append(f"{c.coupon_id}: noga zwrócona — świat bramki nie ma zwrotów")
        legs = tuple((g.record.match_id, g.record.odds_taken) for g in c.legs)
        expected, share = ref.evaluate(now=c.placed_at, stake=c.stake, legs=legs)
        if share is not None and 0.40 <= share <= 0.60:
            band += 1
        recorded = c.tax_factor_applied
        if recorded != expected:
            cycle = False
            if len(legs) == 1 and recorded < expected:
                capital, open_e, match_e, _tax = stake_inputs[c.coupon_id]
                g = c.legs[0].record
                at_one = kelly_expected_stake(g.p_fair_at_bet, g.odds_taken, tax=1.0, capital=capital,
                                              open_exposure=open_e, match_exposure=match_e)  # fmt: skip
                cycle = at_one > 0 and ref.tax(now=c.placed_at, stake=at_one, legs=legs) == 0.94
            if cycle:
                pessimistic += 1
            else:
                errors.append(f"{c.coupon_id}: podatek {recorded} vs checker {expected}")
        ref.add(RefCoupon(c.placed_at, c.stake, legs, c.is_real))
    return errors, pessimistic, band


# -- audyt ścieżki C z księgi przebiegu (naprawa 4b-C, 2026-10-12) --------------
#: WŁASNE literały checkera (jak ``CHECKER_LIMITS``): min. stawka bukmachera
#: (T12), grosz (stawka 0), wyłącznik 25% (TOR_S_PLAN §5, ``kelly.DRAWDOWN_SWITCH``).
REF_MIN_STAKE_PLN = 0.50
REF_GROSZ = 0.01
REF_DRAWDOWN_SWITCH = 0.25
#: Naprawa 4b-C #2 (2026-10-15, bramka 27ae469, kupon c0-004274): surowa stawka bliżej
#: niż ``REF_TIE_PLN`` od x.xx5 to REMIS — stawka silnika może być którymkolwiek z dwóch
#: sąsiednich groszy (kolejność sumowania floatów kapitału przesuwa remis o ~1e-11).
REF_TIE_PLN = 1e-6
#: Twardy warunek: |kapitał z księgi - kapitał silnika| < 1e-6 zł dla każdego kuponu i
#: wpisu odrzucenia (dryf floatów ~4,5e-11; więcej = inny stan przebiegu, klasa B).
REF_CAPITAL_TOL = 1e-6


def kelly_expected_raw(
    p: float, odds: float, *, tax: float, capital: float, open_exposure: float, match_exposure: float
) -> float:
    """``kelly_expected_stake`` PRZED zaokrągleniem do grosza (audyt remisu 4b-C).

    Ten sam wzór; ``kelly_expected_stake`` celowo nietknięty (wspólny z 6-C i
    ``kelly_mismatches``) — zgodność ``round(raw, 2)`` pilnuje test_gate_4bc_tie."""
    def fraction(w: float) -> float:
        eff = odds * tax * w
        full = (p * eff - 1) / (eff - 1) if eff > 1 and p * eff > 1 else 0.0
        return max(0.0, min(0.25 * full, CHECKER_LIMITS.per_bet,
                            CHECKER_LIMITS.per_match - match_exposure,
                            CHECKER_LIMITS.open_exposure - open_exposure))  # fmt: skip

    f = fraction(1.0)
    if round(f * capital, 2) * odds * tax > 2280.0:
        f = min(f, fraction(0.9))
    return f * capital


def is_tie(raw: float) -> bool:
    """Surowa stawka bliżej niż ``REF_TIE_PLN`` od x.xx5 (pół grosza)."""
    cents = raw * 100
    return abs(cents - math.floor(cents) - 0.5) < REF_TIE_PLN * 100


def stake_neighbours(raw: float) -> tuple[float, ...]:
    """Stawki zgodne ze wzorem: przy remisie oba sąsiednie grosze, poza nim ``round``."""
    if is_tie(raw):
        low = math.floor(raw * 100)
        return (low / 100, (low + 1) / 100)
    return (round(raw, 2),)


@dataclass(frozen=True)
class StakeVerdict:
    error: str | None
    tie: bool
    #: Zaakceptowana TYLKO dzięki regule remisu (stawka silnika ≠ ``round`` z księgi).
    by_tie: bool


def stake_verdict(*, engine_stake: float, raw: float, engine_capital: float, ledger_capital: float) -> StakeVerdict:
    """Stawka kuponu vs wzór z księgi: najpierw twardy warunek kapitału, potem stawka
    równa ``round(raw)`` albo — wyłącznie przy remisie — drugiemu sąsiedniemu groszowi."""
    tie = is_tie(raw)
    dcap = engine_capital - ledger_capital
    if not abs(dcap) < REF_CAPITAL_TOL:
        return StakeVerdict(f"kapitał silnika {engine_capital!r} vs księga {ledger_capital!r} (Δ {dcap:.3e})", tie,
                            False)  # fmt: skip
    if not any(abs(engine_stake - s) <= 1e-9 for s in stake_neighbours(raw)):
        return StakeVerdict(f"stawka {engine_stake} vs wzór z księgi {round(raw, 2)}", tie, False)
    return StakeVerdict(None, tie, tie and abs(engine_stake - round(raw, 2)) > 1e-9)


@dataclass(frozen=True)
class PathAuditStats:
    """Raport audytu stawek z księgi (4b-C, pkt 2c naprawy remisu)."""

    checked: int
    ties: int
    tie_accepted: int
    rejected: int
    #: Maksimum |kapitał z księgi - kapitał silnika| po kuponach i wpisach odrzucenia.
    max_dcap: float


@dataclass(frozen=True)
class LedgerCoupon:
    """Kupon odtworzony z wierszy dziennika (bez ``live.bets``): nogi z ``p``, rozliczenie."""

    coupon_id: str
    placed_at: datetime
    stake: float
    tax: float
    mode: str
    #: (mecz, rynek, wynik, kurs, p_fair)
    legs: tuple[tuple[str, str, str, float, float], ...]
    finish_at: datetime
    finish_key: str
    payout: float


def ledger_coupons(rows: Sequence[BetRecord]) -> list[LedgerCoupon]:
    """Kupony z księgi: rozliczenie kuponu = przegrana noga (najwcześniejsza) albo ostatnia
    noga; wypłata z ``reconcile_bets._payout`` (niezależna od ``pricing``)."""
    payout_of = _reconcile_module()._payout
    settle = {r.bet_id.removesuffix("#settle"): (r.settled, r.settled_at) for r in rows if r.is_settlement}
    legs_of: dict[str, list[BetRecord]] = {}
    for r in rows:
        if not r.is_settlement:
            legs_of.setdefault(r.coupon_id, []).append(r)
    out: list[LedgerCoupon] = []
    for cid in sorted(legs_of):
        legs = sorted(legs_of[cid], key=lambda r: r.leg_index)
        states = [(settle[g.bet_id][1], g.bet_id, settle[g.bet_id][0]) for g in legs]
        lost = [x for x in states if x[2] == "lost"]
        at, key, _ = min(lost) if lost else max(states)
        first = legs[0]
        payout = payout_of(first.stake, first.tax_factor_applied, [(g.odds_taken, st) for (_, _, st), g in zip(states, legs, strict=True)])
        out.append(LedgerCoupon(cid, first.placed_at, first.stake, first.tax_factor_applied, first.mode,
                                tuple((g.match_id, g.market, g.outcome, g.odds_taken, g.p_fair_at_bet) for g in legs),
                                at, key, payout))  # fmt: skip
    return out


class LedgerPath:
    """Kapitał, szczyt i otwarte kupony w chwili decyzji — z księgi, jak ``reconcile``.

    Kapitał w chwili t = start + Σ (wypłata - stawka) kuponów prawdziwych rozliczonych
    ≤ t (otwarte stawki wracają do kapitału po koszcie); szczyt — maksimum kapitału po
    każdym rozliczeniu w kolejności (chwila, noga rozstrzygająca), jak kopiec symulatora.
    """

    def __init__(self, coupons_: Sequence[LedgerCoupon], *, start: float) -> None:
        self.coupons = list(coupons_)
        self._active: list[LedgerCoupon] = []
        self._next = 0
        self._last: datetime | None = None
        events = sorted(self.coupons, key=lambda c: (c.finish_at, c.finish_key))
        self.times = [c.finish_at for c in events]
        self.capital = [start]
        self.peak = [start]
        for c in events:
            delta = (c.payout - c.stake) if c.mode == "real" else 0.0
            self.capital.append(self.capital[-1] + delta)
            self.peak.append(max(self.peak[-1], self.capital[-1]))

    def state(self, t: datetime) -> tuple[float, float]:
        i = bisect.bisect_right(self.times, t)
        return self.capital[i], self.peak[i]

    def exposures(self, t: datetime, k: int, legs: Sequence[tuple[str, ...]], capital: float) -> tuple[float, float]:
        """(otwarta ekspozycja, najciaśniejszy mecz) z kuponów o numerze < ``k`` otwartych w t.

        Wołane z (t, k) niemalejącymi — lista otwartych prowadzona przyrostowo."""
        if k < self._next or (self._last is not None and t < self._last):
            raise ValueError("LedgerPath.exposures: (t, k) muszą być niemalejące")
        self._active += self.coupons[self._next:k]
        self._next, self._last = k, t
        self._active = [c for c in self._active if c.finish_at > t]
        open_ = self._active
        total = sum(c.stake for c in open_)
        per_match = max(sum(c.stake for c in open_ if any(g[0] == leg[0] for g in c.legs)) for leg in legs)
        return total / capital, per_match / capital


def path_audit(rows: Sequence[BetRecord], result: RunResult, *, start: datetime
               ) -> tuple[list[str], list[tuple[str, tuple[tuple[str, str, str, float], ...], str, bool, str]],
                          PathAuditStats]:  # fmt: skip
    """Niezależny audyt ścieżki przebiegu C (kryterium 4b-C, 2026-10-12).

    Kupony: stawka = wzór Kelly'ego (kapitał, ekspozycje z księgi; podatek kuponu),
    tryb = (obsunięcie ≥ 25%). Grupy odrzucone: przyczyna z ``dropped_groups``
    potwierdzona przeliczeniem — STAWKA_PONIZEJ_MINIMUM: 0,01 ≤ stawka przy 1.00 <
    0,50 zł; STAWKA_ZERO: stawka < 0,01 przy 1.00 albo przy podatku ``RefRegime``;
    PONIZEJ_PROGU_PO_PODATKU: singiel, ``RefRegime`` < 1.00 i p·k·podatek < 1 + θ;
    KAPITAL_ZERO: kapitał ≤ 0.

    Naprawa 4b-C #2 (2026-10-15): kapitał silnika (``stake_inputs``, pole ``capital``
    wpisu) = kapitał z księgi z dokładnością ``REF_CAPITAL_TOL``; stawka przy remisie na
    pół grosza — którykolwiek z dwóch sąsiednich groszy (``stake_verdict``)."""
    ledger = ledger_coupons(rows)
    path = LedgerPath(ledger, start=START)
    p_of = {(t.isoformat(), m, mk, o, k): pp for t, m, mk, o, k, pp in result.candidates}
    ref = RefRegime(start=start, external_pln=REF_COUNTERFACTUAL_EXTERNAL, min_stake_pln=REF_MIN_STAKE_PLN)
    drops_at: dict[int, list[Any]] = {}
    for d in result.dropped_groups:
        drops_at.setdefault(d.placed_before, []).append(d)
    errors: list[str] = []
    verified: list[tuple[str, tuple[tuple[str, str, str, float], ...], str, bool, str]] = []
    ties = tie_accepted = rejected = 0
    max_dcap = 0.0

    def check_drop(d: Any, k: int) -> None:
        nonlocal max_dcap
        cap, _peak = path.state(d.at)
        note = ""
        max_dcap = max(max_dcap, abs(cap - d.capital))
        ok = abs(cap - d.capital) < REF_CAPITAL_TOL
        if not ok:
            note = f"kapitał wpisu {d.capital!r} ≠ księga {cap!r}"
        elif d.reason == "KAPITAL_ZERO":
            ok = cap <= 0.0
        else:
            ps = [p_of.get((d.at.isoformat(), *leg)) for leg in d.legs]
            if any(x is None for x in ps):
                ok, note = False, "nogi spoza kandydatów"
            else:
                pp, odds = math.prod(x for x in ps if x is not None), math.prod(leg[3] for leg in d.legs)
                oe, me = path.exposures(d.at, k, d.legs, cap)
                raw1 = kelly_expected_raw(pp, odds, tax=1.0, capital=cap, open_exposure=oe, match_exposure=me)
                s1 = round(raw1, 2)
                tau = ref.tax(now=d.at, stake=s1, legs=[(leg[0], leg[3]) for leg in d.legs]) if s1 >= REF_GROSZ else 1.0
                # przy remisie stawka silnika mogła być drugim sąsiednim groszem
                if d.reason == "STAWKA_PONIZEJ_MINIMUM":
                    ok = any(REF_GROSZ <= s < REF_MIN_STAKE_PLN for s in stake_neighbours(raw1))
                elif d.reason == "STAWKA_ZERO":
                    raw_tau = kelly_expected_raw(pp, odds, tax=tau, capital=cap, open_exposure=oe, match_exposure=me)
                    ok = any(min(a, b) < REF_GROSZ for a in stake_neighbours(raw1) for b in stake_neighbours(raw_tau))
                elif d.reason == "PONIZEJ_PROGU_PO_PODATKU":
                    ok = len(d.legs) == 1 and tau < 1.0 and pp * odds * tau < 1 + THETA
                else:
                    ok = False
                note = f"stawka przy 1.00 z księgi {s1:.2f} zł, podatek RefRegime {tau}"
        verified.append((d.at.isoformat(), d.legs, d.reason, ok, note))

    for k, c in enumerate(ledger):
        for d in drops_at.pop(k, []):
            check_drop(d, k)
        cap, peak = path.state(c.placed_at)
        expected_mode = "paper" if peak > 0 and 1 - cap / peak >= REF_DRAWDOWN_SWITCH else "real"
        if c.mode != expected_mode:
            errors.append(f"{c.coupon_id}: tryb {c.mode}, z księgi {expected_mode} (obsunięcie {1 - cap / peak:.3f})")
        oe, me = path.exposures(c.placed_at, k, c.legs, cap)
        raw = kelly_expected_raw(math.prod(g[4] for g in c.legs), math.prod(g[3] for g in c.legs), tax=c.tax,
                                 capital=cap, open_exposure=oe, match_exposure=me)  # fmt: skip
        engine_capital = result.stake_inputs[c.coupon_id][0]
        max_dcap = max(max_dcap, abs(engine_capital - cap))
        verdict = stake_verdict(engine_stake=c.stake, raw=raw, engine_capital=engine_capital, ledger_capital=cap)
        ties += verdict.tie
        tie_accepted += verdict.by_tie
        if verdict.error is not None:
            rejected += 1
            errors.append(f"{c.coupon_id}: {verdict.error}")
        ref.add(RefCoupon(c.placed_at, c.stake, tuple((g[0], g[3]) for g in c.legs), c.mode == "real"))
    for k, ds in sorted(drops_at.items()):
        for d in ds:
            check_drop(d, k)
    return errors, verified, PathAuditStats(len(ledger), ties, tie_accepted, rejected, max_dcap)


def path_explained(base: SeedRun, perm: SeedRun) -> tuple[Counter[str], list[str]]:
    """Kryterium 4b-C: każda różnica kuponów między przebiegiem bazowym a spermutowanym
    wyjaśniona — grupa obecna tylko w jednym przebiegu ma w drugim wpis odrzucenia z
    NIEZALEŻNIE potwierdzoną przyczyną; różnica trybu PAPER — tryby obu przebiegów
    zgodne z obsunięciem z księgi (``path_errors`` puste). Zwraca (wyjaśnione wg
    przyczyny, niewyjaśnione)."""
    unexplained = [f"baza: {e}" for e in base.path_errors] + [f"permutacja: {e}" for e in perm.path_errors]
    explained: Counter[str] = Counter()
    keys = {name: Counter((c[0], c[1]) for c in sr.coupon_list) for name, sr in (("baza", base), ("permutacja", perm))}
    for mine, other, sr in (("baza", "permutacja", perm), ("permutacja", "baza", base)):
        drops = {(t, legs): (reason, ok, note) for t, legs, reason, ok, note in sr.dropped}
        for key in sorted((keys[mine] - keys[other]).elements()):
            found = drops.get(key)
            if found is None:
                unexplained.append(f"{key} jest w: {mine}, w {other} brak kuponu i brak wpisu odrzucenia")
            elif not found[1]:
                unexplained.append(f"{key}: w {other} przyczyna {found[0]} niepotwierdzona ({found[2]})")
            else:
                explained[found[0]] += 1
    mode_b = {(c[0], c[1]): m for c, m in zip(base.coupon_list, base.coupon_modes, strict=True)}
    mode_p = {(c[0], c[1]): m for c, m in zip(perm.coupon_list, perm.coupon_modes, strict=True)}
    explained["PAPER (tryb, obsunięcie z księgi)"] += sum(1 for k, m in mode_b.items() if k in mode_p and mode_p[k] != m)
    return explained, unexplained


@dataclass(frozen=True)
class Limits:
    """Limity stawkowania sprawdzane po fakcie (§4 pkt 6)."""

    per_bet: float
    per_match: float
    open_exposure: float


#: WŁASNE literały sprawdzarki — CLAUDE.md reguła 23 (2% na zakład), TOR_S_PLAN §5
#: (3% na mecz, 15% otwartej ekspozycji). Celowo NIE import z ``pricing.kelly``:
#: literówka w silniku (0.02 → 0.2) przeszłaby bramkę, gdyby sprawdzarka dzieliła
#: z nim stałe. Zgodność z ``pricing.kelly`` pilnuje test w tests/test_engine_gate.py.
CHECKER_LIMITS = Limits(per_bet=0.02, per_match=0.03, open_exposure=0.15)
PRODUCTION_LIMITS = CHECKER_LIMITS


@dataclass(frozen=True)
class _ForcedPlacebo:
    """Jawny znacznik zamiast ``None`` (reguła 30: brak „None = nie sprawdzaj”)."""


#: Wymuszone placebo 2b wstrzykuje płaską stawkę 10 zł z pominięciem Kelly'ego
#: i jego limitów (§4 pkt 2) — limity 2%/3%/15% go z definicji nie dotyczą
#: (bramka e66260a: 1092 „otwarta ekspozycja” wyłącznie w 2b). Kapitał ≥ 0,
#: porządek czasu i podatek sprawdzane zawsze.
FORCED_PLACEBO_NO_LIMITS = _ForcedPlacebo()

#: Reguła (a) A4a-01 (booksum bukmachera < 1.00 → poza best-of) WYŁĄCZONA w
#: świecie bramki: kurs miękki ``(1 + e) / p_true`` na KAŻDYM wyniku ma z
#: konstrukcji booksum ``1 / (1 + e) < 1`` — reguła odrzuciłaby wszystko.
#: Jedyne miejsce wyłączenia; ``margin_check`` w ``threshold_selector`` jest
#: wymagany i bez wartości domyślnej, przebieg produkcyjny bierze go z tabeli
#: strategii (``run_strategy``; test ``test_a4a01_run_strategy_has_rule_a_on_in_production``).
#: Reguła (b) (EV > 0.50) działa w bramce. Raport ENGINE_TESTS mówi o tym wprost.
GATE_WORLD_NO_MARGIN_CHECK = False
MARGIN_NOTE = (
    "Uwaga: reguła (a) A4a-01 WYŁĄCZONA w świecie bramki (`GATE_WORLD_NO_MARGIN_CHECK`): "
    "kurs miękki (1 + e)/p_true ma z konstrukcji booksum 1/(1 + e) < 1. Reguła (b) "
    "(EV > 0.50) włączona. Przebieg produkcyjny (`run_strategy`) ma (a) włączone — "
    "test `test_a4a01_run_strategy_has_rule_a_on_in_production`."
)


@dataclass(frozen=True)
class InvariantReport:
    errors: tuple[str, ...]
    #: Migawki decyzyjne, w których sprawdzono limit ekspozycji (0 przy placebo).
    snapshots_checked: int
    #: Największa zaobserwowana otwarta ekspozycja real / kapitał.
    max_open_exposure: float


def invariant_errors(
    world: Replay, result: RunResult, *, bets: list[BetRecord], limits: Limits | _ForcedPlacebo
) -> InvariantReport:
    """§4 pkt 6: limity (tylko przy stawkowaniu produkcyjnym), kapitał ≥ 0,
    porządek czasu, podatek zgodny z dziedziną; kupon wielonożny (C): nogi z
    różnych meczów, każda ≥ 1.20, **pełna** stawka kuponu w limicie meczu
    każdej nogi (wiersz nogi niesie stawkę kuponu). ``limits`` wymagane (reguła 30)."""
    check_limits = isinstance(limits, Limits)
    errors: list[str] = []
    by_match = {m.match_id: m for m in world.matches}
    eps = 0.01 + 1e-9  # zaokrąglenie stawki do grosza
    per_match: dict[tuple[str, str], float] = {}
    legs_of: dict[str, list[BetRecord]] = {}
    for b in bets:
        legs_of.setdefault(b.coupon_id, []).append(b)
        cap = result.bankroll_at[b.coupon_id]
        m = by_match[b.match_id]
        settled = world.results[b.match_id].settled_at
        if isinstance(limits, Limits):
            if b.leg_index == 0 and b.stake > limits.per_bet * cap + eps:
                errors.append(f"{b.coupon_id}: stawka {b.stake} > {limits.per_bet:.0%} z {cap:.2f}")
            key = (b.match_id, b.placed_at.isoformat())
            per_match[key] = per_match.get(key, 0.0) + b.stake
            if per_match[key] > limits.per_match * cap + 3 * eps:
                errors.append(f"{b.bet_id}: mecz {per_match[key]:.2f} > {limits.per_match:.0%} z {cap:.2f}")
        if not (b.snapshot_observed_at is not None and b.snapshot_observed_at < b.placed_at < m.kickoff < settled):
            errors.append(f"{b.bet_id}: porządek czasu złamany")
        if b.tax_factor_applied not in (1.0, 0.94, 0.88):
            errors.append(f"{b.bet_id}: podatek {b.tax_factor_applied}")
    for coupon_id, legs in legs_of.items():
        if len(legs) < 2:
            continue
        matches = [leg.match_id for leg in legs]
        if len(set(matches)) != len(matches):
            errors.append(f"{coupon_id}: nogi z jednego meczu")
        if any(leg.odds_taken < REF_MIN_LEG_ODDS for leg in legs):
            errors.append(f"{coupon_id}: noga < {REF_MIN_LEG_ODDS}")
    checked = 0
    worst = 0.0
    for point in result.equity:
        if point.cash < -1e-9 or point.capital < -1e-9:
            errors.append(f"{point.at}: kapitał ujemny {point.capital}")
        if point.event != "decision" or not isinstance(limits, Limits):
            continue
        open_real = point.capital - point.cash
        checked += 1
        if point.capital > 0:
            worst = max(worst, open_real / point.capital)
        # W chwili decyzji kapitał stały (stawka przechodzi z gotówki do otwartych);
        # 1 zł zapasu na zaokrąglenia stawek do grosza.
        if open_real > limits.open_exposure * point.capital + 1.0:
            errors.append(f"{point.at}: otwarta ekspozycja {open_real:.2f}")
    return InvariantReport(tuple(errors), checked if check_limits else 0, worst)


def check_six(*, production: Sequence[InvariantReport], other: Sequence[InvariantReport],
              label: str = "6 niezmienniki: limity, kapitał ≥ 0, porządek czasu, podatek",
              extra_errors: Sequence[str] = (), extra_detail: str = "") -> Check:  # fmt: skip
    """Test 6. Ochrona przed pustą zielenią: przebiegi produkcyjne muszą coś sprawdzić."""
    errors = [e for r in [*production, *other] for e in r.errors] + list(extra_errors)
    checked = sum(r.snapshots_checked for r in production)
    worst = max((r.max_open_exposure for r in production), default=0.0)
    passed = not errors and checked > 0 and worst > 0.0
    detail = (
        f"naruszeń {len(errors)}; migawek z limitem sprawdzonych {checked}, "
        f"maks. ekspozycja {worst:.1%}" + extra_detail + (f"; pierwsze: {errors[:3]}" if errors else "")
        + ("" if checked > 0 and worst > 0.0 else " — PUSTA ZIELEŃ: przebiegi produkcyjne nic nie sprawdziły")
    )
    return Check(label, passed, detail)


def _mean_se(values: Sequence[float]) -> tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    if len(arr) == 0:
        return math.nan, math.inf
    return float(arr.mean()), float(arr.std(ddof=1) / math.sqrt(len(arr))) if len(arr) > 1 else math.inf


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


#: Nasiona per test. 200 — §4 pkt 1 (plan; dla C — decyzja Pawła 2026-10-11).
#: Statystyczne 2b i 3a — 50 (plan liczby nie podaje; SE raportowane). Zero
#: zakładów (2a, 3b) — deterministyczne względem nasiona, więc 3 wystarczą.
#: Trucizny — 10 nasion, 4c — 3.
STAT_SEEDS = 50
ZERO_SEEDS = 3
POISON_SEEDS = 10
TRUNC_SEEDS = 3


def plan(n_seeds: int) -> dict[str, int]:
    """Liczba przebiegów nasion per test — jedno źródło dla bramki i paska postępu."""
    p = min(POISON_SEEDS, n_seeds)
    out: dict[str, int] = {}
    for s in ("A", "C"):
        out |= {f"1-{s}": n_seeds, f"2a-{s}": min(ZERO_SEEDS, n_seeds), f"2b-{s}": min(STAT_SEEDS, n_seeds),
                f"3a-{s}": min(STAT_SEEDS, n_seeds), f"3b-{s}": min(ZERO_SEEDS, n_seeds),
                f"4-base-{s}": p, f"4a-{s}": p, f"4b-{s}": p, f"4c-{s}": min(TRUNC_SEEDS, p)}  # fmt: skip
    out["3d-C"] = p
    return out


#: (identyfikator testu, przebiegi nasion) → wyniki. Pozycja: kwargs ``run_seed``
#: bez ``workdir``, z kluczem ``world`` (nazwa świata z ``build_worlds``).
Runner = Callable[[str, list[dict[str, Any]]], list[SeedRun]]


def sequential_runner(worlds: dict[str, list[TrueMatch]], workdir: Path) -> Runner:
    """Bez równoległości i bez zapisu — pytest i ``spy_check``."""
    def runner(_test_id: str, items: list[dict[str, Any]]) -> list[SeedRun]:
        return [run_item(worlds, workdir, item) for item in items]

    return runner


def run_item(worlds: dict[str, list[TrueMatch]], workdir: Path, item: dict[str, Any]) -> SeedRun:
    kw = dict(item)
    return run_seed(worlds[kw.pop("world")], workdir=workdir, **kw)


def gate(truth: Sequence[TrueMatch], *, seeds: Sequence[int], workdir: Path,
         runner: Runner | None = None,
         checkpoint: Callable[[str], None] | None = None) -> list[Check]:  # fmt: skip
    """Wszystkie testy §4 1-6 dla A i C. Pkt 7 (szpiedzy) — :func:`spy_check`.

    ``runner`` — wykonawca przebiegów (``main``: pula procesów, wyniki
    cząstkowe, postęp). ``checkpoint(test)`` wołane przed każdą fazą — w
    ``main`` sprawdza wolne miejsce. Heartbeatu kolektora nie — kolektor na VPS
    od 2026-10-10.
    """
    worlds = build_worlds(truth)
    _remember_cuts(worlds)
    run_many = runner or sequential_runner(worlds, workdir)
    counts = plan(len(list(seeds)))

    def many(test_id: str, world: str, **kw: Any) -> list[SeedRun]:
        if checkpoint is not None:
            checkpoint(test_id)
        chosen = list(seeds)[: counts[test_id]]
        return run_many(test_id, [dict(kw, world=world, seed=s) for s in chosen])

    checks = gate_a(many)
    checks += gate_c(many, worlds)
    return checks


def gate_a(many: Callable[..., list[SeedRun]]) -> list[Check]:
    """Testy 1-6 strategii A — bez zmian merytorycznych względem bramki 2c7cc61."""
    checks: list[Check] = []
    known = many("1-A", "full", strategy="A", soft_factor=1 + EDGE, tax_factor=1.0)
    clv_dev = max(r.clv_max_dev for r in known)
    checks.append(Check("1a znana odpowiedź: CLV każdego zakładu = e", clv_dev < SHIN_TOL,
                        f"max |CLV - e| = {clv_dev:.2e} (tolerancja {SHIN_TOL:.0e}); zakładów {sum(r.n_bets for r in known)}"))  # fmt: skip
    diff = [r.profit - r.expected_profit for r in known]
    mean, se = _mean_se(diff)
    checks.append(Check("1b znana odpowiedź: zysk - Σ stawka·e ≈ 0", abs(mean) <= 2 * se,
                        f"średnia {mean:+.2f} zł, SE {se:.2f}, nasion {len(diff)}"))  # fmt: skip

    zero = many("2a-A", "full", strategy="A", soft_factor=0.95, tax_factor=1.0)
    n_zero = sum(r.n_bets for r in zero)
    checks.append(Check("2a placebo: zero zakładów przy θ = 0.02", n_zero == 0, f"zakładów {n_zero}"))
    forced = many("2b-A", "full", strategy="A", soft_factor=0.95, tax_factor=1.0, forced=True)
    yields = [r.profit / r.turnover for r in forced if r.turnover > 0]
    mean, se = _mean_se(yields)
    checks.append(Check("2b placebo wymuszone: yield -5% ± 2 SE", abs(mean + 0.05) <= 2 * se,
                        f"yield {mean:+.4f}, SE {se:.4f}, nasion {len(yields)}"))  # fmt: skip

    taxed = many("3a-A", "full", strategy="A", soft_factor=1.10, tax_factor=0.94)
    yields = [r.profit / r.turnover for r in taxed if r.turnover > 0]
    target = 1.10 * 0.94 - 1
    mean, se = _mean_se(yields)
    checks.append(Check("3a podatek 0.94, e = 0.10: yield 3.4% ± 2 SE", abs(mean - target) <= 2 * se,
                        f"yield {mean:+.4f} vs {target:+.4f}, SE {se:.4f}"))  # fmt: skip
    small = many("3b-A", "full", strategy="A", soft_factor=1 + EDGE, tax_factor=0.94)
    n_small = sum(r.n_bets for r in small)
    checks.append(Check("3b podatek 0.94, e = 0.025: zero zakładów", n_small == 0, f"zakładów {n_small}"))

    base_runs = many("4-base-A", "full", strategy="A", soft_factor=1 + EDGE, tax_factor=1.0, detail=True)
    base = {r.seed: r for r in base_runs}
    noisy = many("4a-A", "full", strategy="A", soft_factor=1 + EDGE, tax_factor=1.0, closing_noise=True, detail=True)
    same = all(r.decisions == base[r.seed].decisions and r.stakes == base[r.seed].stakes for r in noisy)
    changed = all(r.clv_values != base[r.seed].clv_values for r in noisy)
    checks.append(Check("4a trucizna: losowe zamknięcia → te same zakłady i stawki, inne CLV",
                        same and changed, f"zakłady/stawki identyczne: {same}; CLV inne: {changed}"))  # fmt: skip
    permuted = many("4b-A", "full", strategy="A", soft_factor=1 + EDGE, tax_factor=1.0, permute_results=True,
                    detail=True)  # fmt: skip
    # Decyzja Pawła 2026-10-08 (3): zbiór KANDYDATÓW identyczny po permutacji, każda
    # stawka zgodna z wzorem Kelly'ego dla kapitału w danej chwili; podział
    # real/paper może się różnić po wyłączniku.
    same_cand = all(sorted(r.candidates) == sorted(base[r.seed].candidates) for r in permuted)
    # FSA4a-02 (decyzja Pawła 2026-10-10): lista POSTAWIONYCH zakładów (mecz, rynek,
    # wynik, kurs) identyczna w kolejności — kandydat pominięty przez silnik z powodu
    # wyniku zmienia listę. Stawki w złotych zależą od ścieżki kapitału (inne wyniki),
    # więc porównujemy je ze wzorem Kelly'ego dla kapitału w danej chwili (kelly_ok).
    same_placed = all([d[:4] for d in r.decisions] == [d[:4] for d in base[r.seed].decisions]
                      for r in permuted)  # fmt: skip
    kelly_ok = all(not r.kelly_mismatch for r in [*permuted, *base.values()])
    pnl = all(r.profit != base[r.seed].profit for r in permuted)
    n_cand = sum(len(r.candidates) for r in permuted)
    n_placed = sum(len(r.decisions) for r in permuted)
    mism = [m for r in [*permuted, *base.values()] for m in r.kelly_mismatch]
    checks.append(Check("4b trucizna: spermutowane wyniki → ci sami kandydaci, te same postawione zakłady, stawki wg wzoru Kelly'ego, inny P&L",
                        same_cand and same_placed and kelly_ok and pnl,
                        f"kandydaci identyczni: {same_cand} (n={n_cand}); postawione identyczne: {same_placed} "
                        f"(n={n_placed}); stawki = wzór: {kelly_ok}"
                        + (f" — {mism[:3]}" if mism else "") + f"; P&L inny: {pnl}"))  # fmt: skip
    # D na osi INFORMACJI: usuwamy mecze, których migawka pojawia się po D.
    # Mecz z gwizdkiem po D, ale decyzją przed D, jest wiedzą sprzed D.
    part_runs = many("4c-A", "early", strategy="A", soft_factor=1 + EDGE, tax_factor=1.0, detail=True)
    cut = datetime.fromisoformat(_CUTS["full"])
    trunc_ok = True
    for part in part_runs:
        full_run = base[part.seed]
        # FSA4a-02: w OBIE strony — lista postawionych zakładów do D (z kursem i
        # stawką) w pełnym przebiegu == w uciętym, nie tylko „pełne ⊆ ucięte”.
        upto_full = [(d, s) for d, s in zip(full_run.decisions, full_run.stakes, strict=True)
                     if datetime.fromisoformat(d[5]) <= cut]  # fmt: skip
        upto_part = [(d, s) for d, s in zip(part.decisions, part.stakes, strict=True)
                     if datetime.fromisoformat(d[5]) <= cut]  # fmt: skip
        trunc_ok &= upto_full == upto_part
    checks.append(Check("4c trucizna: mecze po dniu D usunięte → decyzje do D identyczne", trunc_ok,
                        f"dzień D = {cut.date()}"))  # fmt: skip

    recon = sum(r.reconcile_mismatches for r in known + forced)
    checks.append(Check("5 podwójne księgowanie: symulator == reconcile w groszach", recon == 0,
                        f"niezgodnych rozliczeń {recon} (porównanie dokładne, bez tolerancji)"))  # fmt: skip
    checks.append(check_six(production=[r.invariants for r in known + taxed],
                            other=[r.invariants for r in forced]))
    return checks


#: Dzień D trucizny 4c per świat (ISO) — ustawiany w :func:`gate_c`/``gate`` przez
#: :func:`_remember_cuts`; trzymany jako tekst, bo świat jest wspólny dla nasion.
_CUTS: dict[str, str] = {}


def _remember_cuts(worlds: dict[str, list[TrueMatch]]) -> None:
    for name in ("full", "c120"):
        if worlds[name]:
            _CUTS[name] = truncation_cut(worlds[name]).isoformat()


def _coupon_diff(a: Sequence[CouponKey], b: Sequence[CouponKey]) -> str:
    for i, (x, y) in enumerate(itertools.zip_longest(a, b)):
        if x != y:
            return f"pierwsza różnica na kuponie {i + 1}: {x} vs {y}"
    return ""


def gate_c(many: Callable[..., list[SeedRun]], worlds: dict[str, list[TrueMatch]]) -> list[Check]:
    """Testy 1-6 strategii C (wariant B, decyzja Pawła 2026-10-11)."""
    checks: list[Check] = []
    known = many("1-C", "c120", strategy="C", soft_factor=1 + EDGE, tax_factor=1.0)
    clv_dev = max(r.clv_max_dev for r in known)
    n_multi = sum(r.n_multi for r in known)
    n_coupons = sum(r.n_coupons for r in known)
    checks.append(Check("1a-C znana odpowiedź: CLV kuponu = (1+e)^n·tax - 1 (dublet (1+e)^2 - 1)",
                        clv_dev < SHIN_TOL and n_multi > 0,
                        f"max |CLV - wzór| = {clv_dev:.2e} (tolerancja {SHIN_TOL:.0e}); kuponów {n_coupons}, "
                        f"dubletów {n_multi}; świat c120: {len(worlds['c120'])} meczów"))  # fmt: skip
    diff = [r.profit - r.expected_profit for r in known]
    mean, se = _mean_se(diff)
    checks.append(Check("1b-C znana odpowiedź: zysk - Σ stawka·EV kuponu (podatek reżimu, T13) ≈ 0",
                        abs(mean) <= 2 * se, f"średnia {mean:+.2f} zł, SE {se:.2f}, nasion {len(diff)}"))  # fmt: skip

    zero = many("2a-C", "c120", strategy="C", soft_factor=0.95, tax_factor=1.0)
    n_zero = sum(r.n_coupons for r in zero)
    checks.append(Check("2a-C placebo: k = 0.95/p → zero kuponów", n_zero == 0, f"kuponów {n_zero}"))
    forced = many("2b-C", "solo", strategy="C", soft_factor=0.95, tax_factor=1.0, forced=True)
    gaps = [(r.profit - r.expected_profit) / r.turnover for r in forced if r.turnover > 0]
    yields = [r.profit / r.turnover for r in forced if r.turnover > 0]
    theory = [r.expected_profit / r.turnover for r in forced if r.turnover > 0]
    mean, se = _mean_se(gaps)
    f_multi = sum(r.n_multi for r in forced)
    checks.append(Check("2b-C placebo wymuszone: yield = teoria Σ stawka·(0.95·tax - 1)/obrót ± 2 SE",
                        abs(mean) <= 2 * se and f_multi == 0 and len(gaps) > 0,
                        f"yield {np.mean(yields):+.4f} vs teoria {np.mean(theory):+.4f}; różnica {mean:+.4f}, "
                        f"SE {se:.4f}, nasion {len(gaps)}; dubletów {f_multi} (EV dubletu 0.95² - 1 < θ — "
                        "planista nie łączy, single w trybie `literal`)"))  # fmt: skip

    taxed = many("3a-C", "solo", strategy="C", soft_factor=1.10, tax_factor=1.0)
    yields = [r.profit / r.turnover for r in taxed if r.turnover > 0]
    target = 1.10 * 0.94 - 1
    mean, se = _mean_se(yields)
    only_094 = all(tax == 0.94 and kind == "single" for r in taxed for kind, tax, _ in r.tax_counts)
    checks.append(Check("3a-C podatek: udział AKO 0 (brak dubletów) → single 0.94, e = 0.10: yield 3.4% ± 2 SE",
                        abs(mean - target) <= 2 * se and only_094,
                        f"yield {mean:+.4f} vs {target:+.4f}, SE {se:.4f}; wszystkie kupony single 0.94: {only_094}; "
                        f"świat solo: {len(worlds['solo'])} meczów"))  # fmt: skip
    small = many("3b-C", "solo", strategy="C", soft_factor=1 + EDGE, tax_factor=1.0)
    n_small = sum(r.n_coupons for r in small)
    checks.append(Check("3b-C podatek 0.94, e = 0.025, brak dubletów: zero kuponów", n_small == 0,
                        f"kuponów {n_small}"))  # fmt: skip
    checks.append(regime_transitions_check())
    # 3d-C (audyt wariantu B, POWAŻNE 1): reżim w paśmie udziału ~50% — podatek
    # każdego kuponu = niezależny checker; pusta zieleń (brak kuponów w paśmie) = czerwień.
    band = many("3d-C", "band", strategy="C", soft_factor=1.10, tax_factor=1.0)
    band_errors = [e for r in band for e in r.tax_errors]
    in_band = sum(r.share_band for r in band)
    band_taxes = Counter()
    for r in band:
        for kind, tax, n in r.tax_counts:
            band_taxes[(kind, tax)] += n
    both = band_taxes[("single", 1.0)] > 0 and band_taxes[("single", 0.94)] > 0
    checks.append(Check("3d-C reżim w paśmie udziału ~50% (okno, kolejność kandydatów): podatek = niezależny checker",
                        not band_errors and in_band > 0 and both,
                        f"kuponów z udziałem w [0.40, 0.60]: {in_band}; single 1.00 / 0.94: "
                        f"{band_taxes[('single', 1.0)]} / {band_taxes[('single', 0.94)]}; podatek ≠ checker: "
                        f"{len(band_errors)}" + (f" — {band_errors[:3]}" if band_errors else "")
                        + f"; świat band: {len(worlds['band'])} meczów"))  # fmt: skip

    base_runs = many("4-base-C", "c120", strategy="C", soft_factor=1 + EDGE, tax_factor=1.0, detail=True)
    base = {r.seed: r for r in base_runs}
    noisy = many("4a-C", "c120", strategy="C", soft_factor=1 + EDGE, tax_factor=1.0, closing_noise=True, detail=True)
    same = all(r.coupon_list == base[r.seed].coupon_list for r in noisy)
    changed = all(r.clv_values != base[r.seed].clv_values for r in noisy)
    checks.append(Check("4a-C trucizna: losowe zamknięcia → te same kupony (nogi, kursy, stawki), inne CLV",
                        same and changed and all(r.coupon_list for r in noisy),
                        f"kupony identyczne: {same}; CLV inne: {changed}"
                        + "".join(f"; nasiono {r.seed}: {_coupon_diff(r.coupon_list, base[r.seed].coupon_list)}"
                                  for r in noisy if r.coupon_list != base[r.seed].coupon_list)[:400]))  # fmt: skip
    permuted = many("4b-C", "c120", strategy="C", soft_factor=1 + EDGE, tax_factor=1.0, permute_results=True,
                    detail=True)  # fmt: skip
    checks.append(check_4b_c(base, permuted))
    part_runs = many("4c-C", "c120-early", strategy="C", soft_factor=1 + EDGE, tax_factor=1.0, detail=True)
    cut = datetime.fromisoformat(_CUTS["c120"]) if "c120" in _CUTS else _END
    trunc_ok = bool(part_runs)
    for part in part_runs:
        upto_full = [c for c in base[part.seed].coupon_list if datetime.fromisoformat(c[0]) <= cut]
        upto_part = [c for c in part.coupon_list if datetime.fromisoformat(c[0]) <= cut]
        trunc_ok &= upto_full == upto_part and bool(upto_full)
    checks.append(Check("4c-C trucizna: mecze po dniu D usunięte → kupony do D identyczne (nogi, kursy, stawki)",
                        trunc_ok, f"dzień D = {cut.date() if cut != _END else '—'}"))  # fmt: skip

    recon = sum(r.reconcile_mismatches for r in known + forced)
    multi_recon = sum(r.n_multi for r in known)
    checks.append(Check("5-C podwójne księgowanie kuponów wielonożnych: symulator == reconcile w groszach",
                        recon == 0 and multi_recon > 0,
                        f"niezgodnych rozliczeń {recon}; dubletów w porównaniu {multi_recon} "
                        "(reconcile_bets.py nie importuje valuebet — test_reconcile_is_independent_of_pricing)"))  # fmt: skip
    tax_errors = [e for r in known + taxed + forced + band for e in r.tax_errors]
    pessimistic = sum(r.tax_pessimistic for r in known + taxed + forced + band)
    by_tax = Counter()
    for r in known:
        for kind, tax, n in r.tax_counts:
            by_tax[(kind, tax)] += n
    tax_desc = ", ".join(f"{kind} {tax:.2f}: {n}" for (kind, tax), n in sorted(by_tax.items()))
    checks.append(check_six(production=[r.invariants for r in known + taxed],
                            other=[r.invariants for r in forced],
                            label="6-C niezmienniki: limity (pełna stawka dubletu w obu meczach), nogi z różnych meczów ≥ 1.20, porządek czasu, podatek = niezależny checker reżimu",
                            extra_errors=tax_errors,
                            extra_detail=f"; podatek ≠ checker: {len(tax_errors)}; single rozstrzygnięte "
                                         f"pesymistycznie (cykl podatek↔stawka): {pessimistic}; 1-C wg podatku: {tax_desc}"))  # fmt: skip
    return checks


def check_4b_c(base: dict[int, SeedRun], permuted: Sequence[SeedRun]) -> Check:
    """4b-C dla strategii zależnej od ścieżki (zmiana kryterium 2026-10-12, po czerwonym
    4b-C na świecie syntetycznym bramki 2624fff — BACKTEST_FIN_PLAN §4).

    (i) kandydaci identyczni; (ii) wspólne kupony: nogi i kursy z klucza, stawka = wzór
    Kelly'ego z księgi TEGO przebiegu, podatek = ``RefRegime`` (6-C); (iii) kupon tylko w
    jednym przebiegu: w drugim wpis odrzucenia z przyczyną potwierdzoną niezależnie;
    (iv) różnica PAPER: tryby zgodne z obsunięciem z księgi; (v) reszta = CZERWONY;
    (vi) P&L inny."""
    same_cand = all(sorted(r.candidates) == sorted(base[r.seed].candidates) for r in permuted)
    pnl = all(r.profit != base[r.seed].profit for r in permuted)
    kelly_ok = all(not r.kelly_mismatch for r in [*permuted, *base.values()])
    parts: list[str] = []
    bad: list[str] = []
    for r in permuted:
        explained, unexplained = path_explained(base[r.seed], r)
        bad += [f"nasiono {r.seed}: {u}" for u in unexplained]
        counts = ", ".join(f"{k}: {v}" for k, v in sorted(explained.items())) or "brak różnic"
        parts.append(f"nasiono {r.seed}: wyjaśnione — {counts}")
    runs = [*base.values(), *permuted]
    audited = [r.path_stats for r in runs if r.path_stats]
    checked, ties, by_tie, rejected = (sum(x[i] for x in audited) for i in range(4))
    max_dcap = max((x[4] for x in audited), default=0.0)
    # bez audytu z księgi w którymkolwiek przebiegu kryterium nie jest sprawdzone
    passed = (same_cand and pnl and kelly_ok and not bad and all(r.coupon_list for r in permuted)
              and len(audited) == len(runs))
    return Check("4b-C trucizna (kryterium ścieżki, 2026-10-12): spermutowane wyniki → ci sami kandydaci; każda różnica kuponów wyjaśniona stanem przebiegu (kapitał, PAPER, min. stawka) potwierdzonym z księgi; inny P&L",
                 passed, f"kandydaci identyczni: {same_cand}; stawki = wzór (silnik): {kelly_ok}; P&L inny: {pnl}; "
                 + "; ".join(parts) + f"; niewyjaśnionych: {len(bad)}" + (f" — pierwsza: {bad[0]}" if bad else "")
                 + f"; audyt stawek z księgi (przebiegów {len(audited)}/{len(runs)}): kuponów {checked}, remisów "
                 f"{ties}, zaakceptowanych jako remis {by_tie}, odrzuconych {rejected}, max |Δ kapitału| "
                 f"{max_dcap:.3e} (próg {REF_CAPITAL_TOL:.0e})")  # fmt: skip


def regime_transitions_check() -> Check:
    """3c-C: deterministyczne przejścia reżimu — silnik (``pricing.ev``) == checker == literał."""
    from valuebet.pricing.ev import BetclicTaxRegime, CouponLeg, PlacedBet, RegimeConfig

    start = datetime(2025, 1, 1, tzinfo=UTC)
    now = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    seq = itertools.count()

    def coupon(stake: float, legs: Sequence[tuple[str, float]]) -> tuple[PlacedBet, RefCoupon]:
        at = now - timedelta(days=1, minutes=next(seq))
        engine = PlacedBet(coupon_id=f"h{at.timestamp()}", placed_at=at, stake=stake, mode="real",
                           legs=tuple(CouponLeg(match_id=m, odds=k, void=False, market="h2h") for m, k in legs))  # fmt: skip
        return engine, RefCoupon(at, stake, tuple(legs), True)

    ako = (("p", 1.5), ("q", 1.6))
    short = (("a", 1.15), ("b", 2.0))
    cases = [
        # (opis, historia, stawka kandydata, nogi kandydata, oczekiwany literał)
        ("limit: zostaje 0,01 zł, singiel 50 zł", [(999.99, (("x", 2.0),))], 50.0, (("k", 2.0),), 1.00),
        ("limit: 900 + singiel 5000 zł (§3 ust. 4)", [(900.0, (("x", 2.0),))], 5000.0, (("k", 2.0),), 1.00),
        ("limit wyczerpany, udział 0", [(1000.0, (("x", 2.0),))], 0.5, (("k", 2.0),), 0.94),
        ("udział dokładnie 0.50", [(1000.0, ako), (990.0, (("s", 2.0),))], 10.0, (("k", 2.0),), 1.00),
        ("udział 0.4999", [(4999.0, ako), (4991.0, (("s", 2.0),))], 10.0, (("k", 2.0),), 0.94),
        ("wielokrotny niekwalif., udział 0.50", [(1000.0, ako), (990.0, (("s", 2.0),))], 10.0, short, 1.00),
        ("wielokrotny niekwalif., udział 0.4999", [(4999.0, ako), (4991.0, (("s", 2.0),))], 10.0, short, 0.94),
        ("AKO kwalifikowany, udział 0", [(1000.0, (("x", 2.0),))], 10.0, (("m", 1.2), ("n", 3.0)), 1.00),
        ("dwie nogi z jednego meczu, udział 0", [(1000.0, (("x", 2.0),))], 10.0, (("m", 1.5), ("m", 2.0)), 0.94),
    ]
    bad: list[str] = []
    for name, history, stake, legs, literal in cases:
        built = [coupon(s, lg) for s, lg in history]
        cfg = RegimeConfig(promo_active=True, promo_valid_from=start, join_date=start,
                           external_turnover_pln=0.0, external_coupons=0, share_condition_known=True,
                           min_stake_pln=MIN_STAKE_PLN, excluded_markets=frozenset(),
                           share_basis=SHARE_BY_STAKES)  # fmt: skip
        regime = BetclicTaxRegime(now=now, bets=[e for e, _ in built], regime_config=cfg)
        engine_legs = tuple(CouponLeg(match_id=m, odds=k, void=False, market="h2h") for m, k in legs)
        engine = regime.tax_for_coupon(stake=stake, legs=engine_legs)
        ref = RefRegime(start=start, external_pln=0.0, min_stake_pln=MIN_STAKE_PLN)
        for _, r in sorted(built, key=lambda x: x[1].placed_at):
            ref.add(r)
        checker = ref.tax(now=now, stake=stake, legs=legs)
        if not engine == checker == literal:
            bad.append(f"{name}: silnik {engine}, checker {checker}, literał {literal}")
    return Check("3c-C przejścia reżimu (próg limitu 1000 zł, udział 0.50 / 0.4999, wielokrotny niekwalif.): silnik == checker == literał",
                 not bad, f"przypadków {len(cases)}; niezgodnych {len(bad)}" + (f": {bad}" if bad else ""))  # fmt: skip


def spy_check(truth: Sequence[TrueMatch], *, workdir: Path) -> Check:
    """§4 pkt 7: backtest woła funkcje modułów live — szpiedzy na ich miejscu w
    ``financial`` (A) oraz metody ``RegimePlanner`` i reżimu ``pricing.ev`` (C)."""
    import valuebet.backtest.clv as clv_module
    import valuebet.live.bets as bets_module
    import valuebet.pricing.ev as ev_module
    import valuebet.pricing.fair as fair_module
    import valuebet.pricing.kelly as kelly_module

    identity = {
        "fair_prices": financial.fair_prices is fair_module.fair_prices,
        "min_odds": financial.min_odds is ev_module.min_odds,
        "KellyPolicy": financial.KellyPolicy is kelly_module.KellyPolicy,
        "BetJournal": financial.BetJournal is bets_module.BetJournal,
        "open_stake": financial.open_stake is bets_module.open_stake,
        "clv_rows": financial.clv_rows is clv_module.clv_rows,
        "C: BetclicTaxRegime": strategy_c.BetclicTaxRegime is ev_module.BetclicTaxRegime,
        "C: simulate": strategy_c.simulate is financial.simulate,
        "C: min_odds": strategy_c.min_odds is ev_module.min_odds,
    }
    calls: dict[str, int] = dict.fromkeys(
        ["fair_prices", "min_odds", "KellyPolicy", "BetJournal", "open_stake", "clv_rows"], 0
    )
    originals: dict[str, Any] = {}

    def spy(name: str, target: Any) -> Any:
        def wrapper(*a: Any, **k: Any) -> Any:
            calls[name] = calls.get(name, 0) + 1
            return target(*a, **k)
        return wrapper

    for name in ("fair_prices", "min_odds", "open_stake", "clv_rows"):
        originals[name] = getattr(financial, name)
        setattr(financial, name, spy(name, originals[name]))
    from_journal = kelly_module.KellyPolicy.from_journal
    add = bets_module.BetJournal.add_coupon

    def journal_spy(self: BetJournal, legs: Sequence[BetRecord]) -> None:
        calls["BetJournal"] += 1
        add(self, legs)

    def kelly_spy(**kw: Any) -> Any:
        calls["KellyPolicy"] += 1
        return from_journal(**kw)

    patches: list[tuple[Any, str, Any, Any]] = [
        (bets_module.BetJournal, "add_coupon", journal_spy, add),
        (kelly_module.KellyPolicy, "from_journal", staticmethod(kelly_spy), from_journal),
    ]
    c_methods = [
        (strategy_c.RegimePlanner, "begin"), (strategy_c.RegimePlanner, "groups"),
        (strategy_c.RegimePlanner, "price"), (strategy_c.RegimePlanner, "placed"),
        (ev_module.BetclicTaxRegime, "tax_for_single"), (ev_module.BetclicTaxRegime, "tax_for_multi"),
        (ev_module.BetclicTaxRegime, "share_condition_met"), (ev_module.BetclicTaxRegime, "assume"),
    ]  # fmt: skip
    for owner, attr in c_methods:
        key = f"C: {owner.__name__}.{attr}"
        calls[key] = 0
        patches.append((owner, attr, spy(key, getattr(owner, attr)), getattr(owner, attr)))
    for owner, attr, fake, _ in patches:
        setattr(owner, attr, fake)
    try:
        run_seed(truth[:60], strategy="A", seed=0, soft_factor=1 + EDGE, tax_factor=1.0, workdir=workdir)
        run_seed(c120_truth(truth)[:60], strategy="C", seed=0, soft_factor=1 + EDGE, tax_factor=1.0,
                 workdir=workdir)  # fmt: skip
        # solo: same single (dublet niemożliwy) — ścieżka udziału AKO (``share_condition_met``)
        run_seed(solo_truth(truth)[:20], strategy="C", seed=0, soft_factor=1.10, tax_factor=1.0,
                 workdir=workdir)  # fmt: skip
    finally:
        for name, fn in originals.items():
            setattr(financial, name, fn)
        for owner, attr, _, real in patches:
            setattr(owner, attr, real)
    ok = all(identity.values()) and all(v > 0 for v in calls.values())
    return Check("7 jedna ścieżka kodu: szpiedzy wywołani (A i C: RegimePlanner, reżim pricing.ev), nazwy = funkcje live",
                 ok, f"tożsamość: {identity}; wywołania: {calls}")  # fmt: skip


def _lower_priority() -> None:
    """Robotnik bramki z priorytetem BelowNormal — kolektor ma pierwszeństwo."""
    if sys.platform == "win32":
        import ctypes

        below_normal = 0x00004000
        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), below_normal)


#: Domyślnie 3 z 8 rdzeni (incydent 2026-10-08: 8 robotników zagłodziło kolektor).
DEFAULT_WORKERS = 3
#: Bezpiecznik w trakcie: < 3 GB na dysku repo ALBO na dysku katalogu
#: tymczasowego → stop (wyniki cząstkowe zostają w reports/, ``--resume``).
MIN_FREE_BYTES = 3 * 1024**3
#: Preflight przed startem (dopisek 3 Pawła 2026-10-11, zastępuje 8 GB z dopisku
#: 2): ≥ 6 GB na dysku repo i ≥ 10 GB na dysku katalogu tymczasowego (TEMP/TMP
#: — w poleceniu bramki ``D:/vb-tmp``; dzienniki przebiegów i plik wymiany).
MIN_START_FREE_REPO_BYTES = 6 * 1024**3
MIN_START_FREE_TEMP_BYTES = 10 * 1024**3


def temp_dir() -> Path:
    """Katalog tymczasowy bramki — z TEMP/TMP (``tempfile``), tam idą dzienniki nasion."""
    return Path(tempfile.gettempdir())


def _drive(path: Path) -> str:
    return path.resolve().anchor or str(path)


def free_gb(path: Path | None = None) -> float:
    return shutil.disk_usage(ROOT if path is None else path).free / 1024**3


def disk_status() -> str:
    """Wolne miejsce na dysku repo i dysku katalogu tymczasowego — do postępu i komunikatów."""
    tmp = temp_dir()
    return (f"repo {_drive(ROOT)} {free_gb():.1f} GB wolne; tmp {tmp} ({_drive(tmp)}) "
            f"{free_gb(tmp):.1f} GB wolne")  # fmt: skip


def free_ram_mb() -> float | None:
    """Wolny RAM (Windows: ``GlobalMemoryStatusEx``); ``None`` gdzie indziej."""
    if sys.platform != "win32":
        return None
    import ctypes

    class _Status(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]  # fmt: skip

    status = _Status()
    status.dwLength = ctypes.sizeof(_Status)
    ctypes.WinDLL("kernel32").GlobalMemoryStatusEx(ctypes.byref(status))
    return status.ullAvailPhys / 1024**2


def _require_free_space(phase: str) -> None:
    """Twardy próg: < 3 GB na dysku repo albo tymczasowym → bramka staje (każdy seed i faza).

    Niczego nie kasuje — wyniki cząstkowe (małe) zostają w reports/.
    """
    for label, path in (("repo", ROOT), ("tymczasowy", temp_dir())):
        free = shutil.disk_usage(path).free
        if free < MIN_FREE_BYTES:
            raise RuntimeError(
                f"[{phase}] dysk {label} ({path}): wolne {free / 1024**3:.2f} GB < 3 GB — przerywam. "
                "Wyniki cząstkowe zostają w reports/backtest_fin/<commit>/partial/; po zwolnieniu "
                "miejsca wznów to samo polecenie z --resume"
            )


def preflight(phase: str) -> None:
    """Wolne miejsce ≥ 3 GB w trakcie — inaczej bramka staje.

    Bez sprawdzania heartbeatu kolektora: od 2026-10-10 kolektor działa na VPS
    (timer systemd), lokalny ``data/state/odds_api/heartbeat.jsonl`` już nie
    rośnie i zatrzymywałby każdą bramkę (zgoda Pawła 2026-10-10, FIX_LOG_F0).
    """
    _require_free_space(phase)


def preflight_start() -> None:
    """Przed startem: ≥ 6 GB na dysku repo i ≥ 10 GB na dysku katalogu tymczasowego
    (dopisek 3 Pawła 2026-10-11, po awarii 17a0759)."""
    for label, path, need in (("repo", ROOT, MIN_START_FREE_REPO_BYTES),
                              ("tymczasowy", temp_dir(), MIN_START_FREE_TEMP_BYTES)):  # fmt: skip
        free = shutil.disk_usage(path).free
        if free < need:
            raise RuntimeError(
                f"dysk {label} ({path}): wolne {free / 1024**3:.2f} GB < {need // 1024**3} GB — bramka nie "
                "startuje. Katalog tymczasowy przenieś na D: (PowerShell: $env:TEMP i $env:TMP = D:/vb-tmp), zwolnij "
                "miejsce (cache projektu, `uv cache clean`, kosz) i uruchom ponownie; bezpiecznik w trakcie: 3 GB"
            )


# -- wyniki cząstkowe, wznowienie, postęp (dopisek Pawła 2026-10-11) -----------


class ResumeRefusedError(RuntimeError):
    """Wyniki cząstkowe niezgodne z tym przebiegiem (commit, nasiona, parametry)."""


def _partial_name(test_id: str, seed: int) -> str:
    return f"{test_id}__seed{seed:04d}.pkl"


@dataclass
class PartialStore:
    """Wyniki cząstkowe: jeden plik (pickle, zapis atomowy) na test i nasiono.

    Plik niesie commit, liczbę nasion i parametry przebiegu — ``--resume``
    przyjmuje go tylko przy zgodności wszystkich trzech (inaczej odmowa).
    Pliki piszemy i czytamy wyłącznie sami (reports/, nie dane z zewnątrz).
    """

    folder: Path
    commit: str
    n_seeds: int
    resume: bool
    #: sha256 terminarza bramki (``world_digest``) — audyt wariantu B, POWAŻNE 2:
    #: wyniki z innych danych raw nie mogą wejść do raportu.
    world: str
    loaded: int = 0
    resumed: bool = False
    _cache: dict[tuple[str, int], SeedRun] = field(default_factory=dict)

    def __post_init__(self) -> None:
        existing = sorted(self.folder.glob("*.pkl")) if self.folder.exists() else []
        if existing and not self.resume:
            raise ResumeRefusedError(
                f"{self.folder}: są wyniki cząstkowe ({len(existing)} plików) — uruchom z --resume "
                "albo usuń katalog partial/"
            )
        for path in existing:
            payload = pickle.loads(path.read_bytes())
            if payload.get("world") != self.world:
                raise ResumeRefusedError(
                    f"{path.name}: świat (sha256 terminarza) {payload.get('world')} ≠ {self.world} — inne dane "
                    "raw (--raw-root?); wznowienie odrzucone; usuń partial/ i zacznij od nowa"
                )
            if payload["commit"] != self.commit or payload["n_seeds"] != self.n_seeds:
                raise ResumeRefusedError(
                    f"{path.name}: commit {payload['commit']} / nasion {payload['n_seeds']}, a przebieg: "
                    f"{self.commit} / {self.n_seeds} — wznowienie odrzucone; usuń partial/ i zacznij od nowa"
                )
            self._cache[(payload["test_id"], payload["item"]["seed"])] = payload
        self.loaded = len(self._cache)
        self.resumed = self.loaded > 0

    def get(self, test_id: str, item: dict[str, Any]) -> SeedRun | None:
        payload = self._cache.get((test_id, item["seed"]))
        if payload is None:
            return None
        if payload["item"] != item:
            raise ResumeRefusedError(
                f"{test_id} nasiono {item['seed']}: parametry {payload['item']} ≠ {item} — wznowienie odrzucone"
            )
        result: SeedRun = payload["result"]
        return result

    def put(self, test_id: str, item: dict[str, Any], result: SeedRun) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        payload = {"commit": self.commit, "n_seeds": self.n_seeds, "world": self.world, "test_id": test_id,
                   "item": item, "result": result}  # fmt: skip
        write_atomic(self.folder / _partial_name(test_id, item["seed"]), pickle.dumps(payload))


@dataclass
class Progress:
    """Linie postępu co ≥ ``every_s``: test, nasiono k/N, czas, ETA, wolne GB, RAM."""

    total: int
    every_s: float = 60.0
    done: int = 0
    computed: int = 0
    started: float = field(default_factory=time.monotonic)
    _last: float = field(default_factory=time.monotonic)
    _computed_time: float = 0.0
    lines: list[str] = field(default_factory=list)
    #: Kupony w trybie PAPER per test (komunikat raz na przebieg, licznik tutaj).
    paper: Counter[str] = field(default_factory=Counter)

    def tick(self, test_id: str, k: int, n: int, *, computed: bool, seconds: float = 0.0) -> None:
        self.done += 1
        if computed:
            self.computed += 1
            self._computed_time += seconds
        now = time.monotonic()
        if now - self._last < self.every_s and self.done < self.total:
            return
        self._last = now
        elapsed = now - self.started
        per = (elapsed / self.computed) if self.computed else 0.0
        eta = per * (self.total - self.done)
        ram = free_ram_mb()
        line = (f"[postęp] {test_id}: nasiono {k}/{n}; przebiegów {self.done}/{self.total}; "
                f"od startu {timedelta(seconds=int(elapsed))}; do końca ~{timedelta(seconds=int(eta))}; "
                f"{disk_status()}; RAM wolny {'?' if ram is None else f'{ram:.0f} MB'}")  # fmt: skip
        self.lines.append(line)
        log.info(line)


_WORKER: dict[str, Any] = {}


def _init_worker(worlds: dict[str, list[TrueMatch]], workdir: str) -> None:
    _lower_priority()
    _WORKER["worlds"] = worlds
    _WORKER["workdir"] = Path(workdir)


def _run_in_worker(job: tuple[int, dict[str, Any]]) -> tuple[int, SeedRun, float]:
    index, item = job
    t0 = time.monotonic()
    result = run_item(_WORKER["worlds"], _WORKER["workdir"], item)
    return index, result, time.monotonic() - t0


def caching_runner(*, worlds: dict[str, list[TrueMatch]], workdir: Path, store: PartialStore,
                   progress: Progress, pool: Any | None) -> Runner:  # fmt: skip
    """Wykonawca bramki: najpierw wyniki cząstkowe, reszta w puli (albo w procesie)."""
    def runner(test_id: str, items: list[dict[str, Any]]) -> list[SeedRun]:
        out: list[SeedRun | None] = [None] * len(items)
        todo: list[tuple[int, dict[str, Any]]] = []
        for i, item in enumerate(items):
            cached = store.get(test_id, item)
            if cached is None:
                todo.append((i, item))
            else:
                out[i] = cached
                progress.paper[test_id] += cached.paper_coupons
                progress.tick(test_id, i + 1, len(items), computed=False)
        results: Iterator[tuple[int, SeedRun, float]]
        if pool is not None:
            results = pool.imap_unordered(_run_in_worker, todo)
        else:
            results = ((i, run_item(worlds, workdir, item), 0.0) for i, item in todo)
        finished = len(items) - len(todo)
        for i, result, seconds in results:
            store.put(test_id, items[i], result)
            out[i] = result
            progress.paper[test_id] += result.paper_coupons
            finished += 1
            progress.tick(test_id, finished, len(items), computed=True, seconds=seconds)
        assert all(r is not None for r in out)
        return [r for r in out if r is not None]

    return runner


def run_gate(truth: Sequence[TrueMatch], *, seeds: int, workdir: Path, partial: Path, commit: str,
             resume: bool, pool: Any | None = None,
             progress_every_s: float = 60.0) -> tuple[list[Check], PartialStore, Progress]:  # fmt: skip
    """Rdzeń ``main`` (testowalny bez puli): bramka z wynikami cząstkowymi i postępem."""
    store = PartialStore(partial, commit, seeds, resume, world_digest(truth))
    worlds = build_worlds(truth)
    _remember_cuts(worlds)
    progress = Progress(total=sum(plan(seeds).values()), every_s=progress_every_s)
    runner = caching_runner(worlds=worlds, workdir=workdir, store=store, progress=progress, pool=pool)
    checks = gate(truth, seeds=range(seeds), workdir=workdir, runner=runner, checkpoint=preflight)
    return checks, store, progress


def world_digest(truth: Sequence[TrueMatch]) -> str:
    """sha256 terminarza bramki (mecz, liga, sezon, gwizdek, obserwacja, p_true)."""
    import hashlib

    rows = sorted((t.match_id, t.league, t.season, t.kickoff.isoformat(), t.observed_at.isoformat(),
                   sorted(t.p.items())) for t in truth)  # fmt: skip
    return hashlib.sha256(repr(rows).encode("utf-8")).hexdigest()


def fixture_truth(store: RawStore) -> list[TrueMatch]:
    """Terminarz bramki z ``store`` — wyłącznie odczyt (``latest`` + ``read_bytes``)."""
    rule = load_strategy().observed_at_rule
    replays = []
    for league, season in FIXTURE_FILES:
        path = store.latest(RAW_SUBDIR, f"{league}-{season}", ".csv")
        if path is None:
            raise FileNotFoundError(f"{league}-{season} brak w {store.root} — najpierw ingest")
        replays.append(replay_csv(path.read_bytes(), league=league, season=season, rule=rule))
    return truth_from_replay(merge_replays(replays))


# -- tryb częściowy: --only 4b-C (decyzja Architekta 2026-10-15) ----------------------
#: Jedyny test, który wolno uruchomić osobno — naprawa remisu zaokrąglenia w audycie
#: 4b-C dotknęła tylko scripts/ i tests/; reszta bramki 27ae469 (24/25) obowiązuje.
PARTIAL_TESTS = ("4b-C",)
#: Bramka odniesienia: src/ i config/ muszą być z nią bit-w-bit identyczne.
PARTIAL_REFERENCE = "27ae469"
PARTIAL_HEADER = (f"CZĘŚCIOWY — NIE BRAMKA; uzupełnia bramkę {PARTIAL_REFERENCE} "
                  "(24/25 OK, 4b-C czerwone: remis zaokrąglenia)")  # fmt: skip


class PartialRunRefusedError(RuntimeError):
    """src/ albo config/ różnią się od bramki odniesienia — wynik częściowy nic by nie znaczył."""


def src_config_diff(root: Path, reference: str) -> str:
    """``git diff <reference>..HEAD -- src config`` (pełny tekst; pusty = bez zmian)."""
    return subprocess.run(["git", "diff", f"{reference}..HEAD", "--", "src", "config"], cwd=root,
                          capture_output=True, text=True, check=True, encoding="utf-8").stdout  # fmt: skip


def require_unchanged_src(diff: str) -> None:
    """Strażnik trybu częściowego: niepusty diff src/config → odmowa."""
    if diff.strip():
        raise PartialRunRefusedError(
            f"src/ albo config/ zmienione względem {PARTIAL_REFERENCE} — tryb --only odmawia; "
            "potrzebna pełna bramka:\n" + diff[:2000]
        )


def gate_4bc_only(many: Callable[..., list[SeedRun]]) -> list[Check]:
    """4-base-C i 4b-C dokładnie jak w ``gate_c`` (zgodność pilnuje test_engine_partial)."""
    base_runs = many("4-base-C", "c120", strategy="C", soft_factor=1 + EDGE, tax_factor=1.0, detail=True)
    permuted = many("4b-C", "c120", strategy="C", soft_factor=1 + EDGE, tax_factor=1.0, permute_results=True,
                    detail=True)  # fmt: skip
    return [check_4b_c({r.seed: r for r in base_runs}, permuted)]


def run_partial(truth: Sequence[TrueMatch], *, seeds: int, workdir: Path, partial: Path, commit: str,
                pool: Any | None = None,
                progress_every_s: float = 60.0) -> tuple[list[Check], PartialStore, Progress]:  # fmt: skip
    """Rdzeń ``--only 4b-C``: bez wznawiania (``resume=False`` — pliki cząstkowe z innego
    przebiegu w ``partial`` = odmowa), nasiona jak w bramce (``plan``)."""
    store = PartialStore(partial, commit, seeds, False, world_digest(truth))
    worlds = build_worlds(truth)
    counts = plan(seeds)
    progress = Progress(total=counts["4-base-C"] + counts["4b-C"], every_s=progress_every_s)
    runner = caching_runner(worlds=worlds, workdir=workdir, store=store, progress=progress, pool=pool)

    def many(test_id: str, world: str, **kw: Any) -> list[SeedRun]:
        preflight(test_id)
        return runner(test_id, [dict(kw, world=world, seed=s) for s in range(seeds)[: counts[test_id]]])

    return gate_4bc_only(many), store, progress


def main_partial(args: argparse.Namespace, *, commit: str) -> int:
    """``--only 4b-C``: strażnik src/config, 20 przebiegów, raport ENGINE_TESTS_4bC.*."""
    diff = src_config_diff(ROOT, PARTIAL_REFERENCE)
    try:
        require_unchanged_src(diff)
    except PartialRunRefusedError:
        log.exception("tryb --only %s: odmowa", args.only)
        return 3
    truth = fixture_truth(RawStore(root=args.raw_root))
    started = datetime.now(UTC)
    out = ROOT / "reports" / "backtest_fin" / commit
    with tempfile.TemporaryDirectory(prefix="vb-engine-") as tmp:
        work = Path(tmp)
        preflight("start")
        _lower_priority()
        worlds = build_worlds(truth)
        with multiprocessing.Pool(processes=args.workers, initializer=_init_worker,
                                  initargs=(worlds, str(work))) as pool:  # fmt: skip
            checks, store, progress = run_partial(truth, seeds=args.seeds, workdir=work, partial=out / "partial-4bC",
                                                  commit=commit, pool=pool)  # fmt: skip
        preflight("koniec")
    passed = all(c.passed for c in checks)
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "header": PARTIAL_HEADER, "partial": True, "is_gate": False, "only": args.only,
        "commit": commit, "reference_commit": PARTIAL_REFERENCE,
        "src_config_diff_command": f"git diff {PARTIAL_REFERENCE}..HEAD -- src config", "src_config_diff": diff,
        "generated_by": generated_by(script=SCRIPT, root=ROOT),
        "started_at": started.isoformat(), "finished_at": datetime.now(UTC).isoformat(),
        "seeds": args.seeds, "poison_seeds": min(POISON_SEEDS, args.seeds), "workers": args.workers,
        "n_matches": len(truth), "raw_root": str(args.raw_root), "world_sha256": store.world,
        "seed_runs_total": progress.total, "paper_coupons": dict(progress.paper),
        "passed": passed, "checks": [c.__dict__ for c in checks],
    }  # fmt: skip
    (out / "ENGINE_TESTS_4bC.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [f"# Testy silnika (§4) — {PARTIAL_HEADER}", "",
             f"Commit: `{commit}`; odniesienie: `{PARTIAL_REFERENCE}`; tryb `--only {args.only}` "
             f"(4-base-C + 4b-C, nasion {min(POISON_SEEDS, args.seeds)}, przebiegów {progress.total}); "
             f"robotników {args.workers}; mecze świata: {len(truth)}; sha256 terminarza `{store.world}`.", "",
             f"`git diff {PARTIAL_REFERENCE}..HEAD -- src config`: "
             + ("**PUSTY** (src/ i config/ bit-w-bit jak w bramce odniesienia)." if not diff.strip() else "NIEPUSTY"),
             "", f"**WYNIK 4b-C: {'ZIELONE' if passed else 'CZERWONE — STOP'}** (to NIE jest bramka)", "",
             "| test | wynik | szczegóły |", "|---|---|---|"]  # fmt: skip
    lines += [f"| {c.name} | {'OK' if c.passed else 'CZERWONY'} | {c.detail} |" for c in checks]
    (out / "ENGINE_TESTS_4bC.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"passed": passed, "report": (out / "ENGINE_TESTS_4bC.md").as_posix()}, ensure_ascii=False))
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bramka §4 silnika finansowego (A i C)")
    parser.add_argument("--seeds", type=int, default=200)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--resume", action="store_true",
                        help="pomiń nasiona z reports/backtest_fin/<commit>/partial/ (ten sam commit, "
                             "nasiona, parametry)")  # fmt: skip
    parser.add_argument("--raw-root", type=Path, default=RAW_ROOT,
                        help="katalog data/raw — TYLKO ODCZYT (np. data/raw repo głównego z worktree)")  # fmt: skip
    parser.add_argument("--only", choices=PARTIAL_TESTS, default=None,
                        help="tryb częściowy (NIE bramka): tylko 4-base-C + 4b-C; wymaga src/ i config/ "
                             f"identycznych z {PARTIAL_REFERENCE}; raport ENGINE_TESTS_4bC.*")  # fmt: skip
    args = parser.parse_args(argv)
    if args.only is not None and args.resume:
        parser.error("--only nie łączy się z --resume (tryb częściowy liczy wszystko od nowa)")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log.info("katalog tymczasowy bramki: %s; %s", temp_dir(), disk_status())
    preflight_start()
    commit = frozen_commit(script=SCRIPT, root=ROOT)
    if _STRATEGY.backtest_start_capital_pln != START:
        raise ValueError(f"START {START} ≠ backtest_start_capital_pln z config/strategy.yaml (plan §3)")
    if args.only is not None:
        return main_partial(args, commit=commit)
    truth = fixture_truth(RawStore(root=args.raw_root))
    started = datetime.now(UTC)
    out = ROOT / "reports" / "backtest_fin" / commit
    with tempfile.TemporaryDirectory(prefix="vb-engine-") as tmp:
        work = Path(tmp)
        preflight("start")
        _lower_priority()
        worlds = build_worlds(truth)
        with multiprocessing.Pool(processes=args.workers, initializer=_init_worker,
                                  initargs=(worlds, str(work))) as pool:  # fmt: skip
            checks, store, progress = run_gate(truth, seeds=args.seeds, workdir=work, partial=out / "partial",
                                               commit=commit, resume=args.resume, pool=pool)  # fmt: skip
        preflight("koniec")
        checks.append(spy_check(truth, workdir=work))
    passed = all(c.passed for c in checks)
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "commit": commit, "generated_by": generated_by(script=SCRIPT, root=ROOT),
        "started_at": started.isoformat(), "finished_at": datetime.now(UTC).isoformat(),
        "seeds": args.seeds, "stat_seeds": STAT_SEEDS, "zero_seeds": ZERO_SEEDS,
        "workers": args.workers, "is_gate": args.seeds >= 200, "n_matches": len(truth),
        "worlds": {k: len(v) for k, v in build_worlds(truth).items()},
        "fixture": [f"{lg}-{s}" for lg, s in FIXTURE_FILES], "raw_root": str(args.raw_root),
        "passed": passed, "resumed": store.resumed, "partial_loaded": store.loaded, "world_sha256": store.world,
        "seed_runs_total": progress.total, "paper_coupons": dict(progress.paper),
        "margin_check": GATE_WORLD_NO_MARGIN_CHECK, "margin_note": MARGIN_NOTE,
        "checks": [c.__dict__ for c in checks],
    }  # fmt: skip
    (out / "ENGINE_TESTS.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    write_report(out / "ENGINE_TESTS.md", commit=commit, seeds=args.seeds, workers=args.workers,
                 n_matches=len(truth), worlds=payload["worlds"], resumed=store.resumed,
                 loaded=store.loaded, checks=checks, passed=passed, paper=progress.paper)  # fmt: skip
    print(json.dumps({"passed": passed, "report": (out / "ENGINE_TESTS.md").as_posix()}, ensure_ascii=False))
    return 0 if passed else 1


def write_report(path: Path, *, commit: str, seeds: int, workers: int, n_matches: int, worlds: dict[str, int],
                 resumed: bool, loaded: int, checks: Sequence[Check], passed: bool,
                 paper: Counter[str]) -> None:  # fmt: skip
    fixture = ", ".join(f"{lg}-{s}" for lg, s in FIXTURE_FILES)
    lines = [f"# Testy silnika (§4) — commit `{commit}`", "",
             f"Nasion: §4.1 {seeds} dla A i C ({'BRAMKA' if seeds >= 200 else 'NIE jest bramką — za mało nasion'}); "
             f"2b, 3a: {min(STAT_SEEDS, seeds)}; 2a, 3b: {min(ZERO_SEEDS, seeds)}; trucizny {min(POISON_SEEDS, seeds)}; "
             f"robotników {workers}; mecze świata: {n_matches} ({fixture}); światy: {worlds}.", "",
             f"Wznowienie (`--resume`): {'TAK — wczytano ' + str(loaded) + ' wyników cząstkowych' if resumed else 'nie'}.",
             "",
             "Kupony w trybie PAPER (wyłącznik 25%; komunikat logowany raz na przebieg): "
             + (", ".join(f"{k}: {v}" for k, v in sorted(paper.items()) if v) or "brak") + ".",
             "",
             MARGIN_NOTE, "",
             "Strategia C (wariant B, decyzja Pawła 2026-10-11): `run_regime`, reżim wg regulaminu "
             "(udział po stawkach), konfiguracja kontrfaktyczna (limit 1000 zł wykorzystany, min. stawka "
             f"{MIN_STAKE_PLN:.2f} zł). Świat `c120` — kursy miękkie ≥ 1.20 (dublety możliwe); "
             "`solo` — jeden mecz na migawkę (dubletów brak, single 0.94). Podatek kuponów C sprawdza "
             "niezależny checker reżimu z literałów regulaminu (`RefRegime`).", "",
             f"**WYNIK: {'ZIELONE' if passed else 'CZERWONE — STOP'}**", "",
             "| test | wynik | szczegóły |", "|---|---|---|"]  # fmt: skip
    lines += [f"| {c.name} | {'OK' if c.passed else 'CZERWONY'} | {c.detail} |" for c in checks]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
