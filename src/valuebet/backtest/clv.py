"""CLV względem zamknięcia Pinnacle (TOR_S_PLAN §8).

``CLV = odds_taken * tax_factor_applied * p_close - 1``

To jest **metryka nadrzędna** (reguła 26). Model albo kurs, który nie bije
zamknięcia, nie ma przewagi — niezależnie od tego, co pokazuje yield na
backteście. Yield na kilkuset zakładach to głównie szum; CLV mówi, czy
kupujemy taniej od rynku, i mówi to szybciej.

Brak migawki zamknięcia to „n/d", nigdy zero
---------------------------------------------
Zakład bez zamknięcia w tolerancji nie ma policzonego CLV i jest liczony
osobno. Wstawienie tam zera przesunęłoby średnią do zera i **ukryło**
systematyczny problem: migawek brakuje najczęściej tam, gdzie coś się
działo — mecz przełożony, rynek zamknięty wcześniej, awaria kolektora w
dniu meczowym.

Klastry = kolejki
-----------------
Zakłady z jednej kolejki dzielą stan rynku i tę samą migawkę decyzyjną,
więc nie są niezależne. Poniżej ``MIN_CLUSTERS`` klastrów przedział to
``n/d``, nie liczba.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np

from valuebet.backtest.market_benchmark import MIN_CLUSTERS
from valuebet.closing import CLOSING_TOLERANCE
from valuebet.live.bets import BetRecord, coupons
from valuebet.pricing.ev import validate_tax_factor
from valuebet.schema import canonical_market, canonical_outcome

#: Granica „bez granicy” dla składania kuponów — as_of stosujemy osobno.
_END_OF_TIME = datetime.max.replace(tzinfo=UTC)

__all__ = [
    "CLOSING_TOLERANCE",
    "EXCLUDED_FUTURE",
    "ClosingKey",
    "ClvReport",
    "ClvRow",
    "closing_key",
    "clv_report",
    "clv_rows",
]

log = logging.getLogger(__name__)

#: Migawka zamknięcia musi leżeć w tym oknie przed gwizdkiem — stała
#: wspólna z kolektorem (``valuebet.closing``, reguła 28).

#: Poniżej tego pokrycia migawkami zamknięcia średnie CLV nie jest podstawą
#: decyzji. Nie dlatego, że liczba jest zła — dlatego, że jest liczona na
#: podzbiorze wybranym przez sprawność kolektora, a migawek brakuje
#: najczęściej tam, gdzie coś się działo. Zmierzone w lockboxie: Pinnacle
#: ma zamknięcie dla 112 z 375 meczów, czyli 30% pokrycia.
MIN_CLOSING_COVERAGE = 0.80

#: Klastrów wymaganych do KAŻDEGO werdyktu (``beats_closing``,
#: ``unlocks_gk``, ``describe``) — ten sam próg co
#: ``metrics.BootstrapDiff.reliable`` (FSA #0 F-22). Od ``MIN_CLUSTERS`` (5)
#: CI jest tylko liczone i drukowane z adnotacją „poniżej progu
#: wiarygodności”.
MIN_CLUSTERS_RELIABLE = 8
#: Zgodność wsteczna nazwy — ta sama liczba.
MIN_CLUSTERS_FOR_GK = MIN_CLUSTERS_RELIABLE


#: Klucz zamknięcia: jedno ``p_close`` na **wynik** rynku, nie na mecz
#: (FSA0 A-01). ``line`` = ``None`` dla rynków bez linii (1X2).
ClosingKey = tuple[str, str, str, float | None]

#: Status wiersza poza agregatem: zakład albo mecz po chwili ``as_of``.
EXCLUDED_FUTURE = "excluded_future"


@dataclass(frozen=True)
class ClvRow:
    bet_id: str
    mode: str
    market: str
    league: str
    cluster: str
    #: ``None`` = brak migawki zamknięcia. NIE zero.
    clv: float | None
    p_close: float | None
    reason: str = ""

    @property
    def excluded_future(self) -> bool:
        return self.reason == EXCLUDED_FUTURE


def closing_key(match_id: str, market: str, outcome: str, line: float | None) -> ClosingKey:
    """Klucz zamknięcia z rynkiem i wynikiem KANONICZNYM (F0d-04, F0e-03).

    ``h2h`` i ``1x2`` to ten sam rynek, ``Draw`` i ``draw`` ten sam wynik.
    """
    return (
        match_id,
        canonical_market(market).value,
        canonical_outcome(market, outcome).value,
        None if line is None else float(line),
    )


def _canonical_closing(
    closing: Mapping[ClosingKey, tuple[float, datetime]],
    *,
    as_of: datetime,
    kickoffs: Mapping[str, datetime],
    tolerance: timedelta,
) -> dict[ClosingKey, tuple[float, datetime]]:
    """Mapa zamknięć po kanonizacji — wynik niezależny od kolejności wstawiania (F0e-03).

    Kolizja (``h2h`` i ``1x2`` tego samego wyniku): wygrywa najpóźniejsza
    migawka ważna jako zamknięcie (w ``[KO - tolerance, KO]`` i ``<= as_of``),
    potem najpóźniejsza ``<= as_of``, potem najpóźniejsza w ogóle (CLV i tak
    da n/d). Bez okna migawka in-play wypierała zamknięcie (backtest-auditor
    2026-10-07). Ta sama chwila z różnym ``p`` → ``ValueError``.
    Klucz z rynkiem albo wynikiem spoza słownika odpada (noga dostaje n/d),
    zamiast wywracać cały raport. Klucz nie-krotka (stary format „sam
    match_id”, A-01) nie jest zamknięciem i też odpada.
    """
    out: dict[ClosingKey, tuple[float, datetime]] = {}
    for key, value in closing.items():
        if not (isinstance(key, tuple) and len(key) == 4):
            continue
        try:
            canon = closing_key(*key)
        except ValueError:
            continue
        held = out.get(canon)
        if held is None:
            out[canon] = value
            continue
        if held[1] == value[1] and held[0] != value[0]:
            raise ValueError(f"dwie migawki zamknięcia {canon} z chwili {value[1]} z różnym p")

        kickoff = kickoffs.get(canon[0])

        def rank(
            v: tuple[float, datetime], kickoff: datetime | None = kickoff
        ) -> tuple[bool, bool, datetime]:
            valid = (
                kickoff is not None
                and kickoff - tolerance <= v[1] <= kickoff
                and v[1] <= as_of
            )
            return (valid, v[1] <= as_of, v[1])

        if rank(value) > rank(held):
            out[canon] = value
    return out


def clv_rows(
    *,
    bets: Iterable[BetRecord],
    closing: Mapping[ClosingKey, tuple[float, datetime]],
    kickoffs: Mapping[str, datetime],
    as_of: datetime,
    leagues: Mapping[str, str] | None = None,
    tolerance: timedelta = CLOSING_TOLERANCE,
) -> list[ClvRow]:
    """CLV per **kupon**. ``closing``: ``(match_id, market, outcome, line) -> (p_close, observed_at)``.

    ``bets`` to wiersze dziennika; składa je ``live.bets.coupons`` — jeden
    kupon = jedna obserwacja (FSA #0 F-02). CLV kuponu wielokrotnego:
    ``Π(k_i · p_close_i) · tax - 1``; brak zamknięcia którejkolwiek nogi → n/d.
    ``p_close`` ma już być po Shinie.

    ``as_of`` jest **wymagane** (reguła 30, FSA #0 F-04). Agregat CLV wchodzi
    do bramki G-K, więc wszystko, czego w chwili ``as_of`` nie dało się
    wiedzieć, jest poza nim i liczone osobno jako ``excluded_future``:
    kupon postawiony po ``as_of``, noga na meczu bez znanego gwizdka, gwizdek
    po ``as_of``. Migawka zamknięcia obserwowana po ``as_of`` daje n/d.
    Bez tego 40 meczów z przyszłości zamieniało CLV -1.0% w +9.5% i
    otwierało bramkę.
    """
    if as_of.tzinfo is None:
        raise ValueError("as_of musi być timezone-aware (reguła 2)")
    # Jedna nazwa rynku i wyniku po obu stronach (F0d-04, F0e-03).
    closing = _canonical_closing(closing, as_of=as_of, kickoffs=kickoffs, tolerance=tolerance)
    out: list[ClvRow] = []
    # Wszystkie kupony niezależnie od chwili — granicę as_of stosujemy niżej,
    # żeby kupony z przyszłości policzyć jako excluded_future, nie zgubić.
    for coupon in coupons(bets, now=_END_OF_TIME):
        legs = [leg.record for leg in coupon.legs]
        first = legs[0]
        league = (leagues or {}).get(first.match_id, "nieznana")
        market = "+".join(leg.market for leg in legs)
        leg_kickoffs = [kickoffs.get(leg.match_id) for leg in legs]
        known = [k for k in leg_kickoffs if k is not None]
        if (
            coupon.placed_at > as_of
            or len(known) != len(leg_kickoffs)
            or any(k > as_of for k in known)
        ):
            out.append(
                ClvRow(
                    bet_id=coupon.coupon_id,
                    mode=coupon.mode,
                    market=market,
                    league=league,
                    cluster="poza-agregatem",
                    clv=None,
                    p_close=None,
                    reason=EXCLUDED_FUTURE,
                )
            )
            continue
        cluster = _cluster(min(known))

        def missing(
            reason: str,
            coupon_id: str = coupon.coupon_id,
            coupon_mode: str = coupon.mode,
            market: str = market,
            cluster: str = cluster,
            league: str = league,
        ) -> ClvRow:
            return ClvRow(
                bet_id=coupon_id,
                mode=coupon_mode,
                market=market,
                league=league,
                cluster=cluster,
                clv=None,
                p_close=None,
                reason=reason,
            )

        if coupon.placed_at >= min(known):
            out.append(missing("zakład po gwizdku — to nie zakład przedmeczowy"))
            continue
        product = 1.0
        p_product = 1.0
        problem = ""
        for leg, kickoff in zip(legs, known, strict=True):
            entry = closing.get(closing_key(leg.match_id, leg.market, leg.outcome, leg.line))
            if entry is None:
                problem = "brak migawki zamknięcia"
                break
            p_close, observed_at = entry
            if observed_at > as_of:
                problem = f"migawka {observed_at} po as_of {as_of}"
                break
            if not (kickoff - tolerance <= observed_at <= kickoff):
                problem = (
                    f"migawka {observed_at} poza tolerancją {tolerance} "
                    f"przed gwizdkiem {kickoff}"
                )
                break
            product *= leg.odds_taken * p_close
            p_product *= p_close
        if problem:
            out.append(missing(problem))
            continue
        # Druga ścieżka też waliduje — CLV nie ufa rekordowi (F0b-03, wzorzec F-05).
        tax = validate_tax_factor(tax_factor=coupon.tax_factor_applied)
        value = product * tax - 1.0
        out.append(
            ClvRow(
                bet_id=coupon.coupon_id,
                mode=coupon.mode,
                market=market,
                league=league,
                cluster=cluster,
                clv=float(value),
                p_close=float(p_product),
            )
        )
    return out


def _cluster(kickoff: datetime) -> str:
    iso = kickoff.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


@dataclass(frozen=True)
class ClvReport:
    n_total: int
    n_with_clv: int
    n_missing: int
    mean: float | None
    ci_low: float | None
    ci_high: float | None
    n_clusters: int
    note: str = ""
    #: Zakłady poza agregatem, bo w chwili ``as_of`` ich mecz się nie
    #: zaczął (albo nie znamy gwizdka). Nie wchodzą do ``n_total``.
    n_excluded_future: int = 0

    @property
    def coverage(self) -> float:
        """Jaka część zakładów ma policzone CLV."""
        return self.n_with_clv / self.n_total if self.n_total else 0.0

    @property
    def beats_closing(self) -> bool:
        """Czy dolna granica CI jest dodatnia. Brak CI = nie.

        Dodatkowo wymaga pokrycia migawkami zamknięcia: średnia policzona
        na 30% zakładów opisuje te 30%, a nie strategię.
        """
        return (
            self.ci_low is not None
            and self.ci_low > 0.0
            and self.coverage >= MIN_CLOSING_COVERAGE
            and self.n_clusters >= MIN_CLUSTERS_RELIABLE
        )

    @property
    def unlocks_gk(self) -> bool:
        """Czy ten raport wolno użyć do bramki G-K (reguła 21).

        Ostrzejszy warunek niż ``beats_closing``: wymaga też dość klastrów.
        Podwojenie stawek na przedziale z pięciu tygodni to nie decyzja
        oparta na danych.
        """
        return self.beats_closing and self.n_clusters >= MIN_CLUSTERS_RELIABLE

    def describe(self) -> str:
        if self.mean is None:
            return f"CLV n/d — {self.note} (n={self.n_total})"
        if self.ci_low is None:
            return (
                f"CLV {self.mean:+.4f}  CI n/d ({self.n_clusters} klastrów, "
                f"wymagane {MIN_CLUSTERS_RELIABLE})  n={self.n_with_clv}"
                f"  bez zamknięcia: {self.n_missing}"
            )
        flag = (
            ""
            if self.n_clusters >= MIN_CLUSTERS_RELIABLE
            else f"  [poniżej progu wiarygodności: {self.n_clusters} < "
            f"{MIN_CLUSTERS_RELIABLE} klastrów — bez werdyktu]"
        )
        return (
            f"CLV {self.mean:+.4f}  CI [{self.ci_low:+.4f}, {self.ci_high:+.4f}]"
            f"  n={self.n_with_clv}  bez zamknięcia: {self.n_missing}{flag}"
        )


def clv_report(
    rows: Iterable[ClvRow], *, n_boot: int = 4000, seed: int = 0
) -> ClvReport:
    """Średnie CLV z CI z bootstrapu klastrowego po kolejkach."""
    every = list(rows)
    excluded = sum(1 for r in every if r.excluded_future)
    rows = [r for r in every if not r.excluded_future]
    usable = [r for r in rows if r.clv is not None]
    missing = len(rows) - len(usable)
    if not usable:
        return ClvReport(
            n_total=len(rows),
            n_with_clv=0,
            n_missing=missing,
            mean=None,
            ci_low=None,
            ci_high=None,
            n_clusters=0,
            note="żaden zakład nie ma migawki zamknięcia",
            n_excluded_future=excluded,
        )
    values = np.array([r.clv for r in usable], dtype=np.float64)
    clusters = np.array([r.cluster for r in usable])
    unique = np.unique(clusters)
    if len(unique) < MIN_CLUSTERS:
        return ClvReport(
            n_total=len(rows),
            n_with_clv=len(usable),
            n_missing=missing,
            mean=float(values.mean()),
            ci_low=None,
            ci_high=None,
            n_clusters=len(unique),
            note=f"za mało klastrów ({len(unique)})",
            n_excluded_future=excluded,
        )
    rng = np.random.default_rng(seed)
    index = {c: np.flatnonzero(clusters == c) for c in unique}
    sums = np.array([values[index[c]].sum() for c in unique])
    counts = np.array([len(index[c]) for c in unique], dtype=float)
    pick = rng.integers(0, len(unique), size=(n_boot, len(unique)))
    draws = sums[pick].sum(1) / counts[pick].sum(1)
    low, high = (float(v) for v in np.quantile(draws, [0.025, 0.975]))
    return ClvReport(
        n_total=len(rows),
        n_with_clv=len(usable),
        n_missing=missing,
        mean=float(values.mean()),
        ci_low=low,
        ci_high=high,
        n_clusters=len(unique),
        n_excluded_future=excluded,
    )
