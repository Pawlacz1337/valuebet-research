"""Backtest finansowy — pętla zdarzeń po czasie na modułach live (BACKTEST_FIN_PLAN §2).

Jedna ścieżka kodu (reguła 28): wycena ``pricing.fair.fair_prices``, próg
``pricing.ev.min_odds``, stawka ``pricing.kelly.KellyPolicy.from_journal``,
dziennik ``live.bets.BetJournal`` (osobny plik per przebieg), ekspozycja
``live.bets.open_stake`` / ``match_open_stake``, CLV ``backtest.clv``. Ten
moduł tylko układa zdarzenia w czasie i prowadzi kasę.

Zdarzenia w chwili ``t`` (``decision_at`` z replayu), w tej kolejności:

1. rozliczenia kuponów z ``settled_at <= t`` — wynik z ``Replay.results``,
   jedyne miejsce, w którym pętla go dotyka;
2. decyzje: ``fair_prices`` z migawek Pinnacle meczów tej chwili →
   ``selector`` (kandydaci) → ``staker`` (stawka) → dziennik.

Kapitał do stawki = gotówka + otwarte stawki prawdziwe po koszcie (§2).
Raport CLV dla Kelly'ego (G-K — liczona i raportowana, ``c`` zostaje ¼)
liczony z dziennika z ``as_of = t``.

``selector`` i ``staker`` są **wymagane** (§4 pkt 2): test placebo
wstrzykuje „każdy wynik” i stawkę płaską, przebieg produkcyjny —
:func:`threshold_selector` i :func:`kelly_staker`.
"""

from __future__ import annotations

import heapq
import logging
import math
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Final, Protocol

from valuebet.backtest.clv import (
    ClosingKey,
    ClvReport,
    closing_key,
    clv_report,
    clv_rows,
)
from valuebet.backtest.replay import MatchResult, Replay, ReplayMatch
from valuebet.live.bets import (
    BetJournal,
    BetRecord,
    Coupon,
    coupons,
    match_open_stake,
    open_stake,
    real_coupon_count,
)
from valuebet.pricing.ev import WINNINGS_UNTAXED, min_odds, validate_tax_factor
from valuebet.pricing.fair import FairPricing, MarketQuote, fair_prices
from valuebet.pricing.kelly import KellyPolicy, StakeDecision, meets_min_stake
from valuebet.pricing.shin import ShinNotConvergedError, shin_probabilities

__all__ = [
    "DROP_BELOW_MIN_STAKE",
    "DROP_EV",
    "DROP_NO_CAPITAL",
    "DROP_REASONS",
    "DROP_ZERO_STAKE",
    "MAX_PLAUSIBLE_EV",
    "MIN_SOFT_BOOKSUM",
    "PINNACLE",
    "REJECT_BOOKSUM",
    "REJECT_EV",
    "SKIP_BELOW_MIN_STAKE",
    "Candidate",
    "ConstantTaxPlanner",
    "DecisionContext",
    "DroppedGroup",
    "EquityPoint",
    "Planner",
    "RunResult",
    "Selector",
    "StakeContext",
    "Staker",
    "closing_map",
    "kelly_staker",
    "leg_result",
    "run",
    "simulate",
    "tagged_selector",
    "threshold_selector",
]

log = logging.getLogger(__name__)

PINNACLE = "pinnacle"
#: Stawka poniżej grosza nie jest zakładem (zaokrąglenie Kelly'ego do 0.00).
MIN_STAKE = 0.01
#: Licznik pominięć: stawka ≥ 1 gr, ale poniżej minimalnej stawki bukmachera
#: (decyzja Pawła 2026-10-11, T12 — wszystkie strategie; nie zaokrąglamy w górę).
SKIP_BELOW_MIN_STAKE = "stawka < min. stawki (T12)"
#: AB-9 (naprawa 4b-C, 2026-10-12): zamknięta lista przyczyn odrzucenia grupy —
#: tylko obserwacja (``RunResult.dropped_groups``), żadna decyzja się nie zmienia.
DROP_BELOW_MIN_STAKE = "STAWKA_PONIZEJ_MINIMUM"
DROP_EV = "PONIZEJ_PROGU_PO_PODATKU"
DROP_ZERO_STAKE = "STAWKA_ZERO"
DROP_NO_CAPITAL = "KAPITAL_ZERO"
DROP_REASONS: Final = (DROP_BELOW_MIN_STAKE, DROP_EV, DROP_ZERO_STAKE, DROP_NO_CAPITAL)
#: A4a-01 (a), decyzja Pawła 2026-10-10, zamrożone przed wynikiem: kwotowanie
#: bukmachera z sumą odwrotności kursów < 1.00 (ujemna marża) to błąd danych —
#: bukmacher wypada z best-of dla tego meczu i rynku. Nie dotyczy ``max``
#: (kolumna Max to nie kwotowanie jednego bukmachera).
MIN_SOFT_BOOKSUM: Final = 1.00
#: A4a-01 (b), jw.: EV przy podatku 1.00 względem fair Pinnacle > 0.50 to na
#: piłce błąd danych (zamienione H/A, literówka), nie okazja — zakład odrzucony.
MAX_PLAUSIBLE_EV: Final = 0.50
REJECT_BOOKSUM = "a: booksum bukmachera < 1.00"
REJECT_EV = "b: EV > 0.50 względem Pinnacle"


@dataclass(frozen=True)
class Candidate:
    """Wynik do zagrania: uczciwe ``p`` i najlepszy kurs z dozwolonych bukmacherów."""

    match_id: str
    market: str
    outcome: str
    line: float | None
    p: float
    odds: float
    bookmaker: str
    observed_at: datetime


@dataclass(frozen=True)
class DecisionContext:
    decision_time: datetime
    matches: tuple[ReplayMatch, ...]
    fair: FairPricing


class Selector(Protocol):
    """Selektor kandydatów chwili decyzji.

    ``selection_tax`` — podatek, przy którym selektor liczy próg ``k_min``.
    ``run`` porównuje go z podatkiem wyboru strategii (FSA4a-01): podatek
    podany dwa razy, niezależnie, rozjeżdżał się bez błędu.
    """

    @property
    def selection_tax(self) -> float: ...

    def __call__(self, ctx: DecisionContext, /) -> list[Candidate]: ...


@dataclass(frozen=True)
class _TaggedSelector:
    select: Callable[[DecisionContext], list[Candidate]]
    selection_tax: float

    def __call__(self, ctx: DecisionContext, /) -> list[Candidate]:
        return self.select(ctx)


def tagged_selector(
    select: Callable[[DecisionContext], list[Candidate]], *, selection_tax: float
) -> Selector:
    """Selektor z jawnie zadeklarowanym podatkiem wyboru (np. wymuszone placebo bramki)."""
    return _TaggedSelector(select, validate_tax_factor(tax_factor=selection_tax))


@dataclass(frozen=True, kw_only=True)
class StakeContext:
    """Wszystko, czego potrzebuje stawkowanie — stan z chwili decyzji."""

    candidate: Candidate
    bankroll: float
    peak_bankroll: float
    clv_report: ClvReport
    n_real_bets: int
    open_exposure: float
    match_exposure: float
    tax_factor: float


Staker = Callable[[StakeContext], StakeDecision]


@dataclass(frozen=True)
class DroppedGroup:
    """Grupa odrzucona w pętli: nogi, przyczyna z ``DROP_REASONS``, stan w chwili decyzji.

    ``stake`` — stawka z pierwszego wywołania stawkowania (przy podatku wyboru);
    ``placed_before`` — kupony postawione w przebiegu przed tą grupą (kolejność).
    """

    at: datetime
    legs: tuple[tuple[str, str, str, float], ...]
    reason: str
    capital: float
    stake: float
    mode: str
    placed_before: int


@dataclass(frozen=True)
class EquityPoint:
    at: datetime
    cash: float
    #: gotówka + otwarte stawki prawdziwe po koszcie.
    capital: float
    #: ``coupon_id`` rozliczonego kuponu albo ``"decision"``.
    event: str


@dataclass
class RunResult:
    journal_path: Path
    start_capital: float
    equity: list[EquityPoint]
    cash: float
    n_coupons: int
    #: Pominięcia: wycena (``fair_prices``), stawki zerowe, mecze bez wyceny.
    skipped: Counter[str] = field(default_factory=Counter)
    #: Raport CLV na koniec przebiegu (``as_of`` = ostatnie rozliczenie).
    clv: ClvReport | None = None
    #: Numer kuponu (od 1), przy którym bramka G-K byłaby otwarta — raport.
    gk_first_unlock: int | None = None
    #: Kapitał (gotówka + otwarte prawdziwe) w chwili decyzji o kuponie — do
    #: sprawdzenia limitów 2/3/15% po fakcie (§4 pkt 6).
    bankroll_at: dict[str, float] = field(default_factory=dict)
    #: Każdy kandydat selektora, przed stawkowaniem: (chwila, mecz, rynek,
    #: wynik, kurs, p) — do testu trucizny 4b (zbiór kandydatów niezależny
    #: od wyników).
    candidates: list[tuple[datetime, str, str, str, float, float]] = field(default_factory=list)
    #: Wejścia stawki per kupon: (kapitał, ekspozycja łączna, meczowa, podatek)
    #: — do niezależnego sprawdzenia wzoru Kelly'ego (bramka §4, 4b).
    stake_inputs: dict[str, tuple[float, float, float, float]] = field(default_factory=dict)
    #: Etykieta przebiegu (C: „kontrfaktyczny reżim Betclica …”).
    label: str = ""
    #: Kupony postawione w trybie PAPER (po wyłączniku 25%) — licznik do raportu;
    #: komunikat ``tryb PAPER`` logowany raz na przebieg.
    paper_coupons: int = 0
    #: AB-9: każda grupa odrzucona przez pętlę, z nazwaną przyczyną.
    dropped_groups: list[DroppedGroup] = field(default_factory=list)


def leg_result(*, market: str, outcome: str, line: float | None, result: MatchResult) -> str:
    """``won``/``lost``/``void`` nogi z wyniku meczu."""
    h, a = result.home_goals, result.away_goals
    if h is None or a is None:
        return "void"
    if market == "1x2":
        actual = "home" if h > a else "away" if a > h else "draw"
        return "won" if outcome == actual else "lost"
    if market == "over_under" and line is not None:
        total = h + a
        if total == line:
            return "void"
        actual = "over" if total > line else "under"
        return "won" if outcome == actual else "lost"
    raise ValueError(f"rynek {market!r} bez reguły rozliczenia")


def closing_map(replay: Replay) -> dict[ClosingKey, tuple[float, datetime]]:
    """``p_close`` po Shinie z migawek zamknięcia Pinnacle (reguła 16), klucz per wynik."""
    out: dict[ClosingKey, tuple[float, datetime]] = {}
    for match in replay.matches:
        for quote in match.closing.get(PINNACLE, ()):
            try:
                shin = shin_probabilities(list(quote.odds), strict=True)
            except (ShinNotConvergedError, ValueError):
                continue
            for outcome, p in zip(quote.outcomes, shin.probabilities, strict=True):
                key = closing_key(match.match_id, quote.market, outcome, quote.line)
                out[key] = (float(p), quote.observed_at)
    return out


def threshold_selector(
    *,
    books: Mapping[str, Sequence[str]],
    tax_factor: float,
    edge_threshold: float,
    require_complete: bool,
    excluded: Counter[tuple[str, str, str]],
    rejected: Counter[tuple[str, str, str]],
    margin_check: bool,
) -> Selector:
    """Produkcja: najlepszy kurs z ``books[rynek]`` ≥ ``k_min`` z ``pricing.ev`` (w = 1.00).

    ``books`` — bukmacherzy per rynek (``1x2``, ``over_under``); rynek spoza
    mapy nie jest grany. ``require_complete`` — rynek meczu grany tylko, gdy
    KAŻDY bukmacher z listy ma komplet notowań (decyzja Pawła 2026-10-08 dla
    A); brak → wyłączenie liczone raz na mecz i rynek w ``excluded[(liga,
    sezon, powód)]``.

    Podatek od wygranej (T13) zależy od stawki, więc w progu jest 1.00; Kelly
    przelicza go przy stawce (``KellyPolicy.stake``).

    Wiarygodność kursu (A4a-01, wyłącznie z migawki decyzyjnej):
    ``margin_check`` — kwotowanie z booksum < :data:`MIN_SOFT_BOOKSUM` wypada
    z best-of (``False`` tylko dla ``max`` i dla świata bramki §4, w którym
    kurs miękki ma z konstrukcji ujemną marżę); kandydat z EV przy 1.00 >
    :data:`MAX_PLAUSIBLE_EV` — odrzucony zawsze. Odrzucenia liczone raz na
    mecz i regułę w ``rejected[(liga, sezon, reguła)]``.
    """
    allowed = {market: tuple(names) for market, names in books.items()}
    tax = validate_tax_factor(tax_factor=tax_factor)

    def select(ctx: DecisionContext) -> list[Candidate]:
        by_match = {m.match_id: m for m in ctx.matches}
        out: list[Candidate] = []
        counted: set[tuple[str, str]] = set()
        rejected_once: set[tuple[str, str]] = set()

        def reject(match: ReplayMatch, rule: str) -> None:
            if (match.match_id, rule) not in rejected_once:
                rejected_once.add((match.match_id, rule))
                rejected[(match.league, match.season, rule)] += 1
        for price in ctx.fair.prices:
            match = by_match[price.match_id]
            names = allowed.get(price.market, ())
            quotes: dict[str, MarketQuote] = {}
            for book in names:
                for quote in match.decision.get(book, ()):
                    if quote.market == price.market and quote.line == price.line:
                        quotes[book] = quote
            missing = [b for b in names if b not in quotes]
            if not names or (require_complete and missing):
                key = (price.match_id, price.market)
                if names and key not in counted:
                    counted.add(key)
                    excluded[(match.league, match.season, f"{price.market}: brak kompletu {missing[0]}")] += 1
                continue
            if margin_check:
                for book in list(quotes):
                    if sum(1.0 / k for k in quotes[book].odds) < MIN_SOFT_BOOKSUM:
                        del quotes[book]
                        reject(match, REJECT_BOOKSUM)
            best: tuple[float, str] | None = None
            for book in names:
                if book not in quotes:
                    continue
                quote = quotes[book]
                odds = quote.odds[quote.outcomes.index(price.outcome)]
                if best is None or odds > best[0]:
                    best = (odds, book)
            if best is None:
                continue
            if price.p * best[0] - 1.0 > MAX_PLAUSIBLE_EV:
                reject(match, REJECT_EV)
                continue
            k_min = min_odds(
                price.p,
                tax_factor=tax,
                winnings_factor=WINNINGS_UNTAXED,
                edge_threshold=edge_threshold,
            )
            if best[0] >= k_min:
                out.append(
                    Candidate(
                        match_id=price.match_id,
                        market=price.market,
                        outcome=price.outcome,
                        line=price.line,
                        p=price.p,
                        odds=best[0],
                        bookmaker=best[1],
                        observed_at=price.observed_at,
                    )
                )
        return out

    return _TaggedSelector(select, tax)


def kelly_staker(ctx: StakeContext) -> StakeDecision:
    """Produkcja: Kelly ¼ z limitami i wyłącznikiem — ``KellyPolicy.from_journal``."""
    policy = KellyPolicy.from_journal(
        bankroll=ctx.bankroll,
        peak_bankroll=ctx.peak_bankroll,
        clv_report=ctx.clv_report,
        n_real_bets=ctx.n_real_bets,
        open_exposure=ctx.open_exposure,
        match_exposure=ctx.match_exposure,
    )
    return policy.stake(ctx.candidate.p, ctx.candidate.odds, tax_factor=ctx.tax_factor)


def _ev_order(candidate: Candidate, tax: float) -> tuple[float, str, str, str]:
    """Kolejność w chwili decyzji: EV malejąco, potem klucz (deterministycznie)."""
    return (-(candidate.p * candidate.odds * tax), candidate.match_id, candidate.market, candidate.outcome)


class Planner(Protocol):
    """Jak z kandydatów chwili ``t`` powstają kupony i jaki mają podatek.

    ``begin`` — stan na początku chwili decyzji (kupony do ``t``);
    ``groups`` — kupony do wyceny w kolejności (krotka nóg);
    ``price`` — (podatek, decyzja stawki) albo ``None`` (kupon odpada);
    ``placed`` — kupon zawarty (kolejni kandydaci go widzą, T3).
    """

    def begin(self, *, t: datetime, current: Sequence[Coupon]) -> None: ...

    def groups(self, candidates: Sequence[Candidate]) -> list[tuple[Candidate, ...]]: ...

    def price(
        self, legs: tuple[Candidate, ...], *, stake_at: Callable[[float], StakeDecision]
    ) -> tuple[float, StakeDecision] | None: ...

    def placed(self, coupon: Coupon) -> None: ...


@dataclass
class ConstantTaxPlanner:
    """A, B, D, E: każdy kandydat to singiel o stałym podatku.

    Stawka liczona przy ``selection_tax``, rozliczenie przy ``settlement_tax``.
    Równe we wszystkich strategiach poza D — kontrolą podatku, nie strategią
    do zagrania: zakłady A (wybór i stawka przy 1.00) rozliczone przy 0.88
    (decyzja Pawła 2026-10-10, jawne odstępstwo od planu §3).
    """

    selection_tax: float
    settlement_tax: float

    def begin(self, *, t: datetime, current: Sequence[Coupon]) -> None:
        del t, current  # stały podatek nie zależy od historii

    def groups(self, candidates: Sequence[Candidate]) -> list[tuple[Candidate, ...]]:
        return [(c,) for c in candidates]

    def price(
        self, legs: tuple[Candidate, ...], *, stake_at: Callable[[float], StakeDecision]
    ) -> tuple[float, StakeDecision] | None:
        del legs
        return self.settlement_tax, stake_at(self.selection_tax)

    def placed(self, coupon: Coupon) -> None:
        del coupon


def run(
    replay: Replay,
    *,
    selector: Selector,
    staker: Staker,
    selection_tax_factor: float,
    settlement_tax_factor: float,
    journal_path: Path,
    run_id: str,
    start_capital: float,
    ingested_at: datetime,
    min_stake_pln: float,
) -> RunResult:
    """Jeden przebieg strategii o stałym podatku (A, B, D, E).

    Oba podatki wymagane i jawne; podatek wyboru musi być tym, przy którym
    selektor liczy próg — inaczej ``ValueError`` (FSA4a-01). Strategie z tabeli
    wołają to przez ``backtest.strategies.run_strategy`` (jedno źródło).
    """
    selection = validate_tax_factor(tax_factor=selection_tax_factor)
    settlement = validate_tax_factor(tax_factor=settlement_tax_factor)
    if selector.selection_tax != selection:
        raise ValueError(
            f"podatek wyboru {selection} ≠ podatek selektora {selector.selection_tax} "
            "(FSA4a-01: jedno źródło podatku strategii)"
        )
    return simulate(
        replay,
        selector=selector,
        staker=staker,
        planner=ConstantTaxPlanner(selection, settlement),
        order_tax=selection,
        journal_path=journal_path,
        run_id=run_id,
        start_capital=start_capital,
        ingested_at=ingested_at,
        min_stake_pln=min_stake_pln,
    )


def simulate(
    replay: Replay,
    *,
    selector: Selector,
    staker: Staker,
    planner: Planner,
    order_tax: float,
    journal_path: Path,
    run_id: str,
    start_capital: float,
    ingested_at: datetime,
    min_stake_pln: float,
    label: str = "",
) -> RunResult:
    """Pętla zdarzeń: rozliczenia z ``settled_at <= t``, potem kupony planisty.

    ``min_stake_pln`` wymagane (reguła 30, decyzja Pawła 2026-10-11): stawka
    poniżej → kupon pominięty, licznik :data:`SKIP_BELOW_MIN_STAKE`.
    """
    meets_min_stake(0.0, min_stake_pln=min_stake_pln)  # walidacja przed pętlą
    if journal_path.exists() and journal_path.stat().st_size > 0:
        raise ValueError(f"{journal_path}: dziennik przebiegu musi być nowy (osobny plik)")
    if ingested_at.tzinfo is None:
        raise ValueError("ingested_at musi być timezone-aware (reguła 2)")
    journal = BetJournal(journal_path=journal_path)
    closing = closing_map(replay)
    kickoffs: Mapping[str, datetime] = {m.match_id: m.kickoff for m in replay.matches}
    by_time: dict[datetime, list[ReplayMatch]] = {}
    for match in replay.matches:
        by_time.setdefault(match.decision_at, []).append(match)

    cash = float(start_capital)
    peak = cash
    pending: list[tuple[datetime, str, str]] = []  # (settled_at, bet_id, match_id)
    legs: dict[str, BetRecord] = {}
    coupon_rows: dict[str, list[BetRecord]] = {}
    finished: set[str] = set()
    open_real = 0.0
    equity: list[EquityPoint] = []
    skipped: Counter[str] = Counter()
    gk_first: int | None = None
    bankroll_at: dict[str, float] = {}
    candidate_log: list[tuple[datetime, str, str, str, float, float]] = []
    stake_inputs: dict[str, tuple[float, float, float, float]] = {}
    n = 0
    paper_coupons = 0
    dropped: list[DroppedGroup] = []

    def settle_until(limit: datetime | None) -> None:
        nonlocal cash, peak, open_real
        while pending and (limit is None or pending[0][0] <= limit):
            settled_at, bet_id, match_id = heapq.heappop(pending)
            leg = legs[bet_id]
            outcome = leg_result(
                market=leg.market, outcome=leg.outcome, line=leg.line,
                result=replay.results[match_id],
            )  # fmt: skip
            journal.settle(bet_id, outcome, now=settled_at)
            own = coupon_rows[leg.coupon_id]
            own.append(journal.read()[-1])
            (coupon,) = coupons(own, now=settled_at)
            if coupon.is_open or coupon.coupon_id in finished:
                continue  # kupon czeka na kolejną nogę albo przegrał już wcześniej
            finished.add(coupon.coupon_id)
            if coupon.is_real:
                payout = coupon.payout
                if payout is None:
                    raise RuntimeError(f"{bet_id}: kupon po rozliczeniu nadal otwarty")
                cash += payout
                open_real -= coupon.stake
            capital = cash + open_real
            peak = max(peak, capital)
            equity.append(EquityPoint(settled_at, cash, capital, coupon.coupon_id))

    for t in sorted(by_time):
        settle_until(t)
        matches = tuple(by_time[t])
        quotes: list[MarketQuote] = [q for m in matches for q in m.decision.get(PINNACLE, ())]
        if not quotes:
            skipped["mecz bez notowania Pinnacle"] += len(matches)
            continue
        pricing = fair_prices(quotes, decision_time=t, kickoffs=kickoffs)
        skipped.update(pricing.skipped)
        candidates = sorted(
            selector(DecisionContext(t, matches, pricing)), key=lambda c: _ev_order(c, order_tax)
        )
        candidate_log.extend((t, c.match_id, c.market, c.outcome, c.odds, c.p) for c in candidates)
        if not candidates:
            continue
        rows = journal.read()
        current: list[Coupon] = coupons(rows, now=t)
        # Funkcje live na kuponach OTWARTYCH w chwili t — rozliczone nic nie
        # wnoszą do ekspozycji, a ich przeglądanie przy każdym kandydacie było
        # kwadratowe (256 s na seed bramki §4). Licznik G-K raz na chwilę + przyrost.
        open_now = [c for c in current if c.is_open]
        n_real = real_coupon_count(current)
        report = clv_report(clv_rows(bets=rows, closing=closing, kickoffs=kickoffs, as_of=t))
        planner.begin(t=t, current=current)
        for group in planner.groups(candidates):
            capital = cash + open_real
            legs_key = tuple((c.match_id, c.market, c.outcome, c.odds) for c in group)
            if capital <= 0.0:
                skipped["kapitał 0"] += 1
                dropped.append(DroppedGroup(t, legs_key, DROP_NO_CAPITAL, capital, 0.0, "", n))
                continue
            # Wszystkie otwarte kupony, paper też — jak ``open_stake`` w live.
            # Same real wyłączały limity 3%/15% po wyłączniku 25% (bramka §4,
            # 2026-10-08: 285 naruszeń). Kupon wielonożny: najciaśniejszy mecz.
            open_exposure = open_stake(open_now) / capital
            match_exposure = max(match_open_stake(open_now, c.match_id) for c in group) / capital
            coupon_view = replace(
                group[0],
                match_id="+".join(c.match_id for c in group),
                p=math.prod(c.p for c in group),
                odds=math.prod(c.odds for c in group),
            )

            stake_tax: list[float] = []
            made: list[StakeDecision] = []

            def stake_at(
                tax: float,
                view: Candidate = coupon_view,
                me: float = match_exposure,
                oe: float = open_exposure,
                cap: float = capital,
                rpt: ClvReport = report,
                nr: int = n_real,
                used: list[float] = stake_tax,
                seen: list[StakeDecision] = made,
            ) -> StakeDecision:
                used.append(tax)
                seen.append(staker(
                    StakeContext(
                        candidate=view,
                        bankroll=cap,
                        peak_bankroll=peak,
                        clv_report=rpt,
                        n_real_bets=nr,
                        open_exposure=oe,
                        match_exposure=me,
                        tax_factor=tax,
                    )
                ))
                return seen[-1]

            priced = planner.price(group, stake_at=stake_at)
            first = made[0] if made else None
            if priced is None:
                # AB-9: stawka < min. stawki daje w reżimie C 0.88 (T12) i grupa odpada —
                # przyczyną jest stawka poniżej minimum, nie próg EV.
                below = first is not None and first.stake >= MIN_STAKE and not meets_min_stake(
                    first.stake, min_stake_pln=min_stake_pln)  # fmt: skip
                skipped[SKIP_BELOW_MIN_STAKE if below else "kupon poza progiem po podatku"] += 1
                dropped.append(DroppedGroup(t, legs_key, DROP_BELOW_MIN_STAKE if below else DROP_EV, capital,
                                            first.stake if first else 0.0, first.mode if first else "", n))  # fmt: skip
                continue
            tax, decision = priced
            if decision.stake < MIN_STAKE:
                skipped["stawka 0"] += 1
                dropped.append(DroppedGroup(t, legs_key, DROP_ZERO_STAKE, capital, decision.stake, decision.mode, n))
                continue
            if not meets_min_stake(decision.stake, min_stake_pln=min_stake_pln):
                skipped[SKIP_BELOW_MIN_STAKE] += 1
                dropped.append(DroppedGroup(t, legs_key, DROP_BELOW_MIN_STAKE, capital, decision.stake, decision.mode, n))
                continue
            n += 1
            coupon_id = f"{run_id}-{n:06d}"
            multi = len(group) > 1
            records = [
                BetRecord(
                    bet_id=f"{coupon_id}.{i}" if multi else coupon_id,
                    placed_at=t,
                    mode=decision.mode,
                    bookmaker=cand.bookmaker,
                    coupon_id=coupon_id,
                    coupon_type="multi" if multi else "single",
                    n_legs=len(group),
                    leg_index=i,
                    match_id=cand.match_id,
                    market=cand.market,
                    outcome=cand.outcome,
                    line=cand.line,
                    odds_taken=cand.odds,
                    stake=decision.stake,
                    tax_factor_applied=tax,
                    p_fair_at_bet=cand.p,
                    snapshot_observed_at=cand.observed_at,
                    price_available=True,
                    ingested_at=ingested_at,
                    source=f"backtest:{run_id}",
                )
                for i, cand in enumerate(group)
            ]
            journal.add_coupon(records)
            coupon_rows[coupon_id] = list(records)
            for record in records:
                legs[record.bet_id] = record
                heapq.heappush(
                    pending,
                    (replay.results[record.match_id].settled_at, record.bet_id, record.match_id),
                )
            bankroll_at[coupon_id] = capital
            # Podatek, przy którym policzono stawkę (ostatnie wywołanie) — w D ≠ rozliczeniu.
            stake_inputs[coupon_id] = (capital, open_exposure, match_exposure, stake_tax[-1])
            (placed,) = coupons(records, now=t)
            open_now.append(placed)
            n_real += real_coupon_count([placed])
            planner.placed(placed)
            if placed.is_real:
                cash -= decision.stake
                open_real += decision.stake
            if decision.gk_would_unlock and gk_first is None:
                gk_first = n
            if decision.is_paper:
                if paper_coupons == 0:
                    log.warning(
                        "%s: tryb PAPER od kuponu %d (%s) — %s; dalsze kupony paper tylko w liczniku",
                        run_id, n, t.isoformat(), "; ".join(decision.reasons),
                    )  # fmt: skip
                paper_coupons += 1
        equity.append(EquityPoint(t, cash, cash + open_real, "decision"))
    settle_until(None)
    rows = journal.read()
    end = max((r.settled_at for r in rows if r.settled_at is not None), default=None)
    final = (
        clv_report(clv_rows(bets=rows, closing=closing, kickoffs=kickoffs, as_of=end))
        if end is not None
        else None
    )
    return RunResult(
        journal_path=journal_path,
        start_capital=float(start_capital),
        equity=equity,
        cash=cash,
        n_coupons=n,
        skipped=skipped,
        clv=final,
        gk_first_unlock=gk_first,
        bankroll_at=bankroll_at,
        candidates=candidate_log,
        stake_inputs=stake_inputs,
        label=label,
        paper_coupons=paper_coupons,
        dropped_groups=dropped,
    )
