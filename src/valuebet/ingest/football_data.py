"""Ingest wyników i kursów zamknięcia z football-data.co.uk (Ekstraklasa).

Źródło: sekcja „extra leagues", plik ``POL.csv``. Jeden wiersz na mecz,
wszystkie sezony od 2012/13 w jednym pliku, który serwis **nadpisuje** po
każdej kolejce. Stąd dwie warstwy zapisu:

* ``data/raw/football_data/`` — każdy pobrany plik ląduje jako osobny,
  datowany parquet ze wszystkimi kolumnami jako tekst (bezstratnie).
  Nigdy nie nadpisujemy — serwis koryguje wiersze wstecz (wyniki walkowerów,
  przełożone mecze) i chcemy widzieć, co widzieliśmy w danym dniu.
* ``data/interim/football_data/`` — sparsowane mecze zgodne z
  :class:`valuebet.schema.Match` oraz osobna tabela kursów zamknięcia.
  To warstwa pochodna, wolno ją regenerować.

Nagłówek zweryfikowany 2026-09-21
---------------------------------
::

    Country, League, Season, Date, Time, Home, Away, HG, AG, Res,
    PSCH, PSCD, PSCA,       Pinnacle — zamknięcie
    MaxCH, MaxCD, MaxCA,    maksimum rynku — zamknięcie
    AvgCH, AvgCD, AvgCA,    średnia rynku — zamknięcie
    BFECH, BFECD, BFECA,    Betfair Exchange — zamknięcie (od 2024/25)
    B365CH, B365CD, B365CA  bet365 — zamknięcie (od 2024/25)

Plik ma BOM (``utf-8-sig``). Sufiks ``C`` w nazwach kursów oznacza
*closing*. Kolumn otwarcia (``PH/PD/PA``) w pliku **nie ma**.

Kursy zamknięcia służą WYŁĄCZNIE do CLV
---------------------------------------
Reguła 7 w CLAUDE.md. Zamknięcie to najlepsza dostępna estymata „prawdy"
rynku i punkt odniesienia dla CLV — ale zawiera informację, której w
momencie stawiania zakładu nie było (składy, ruch pieniędzy). Użycie go
jako ceny wejścia albo jako cechy modelu to look-ahead bias. Dlatego kursy
NIE trafiają do ramki meczów, tylko do osobnej tabeli ``closing_odds``,
i nigdy nie są łączone z cechami.

Pułapka czasowa
---------------
``Date`` i ``Time`` są w **czasie lokalnym brytyjskim** z DST, nie w CET
i nie w UTC. Zweryfikowane empirycznie: najczęstsze godziny w pliku to
17:00, 19:30, 14:30, 16:30 — czyli polskie 18:00, 20:30, 15:30, 17:30
minus jedna godzina. Naiwna konwersja daje błąd 1-2h, który przy regule
``asof_utc = kickoff_utc - bet_lead_time`` przerzuca fakty na drugą
stronę granicy odcięcia.

Konwersja: ``tz_localize("Europe/London", ambiguous="NaT",
nonexistent="NaT")`` → ``tz_convert("UTC")``. Godziny dwuznaczne (jesienne
cofnięcie zegara) i nieistniejące (wiosenny skok) dają ``NaT``; takie
wiersze są **odrzucane i raportowane**, nigdy cicho przesuwane.

Wiersze bez ``Time``
--------------------
Decyzja: **odrzucamy i liczymy**. Bez godziny nie da się ustalić momentu
odcięcia — data to za mało, bo ``bet_lead_time`` rzędu godzin jest
mniejszy niż niepewność. Wpisanie sztucznej godziny (np. 12:00) tworzyłoby
mecze, dla których cechy z tego samego dnia mogłyby pochodzić sprzed lub
zza gwizdka w zależności od realnej godziny. Liczba odrzuconych jest w
raporcie; jeśli kiedyś przestanie być zerem, trzeba to zobaczyć.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd

from valuebet.backtest.lockbox import parse_season
from valuebet.ingest.raw_store import RawStore, parquet_bytes
from valuebet.ingest.team_mapping import AliasStore, TeamResolver
from valuebet.net.http import HttpClient, HttpError
from valuebet.schema import Match, MatchStatus, Sport, make_match_id

__all__ = [
    "CLOSING_BOOKMAKERS",
    "COMPETITIONS",
    "FOOTBALL_DATA_URL",
    "SOURCE",
    "SOURCE_NAME_OVERRIDES",
    "ParseReport",
    "ParseResult",
    "download",
    "load_raw_latest",
    "main",
    "parse_matches",
    "read_raw_csv",
    "write_interim",
    "write_raw",
]

log = logging.getLogger(__name__)

_HTTP_OK = 200

FOOTBALL_DATA_URL = "https://www.football-data.co.uk/new/POL.csv"
SOURCE = "football_data"

#: Para (Country, League) z pliku → kanoniczne ID rozgrywek, wspólne dla
#: wszystkich źródeł (API-Football liga 106 musi mapować się na to samo).
#: Nieznana para jest błędem, nie pominięciem — pojawienie się nowej ligi
#: w pliku ma być głośne.
COMPETITIONS: dict[tuple[str, str], str] = {
    ("Poland", "Ekstraklasa"): "ekstraklasa",
}

#: Kolumny wymagane do zbudowania meczu. Reszta jest opcjonalna.
REQUIRED_COLUMNS: tuple[str, ...] = (
    "Country", "League", "Season", "Date", "Time", "Home", "Away", "HG", "AG", "Res",
)  # fmt: skip

#: Bukmacher → prefiks kolumn kursów zamknięcia (sufiksy H/D/A).
CLOSING_BOOKMAKERS: dict[str, str] = {
    "pinnacle": "PSC",
    "market_max": "MaxC",
    "market_avg": "AvgC",
    "betfair_exchange": "BFEC",
    "bet365": "B365C",
}

#: Skróty specyficzne dla TEGO źródła, które globalnie są niejednoznaczne.
#:
#: football-data pisze „Wisla" dla Wisły Kraków, ale „Wisla Plock" dla
#: Płocka; „Ruch" dla Chorzowa; „Zaglebie" dla Lubina, a „Zaglebie
#: Sosnowiec" pełną nazwą; „Gornik Z." dla Zabrza, a Łęczna to „Leczna".
#: W obrębie pliku jest to jednoznaczne, ale dopisanie samego „Wisla"
#: jako globalnego aliasu w ``team_aliases.yaml`` złamałoby zasadę z tego
#: pliku („nazwa miasta jest częścią klucza") i przy następnym źródle
#: mogłoby po cichu skleić Płock z Krakowem. „Gornik Z." jest podstępne
#: inaczej: ``normalise_name`` usuwa jednoliterowe tokeny, więc alias
#: indeksowałby się jako samo „gornik".
#:
#: Dlatego rozwijamy skrót do pełnej nazwy PRZED resolverem, jawnie i
#: tylko dla tego źródła. To jest słownik, nie fuzzy — reguła 15 stoi.
SOURCE_NAME_OVERRIDES: dict[str, str] = {
    "Wisla": "Wisla Krakow",
    "Ruch": "Ruch Chorzow",
    "Zaglebie": "Zaglebie Lubin",
    "Gornik Z.": "Gornik Zabrze",
}

_TZ_SOURCE = "Europe/London"
_DATE_FORMAT = "%d/%m/%Y %H:%M"

_RESULT_BY_SIGN = {1: "H", 0: "D", -1: "A"}


# ---------------------------------------------------------------------------
# Pobranie i zapis surowy
# ---------------------------------------------------------------------------


def download(http: HttpClient, url: str = FOOTBALL_DATA_URL) -> bytes:
    """Pobiera plik CSV przez jedyny klient sieciowy (odstęp, robots.txt — F-26)."""
    response = http.get(url)
    if response.status_code != _HTTP_OK:
        raise HttpError(f"football-data: {url} zwróciło HTTP {response.status_code}")
    return bytes(response.content)


def read_raw_csv(content: bytes) -> pd.DataFrame:
    """Parsuje bajty CSV bezstratnie: każda kolumna jako tekst.

    Typowanie odbywa się dopiero w :func:`parse_matches`. Dzięki temu warstwa
    raw jest odwracalna do bajtów wejściowych (poza BOM i końcami linii),
    a zmiana formatu kursu albo daty przez serwis nie psuje archiwum.
    """
    frame = pd.read_csv(BytesIO(content), encoding="utf-8-sig", dtype=str)
    frame.columns = [str(c).strip() for c in frame.columns]
    missing = set(REQUIRED_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(
            f"football-data: brak wymaganych kolumn {sorted(missing)}; "
            f"nagłówek: {list(frame.columns)}. Format pliku się zmienił — "
            "dostosuj parser, nie zgaduj."
        )
    return frame


def write_raw(
    raw: pd.DataFrame,
    store: RawStore,
    *,
    content: bytes,
    now: datetime,
    source_url: str = FOOTBALL_DATA_URL,
    subdir: str = "football_data",
) -> Path:
    """Zapisuje surową ramkę jako nowy plik parquet w raw — przez ``RawStore``.

    Append-only z manifestem (reguła 12, FSA #0 F-12): nazwę i hash nadaje
    magazyn, drugi zapis tych samych bajtów w tej samej chwili to wyjątek.
    ``content_sha256`` pozwala stwierdzić, czy dwa pobrania to ten sam plik,
    bez porównywania wierszy.
    """
    ingested_at = now.astimezone(UTC)
    frame = raw.copy()
    frame["row_number"] = range(len(frame))
    frame["ingested_at"] = pd.Timestamp(ingested_at)
    frame["source"] = SOURCE
    frame["source_url"] = source_url
    frame["content_sha256"] = hashlib.sha256(content).hexdigest()
    path = store.write_raw(
        subdir, "POL", ".parquet", parquet_bytes(frame), now=ingested_at
    )
    log.info("football-data: zapisano %d surowych wierszy do %s", len(frame), path)
    return path


def _raw_stamp(path: Path) -> str:
    """Znacznik czasu z nazwy — stary (``POL-<s>Z-<uuid>``) i nowy format."""
    match = _STAMP.search(path.name)
    if match is None:
        return ""
    return match.group(1) + (match.group(2) or "000000")


_STAMP = re.compile(r"(\d{8}T\d{6})(\d{6})?Z")


def load_raw_latest(root: Path) -> pd.DataFrame:
    """Wczytuje najnowszy surowy parquet (po nazwie, czyli po czasie pobrania)."""
    files = sorted(Path(root).glob("POL[-.]*.parquet"), key=_raw_stamp)
    if not files:
        raise FileNotFoundError(f"brak surowych plików football-data w {root}")
    frame = pd.read_parquet(files[-1])
    return frame.drop(
        columns=["row_number", "ingested_at", "source", "source_url", "content_sha256"],
        errors="ignore",
    )


# ---------------------------------------------------------------------------
# Parsowanie
# ---------------------------------------------------------------------------


@dataclass
class ParseReport:
    """Co wypadło i dlaczego. Każda liczba tu to mecze, których NIE MA w wyniku.

    Zero jest normą. Każda niezerowa wartość poza ``closing_incomplete``
    powinna zostać przeczytana przez człowieka, zanim pójdzie dalej —
    odrzucenia skorelowane z drużyną albo sezonem to survivorship bias.
    """

    rows_in: int = 0
    rows_out: int = 0
    rows_without_time: int = 0
    rows_ambiguous_dst: int = 0
    rows_unknown_competition: int = 0
    rows_unresolved_team: int = 0
    #: Nazwa surowa → liczba wystąpień (mecze, w których wystąpiła).
    unresolved_teams: Counter[str] = field(default_factory=Counter)
    #: Bukmacher → liczba meczów bez kompletnego rynku 1X2 na zamknięciu.
    closing_incomplete: Counter[str] = field(default_factory=Counter)
    #: Sezon → liczba meczów bez zamknięcia Pinnacle. To decyduje, na jakim
    #: okresie da się policzyć CLV względem Pinnacle.
    pinnacle_missing_by_season: Counter[str] = field(default_factory=Counter)
    team_coverage: float = 1.0

    @property
    def rows_dropped(self) -> int:
        return self.rows_in - self.rows_out

    def log_summary(self) -> None:
        log.info(
            "football-data: %d wierszy → %d meczów (odrzucone: %d; bez godziny %d, "
            "DST %d, nieznane rozgrywki %d, nieznana drużyna %d); pokrycie nazw %.2f%%",
            self.rows_in,
            self.rows_out,
            self.rows_dropped,
            self.rows_without_time,
            self.rows_ambiguous_dst,
            self.rows_unknown_competition,
            self.rows_unresolved_team,
            self.team_coverage * 100,
        )
        for name, count in self.unresolved_teams.most_common():
            log.warning(
                "football-data: nierozpoznana drużyna %r w %d meczach", name, count
            )
        for bookmaker, count in sorted(self.closing_incomplete.items()):
            log.info(
                "football-data: %s — brak kompletnego zamknięcia w %d meczach",
                bookmaker,
                count,
            )
        for season, count in sorted(self.pinnacle_missing_by_season.items()):
            if count:
                log.warning(
                    "football-data: sezon %s bez Pinnacle w %d meczach", season, count
                )


@dataclass(frozen=True)
class ParseResult:
    """Wynik parsowania. ``matches`` i ``closing_odds`` są celowo rozłączne."""

    #: Jeden wiersz na mecz, kolumny dokładnie jak pola ``schema.Match``
    #: (bez ``stats``/``extra``). Zwalidowane przez Pydantic.
    matches: pd.DataFrame
    #: Kursy zamknięcia 1X2: ``match_id, bookmaker, odds_home, odds_draw,
    #: odds_away, kickoff_utc, ingested_at, source``. Tylko kompletne rynki.
    #: WYŁĄCZNIE do CLV — patrz docstring modułu.
    closing_odds: pd.DataFrame
    report: ParseReport


def _normalise_season(raw: str) -> str:
    """'2012/2013' → '2012/13'. Przez ``lockbox.parse_season`` — jedyne miejsce.

    Nieczytelna etykieta to błąd, nie przepuszczony surowy tekst: lockbox
    porównuje sezony po parsowaniu (FSA #0 F-01).
    """
    return parse_season(raw)


def _to_kickoff_utc(date: pd.Series, time: pd.Series) -> pd.Series:
    """Czas lokalny brytyjski → UTC. Dwuznaczne i nieistniejące godziny → NaT."""
    naive = pd.to_datetime(date + " " + time, format=_DATE_FORMAT)
    localized = naive.dt.tz_localize(_TZ_SOURCE, ambiguous="NaT", nonexistent="NaT")
    return localized.dt.tz_convert("UTC")


def _validate_results(frame: pd.DataFrame) -> None:
    """``Res`` musi zgadzać się z ``HG``/``AG``. Rozjazd to uszkodzony wiersz."""
    with_result = frame["home_goals"].notna() & frame["away_goals"].notna()
    diff = (
        frame.loc[with_result, "home_goals"] - frame.loc[with_result, "away_goals"]
    ).astype(int)
    expected = diff.map(lambda d: _RESULT_BY_SIGN[int(np.sign(d))])
    actual = frame.loc[with_result, "Res"]
    bad = expected != actual
    if bad.any():
        sample = frame.loc[
            bad[bad].index[:5], ["Date", "Home", "Away", "HG", "AG", "Res"]
        ]
        raise ValueError(
            f"football-data: {int(bad.sum())} wierszy z Res niezgodnym z wynikiem; "
            f"pierwsze:\n{sample.to_string()}"
        )


def _resolve_teams(
    frame: pd.DataFrame, resolver: TeamResolver, report: ParseReport
) -> pd.DataFrame:
    """Mapuje nazwy na team_id. Nierozpoznane wiersze wypadają — i są liczone.

    Resolver jest wołany per WIERSZ, nie per unikalną nazwę, żeby jego
    ``coverage()`` i ``report_unresolved()`` liczyły mecze, a nie nazwy.
    Klub, który przegrał dwa sezony i zniknął, kosztuje 60 meczów, a nie
    jedną pozycję na liście — i tak ma być widziany.
    """

    def resolve(name: str) -> str | None:
        return resolver.resolve(SOURCE_NAME_OVERRIDES.get(name, name))

    home_id = frame["Home"].map(resolve)
    away_id = frame["Away"].map(resolve)
    ok = home_id.notna() & away_id.notna()

    report.unresolved_teams.update(frame.loc[home_id.isna(), "Home"].tolist())
    report.unresolved_teams.update(frame.loc[away_id.isna(), "Away"].tolist())
    report.rows_unresolved_team = int((~ok).sum())
    report.team_coverage = resolver.coverage()

    out = frame.loc[ok].copy()
    out["home_team_id"] = home_id[ok].astype(str)
    out["away_team_id"] = away_id[ok].astype(str)
    return out


def _build_closing_odds(
    frame: pd.DataFrame, report: ParseReport, *, ingested_at: datetime
) -> pd.DataFrame:
    """Tabela kursów zamknięcia w formacie długim po bukmacherze.

    Rynek niekompletny (brak choć jednego z H/D/A) jest pomijany — Shin
    wymaga kompletnego rynku (reguła 17), a 2 z 3 kursów nie ma sensownej
    interpretacji marży.
    """
    parts: list[pd.DataFrame] = []
    for bookmaker, prefix in CLOSING_BOOKMAKERS.items():
        cols = [f"{prefix}H", f"{prefix}D", f"{prefix}A"]
        if not all(c in frame.columns for c in cols):
            report.closing_incomplete[bookmaker] = len(frame)
            continue
        odds = frame[cols].apply(pd.to_numeric, errors="coerce")
        complete = odds.notna().all(axis=1) & (odds > 1.0).all(axis=1)
        report.closing_incomplete[bookmaker] = int((~complete).sum())
        if bookmaker == "pinnacle":
            report.pinnacle_missing_by_season.update(
                frame.loc[~complete, "season"].value_counts().to_dict()
            )
            for season in frame["season"].unique():
                report.pinnacle_missing_by_season.setdefault(season, 0)
        part = pd.DataFrame(
            {
                "match_id": frame.loc[complete, "match_id"],
                "bookmaker": bookmaker,
                "odds_home": odds.loc[complete, cols[0]].astype(float),
                "odds_draw": odds.loc[complete, cols[1]].astype(float),
                "odds_away": odds.loc[complete, cols[2]].astype(float),
                "kickoff_utc": frame.loc[complete, "kickoff_utc"],
            }
        )
        parts.append(part)

    columns = [
        "match_id",
        "bookmaker",
        "odds_home",
        "odds_draw",
        "odds_away",
        "kickoff_utc",
    ]
    closing = (
        pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=columns)
    )
    closing["ingested_at"] = pd.Timestamp(ingested_at)
    closing["source"] = SOURCE
    return closing.sort_values(
        ["kickoff_utc", "match_id", "bookmaker"], kind="mergesort"
    ).reset_index(drop=True)


def _validate_schema(matches: pd.DataFrame) -> None:
    """Przepuszcza każdy wiersz przez ``schema.Match`` — kontrakt, nie konwencja."""
    for row in matches.to_dict(orient="records"):
        Match.model_validate(
            {
                **row,
                "kickoff_utc": row["kickoff_utc"].to_pydatetime(),
                "ingested_at": row["ingested_at"].to_pydatetime(),
                "home_goals": None
                if pd.isna(row["home_goals"])
                else int(row["home_goals"]),
                "away_goals": None
                if pd.isna(row["away_goals"])
                else int(row["away_goals"]),
            }
        )


def parse_matches(
    raw: pd.DataFrame,
    resolver: TeamResolver,
    *,
    now: datetime,
    strict: bool = True,
) -> ParseResult:
    """Surowa ramka (kolumny tekstowe) → mecze + kursy zamknięcia + raport.

    Parameters
    ----------
    raw:
        Wynik :func:`read_raw_csv` albo :func:`load_raw_latest`.
    resolver:
        Resolver nazw. Nierozpoznana nazwa NIGDY nie jest zgadywana.
    strict:
        ``True`` (produkcja): jakakolwiek nierozpoznana drużyna podnosi
        ``KeyError`` — cicha strata meczów jest gorsza niż zatrzymanie.
        ``False`` (przegląd pokrycia): wiersze wypadają, a raport mówi które.
    now:
        Znacznik ``ingested_at``; domyślnie :func:`valuebet.schema.utcnow`.
    """
    if now.tzinfo is None:
        raise ValueError("now musi być timezone-aware (reguła 2)")
    ingested_at = now.astimezone(UTC)
    report = ParseReport(rows_in=len(raw))
    frame = raw.copy()

    # 1. Rozgrywki — nieznana para (kraj, liga) jest głośna.
    frame["competition"] = [
        COMPETITIONS.get((c, lg))
        for c, lg in zip(frame["Country"], frame["League"], strict=True)
    ]
    unknown = frame["competition"].isna()
    if unknown.any():
        pairs = (
            frame.loc[unknown, ["Country", "League"]]
            .drop_duplicates()
            .to_records(index=False)
        )
        raise ValueError(
            f"football-data: nieznane rozgrywki {list(map(tuple, pairs))}; "
            "dopisz do COMPETITIONS zamiast pomijać."
        )

    # 2. Godzina rozpoczęcia. Bez Time — odrzuć i policz (patrz docstring modułu).
    has_time = frame["Time"].notna() & (frame["Time"].str.strip() != "")
    report.rows_without_time = int((~has_time).sum())
    frame = frame.loc[has_time].copy()

    frame["kickoff_utc"] = _to_kickoff_utc(frame["Date"], frame["Time"])
    ambiguous = frame["kickoff_utc"].isna()
    report.rows_ambiguous_dst = int(ambiguous.sum())
    if ambiguous.any():
        log.warning(
            "football-data: %d meczów w dwuznacznej/nieistniejącej godzinie DST, "
            "odrzucone: %s",
            int(ambiguous.sum()),
            frame.loc[ambiguous, ["Date", "Time", "Home", "Away"]].to_dict(
                orient="records"
            ),
        )
    frame = frame.loc[~ambiguous].copy()

    # 3. Wynik.
    frame["home_goals"] = pd.to_numeric(frame["HG"], errors="coerce").astype("Int64")
    frame["away_goals"] = pd.to_numeric(frame["AG"], errors="coerce").astype("Int64")
    half_result = frame["home_goals"].isna() != frame["away_goals"].isna()
    if half_result.any():
        raise ValueError(
            f"football-data: {int(half_result.sum())} wierszy z połową wyniku (HG bez AG lub odwrotnie)"
        )
    _validate_results(frame)
    frame["status"] = [
        MatchStatus.FINISHED.value if has else MatchStatus.SCHEDULED.value
        for has in frame["home_goals"].notna()
    ]
    frame["season"] = frame["Season"].map(_normalise_season)

    # 4. Drużyny — słownik, nie fuzzy.
    frame = _resolve_teams(frame, resolver, report)
    if strict and report.unresolved_teams:
        names = ", ".join(
            f"{n!r} ({c})" for n, c in report.unresolved_teams.most_common()
        )
        raise KeyError(
            f"football-data: nierozpoznane drużyny: {names}. Dopisz aliasy do "
            "data/team_aliases.yaml (albo SOURCE_NAME_OVERRIDES dla skrótów "
            "niejednoznacznych globalnie) — nie obchodź tego fuzzy-matchem."
        )

    # 5. Identyfikatory i kontrola duplikatów.
    frame["match_id"] = [
        make_match_id(comp, ko.to_pydatetime(), h, a)
        for comp, ko, h, a in zip(
            frame["competition"],
            frame["kickoff_utc"],
            frame["home_team_id"],
            frame["away_team_id"],
            strict=True,
        )
    ]
    dupes = frame["match_id"].duplicated(keep=False)
    if dupes.any():
        raise ValueError(
            f"football-data: {int(dupes.sum())} wierszy z powtórzonym match_id:\n"
            f"{frame.loc[dupes, ['Date', 'Time', 'Home', 'Away']].to_string()}"
        )

    # 6. Kursy zamknięcia — osobna tabela, nigdy w ramce meczów.
    closing = _build_closing_odds(frame, report, ingested_at=ingested_at)

    matches = pd.DataFrame(
        {
            "match_id": frame["match_id"].astype(str),
            "sport": Sport.FOOTBALL.value,
            "competition": frame["competition"].astype(str),
            "season": frame["season"].astype(str),
            "kickoff_utc": frame["kickoff_utc"],
            "home_team_id": frame["home_team_id"],
            "away_team_id": frame["away_team_id"],
            "status": frame["status"],
            "home_goals": frame["home_goals"],
            "away_goals": frame["away_goals"],
            "ingested_at": pd.Timestamp(ingested_at),
            "source": SOURCE,
        }
    )
    matches = matches.sort_values(
        ["kickoff_utc", "match_id"], kind="mergesort"
    ).reset_index(drop=True)
    _validate_schema(matches)

    report.rows_out = len(matches)
    return ParseResult(matches=matches, closing_odds=closing, report=report)


# ---------------------------------------------------------------------------
# Zapis pochodny
# ---------------------------------------------------------------------------


def write_interim(result: ParseResult, root: Path) -> tuple[Path, Path]:
    """Zapisuje mecze i kursy zamknięcia do ``data/interim/football_data/``.

    Warstwa pochodna — nadpisanie jest dozwolone, bo całość da się
    odtworzyć z ``data/raw``.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    matches_path = root / "matches.parquet"
    closing_path = root / "closing_odds.parquet"
    result.matches.to_parquet(matches_path, index=False)
    result.closing_odds.to_parquet(closing_path, index=False)
    log.info(
        "football-data: zapisano %d meczów i %d wierszy kursów zamknięcia do %s",
        len(result.matches),
        len(result.closing_odds),
        root,
    )
    return matches_path, closing_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """``python -m valuebet.ingest.football_data [--no-download] [--allow-unresolved]``"""
    parser = argparse.ArgumentParser(description="Ingest football-data.co.uk (POL.csv)")
    parser.add_argument("--url", default=FOOTBALL_DATA_URL)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/football_data"))
    parser.add_argument(
        "--interim-dir", type=Path, default=Path("data/interim/football_data")
    )
    parser.add_argument("--aliases", type=Path, default=Path("data/team_aliases.yaml"))
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="nie pobieraj, parsuj najnowszy plik z --raw-dir",
    )
    parser.add_argument(
        "--allow-unresolved",
        action="store_true",
        help="tryb przeglądu pokrycia: nierozpoznane drużyny wypadają zamiast zatrzymać przebieg",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    try:
        if args.no_download:
            raw = load_raw_latest(args.raw_dir)
        else:
            with HttpClient(clock=time.time, sleep=time.sleep) as http:
                content = download(http, args.url)
            raw = read_raw_csv(content)
            write_raw(
                raw,
                RawStore(root=args.raw_dir.parent),
                content=content,
                now=datetime.now(UTC),
                source_url=args.url,
                subdir=args.raw_dir.name,
            )

        resolver = TeamResolver(AliasStore.from_yaml(args.aliases))
        result = parse_matches(
            raw, resolver, strict=not args.allow_unresolved, now=datetime.now(UTC)
        )
        result.report.log_summary()
        for item in resolver.report_unresolved():
            log.warning(
                "nierozpoznana: %r (x%d) — sugestie do RĘCZNEGO zatwierdzenia: %s",
                item.raw,
                item.occurrences,
                item.suggestions,
            )
        write_interim(result, args.interim_dir)
    except Exception:
        log.exception("ingest football-data nieudany")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
