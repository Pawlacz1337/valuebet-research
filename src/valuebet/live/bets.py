"""Dziennik zakładów — tylko dopisywanie (TOR_S_PLAN §7).

``data/bets/bets.csv``. Append-only, bez wyjątków: zakład raz zapisany nie
jest poprawiany, a korekta idzie jako nowy wiersz z notatką. Dziennik jest
źródłem prawdy dla reżimu podatkowego, bramek G-S i G-K oraz CLV — plik,
który da się edytować w miejscu, przestaje być dowodem. CSV, nie parquet —
czytelny dla człowieka (wyjątek od reguły 13, ``CLAUDE.md``); kolumny
``ingested_at`` i ``source`` są (reguła 14, FSA #0 F-31).

Jednostką jest KUPON
--------------------
Kupon wielokrotny to N wierszy (nóg) z jednym ``coupon_id`` i **stawką
kuponu powtórzoną na każdej nodze**. Wszyscy konsumenci — reżim podatkowy,
ekspozycja, G-K, CLV, ``reconcile_bets.py`` — pracują na kuponach z
:func:`coupons`, nigdy na wierszach. Wcześniej każdy wiersz był osobnym
„singlem”: udział AKO był strukturalnie 0, a obrót AKO liczony N razy
(FSA #0 F-02).

Status nogi i kuponu wynika z wierszy rozliczeniowych z ``settled_at ≤
now``; wiersz zakładu ma zawsze stan otwarty — dziennik jest append-only.

``price_available`` to licznik do bramki G-S
--------------------------------------------
„≥ 70% alertów z kursem wciąż dostępnym" (ROADMAP §7). Bez tego pola nie da
się odróżnić „model nie znalazł value" od „value było, ale zniknęło, zanim
człowiek kliknął" — a to dwie zupełnie różne diagnozy.
"""

from __future__ import annotations

import csv
import io
import logging
import math
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime
from pathlib import Path

from valuebet.pricing.ev import (
    CouponLeg,
    PlacedBet,
    qualifies_as_ako,
    settlement_payout,
    validate_tax_factor,
)
from valuebet.schema import canonical_market, canonical_outcome

__all__ = [
    "BETS_COLUMNS",
    "BetJournal",
    "BetRecord",
    "Coupon",
    "coupons",
    "live_coupons",
    "match_open_stake",
    "open_stake",
    "real_coupon_count",
]

log = logging.getLogger(__name__)

LIVE_PATH = Path("data/bets/bets.csv")
#: Jedyne źródło wierszy dopuszczalne w dzienniku live.
LIVE_SOURCE = "manual"
#: Wyniki nogi. ``half_*`` tylko dla singli na liniach ćwiartkowych — dziś
#: takich linii nie gramy, więc nie ma ich w dziedzinie.
LEG_RESULTS = ("won", "lost", "void")


@dataclass(frozen=True)
class BetRecord:
    """Jeden wiersz dziennika = jedna noga kuponu. Kolejność pól = kolumny CSV."""

    bet_id: str
    placed_at: datetime
    mode: str
    bookmaker: str
    coupon_id: str
    #: ``single`` albo ``multi``.
    coupon_type: str
    n_legs: int
    leg_index: int
    match_id: str
    market: str
    outcome: str
    line: float | None
    odds_taken: float
    #: Stawka KUPONU, powtórzona na każdej nodze.
    stake: float
    tax_factor_applied: float
    p_fair_at_bet: float
    snapshot_observed_at: datetime | None
    price_available: bool
    #: Reguła 14.
    ingested_at: datetime
    #: ``manual`` (live) albo ``backtest:<run_id>``.
    source: str
    notes: str = ""
    #: Wynik nogi w wierszu rozliczeniowym (``won``/``lost``/``void``).
    settled: str = ""
    settled_at: datetime | None = None
    payout: float | None = None
    #: ``qualifies_as_ako`` na nogach postawionych — do wglądu w CSV,
    #: sprawdzane przy odczycie. ``None`` = wiersz jeszcze niezapisany.
    ako_at_placement: bool | None = None

    def __post_init__(self) -> None:
        if self.mode not in ("paper", "real"):
            raise ValueError(f"mode musi być paper albo real, jest {self.mode!r}")
        if self.coupon_type not in ("single", "multi"):
            raise ValueError(f"coupon_type musi być single albo multi: {self.coupon_type!r}")
        if self.n_legs < 1 or not 0 <= self.leg_index < self.n_legs:
            raise ValueError(f"leg_index {self.leg_index} poza 0..{self.n_legs - 1}")
        if (self.coupon_type == "single") != (self.n_legs == 1):
            raise ValueError("single ma dokładnie jedną nogę, multi co najmniej dwie")
        if self.odds_taken <= 1.0:
            raise ValueError(f"kurs musi być > 1.0, jest {self.odds_taken}")
        if self.stake <= 0.0:
            raise ValueError(f"stawka musi być dodatnia, jest {self.stake}")
        if not 0.0 < self.p_fair_at_bet <= 1.0:
            raise ValueError(f"p_fair poza (0, 1]: {self.p_fair_at_bet}")
        # Dziennik live wpisuje człowiek — literówka w podatku (1.12 zamiast
        # 0.88) zmieniała znak CLV, zanim cokolwiek ją sprawdziło (F0b-03).
        validate_tax_factor(tax_factor=self.tax_factor_applied)
        # Rynek ze słownika — inaczej wyłączenie T12 nie złapie nogi (F0c-03).
        # Kanonizacja na granicy dziennika: wewnątrz systemu jedna nazwa
        # (``1x2``, nie ``h2h``) — CLV porównuje kanoniczne (F0d-04).
        object.__setattr__(self, "market", canonical_market(self.market).value)
        # Wynik tak samo — kanoniczny i z kompletu rynku (F0e-03).
        object.__setattr__(self, "outcome", canonical_outcome(self.market, self.outcome).value)
        for name in ("placed_at", "ingested_at"):
            if getattr(self, name).tzinfo is None:
                raise ValueError(f"{name} musi być timezone-aware (reguła 2)")
        if not (self.source == LIVE_SOURCE or self.source.startswith("backtest:")):
            raise ValueError(f"source musi być manual albo backtest:<run_id>: {self.source!r}")
        if (
            self.snapshot_observed_at is not None
            and self.snapshot_observed_at >= self.placed_at
        ):
            raise ValueError(
                "migawka nie jest sprzed zakładu — wycena z przyszłości "
                f"({self.snapshot_observed_at} >= {self.placed_at})"
            )
        if self.settled:
            if self.settled not in LEG_RESULTS:
                raise ValueError(f"nieznany wynik rozliczenia: {self.settled!r}")
            if self.settled_at is None or self.settled_at.tzinfo is None:
                raise ValueError("wiersz rozliczeniowy wymaga settled_at ze strefą")

    @property
    def is_settlement(self) -> bool:
        return bool(self.settled)


BETS_COLUMNS: tuple[str, ...] = tuple(f.name for f in fields(BetRecord))


@dataclass(frozen=True)
class LegState:
    record: BetRecord
    #: ``open``, ``won``, ``lost`` albo ``void`` w chwili ``now``.
    status: str
    settled_at: datetime | None


@dataclass(frozen=True)
class Coupon:
    """Kupon złożony z nóg dziennika, w stanie z chwili ``now``."""

    coupon_id: str
    placed_at: datetime
    mode: str
    bookmaker: str
    coupon_type: str
    stake: float
    tax_factor_applied: float
    source: str
    legs: tuple[LegState, ...]

    @property
    def is_real(self) -> bool:
        return self.mode == "real"

    @property
    def status(self) -> str:
        statuses = [leg.status for leg in self.legs]
        if "lost" in statuses:
            return "lost"
        if "open" in statuses:
            return "open"
        if all(s == "void" for s in statuses):
            return "void"
        return "won"

    @property
    def is_open(self) -> bool:
        return self.status == "open"

    @property
    def odds(self) -> float:
        """Kurs kuponu na postawieniu."""
        return math.prod(leg.record.odds_taken for leg in self.legs)

    @property
    def settled_at(self) -> datetime | None:
        if self.is_open:
            return None
        if self.status == "lost":
            return min(g.settled_at for g in self.legs if g.status == "lost" and g.settled_at)
        return max(g.settled_at for g in self.legs if g.settled_at)

    @property
    def payout(self) -> float | None:
        """Wypłata netto: wygrany — brutto · T13; zwrot — ``stawka · tax``; ``None`` = otwarty."""
        status = self.status
        if status == "open":
            return None
        if status == "lost":
            return 0.0
        if status == "void":
            return round(self.stake * self.tax_factor_applied, 2)
        odds = math.prod(g.record.odds_taken for g in self.legs if g.status != "void")
        return round(
            settlement_payout(stake=self.stake, odds=odds, tax_factor=self.tax_factor_applied),
            2,
        )

    def ev_legs(self, *, as_placed: bool) -> tuple[CouponLeg, ...]:
        return tuple(
            CouponLeg(
                match_id=g.record.match_id,
                odds=g.record.odds_taken,
                void=False if as_placed else g.status == "void",
                market=g.record.market,
            )
            for g in self.legs
        )

    @property
    def ako_at_placement(self) -> bool:
        return qualifies_as_ako(self.ev_legs(as_placed=True))

    def to_placed_bet(self) -> PlacedBet:
        """Wejście reżimu podatkowego — stan nóg w chwili ``now`` (T6)."""
        return PlacedBet(
            coupon_id=self.coupon_id,
            placed_at=self.placed_at,
            stake=self.stake,
            legs=self.ev_legs(as_placed=False),
            mode=self.mode,
        )

    def match_ids(self) -> set[str]:
        return {g.record.match_id for g in self.legs}


_COUPON_FIELDS = ("placed_at", "mode", "bookmaker", "stake", "tax_factor_applied", "coupon_type", "n_legs", "source")


def _check_legs(legs: Sequence[BetRecord]) -> None:
    """Spójność nóg kuponu: jedna stawka, czas, tryb, bukmacher, komplet nóg."""
    first = legs[0]
    for leg in legs:
        for name in _COUPON_FIELDS:
            if getattr(leg, name) != getattr(first, name):
                raise ValueError(f"kupon {first.coupon_id}: nogi różnią się polem {name}")
        if leg.coupon_id != first.coupon_id:
            raise ValueError("nogi z różnych kuponów")
    if first.n_legs != len(legs):
        raise ValueError(f"kupon {first.coupon_id}: n_legs={first.n_legs}, nóg {len(legs)}")
    if sorted(leg.leg_index for leg in legs) != list(range(len(legs))):
        raise ValueError(f"kupon {first.coupon_id}: leg_index nie jest 0..{len(legs) - 1}")


def coupons(journal_rows: Iterable[BetRecord], *, now: datetime) -> list[Coupon]:
    """Wiersze dziennika → kupony w stanie z chwili ``now``. Jedyna taka funkcja.

    Kupony postawione po ``now`` nie istnieją; rozliczenia z ``settled_at >
    now`` nie są jeszcze znane (reguła 1). Wartość ``ako_at_placement``
    zapisana w CSV musi zgadzać się z wyliczoną — rozjazd to wyjątek.
    """
    if now.tzinfo is None:
        raise ValueError("now musi być timezone-aware (reguła 2)")
    rows = list(journal_rows)
    bets: dict[str, list[BetRecord]] = {}
    results: dict[str, BetRecord] = {}
    for row in rows:
        if row.is_settlement:
            original = row.bet_id.removesuffix("#settle")
            if row.settled_at is not None and row.settled_at <= now:
                results[original] = row
        else:
            bets.setdefault(row.coupon_id, []).append(row)
    out: list[Coupon] = []
    for coupon_id, legs in bets.items():
        legs.sort(key=lambda r: r.leg_index)
        _check_legs(legs)
        first = legs[0]
        if first.placed_at > now:
            continue
        states = tuple(
            LegState(
                record=leg,
                status=results[leg.bet_id].settled if leg.bet_id in results else "open",
                settled_at=results[leg.bet_id].settled_at if leg.bet_id in results else None,
            )
            for leg in legs
        )
        coupon = Coupon(
            coupon_id=coupon_id,
            placed_at=first.placed_at,
            mode=first.mode,
            bookmaker=first.bookmaker,
            coupon_type=first.coupon_type,
            stake=first.stake,
            tax_factor_applied=first.tax_factor_applied,
            source=first.source,
            legs=states,
        )
        for leg in legs:
            if leg.ako_at_placement is not None and leg.ako_at_placement != coupon.ako_at_placement:
                raise ValueError(
                    f"kupon {coupon_id}: zapisane ako={leg.ako_at_placement}, wyliczone "
                    f"{coupon.ako_at_placement} — dziennik i ev.qualifies_as_ako się rozjechały"
                )
        out.append(coupon)
    return sorted(out, key=lambda c: (c.placed_at, c.coupon_id))


def open_stake(coupons_: Iterable[Coupon]) -> float:
    """Otwarta ekspozycja: stawki kuponów otwartych, każda raz."""
    return sum(c.stake for c in coupons_ if c.is_open)


def match_open_stake(coupons_: Iterable[Coupon], match_id: str) -> float:
    """Otwarta ekspozycja na mecz: PEŁNA stawka każdego kuponu z nogą na nim."""
    return sum(c.stake for c in coupons_ if c.is_open and match_id in c.match_ids())


def real_coupon_count(coupons_: Iterable[Coupon]) -> int:
    """Liczba prawdziwych kuponów — wejście bramki G-K."""
    return sum(1 for c in coupons_ if c.is_real)


@dataclass
class BetJournal:
    """Dziennik. Dopisywanie i odczyt; **nigdy** nadpisywanie wiersza.

    ``journal_path`` jest wymagane — dziennik backtestu to osobny plik per
    przebieg, a domyślna ścieżka live w bibliotece oznaczałaby, że pominięty
    argument pisze do prawdziwego dziennika.
    """

    journal_path: Path
    #: Pamięć wierszy i indeksy (Filar 1: backtest dopisuje dziesiątki tysięcy
    #: kuponów przez ten sam dziennik — pełne parsowanie przy każdym zapisie
    #: było kwadratowe). Odświeżana, gdy plik zmienił rozmiar albo mtime,
    #: czyli także po dopisaniu przez inną instancję albo proces.
    _rows: list[BetRecord] = field(default_factory=list, init=False, repr=False)
    _ids: dict[str, BetRecord] = field(default_factory=dict, init=False, repr=False)
    _by_coupon: dict[str, list[BetRecord]] = field(default_factory=dict, init=False, repr=False)
    _stat: tuple[int, int] | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)

    def _file_stat(self) -> tuple[int, int]:
        if not self.journal_path.exists():
            return (0, 0)
        st = self.journal_path.stat()
        return (st.st_size, st.st_mtime_ns)

    def _index(self, records: Sequence[BetRecord]) -> None:
        for record in records:
            self._rows.append(record)
            self._ids.setdefault(record.bet_id, record)
            self._by_coupon.setdefault(record.coupon_id, []).append(record)

    def _load(self) -> None:
        """Wiersze z pliku do pamięci — tylko gdy plik zmienił się od ostatniego razu."""
        stat = self._file_stat()
        if stat == self._stat:
            return
        self._rows, self._ids, self._by_coupon = [], {}, {}
        self._index(self._parse())
        self._stat = stat

    def _ensure_header(self) -> None:
        if self.journal_path.exists() and self.journal_path.stat().st_size > 0:
            return
        with self.journal_path.open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerow(BETS_COLUMNS)

    def _append(self, records: Sequence[BetRecord]) -> None:
        self._ensure_header()
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        for record in records:
            row = asdict(record)
            writer.writerow([_to_cell(row[name]) for name in BETS_COLUMNS])
        # Jeden zapis na kupon — kupon nie może trafić do dziennika w połowie.
        self._load()
        with self.journal_path.open("a", encoding="utf-8", newline="") as handle:
            handle.write(buffer.getvalue())
        self._index(records)
        self._stat = self._file_stat()

    def add_coupon(self, legs: Sequence[BetRecord]) -> None:
        """Dopisuje kupon atomowo. Powtórzony ``bet_id`` albo ``coupon_id`` to błąd."""
        if not legs:
            raise ValueError("kupon bez nóg")
        if any(leg.is_settlement for leg in legs):
            raise ValueError("add_coupon przyjmuje nogi, nie rozliczenia")
        legs = sorted(legs, key=lambda r: r.leg_index)
        _check_legs(legs)
        self._load()
        if any(leg.bet_id in self._ids for leg in legs) or legs[0].coupon_id in self._by_coupon:
            raise ValueError(
                f"kupon {legs[0].coupon_id} albo jego bet_id już w dzienniku — dziennik "
                "jest append-only, korekta idzie jako nowy wiersz z notatką"
            )
        ako = qualifies_as_ako(
            CouponLeg(match_id=g.match_id, odds=g.odds_taken, void=False, market=g.market)
            for g in legs
        )
        self._append([replace(leg, ako_at_placement=ako) for leg in legs])

    def add(self, record: BetRecord) -> None:
        """Singiel — kupon jednonożny."""
        self.add_coupon([record])

    def read(self) -> list[BetRecord]:
        """Wszystkie wiersze w kolejności zapisu (kopia — zmiana listy nie psuje pamięci)."""
        self._load()
        return list(self._rows)

    def _parse(self) -> list[BetRecord]:
        if not self.journal_path.exists() or self.journal_path.stat().st_size == 0:
            return []
        out: list[BetRecord] = []
        with self.journal_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                out.append(
                    BetRecord(
                        bet_id=row["bet_id"],
                        placed_at=datetime.fromisoformat(row["placed_at"]),
                        mode=row["mode"],
                        bookmaker=row["bookmaker"],
                        coupon_id=row["coupon_id"],
                        coupon_type=row["coupon_type"],
                        n_legs=int(row["n_legs"]),
                        leg_index=int(row["leg_index"]),
                        match_id=row["match_id"],
                        market=row["market"],
                        outcome=row["outcome"],
                        line=_opt_float(row["line"]),
                        odds_taken=float(row["odds_taken"]),
                        stake=float(row["stake"]),
                        tax_factor_applied=float(row["tax_factor_applied"]),
                        p_fair_at_bet=float(row["p_fair_at_bet"]),
                        snapshot_observed_at=_opt_dt(row["snapshot_observed_at"]),
                        price_available=row["price_available"].lower() in ("true", "1", "tak"),
                        ingested_at=datetime.fromisoformat(row["ingested_at"]),
                        source=row["source"],
                        notes=row.get("notes", ""),
                        settled=row.get("settled", ""),
                        settled_at=_opt_dt(row.get("settled_at", "")),
                        payout=_opt_float(row.get("payout", "")),
                        ako_at_placement=_opt_bool(row.get("ako_at_placement", "")),
                    )
                )
        return out

    def settle(self, bet_id: str, result: str, *, now: datetime) -> None:
        """Rozliczenie NOGI jako nowy wiersz, nie edycja starego.

        ``now`` to chwila rozliczenia (``settled_at``), podana — nie
        ``datetime.now``. Wiersz rozliczeniowy zachowuje ``placed_at`` nogi.
        Wypłatę kuponu liczy :attr:`Coupon.payout` (T13); tu zapisujemy ją
        tylko dla singla, do wglądu.
        """
        if now.tzinfo is None:
            raise ValueError("now musi być timezone-aware (reguła 2)")
        if result not in LEG_RESULTS:
            raise ValueError(f"nieznany wynik rozliczenia: {result!r}")
        self._load()
        original = self._ids.get(bet_id)
        if original is None or original.is_settlement:
            raise ValueError(f"nie ma zakładu {bet_id!r} do rozliczenia")
        if f"{bet_id}#settle" in self._ids:
            raise ValueError(f"noga {bet_id!r} już rozliczona")
        if now < original.placed_at:
            raise ValueError("rozliczenie przed postawieniem zakładu")
        settlement = replace(
            original,
            bet_id=f"{bet_id}#settle",
            settled=result,
            settled_at=now,
            notes=f"rozliczenie {bet_id}",
            snapshot_observed_at=None,
            payout=None,
            ako_at_placement=None,
        )
        if original.coupon_type == "single":
            # Kupon składany z JEGO wierszy — ten sam wynik co z całego dziennika.
            own = self._by_coupon[original.coupon_id]
            (coupon,) = coupons([*own, settlement], now=now)
            settlement = replace(settlement, payout=coupon.payout)
        self._append([settlement])


def live_coupons(path: Path, *, now: datetime) -> list[Coupon]:
    """Dziennik LIVE dla reżimu i G-K: każdy wiersz musi mieć ``source == manual``.

    Wiersz z backtestu w prawdziwym dzienniku to wyjątek, nie filtr po cichu
    — oznacza pomyloną ścieżkę albo skażony plik.
    """
    rows = BetJournal(journal_path=path).read()
    foreign = sorted({r.source for r in rows if r.source != LIVE_SOURCE})
    if foreign:
        raise ValueError(
            f"{path}: wiersze ze źródłem {foreign} w dzienniku live — dozwolone tylko "
            f"{LIVE_SOURCE!r}"
        )
    return coupons(rows, now=now)


def _to_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _opt_float(raw: str | None) -> float | None:
    if raw is None or raw == "":
        return None
    return float(raw)


def _opt_dt(raw: str | None) -> datetime | None:
    if raw is None or raw == "":
        return None
    return datetime.fromisoformat(raw)


def _opt_bool(raw: str | None) -> bool | None:
    if raw is None or raw == "":
        return None
    return raw.lower() == "true"
