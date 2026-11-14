"""Krok 5 Filaru 1 — przebieg strategii A-F i raport (BACKTEST_FIN_PLAN §3, §5, §6).

Jedna ścieżka kodu (reguła 28): strategie z tabeli przez
``backtest.strategies.run_strategy``, C przez ``backtest.strategy_c.run_regime``
— te same funkcje, które sprawdza bramka §4. Runner tylko układa przebiegi,
liczy metryki z dzienników i pisze raport.

Przebiegi (zamrożone przed wynikiem — plan §3 i zmiany 2026-10-11):

- **główne** (θ = 0.02, kapitał 10 000 zł): A, A3, B365, B-BW, B-WH, C
  (``production``, udział po stawkach — regulamin), D, E; F (Ekstraklasa,
  zamknięcie vs zamknięcie) — tylko raport;
- **wrażliwość** (tylko raport): θ ∈ {0.01, 0.03, 0.05} dla strategii
  głównych poza F; C z udziałem „po stawkach i po kuponach”; kapitał 1000 zł
  dla A i C; wariant bez wyłącznika 25% dla A i C.

Werdykt w trzech częściach (plan §6, zmiany 2026-10-11): logika toru S (A),
reżim Betclica (C), pojedynczy bukmacherzy (B365, B-BW, B-WH — raport).
Alarmy (§6): zysk w D; yield punktowy > 8% w agregacie albo grupie lig dla
A, A3, B, C, D, F → raport z flagą ALARM, bez wniosków, kod wyjścia 2.
Niezgodność z niezależnym ``reconcile_bets.py`` → też ALARM.

Użycie (krok 5 — dopiero po zielonej bramce i zgodzie Pawła)::

    uv run python scripts/run_backtest_fin.py --raw-root <repo>/data/raw --workers 1

Zapis wyłącznie do ``reports/backtest_fin/<commit>/`` (dzienniki per
przebieg, nigdy ``data/bets/bets.csv``); ``data/raw`` tylko do odczytu.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import logging
import math
import multiprocessing
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import KW_ONLY, asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np

from valuebet.backtest import financial
from valuebet.backtest.clv import ClvReport, clv_report, clv_rows
from valuebet.backtest.financial import (
    RunResult,
    StakeContext,
    kelly_staker,
    tagged_selector,
    threshold_selector,
)
from valuebet.backtest.replay import (
    Replay,
    merge_replays,
    replay_csv,
    replay_pol_closing,
)
from valuebet.backtest.strategies import STRATEGIES, Strategy, run_strategy
from valuebet.backtest.strategy_c import (
    C_LABEL,
    counterfactual_regime_config,
    run_regime,
)
from valuebet.config import STRATEGY_PATH, load_strategy
from valuebet.ingest.football_data import load_raw_latest
from valuebet.ingest.football_data_main import (
    FIN_SEASONS,
    RAW_SUBDIR,
    ObservedAtRule,
    fin_files,
)
from valuebet.ingest.raw_store import RAW_ROOT, RawStore
from valuebet.live.bets import BetJournal, Coupon, coupons
from valuebet.pricing.ev import SHARE_BY_STAKES, SHARE_BY_STAKES_AND_COUPONS
from valuebet.pricing.kelly import StakeDecision
from valuebet.provenance import frozen_commit, generated_by

log = logging.getLogger("run_backtest_fin")

SCRIPT = Path(__file__)
ROOT = SCRIPT.resolve().parents[1]
_END = datetime.max.replace(tzinfo=UTC)

#: Plan §3: grupy lig — najwyższe vs „strefa pośrednia”.
TOP_LEAGUES = ("E0", "D1", "I1", "SP1", "F1")
#: Plan §6: alarm yield > 8% (wartość punktowa).
YIELD_ALARM = 0.08
#: Strategie bez alarmu yieldu (§6): E — ``Max``, górna granica, tylko porównanie.
NO_YIELD_ALARM = ("E",)
THETA_MAIN = 0.02
THETA_SENSITIVITY = (0.01, 0.03, 0.05)
#: Wariant informacyjny „kapitał 1000 zł” (decyzja Pawła 2026-10-11).
CAPITAL_SMALL = 1000.0
N_BOOT = 4000

#: C: „konto” to jedno konto Betclic, kursy zastępcze z B365/BW — etykieta
#: kuponu jednolita (``_check_legs``: jeden bukmacher na kupon; awaria
#: 2026-10-16, C-000008). Pole ``bookmaker`` nie bierze udziału w żadnej
#: decyzji — ``financial.py:655`` to jedyny odczyt ``Candidate.bookmaker``.
C_BOOKMAKER = "betclic"

#: F (Ekstraklasa, POL.csv): tylko zamknięcia — B365C kontra PSC (decyzja Pawła
#: 2026-10-08: strategia wyłącznie raportowa; na zamknięciu nie da się zagrać).
STRATEGY_F = Strategy("F", {"1x2": ("bet365",)}, 1.00, 1.00, True, True,
                      "Ekstraklasa: B365C vs PSC, zamknięcie vs zamknięcie — tylko raport")  # fmt: skip


@dataclass(frozen=True)
class RunSpec:
    """Jeden przebieg. ``kind``: ``table`` (``run_strategy``), ``C`` (``run_regime``), ``F``.

    ``main`` (przebieg główny, werdykt) i ``alarm`` (alarm yieldu > 8%, §6) —
    wymagane, bez wartości domyślnej (reguła 30; audyt wariantu B, POWAŻNE 3):
    pominięta flaga nie może wyłączyć bezpiecznika."""

    name: str
    kind: str
    strategy: str
    theta: float
    capital: float
    _: KW_ONLY
    main: bool
    alarm: bool
    share_basis: str = SHARE_BY_STAKES
    breaker: bool = True
    note: str = ""


def run_specs(*, capital: float, with_f: bool) -> list[RunSpec]:
    """Lista przebiegów — zamrożona przed wynikiem (plan §3, zmiany 2026-10-11)."""
    table = ("A", "A3", "B365", "B-BW", "B-WH", "D", "E")

    def alarmed(s: str) -> bool:
        return s not in NO_YIELD_ALARM

    specs = [RunSpec(s, "table", s, THETA_MAIN, capital, main=True, alarm=alarmed(s)) for s in table]
    specs.append(RunSpec("C", "C", "C", THETA_MAIN, capital, main=True, alarm=True, note=C_LABEL))
    specs.append(RunSpec("C-udział-kupony", "C", "C", THETA_MAIN, capital, main=False, alarm=True,
                         share_basis=SHARE_BY_STAKES_AND_COUPONS,
                         note="wrażliwość: udział po stawkach I po kuponach (margines 2026-10-02)"))  # fmt: skip
    if with_f:
        specs.append(RunSpec("F", "F", "F", THETA_MAIN, capital, main=True, alarm=True, note=STRATEGY_F.role))
    # Wrażliwość: alarm yieldu także tu (detektor błędu, nie werdykt; audyt, DROBNE 10).
    for theta in THETA_SENSITIVITY:
        specs += [RunSpec(f"{s}@θ{theta:.2f}", "table", s, theta, capital, main=False, alarm=alarmed(s))
                  for s in table]  # fmt: skip
        specs.append(RunSpec(f"C@θ{theta:.2f}", "C", "C", theta, capital, main=False, alarm=True))
    for s in ("A", "C"):
        kind = "C" if s == "C" else "table"
        specs.append(RunSpec(f"{s}@1000zł", kind, s, THETA_MAIN, CAPITAL_SMALL, main=False, alarm=True,
                             note="wariant informacyjny: kapitał 1000 zł, min. stawka 0,50 zł"))  # fmt: skip
        specs.append(RunSpec(f"{s}-bez-wyłącznika", kind, s, THETA_MAIN, capital, main=False, alarm=True,
                             breaker=False, note="wariant bez wyłącznika 25% — do oceny przewagi, tylko raport"))  # fmt: skip
    return specs


def no_breaker_staker(ctx: StakeContext) -> StakeDecision:
    """Kelly produkcyjny, ale bez przełączenia w PAPER po obsunięciu 25% — tylko raport.

    Stawka liczona tą samą funkcją (``kelly_staker``); zmienia się wyłącznie
    tryb kuponu, więc różnica wyników to dokładnie skutek wyłącznika."""
    decision = kelly_staker(ctx)
    return replace(decision, mode="real") if decision.is_paper else decision


@dataclass
class RunOutput:
    spec: RunSpec
    result: RunResult
    excluded: Counter[tuple[str, str, str]]
    rejected: Counter[tuple[str, str, str]]
    journal: Path


def execute(spec: RunSpec, replay: Replay, *, out: Path, min_stake_pln: float) -> RunOutput:
    """Przebieg jednej specyfikacji przez funkcje produkcyjne (reguła 28)."""
    folder = out / _safe(spec.name)
    folder.mkdir(parents=True, exist_ok=True)
    journal = folder / "bets.csv"
    excluded: Counter[tuple[str, str, str]] = Counter()
    rejected: Counter[tuple[str, str, str]] = Counter()
    staker = kelly_staker if spec.breaker else no_breaker_staker
    ingested = datetime.now(UTC)
    if spec.kind == "C":
        books = STRATEGIES["A"].books  # plan §3: C — kursy jak A
        best_of = threshold_selector(books=books, tax_factor=1.0, edge_threshold=spec.theta,
                                     require_complete=True, excluded=excluded, rejected=rejected,
                                     margin_check=True)  # fmt: skip
        selector = tagged_selector(lambda ctx: [replace(c, bookmaker=C_BOOKMAKER) for c in best_of(ctx)],
                                   selection_tax=best_of.selection_tax)  # fmt: skip
        start = min(m.decision_at for m in replay.matches)
        result = run_regime(replay, selector=selector, staker=staker,
                            regime_config=counterfactual_regime_config(
                                start=start, share_basis=spec.share_basis, min_stake_pln=min_stake_pln),
                            edge_threshold=spec.theta, single_mode="production", journal_path=journal,
                            run_id=_safe(spec.name), start_capital=spec.capital, ingested_at=ingested,
                            min_stake_pln=min_stake_pln)  # fmt: skip
    else:
        strategy = STRATEGY_F if spec.kind == "F" else STRATEGIES[spec.strategy]
        result = run_strategy(replay, strategy=strategy, staker=staker, edge_threshold=spec.theta,
                              excluded=excluded, rejected=rejected, journal_path=journal,
                              run_id=_safe(spec.name), start_capital=spec.capital, ingested_at=ingested,
                              min_stake_pln=min_stake_pln)  # fmt: skip
    with (folder / "equity.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["at", "cash", "capital", "event"])
        writer.writerows([p.at.isoformat(), f"{p.cash:.2f}", f"{p.capital:.2f}", p.event] for p in result.equity)
    return RunOutput(spec, result, excluded, rejected, journal)


def _safe(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in name)


# -- metryki (plan §5) ----------------------------------------------------------


def _iso_week(moment: datetime) -> str:
    iso = moment.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def ratio_ci(clusters: dict[str, tuple[float, float]], *, n_boot: int = N_BOOT, seed: int = 0
             ) -> tuple[float | None, float | None, float | None]:  # fmt: skip
    """(Σ licznik / Σ mianownik, CI 95%) z bootstrapu klastrowego (klastry = tygodnie ISO)."""
    keys = sorted(clusters)
    if not keys:
        return None, None, None
    num = np.array([clusters[k][0] for k in keys])
    den = np.array([clusters[k][1] for k in keys])
    if den.sum() <= 0:
        return None, None, None
    point = float(num.sum() / den.sum())
    if len(keys) < 5:
        return point, None, None
    pick = np.random.default_rng(seed).integers(0, len(keys), size=(n_boot, len(keys)))
    draws = num[pick].sum(1) / den[pick].sum(1)
    low, high = (float(v) for v in np.quantile(draws, [0.025, 0.975]))
    return point, low, high


@dataclass(frozen=True)
class Metrics:
    n_coupons: int
    n_real: int
    n_paper: int
    turnover: float
    profit: float
    yield_: float | None
    yield_ci: tuple[float | None, float | None]
    clv: dict[str, Any]
    opportunities_per_100: float | None
    n_matches: int
    n_weeks: int
    bets_per_week: float | None


def coupon_scope(c: Coupon, leagues: dict[str, str]) -> set[str]:
    return {leagues[g.record.match_id] for g in c.legs}


def coupon_market(c: Coupon) -> str:
    markets = {g.record.market for g in c.legs}
    return markets.pop() if len(markets) == 1 else "mieszany"


def metrics_for(placed: Sequence[Coupon], clv: Sequence[Any], *, kickoffs: dict[str, datetime],
                n_matches: int, weeks: int) -> Metrics:  # fmt: skip
    """Metryki zbioru kuponów: yield i CLV z CI klastrowym po tygodniach ISO (reguła 11)."""
    real = [c for c in placed if c.is_real and c.payout is not None]
    clusters: dict[str, tuple[float, float]] = {}
    for c in real:
        week = _iso_week(min(kickoffs[g.record.match_id] for g in c.legs))
        num, den = clusters.get(week, (0.0, 0.0))
        clusters[week] = (num + (c.payout or 0.0) - c.stake, den + c.stake)
    point, low, high = ratio_ci(clusters)
    ids = {c.coupon_id for c in placed}
    report: ClvReport = clv_report([r for r in clv if r.bet_id in ids], n_boot=N_BOOT, seed=0)
    turnover = sum(c.stake for c in real)
    return Metrics(
        n_coupons=len(placed), n_real=len(real), n_paper=sum(1 for c in placed if not c.is_real),
        turnover=round(turnover, 2), profit=round(sum((c.payout or 0.0) - c.stake for c in real), 2),
        yield_=point, yield_ci=(low, high),
        clv={"n": report.n_with_clv, "mean": report.mean, "ci_low": report.ci_low, "ci_high": report.ci_high,
             "clusters": report.n_clusters, "missing": report.n_missing, "describe": report.describe()},
        opportunities_per_100=100.0 * len(placed) / n_matches if n_matches else None,
        n_matches=n_matches, n_weeks=weeks, bets_per_week=len(placed) / weeks if weeks else None,
    )  # fmt: skip


def equity_stats(result: RunResult) -> dict[str, Any]:
    """ROC roczny (procent składany), maks. obsunięcie, najdłuższy czas pod kreską."""
    points = [(p.at, p.capital) for p in result.equity]
    if not points:
        return {"roc_annual": None, "max_drawdown": 0.0, "longest_underwater_days": 0.0}
    start = result.start_capital
    end_at, end_cap = points[-1]
    days = (end_at - points[0][0]).total_seconds() / 86400
    roc = (end_cap / start) ** (365.25 / days) - 1 if days > 0 and end_cap > 0 else None
    peak, peak_at, worst, longest = start, points[0][0], 0.0, 0.0
    for at, cap in points:
        if cap >= peak:
            longest = max(longest, (at - peak_at).total_seconds() / 86400)
            peak, peak_at = cap, at
        else:
            worst = max(worst, 1 - cap / peak)
    longest = max(longest, (end_at - peak_at).total_seconds() / 86400 if end_cap < peak else 0.0)
    return {"roc_annual": roc, "max_drawdown": worst, "longest_underwater_days": longest}


def final_capital_bootstrap(placed: Sequence[Coupon], *, start: float, kickoffs: dict[str, datetime],
                            n_boot: int = N_BOOT) -> dict[str, float] | None:  # fmt: skip
    """Rozkład kapitału końcowego z bootstrapu tygodni (P&L tygodnia, bez procentu składanego)."""
    weekly: dict[str, float] = {}
    for c in placed:
        if c.is_real and c.payout is not None:
            week = _iso_week(min(kickoffs[g.record.match_id] for g in c.legs))
            weekly[week] = weekly.get(week, 0.0) + c.payout - c.stake
    if len(weekly) < 5:
        return None
    values = np.array(list(weekly.values()))
    pick = np.random.default_rng(1).integers(0, len(values), size=(n_boot, len(values)))
    finals = start + values[pick].sum(1)
    q5, q50, q95 = (float(v) for v in np.quantile(finals, [0.05, 0.5, 0.95]))
    return {"p05": q5, "p50": q50, "p95": q95}


def reconcile_check(journal: Path, result: RunResult) -> dict[str, Any]:
    """Niezależne podwójne księgowanie (§2): gotówka po każdym rozliczeniu, w groszach."""
    module = _reconcile_module()
    if not journal.exists():
        return {"ok": True, "n": 0}
    ledger = module.reconcile(journal, start_capital=result.start_capital)
    sim = [p.cash for p in result.equity if p.event != "decision"]
    bad = len(ledger) != len(sim) or any(cents != round(cash * 100) for (_, _, cents), cash in zip(ledger, sim, strict=False))
    return {"ok": not bad, "n": len(ledger)}


def _reconcile_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("reconcile_bets", ROOT / "scripts" / "reconcile_bets.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def summarize(run: RunOutput, replay: Replay) -> dict[str, Any]:
    """Wszystko o jednym przebiegu: agregat, grupy lig, rynki, ligi, podatek, wyłącznik."""
    rows = BetJournal(journal_path=run.journal).read() if run.journal.exists() else []
    placed = sorted(coupons(rows, now=_END), key=lambda c: c.coupon_id)
    kickoffs = {m.match_id: m.kickoff for m in replay.matches}
    leagues = {m.match_id: m.league for m in replay.matches}
    end = max((r.settled_at for r in rows if r.settled_at is not None), default=None)
    clv = clv_rows(bets=rows, closing=financial.closing_map(replay), kickoffs=kickoffs, as_of=end) if end else []
    weeks_by_league: dict[str, set[str]] = {}
    for m in replay.matches:
        weeks_by_league.setdefault(m.league, set()).add(_iso_week(m.kickoff))
    all_weeks = len({w for ws in weeks_by_league.values() for w in ws})
    matches_by_league = Counter(m.league for m in replay.matches)

    def subset(pred: Callable[[Coupon], bool], scope: Iterable[str]) -> Metrics:
        scope = list(scope)
        return metrics_for([c for c in placed if pred(c)], clv, kickoffs=kickoffs,
                           n_matches=sum(matches_by_league[lg] for lg in scope),
                           weeks=len({w for lg in scope for w in weeks_by_league.get(lg, set())}))  # fmt: skip

    all_leagues = sorted(matches_by_league)
    top = [lg for lg in all_leagues if lg in TOP_LEAGUES]
    mid = [lg for lg in all_leagues if lg not in TOP_LEAGUES]
    groups = {
        "najwyższe": subset(lambda c: coupon_scope(c, leagues) <= set(TOP_LEAGUES), top),
        "strefa pośrednia": subset(lambda c: not coupon_scope(c, leagues) & set(TOP_LEAGUES), mid),
    }
    mixed = sum(1 for c in placed if coupon_scope(c, leagues) & set(TOP_LEAGUES)
                and coupon_scope(c, leagues) - set(TOP_LEAGUES))  # fmt: skip
    markets = {mk: subset(lambda c, mk=mk: coupon_market(c) == mk, all_leagues)
               for mk in sorted({coupon_market(c) for c in placed})}  # fmt: skip
    per_league = {lg: subset(lambda c, lg=lg: coupon_scope(c, leagues) == {lg}, [lg]) for lg in all_leagues}
    paper = [c for c in placed if not c.is_real]
    taxes = Counter(f"{'multi' if len(c.legs) > 1 else 'single'} {c.tax_factor_applied:.2f}" for c in placed)
    return {
        "name": run.spec.name, "spec": asdict(run.spec),
        "aggregate": asdict(metrics_for(placed, clv, kickoffs=kickoffs, n_matches=len(replay.matches),
                                        weeks=all_weeks)),
        "groups": {k: asdict(v) for k, v in groups.items()}, "mixed_group_coupons": mixed,
        "markets": {k: asdict(v) for k, v in markets.items()},
        "leagues": {k: asdict(v) for k, v in per_league.items()},
        "equity": equity_stats(run.result),
        "final_capital_bootstrap": final_capital_bootstrap(placed, start=run.result.start_capital, kickoffs=kickoffs),
        "cash_end": round(run.result.cash, 2), "start_capital": run.result.start_capital,
        "tax_counts": dict(sorted(taxes.items())),
        "breaker": {
            "first_paper_at": min((c.placed_at for c in paper), default=None),
            "paper_coupons": len(paper),
            # P&L hipotetyczny kuponów paper — gdyby postawiono je naprawdę (tylko raport)
            "paper_hypothetical_profit": round(sum((c.payout or 0.0) - c.stake for c in paper if c.payout is not None), 2),
        },
        "skipped": dict(run.result.skipped),
        "excluded": {" / ".join(k): v for k, v in sorted(run.excluded.items())},
        "rejected": {" / ".join(k): v for k, v in sorted(run.rejected.items())},
        "gk_first_unlock": run.result.gk_first_unlock,
        "reconcile": reconcile_check(run.journal, run.result),
        "label": run.result.label,
    }


# -- werdykt i alarmy (plan §6, zmiany 2026-10-11) -------------------------------


def clv_verdict(summary: dict[str, Any]) -> str:
    """POTWIERDZONA / NIEPOTWIERDZONA / OBALONA wg §6 (CLV z CI po tygodniach ISO + yield)."""
    agg = summary["aggregate"]
    clv = agg["clv"]
    if clv["ci_low"] is None or clv["ci_high"] is None:
        return "NIEPOTWIERDZONA (brak CI CLV — za mało klastrów albo zakładów)"
    if clv["ci_high"] < 0:
        return "OBALONA"
    if clv["ci_low"] > 0 and (agg["yield_"] or 0.0) > 0:
        return "POTWIERDZONA"
    if clv["ci_low"] > 0:
        return "NIEPOTWIERDZONA (CLV > 0, ale yield punktowy ≤ 0)"
    return "NIEPOTWIERDZONA"


def recommendation(a: str, c: str) -> str:
    """Rekomendacja dla Filaru 2 — spisana przed wynikiem (BACKTEST_FIN_PLAN, zmiany 2026-10-11)."""
    if a.startswith("POTWIERDZONA") and c.startswith("POTWIERDZONA"):
        return "A i C POTWIERDZONE → Filar 2 na Betclicu w reżimie Bez Podatku 2.0 uzasadniony."
    if a.startswith("POTWIERDZONA"):
        return ("A POTWIERDZONA, C nie → edge istnieje, ale reżim Betclica go nie przenosi: Filar 2 na "
                "Betclicu nieuzasadniony; decyzja Pawła o alternatywie jako osobny plan.")  # fmt: skip
    return "A NIEPOTWIERDZONA / OBALONA → jak w §6 (nie idziemy na rynek / tor S zamknięty)."


def alarms(summaries: dict[str, dict[str, Any]]) -> list[str]:
    """Alarmy przerywające (§6): zysk w D, yield > 8% w przebiegach z ``alarm``
    (flaga przebiegu, nie lista nazw), niezgodność z reconcile — wszystkie przebiegi."""
    out: list[str] = []
    for name, s in summaries.items():
        if not s["reconcile"]["ok"]:
            out.append(f"{name}: kapitał symulatora ≠ reconcile_bets.py")
        if s["spec"].get("strategy") == "D" and s["aggregate"]["profit"] > 0:
            out.append(f"{name}: zysk {s['aggregate']['profit']:+.2f} zł w kontroli podatku D (musi tracić)")
        if s["spec"]["alarm"]:
            for scope, m in [("agregat", s["aggregate"]), *s["groups"].items()]:
                y = m["yield_"]
                if y is not None and y > YIELD_ALARM:
                    out.append(f"{name} ({scope}): yield {y:+.2%} > 8%")
    return out


# -- raport ------------------------------------------------------------------------


def _fmt(v: float | None, pct: bool = True) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "n/d"
    return f"{v:+.2%}" if pct else f"{v:+.4f}"


def _row(name: str, m: dict[str, Any]) -> str:
    low, high = m["yield_ci"]
    clv = m["clv"]
    return (f"| {name} | {m['n_coupons']} | {m['n_real']} | {m['turnover']:.2f} | {m['profit']:+.2f} | "
            f"{_fmt(m['yield_'])} [{_fmt(low)}, {_fmt(high)}] | "
            f"{_fmt(clv['mean'], False)} [{_fmt(clv['ci_low'], False)}, {_fmt(clv['ci_high'], False)}] "
            f"(n={clv['n']}, kl.={clv['clusters']}) | "
            f"{'n/d' if m['opportunities_per_100'] is None else f'{m['opportunities_per_100']:.1f}'} |")  # fmt: skip


_HEAD = ("| przebieg | kuponów | real | obrót | zysk | yield [CI 95%] | CLV [CI 95%] | okazje/100 meczów |\n"
         "|---|---|---|---|---|---|---|---|")  # fmt: skip


def write_report(out: Path, payload: dict[str, Any]) -> None:
    s = payload["summaries"]
    lines = [f"# Backtest finansowy Filaru 1 — commit `{payload['commit']}`", "",
             f"Wygenerowano: {payload['generated_at']}; reguła observed_at: `{payload['observed_at_rule']}`; "
             f"mecze: {payload['n_matches']}; min. stawka {payload['min_stake_pln']:.2f} zł.", ""]  # fmt: skip
    if payload["alarms"]:
        lines += ["## ALARM — wnioski wstrzymane (plan §6, CLAUDE.md: domyślnie błąd)", ""]
        lines += [f"- {a}" for a in payload["alarms"]]
        lines += ["", "Werdykt i rekomendacja NIE są generowane. Szukaj przyczyny przed jakimkolwiek wnioskiem.", ""]
    else:
        v = payload["verdict"]
        lines += ["## Werdykt (plan §6, zmiany 2026-10-11)", "",
                  f"1. **Logika toru S (A):** {v['A']}",
                  f"2. **Reżim Betclica (C, production):** {v['C']} — {C_LABEL}",
                  "3. **Pojedynczy bukmacherzy (B365, B-BW, B-WH):** raport z CI niżej, bez werdyktu.", "",
                  f"**Rekomendacja dla Filaru 2:** {v['recommendation']}", ""]  # fmt: skip
    lines += ["## Przebiegi główne (θ = 0.02, kapitał 10 000 zł)", "", _HEAD]
    lines += [_row(n, x["aggregate"]) for n, x in s.items() if x["spec"]["main"]]
    lines += ["", "## Grupy lig i rynki (przebiegi główne)", "", _HEAD]
    for n, x in s.items():
        if x["spec"]["main"]:
            lines += [_row(f"{n} — {g}", m) for g, m in x["groups"].items()]
            lines += [_row(f"{n} — rynek {mk}", m) for mk, m in x["markets"].items()]
    lines += ["", "## Wrażliwość (tylko raport, bez wpływu na werdykt)", "", _HEAD]
    lines += [_row(n, x["aggregate"]) for n, x in s.items() if not x["spec"]["main"]]
    lines += ["", "## Tabela per liga — A i C (hipoteza wyboru lig do Filaru 2, bez korekty na wielokrotne porównania)", "",
              "| przebieg | liga | kuponów | CLV [CI 95%] | yield | kuponów / tydzień sezonu | rankingowana (≥ 300 A) |",
              "|---|---|---|---|---|---|---|"]  # fmt: skip
    for n in ("A", "C"):
        for lg, m in s.get(n, {}).get("leagues", {}).items():
            clv = m["clv"]
            ranked = "tak" if n == "A" and m["n_coupons"] >= 300 else ("nie" if n == "A" else "—")
            lines.append(f"| {n} | {lg} | {m['n_coupons']} | {_fmt(clv['mean'], False)} "
                         f"[{_fmt(clv['ci_low'], False)}, {_fmt(clv['ci_high'], False)}] | {_fmt(m['yield_'])} | "
                         f"{'n/d' if m['bets_per_week'] is None else f'{m['bets_per_week']:.2f}'} | {ranked} |")  # fmt: skip
    lines += ["", "## Kapitał, wyłącznik, podatek, liczniki", ""]
    for n, x in s.items():
        e, b = x["equity"], x["breaker"]
        lines.append(f"- **{n}**: kapitał końcowy {x['cash_end']:.2f} zł (start {x['start_capital']:.0f}); "
                     f"ROC roczny {_fmt(e['roc_annual'])}; maks. obsunięcie {e['max_drawdown']:.1%}; najdłużej pod "
                     f"kreską {e['longest_underwater_days']:.0f} dni; bootstrap kapitału końcowego {x['final_capital_bootstrap']}; "
                     f"wyłącznik: pierwszy kupon PAPER {b['first_paper_at']}, kuponów paper {b['paper_coupons']}, "
                     f"ich hipotetyczny P&L {b['paper_hypothetical_profit']:+.2f} zł; podatek {x['tax_counts']}; "
                     f"G-K od kuponu {x['gk_first_unlock']}; pominięte {x['skipped']}; wyłączone (brak kompletu) "
                     f"{sum(x['excluded'].values())}; odrzucone A4a-01 {x['rejected']}; reconcile {x['reconcile']}; "
                     f"kuponów mieszanych grup {x['mixed_group_coupons']}")  # fmt: skip
    lines += ["", "Każda liczba z n i CI (reguła 11); CI yieldu i CLV — bootstrap klastrowy po tygodniach ISO.",
              f"PNG: {payload['png']}.", ""]  # fmt: skip
    (out / "RAPORT.md").write_text("\n".join(lines), encoding="utf-8")


def write_png(out: Path, outputs: Sequence[RunOutput]) -> str:
    """Krzywe kapitału przebiegów głównych — wymaga ``matplotlib`` (``uv sync --extra viz``)."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return "pominięte — brak matplotlib (uv sync --extra viz)"
    fig, ax = plt.subplots(figsize=(10, 5))
    for run in outputs:
        if run.spec.main and run.result.equity:
            ax.plot([p.at for p in run.result.equity], [p.capital for p in run.result.equity], label=run.spec.name)
    ax.set_ylabel("kapitał [zł]")
    ax.legend()
    fig.savefig(out / "equity.png", dpi=120)
    plt.close(fig)
    return "equity.png"


# -- orkiestracja -------------------------------------------------------------------

_WORKER: dict[str, Any] = {}


def _init_worker(replay: Replay, f_replay: Replay | None, out: str, min_stake: float) -> None:
    _WORKER.update(replay=replay, f_replay=f_replay, out=Path(out), min_stake=min_stake)


def _run_in_worker(spec: RunSpec) -> tuple[RunSpec, dict[str, Any], RunOutput]:
    replay = _WORKER["f_replay"] if spec.kind == "F" else _WORKER["replay"]
    run = execute(spec, replay, out=_WORKER["out"], min_stake_pln=_WORKER["min_stake"])
    return spec, summarize(run, replay), run


def run_all(replay: Replay, *, f_replay: Replay | None, out: Path, min_stake_pln: float, commit: str,
            observed_at_rule: str, workers: int = 0,
            specs: Sequence[RunSpec] | None = None) -> tuple[dict[str, Any], int]:  # fmt: skip
    """Wszystkie przebiegi + raport. Zwraca (payload, kod wyjścia: 0 albo 2 przy alarmie)."""
    out.mkdir(parents=True, exist_ok=True)
    chosen = list(specs) if specs is not None else run_specs(capital=load_strategy(ROOT / STRATEGY_PATH)
                                                             .backtest_start_capital_pln, with_f=f_replay is not None)  # fmt: skip
    results: dict[str, tuple[dict[str, Any], RunOutput]] = {}
    if workers > 0:
        with multiprocessing.Pool(workers, initializer=_init_worker,
                                  initargs=(replay, f_replay, str(out), min_stake_pln)) as pool:  # fmt: skip
            for spec, summary, run in pool.imap_unordered(_run_in_worker, chosen):
                log.info("gotowe: %s", spec.name)
                results[spec.name] = (summary, run)
    else:
        _init_worker(replay, f_replay, str(out), min_stake_pln)
        for spec in chosen:
            done = _run_in_worker(spec)
            log.info("gotowe: %s", spec.name)
            results[spec.name] = (done[1], done[2])
    summaries = {s.name: results[s.name][0] for s in chosen}
    found = alarms(summaries)
    verdict = None
    if not found and "A" in summaries and "C" in summaries:
        a, c = clv_verdict(summaries["A"]), clv_verdict(summaries["C"])
        verdict = {"A": a, "C": c, "recommendation": recommendation(a, c)}
    payload = {
        "commit": commit, "generated_by": generated_by(script=SCRIPT, root=ROOT) if commit != "test" else "test",
        "generated_at": datetime.now(UTC).isoformat(), "observed_at_rule": observed_at_rule,
        "n_matches": len(replay.matches), "min_stake_pln": min_stake_pln,
        "replay_skipped": {" / ".join(k): v for k, v in sorted(replay.skipped.items())},
        "alarms": found, "verdict": verdict, "summaries": summaries,
        "png": write_png(out, [results[s.name][1] for s in chosen]),
    }  # fmt: skip
    (out / "RAPORT.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    write_report(out, payload)
    return payload, 2 if found else 0


def load_replays(raw_root: Path, rule: ObservedAtRule) -> tuple[Replay, Replay | None]:
    """22 ligi x 7 sezonów z raw (odczyt) + F z POL.csv, jeśli jest."""
    store = RawStore(root=raw_root)
    replays = []
    for file in fin_files():
        path = store.latest(RAW_SUBDIR, f"{file.league}-{file.season}", ".csv")
        if path is None:
            log.warning("brak %s-%s w raw — pomijam", file.league, file.season)
            continue
        replays.append(replay_csv(path.read_bytes(), league=file.league, season=file.season, rule=rule))
    try:
        frame = load_raw_latest(raw_root / "football_data")
    except FileNotFoundError:
        log.warning("brak POL.csv w raw — strategia F pominięta")
        return merge_replays(replays), None
    seasons = tuple(f"20{s[:2]}/20{s[2:]}" for s in FIN_SEASONS)
    return merge_replays(replays), replay_pol_closing(frame, seasons=seasons)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Krok 5 Filaru 1: strategie A-F i raport")
    parser.add_argument("--raw-root", type=Path, default=RAW_ROOT, help="data/raw — TYLKO ODCZYT")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--observed-at-rule", choices=[r.value for r in ObservedAtRule], default=None,
                        help="domyślnie z config/strategy.yaml; 23:59 — przebieg wrażliwości (decyzja 2026-10-08)")  # fmt: skip
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    strategy = load_strategy(ROOT / STRATEGY_PATH)
    rule = ObservedAtRule(args.observed_at_rule) if args.observed_at_rule else strategy.observed_at_rule
    commit = frozen_commit(script=SCRIPT, root=ROOT)
    suffix = "" if rule is strategy.observed_at_rule else f"-{rule.value}"
    out = ROOT / "reports" / "backtest_fin" / commit / f"strategie{suffix}"
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} już istnieje — przebieg kroku 5 jest jednorazowy; nie nadpisuję")
    replay, f_replay = load_replays(args.raw_root, rule)
    _, code = run_all(replay, f_replay=f_replay, out=out, min_stake_pln=strategy.min_stake_pln, commit=commit,
                      observed_at_rule=rule.value, workers=args.workers)  # fmt: skip
    print(json.dumps({"exit": code, "report": (out / "RAPORT.md").as_posix()}, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
