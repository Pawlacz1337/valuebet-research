"""Replay football-data → migawki w formacie S1 + wynik (BACKTEST_FIN_PLAN §2).

Jeden wiersz pliku sezonu to trzy rzeczy, każda z innym czasem:

- **migawka decyzyjna** — kursy sprzed meczu (``PSH``, ``B365H``, ``P>2.5``…)
  z ``observed_at`` z reguły ``ObservedAtRule`` (``config/strategy.yaml``);
- **migawka zamknięcia** — kolumny z „C” (``PSCH``, ``PC>2.5``…), umownie
  ``CLOSING_BEFORE_KICKOFF`` przed gwizdkiem (w tolerancji CLV 30 min);
- **wynik** — ``FTHG``/``FTAG``, znany dopiero w ``settled_at``.

Wynik celowo **nie jest polem** :class:`ReplayMatch`: decyzja dostaje mecz,
rozliczenie dostaje :class:`MatchResult`. Pętla zdarzeń w
``backtest/financial.py`` nie ma jak zajrzeć do wyniku przed ``settled_at``
(trucizna, klasa błędu KRYT 2).

Notowania są w typie wyceny (``pricing.fair.MarketQuote``), więc
``fair_prices`` dostaje dokładnie to, co dostałby z kolektora S1 (reguła 28).

Umowy (spisane przed wynikiem, ``docs/sources.md``):

- ``DECISION_LAG`` — decyzja minutę po obserwacji (``observed_at <
  decision_at``); kapitał do stawki liczony w tej chwili;
- ``CLOSING_BEFORE_KICKOFF`` — football-data nie podaje chwili zamknięcia;
  „closing odds” = ostatni kurs przed gwizdkiem, umownie minuta przed;
- ``SETTLE_AFTER`` — wynik znany 3 h po gwizdku (mecz ~1 h 55 min + zapas);
  późniejsze rozliczenie dłużej blokuje kapitał, więc jest zachowawcze.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pandas as pd

from valuebet.ingest.football_data_main import (
    ObservedAtRule,
    kickoff_utc,
    pre_match_observed_at,
    read_csv_bytes,
)
from valuebet.ingest.football_data_main import _match_id as football_data_match_id
from valuebet.pricing.fair import MarketQuote

__all__ = [
    "BOOKS_1X2",
    "BOOKS_OU",
    "CLOSING_BEFORE_KICKOFF",
    "DECISION_LAG",
    "OU_LINE",
    "SETTLE_AFTER",
    "MatchResult",
    "Replay",
    "ReplayMatch",
    "merge_replays",
    "replay_csv",
    "replay_pol_closing",
]

log = logging.getLogger(__name__)

DECISION_LAG = timedelta(minutes=1)
CLOSING_BEFORE_KICKOFF = timedelta(minutes=1)
SETTLE_AFTER = timedelta(hours=3)
OU_LINE = 2.5

OUTCOMES_1X2 = ("home", "draw", "away")
OUTCOMES_OU = ("over", "under")

#: Bukmacher → (kolumny sprzed meczu, kolumny zamknięcia) dla 1X2 (notes.txt).
BOOKS_1X2: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "pinnacle": (("PSH", "PSD", "PSA"), ("PSCH", "PSCD", "PSCA")),
    "bet365": (("B365H", "B365D", "B365A"), ("B365CH", "B365CD", "B365CA")),
    "betandwin": (("BWH", "BWD", "BWA"), ("BWCH", "BWCD", "BWCA")),
    "williamhill": (("WHH", "WHD", "WHA"), ("WHCH", "WHCD", "WHCA")),
    "max": (("MaxH", "MaxD", "MaxA"), ("MaxCH", "MaxCD", "MaxCA")),
}
#: Totale 2.5 — Pinnacle to ``P``, nie ``PS`` (notes.txt).
BOOKS_OU: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "pinnacle": (("P>2.5", "P<2.5"), ("PC>2.5", "PC<2.5")),
    "bet365": (("B365>2.5", "B365<2.5"), ("B365C>2.5", "B365C<2.5")),
    "max": (("Max>2.5", "Max<2.5"), ("MaxC>2.5", "MaxC<2.5")),
}

SKIP_KICKOFF = "gwizdek ≤ observed_at"
SKIP_NO_RESULT = "brak wyniku → void"


@dataclass(frozen=True)
class ReplayMatch:
    """Mecz w chwili decyzji. **Bez wyniku** — ten jest w :class:`MatchResult`."""

    match_id: str
    league: str
    season: str
    home_team: str
    away_team: str
    kickoff: datetime
    observed_at: datetime
    decision_at: datetime
    closing_at: datetime
    #: bukmacher → notowania kompletnych rynków z migawki decyzyjnej.
    decision: Mapping[str, tuple[MarketQuote, ...]]
    #: bukmacher → notowania z migawki zamknięcia.
    closing: Mapping[str, tuple[MarketQuote, ...]]


@dataclass(frozen=True)
class MatchResult:
    match_id: str
    home_goals: int | None
    away_goals: int | None
    settled_at: datetime

    @property
    def void(self) -> bool:
        """Brak wyniku w pliku → zakład zwracany (bez selekcji po przyszłości)."""
        return self.home_goals is None or self.away_goals is None


@dataclass(frozen=True)
class Replay:
    matches: tuple[ReplayMatch, ...]
    results: Mapping[str, MatchResult]
    #: (liga, sezon, powód) → liczba. Nic nie ginie po cichu.
    skipped: Counter[tuple[str, str, str]] = field(default_factory=Counter)


def _quote(
    row: pd.Series,
    columns: tuple[str, ...],
    *,
    match_id: str,
    market: str,
    outcomes: tuple[str, ...],
    observed_at: datetime,
    line: float | None,
) -> MarketQuote | None:
    """Kompletny rynek albo ``None`` (brak kolumny, pusto, kurs ≤ 1.0)."""
    odds: list[float] = []
    for column in columns:
        if column not in row.index:
            return None
        value = pd.to_numeric(row[column], errors="coerce")
        if pd.isna(value) or float(value) <= 1.0:
            return None
        odds.append(float(value))
    return MarketQuote(
        match_id=match_id,
        market=market,
        outcomes=outcomes,
        odds=tuple(odds),
        observed_at=observed_at,
        line=line,
    )


def _goals(value: object) -> int | None:
    """Liczba goli albo ``None`` (pusto, NaN, napis)."""
    try:
        number = float(str(value))
    except ValueError:
        return None
    return None if number != number else int(number)


def replay_csv(content: bytes, *, league: str, season: str, rule: ObservedAtRule) -> Replay:
    """Surowy CSV sezonu (bajty z raw) → :class:`Replay`.

    Raises
    ------
    ValueError
        Powtórzony ``match_id`` albo data/godzina spoza formatu — głośno,
        nie cicho (``kickoff_utc``).
    """
    frame = read_csv_bytes(content).dropna(how="all")
    skipped: Counter[tuple[str, str, str]] = Counter()
    matches: list[ReplayMatch] = []
    results: dict[str, MatchResult] = {}
    for _, row in frame.iterrows():
        kickoff = kickoff_utc(str(row["Date"]), str(row["Time"]))
        home, away = str(row["HomeTeam"]), str(row["AwayTeam"])
        match_id = football_data_match_id(league, pd.Timestamp(kickoff), home, away)
        if match_id in results:
            raise ValueError(f"{league}-{season}: powtórzony mecz {home} - {away} {kickoff}")
        home_goals, away_goals = _goals(row.get("FTHG")), _goals(row.get("FTAG"))
        result = MatchResult(match_id, home_goals, away_goals, kickoff + SETTLE_AFTER)
        results[match_id] = result
        observed = pre_match_observed_at(kickoff, rule=rule)
        if observed is None:
            skipped[(league, season, SKIP_KICKOFF)] += 1
            continue
        if result.void:
            skipped[(league, season, SKIP_NO_RESULT)] += 1
        closing_at = kickoff - CLOSING_BEFORE_KICKOFF
        decision: dict[str, list[MarketQuote]] = {}
        closing: dict[str, list[MarketQuote]] = {}
        for market, books, outcomes, line in (
            ("1x2", BOOKS_1X2, OUTCOMES_1X2, None),
            ("over_under", BOOKS_OU, OUTCOMES_OU, OU_LINE),
        ):
            for book, (pre_cols, close_cols) in books.items():
                for target, cols, at, label in (
                    (decision, pre_cols, observed, "niekompletny"),
                    (closing, close_cols, closing_at, "niekompletne zamknięcie"),
                ):
                    quote = _quote(
                        row, cols, match_id=match_id, market=market,
                        outcomes=outcomes, observed_at=at, line=line,
                    )  # fmt: skip
                    if quote is None:
                        skipped[(league, season, f"{label} {book} {market}")] += 1
                    else:
                        target.setdefault(book, []).append(quote)
        matches.append(
            ReplayMatch(
                match_id=match_id,
                league=league,
                season=season,
                home_team=home,
                away_team=away,
                kickoff=kickoff,
                observed_at=observed,
                decision_at=observed + DECISION_LAG,
                closing_at=closing_at,
                decision={b: tuple(q) for b, q in decision.items()},
                closing={b: tuple(q) for b, q in closing.items()},
            )
        )
    return Replay(matches=tuple(matches), results=results, skipped=skipped)


def merge_replays(replays: Iterable[Replay]) -> Replay:
    """Sklejenie lig i sezonów; mecze po ``decision_at``, potem ``match_id``."""
    matches: list[ReplayMatch] = []
    results: dict[str, MatchResult] = {}
    skipped: Counter[tuple[str, str, str]] = Counter()
    for replay in replays:
        overlap = set(results) & set(replay.results)
        if overlap:
            raise ValueError(f"powtórzone mecze między plikami: {sorted(overlap)[:3]}")
        matches.extend(replay.matches)
        results.update(replay.results)
        skipped.update(replay.skipped)
    matches.sort(key=lambda m: (m.decision_at, m.match_id))
    return Replay(matches=tuple(matches), results=results, skipped=skipped)


#: F (Ekstraklasa, ``POL.csv`` z „extra leagues”): tylko zamknięcia. Migawka
#: „decyzyjna” = zamknięcie, umownie 2 min przed gwizdkiem, decyzja minutę
#: później. CLV = EV z definicji — na zamknięciu nie da się zagrać po kursie
#: zamknięcia; strategia wyłącznie raportowa (decyzja Pawła 2026-10-08).
POL_OBSERVED_BEFORE_KICKOFF = timedelta(minutes=2)
_POL_BOOKS = {"pinnacle": ("PSCH", "PSCD", "PSCA"), "bet365": ("B365CH", "B365CD", "B365CA")}
SKIP_POL_INCOMPLETE = "brak kompletu PSC/B365C"


def replay_pol_closing(frame: pd.DataFrame, *, seasons: Iterable[str]) -> Replay:
    """Ramka ``POL.csv`` (raw) → replay F: B365C kontra PSC, mecze z kompletem obu."""
    wanted = set(seasons)
    skipped: Counter[tuple[str, str, str]] = Counter()
    matches: list[ReplayMatch] = []
    results: dict[str, MatchResult] = {}
    for _, row in frame.iterrows():
        season = str(row["Season"])
        if season not in wanted:
            continue
        kickoff = kickoff_utc(str(row["Date"]), str(row["Time"]))
        home, away = str(row["Home"]), str(row["Away"])
        match_id = football_data_match_id("POL", pd.Timestamp(kickoff), home, away)
        if match_id in results:
            raise ValueError(f"POL {season}: powtórzony mecz {home} - {away} {kickoff}")
        observed = kickoff - POL_OBSERVED_BEFORE_KICKOFF
        quotes = {
            book: _quote(row, cols, match_id=match_id, market="1x2", outcomes=OUTCOMES_1X2,
                         observed_at=observed, line=None)
            for book, cols in _POL_BOOKS.items()
        }  # fmt: skip
        if any(q is None for q in quotes.values()):
            skipped[("POL", season, SKIP_POL_INCOMPLETE)] += 1
            continue
        results[match_id] = MatchResult(
            match_id, _goals(row.get("HG")), _goals(row.get("AG")), kickoff + SETTLE_AFTER
        )
        decision = {book: (q,) for book, q in quotes.items() if q is not None}
        matches.append(
            ReplayMatch(
                match_id=match_id,
                league="POL",
                season=season,
                home_team=home,
                away_team=away,
                kickoff=kickoff,
                observed_at=observed,
                decision_at=observed + DECISION_LAG,
                closing_at=observed,
                decision=decision,
                closing={"pinnacle": decision["pinnacle"]},
            )
        )
    matches.sort(key=lambda m: (m.decision_at, m.match_id))
    return Replay(matches=tuple(matches), results=results, skipped=skipped)
