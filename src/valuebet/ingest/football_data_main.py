"""Parser plików football-data.co.uk dla **głównych lig** (E0, D1, ...).

Osobny moduł od ``ingest/football_data.py``, który obsługuje „extra
leagues" (``POL.csv``). To nie jest duplikacja — to dwa różne formaty:

===============  ==========================  =============================
                 extra leagues (POL.csv)     główne ligi (E0.csv)
===============  ==========================  =============================
kolumn           30                          120
układ            jeden plik, wiele sezonów   jeden plik na sezon
data             ``Date`` + ``Time``         ``Date`` + ``Time``
drużyny          ``Home`` / ``Away``         ``HomeTeam`` / ``AwayTeam``
gole             ``HG`` / ``AG``             ``FTHG`` / ``FTAG``
kursy 1X2 zamk.  ``PSCH/PSCD/PSCA``          ``PSCH/PSCD/PSCA``
totale zamk.     **brak**                    ``PC>2.5`` / ``PC<2.5``
===============  ==========================  =============================

Po co nam ten format
--------------------
Brak kursów O/U w ``POL.csv`` uniemożliwia sprawdzenie, czy suma goli
wyprowadzona z samego 1X2 jest w ogóle dobrym instrumentem. Premier League
ma zamknięcie Pinnacle i dla 1X2, i dla totali, więc da się porównać
**dwa niezależne odczyty tej samej wielkości** (STEP4_ENSEMBLE §11.10 A).

To jest walidacja narzędzia pomiarowego, nie rozszerzanie zakresu gry.
Ekstraklasa i I liga pozostają jedynymi ligami, które wyceniamy.

Nazwy kolumn czytamy z nagłówka
--------------------------------
Nie z pozycji i nie z zaszytej listy. Football-data dokłada kolumny między
sezonami, a plik z 2019 ma ich mniej niż z 2024. Brakująca kolumna ma być
jawnym błędem przy wywołaniu, nie cichym ``NaN`` w połowie analizy.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

import pandas as pd

from valuebet.backtest.lockbox import parse_season
from valuebet.fsutil import file_lock
from valuebet.ingest.raw_store import RawStore, read_manifest, sha256_file
from valuebet.net.http import HttpClient

__all__ = [
    "FIN_LEAGUES",
    "FIN_SEASONS",
    "MAIN_LEAGUE_COLUMNS",
    "IngestOutcome",
    "MainLeagueFile",
    "ObservedAtRule",
    "RawIntegrityError",
    "column_report",
    "fin_files",
    "ingest_files",
    "ingest_notes",
    "kickoff_utc",
    "parse_main_league",
    "pre_match_observed_at",
    "read_csv_bytes",
    "season_url",
    "write_season_raw",
]

log = logging.getLogger(__name__)

BASE_URL = "https://www.football-data.co.uk/mmz4281"
#: Opis kolumn i reguła zbierania kursów sprzed meczu (BACKTEST_FIN_PLAN §1).
NOTES_URL = "https://www.football-data.co.uk/notes.txt"

#: Kolumny, bez których analiza nie ma sensu. Reszta pliku nas nie obchodzi.
MAIN_LEAGUE_COLUMNS: dict[str, str] = {
    "date": "Date",
    "home_team": "HomeTeam",
    "away_team": "AwayTeam",
    "home_goals": "FTHG",
    "away_goals": "FTAG",
    "odds_home": "PSCH",
    "odds_draw": "PSCD",
    "odds_away": "PSCA",
    "odds_over25": "PC>2.5",
    "odds_under25": "PC<2.5",
}


@dataclass(frozen=True)
class MainLeagueFile:
    """Jeden plik sezonu: kod ligi, kod sezonu, adres."""

    league: str
    season: str

    @property
    def url(self) -> str:
        return f"{BASE_URL}/{self.season}/{self.league}.csv"

    @property
    def label(self) -> str:
        return f"{self.league}-{self.season}"


#: Podkatalog plików głównych lig w ``data/raw``.
RAW_SUBDIR = "football_data_main"


def write_season_raw(
    store: RawStore, file: MainLeagueFile, content: bytes, *, now: datetime
) -> Path:
    """Surowy CSV sezonu do raw przez ``RawStore`` (reguła 12, FSA #0 F-12).

    Nazwa ``<liga>-<sezon>.<znacznik z mikrosekundami>.<hash>.csv`` — dwa
    pobrania w jednej sekundzie nie dostają już tego samego stempla (F-17).
    """
    return store.write_raw(
        RAW_SUBDIR, file.label, ".csv", content, now=now, recorded_by="football_data_main"
    )


def season_url(league: str, season: str) -> str:
    """``season`` w konwencji football-data: ``2425`` = sezon 2024/25."""
    return MainLeagueFile(league=league, season=season).url


def _season_label(season_code: str) -> str:
    """``2425`` -> ``2024/25``."""
    if len(season_code) != 4 or not season_code.isdigit():
        raise ValueError(f"kod sezonu ma mieć 4 cyfry, jest {season_code!r}")
    return parse_season(f"20{season_code[:2]}/{season_code[2:]}")


def _match_id(competition: str, date: pd.Timestamp, home: str, away: str) -> str:
    """Deterministyczne ID: liga | DATA (nie godzina) | gospodarz | gość.

    Ta sama konwencja co w ``ingest/football_data.py`` (CONTEXT.md §5.17).
    Data, nie pełny znacznik czasu — źródła korygują godziny o kilka minut,
    a jedna para drużyn gra najwyżej raz dziennie.
    """
    raw = f"{competition}|{date.date().isoformat()}|{home}|{away}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def parse_main_league(
    csv_text: str,
    *,
    league: str,
    season_code: str,
    source_url: str,
    now: datetime,
) -> pd.DataFrame:
    """Surowy CSV głównej ligi -> ramka z kolumnami kanonicznymi.

    Zwraca **wyłącznie** mecze z kompletem potrzebnych kursów i wynikiem.
    Liczbę odrzuconych i powód zapisuje w ``.attrs`` — nic nie ginie po
    cichu (COLLECTOR_PLAN §3.2, ta sama zasada).

    Raises
    ------
    ValueError
        Gdy w nagłówku brakuje którejkolwiek z ``MAIN_LEAGUE_COLUMNS``.
        Cichy ``NaN`` w połowie analizy jest gorszy niż błąd na wejściu.
    """
    frame = pd.read_csv(io.StringIO(csv_text), encoding_errors="replace")
    missing = [
        source
        for source in MAIN_LEAGUE_COLUMNS.values()
        if source not in frame.columns
    ]
    if missing:
        raise ValueError(
            f"{league}-{season_code}: brak kolumn {missing}. "
            f"Plik ma {len(frame.columns)} kolumn; nazwy czytamy z nagłówka, "
            "więc to znaczy, że ten sezon ich nie zawiera."
        )

    renamed = frame[list(MAIN_LEAGUE_COLUMNS.values())].rename(
        columns={v: k for k, v in MAIN_LEAGUE_COLUMNS.items()}
    )
    n_raw = len(renamed)

    # Football-data miesza %d/%m/%y i %d/%m/%Y w obrębie jednego pliku.
    parsed_date = pd.to_datetime(
        renamed["date"], format="mixed", dayfirst=True, errors="coerce"
    )
    renamed = renamed.assign(date=parsed_date)

    numeric = [
        "home_goals",
        "away_goals",
        "odds_home",
        "odds_draw",
        "odds_away",
        "odds_over25",
        "odds_under25",
    ]
    for column in numeric:
        renamed[column] = pd.to_numeric(renamed[column], errors="coerce")

    complete = renamed["date"].notna() & renamed[numeric].notna().all(axis=1)
    # Kurs <= 1.0 to nie kurs. Zero też nie.
    positive = (renamed[[c for c in numeric if c.startswith("odds")]] > 1.0).all(axis=1)
    keep = complete & positive
    out = renamed.loc[keep].copy()

    competition = f"{league}"
    out["competition"] = competition
    out["season"] = _season_label(season_code)
    out["match_id"] = [
        _match_id(competition, d, h, a)
        for d, h, a in zip(out["date"], out["home_team"], out["away_team"], strict=True)
    ]
    # Reguła 14: każdy zapisany zbiór ma ingested_at (UTC) i source.
    if now.tzinfo is None:
        raise ValueError("now musi być timezone-aware (reguła 2)")
    out["ingested_at"] = now.astimezone(UTC)
    out["source"] = source_url

    duplicated = int(out["match_id"].duplicated().sum())
    if duplicated:
        log.warning("%s: %d powtórzonych match_id", f"{league}-{season_code}", duplicated)
    out.attrs["n_raw"] = n_raw
    out.attrs["n_kept"] = len(out)
    out.attrs["n_dropped_incomplete"] = int((~complete).sum())
    out.attrs["n_dropped_bad_odds"] = int((complete & ~positive).sum())
    out.attrs["n_duplicated_ids"] = duplicated
    return out.reset_index(drop=True)


# -- ingest Filaru 1 (BACKTEST_FIN_PLAN §1, §7 krok 2) -----------------------

#: Ligi w formacie głównych lig — lista z ``BACKTEST_FIN_PLAN.md`` §1.
FIN_LEAGUES: tuple[str, ...] = (
    "E0", "E1", "E2", "E3", "EC",
    "SC0", "SC1", "SC2", "SC3",
    "D1", "D2", "I1", "I2", "SP1", "SP2", "F1", "F2",
    "N1", "B1", "P1", "T1", "G1",
)  # fmt: skip
#: Sezony 2019/20-2025/26 — od 2019/20 pliki mają kursy zamknięcia.
FIN_SEASONS: tuple[str, ...] = ("1920", "2021", "2122", "2223", "2324", "2425", "2526")


def fin_files() -> list[MainLeagueFile]:
    """22 ligi x 7 sezonów, liga po lidze (raport postępu czyta się po lidze)."""
    return [MainLeagueFile(league=lg, season=s) for lg in FIN_LEAGUES for s in FIN_SEASONS]


class RawIntegrityError(RuntimeError):
    """Plik w raw niezgodny z manifestem albo bez wpisu — nie pobieram od nowa.

    Jedyna sankcjonowana naprawa sieroty: ``scripts/verify_raw.py
    --adopt-orphan`` (``raw_store``). Zmieniony plik to incydent reguły 12.
    """


IngestStatus = Literal["fetched", "verified", "missing"]


@dataclass(frozen=True)
class IngestOutcome:
    file: MainLeagueFile
    status: IngestStatus
    path: Path | None
    sha256: str | None


_HTTP_OK = 200
_HTTP_NOT_FOUND = 404


def _verified_raw(store: RawStore, stem: str, suffix: str) -> tuple[Path, str] | None:
    """Plik sezonu już w raw i zgodny z manifestem — albo ``None``, gdy go nie ma.

    Zgodny = sha256 z dysku równy wpisowi w manifeście. Każda inna sytuacja
    (brak wpisu, inny hash) to :class:`RawIntegrityError`, nie powód do
    ponownego pobrania: raw jest niemodyfikowalne, a cichy drugi plik
    ukryłby incydent.
    """
    path = store.latest(RAW_SUBDIR, stem, suffix)
    if path is None:
        return None
    relative = path.relative_to(store.root).as_posix()
    known = {e.path: e.sha256 for e in read_manifest(store.manifest)}
    if relative not in known:
        raise RawIntegrityError(
            f"{relative}: plik w raw bez wpisu w manifeście — "
            "scripts/verify_raw.py --adopt-orphan albo wyjaśnienie, nie ponowne pobranie"
        )
    actual = sha256_file(path)
    if actual != known[relative]:
        raise RawIntegrityError(
            f"{relative}: hash niezgodny z manifestem "
            f"({known[relative][:12]}… vs {actual[:12]}…) — incydent reguły 12"
        )
    return path, actual


def _looks_like_csv(content: bytes) -> bool:
    """Nagłówek pliku głównej ligi: ``Div`` + ``HomeTeam`` + ``AwayTeam``.

    Serwer potrafi oddać 200 ze stroną HTML zamiast pliku; taka treść nie
    może trafić do niemodyfikowalnego raw.
    """
    first = content.removeprefix(b"\xef\xbb\xbf").split(b"\n", 1)[0]
    columns = {c.strip() for c in first.decode("latin-1").split(",")}
    return {"Div", "HomeTeam", "AwayTeam"} <= columns


def _log_progress(progress: Path, record: dict[str, Any]) -> None:
    progress.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
    with file_lock(progress), progress.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)


def ingest_files(
    files: Sequence[MainLeagueFile],
    *,
    client: HttpClient,
    store: RawStore,
    progress: Path,
    now: Callable[[], datetime],
) -> list[IngestOutcome]:
    """Pobiera brakujące pliki sezonów do raw; wznawialny po każdym pliku.

    - plik zweryfikowany sumą kontrolną → pomijany, bez zapytania;
    - pobranie wyłącznie przez ``client`` (odstęp per host, robots.txt —
      ``RobotsDisallowedError`` przerywa cały przebieg);
    - surowe bajty odpowiedzi do raw przez ``store`` — wpis w manifeście
      powstaje przy każdym pliku, więc przerwanie w połowie niczego nie gubi;
    - 404 → ``missing`` w dzienniku postępu, nic w raw;
    - inny status albo treść niebędąca CSV → ``RuntimeError`` (przebieg staje;
      następne uruchomienie zaczyna od tego pliku).

    ``progress`` to dziennik postępu (JSONL, jeden wiersz na plik). Prawdą o
    tym, co jest pobrane, pozostaje raw + manifest, nie ten dziennik.
    """
    outcomes: list[IngestOutcome] = []
    for file in files:
        found = _verified_raw(store, file.label, ".csv")
        record: dict[str, Any] = {"league": file.league, "season": file.season, "url": file.url}
        if found is not None:
            path, digest = found
            outcome = IngestOutcome(file, "verified", path, digest)
            record |= {"status": "verified", "http_status": None, "bytes": path.stat().st_size}
        else:
            response = client.get(file.url)
            if response.status_code == _HTTP_NOT_FOUND:
                outcome = IngestOutcome(file, "missing", None, None)
                record |= {"status": "missing", "http_status": _HTTP_NOT_FOUND, "bytes": None}
            elif response.status_code != _HTTP_OK:
                raise RuntimeError(f"{file.url}: HTTP {response.status_code} — przebieg przerwany")
            else:
                content = response.content
                if not _looks_like_csv(content):
                    raise RuntimeError(
                        f"{file.url}: odpowiedź 200 nie wygląda na CSV głównej ligi — "
                        "nie zapisuję do raw"
                    )
                path = store.write_raw(
                    RAW_SUBDIR,
                    file.label,
                    ".csv",
                    content,
                    now=now(),
                    recorded_by="ingest_football_data",
                )
                outcome = IngestOutcome(file, "fetched", path, sha256_file(path))
                record |= {"status": "fetched", "http_status": _HTTP_OK, "bytes": len(content)}
        relative = None if outcome.path is None else outcome.path.relative_to(store.root)
        record |= {
            "at": now().astimezone(UTC).isoformat(),
            "path": None if relative is None else relative.as_posix(),
            "sha256": outcome.sha256,
        }
        _log_progress(progress, record)
        log.info("%s: %s", file.label, outcome.status)
        outcomes.append(outcome)
    return outcomes


def ingest_notes(
    *, client: HttpClient, store: RawStore, progress: Path, now: Callable[[], datetime]
) -> tuple[IngestStatus, Path, str]:
    """``notes.txt`` do raw (źródło reguły ``observed_at``); wznawialne jak sezony.

    Plik już zweryfikowany sumą kontrolną nie jest pobierany drugi raz —
    reguła ma się opierać na tej samej wersji notatek, na której ją spisano.
    """
    found = _verified_raw(store, "notes", ".txt")
    status: IngestStatus
    if found is not None:
        path, digest = found
        status = "verified"
    else:
        response = client.get(NOTES_URL)
        if response.status_code != _HTTP_OK:
            raise RuntimeError(f"{NOTES_URL}: HTTP {response.status_code}")
        if b"Betting odds for weekend games" not in response.content:
            raise RuntimeError(f"{NOTES_URL}: brak zdania o momencie zbierania kursów")
        path = store.write_raw(
            RAW_SUBDIR, "notes", ".txt", response.content,
            now=now(), recorded_by="ingest_football_data",
        )  # fmt: skip
        digest = sha256_file(path)
        status = "fetched"
    _log_progress(
        progress,
        {
            "league": None,
            "season": None,
            "url": NOTES_URL,
            "status": status,
            "http_status": None if status == "verified" else _HTTP_OK,
            "bytes": path.stat().st_size,
            "at": now().astimezone(UTC).isoformat(),
            "path": path.relative_to(store.root).as_posix(),
            "sha256": digest,
        },
    )
    return status, path, digest


# -- czas: gwizdek i moment obserwacji kursów sprzed meczu -----------------

#: Strefa kolumny ``Time``. notes.txt jej NIE podaje — ustalona testem na
#: meczach o znanej godzinie (decyzja Pawła 2026-10-08; wyniki z cytatami w
#: ``docs/sources.md`` §football-data). Obowiązuje tylko przy zgodności
#: wszystkich przypadków testu.
KICKOFF_TZ = ZoneInfo("Europe/London")
#: Strefa, w której football-data zbiera kursy („Friday afternoons”).
COLLECTION_TZ = ZoneInfo("Europe/London")

_WEEKEND_FIRST_DAY = 4  # piątek
_TUESDAY = 1


class ObservedAtRule(StrEnum):
    """Kiedy, najpóźniej, zebrano kursy sprzed meczu (konserwatywnie).

    notes.txt: „Betting odds for weekend games are collected Friday
    afternoons, and on Tuesday afternoons for midweek games.” To **założenie**
    o praktyce serwisu, niezweryfikowane dla starszych sezonów
    (``docs/sources.md``). Wariant wybiera ``config/strategy.yaml``
    (``fd_observed_at_rule``) — jedno miejsce definicji.
    """

    #: Koniec „afternoon” = 18:00 London (decyzja Pawła 2026-10-08).
    AFTERNOON_1800 = "friday_tuesday_1800_london"
    #: Wariant wrażliwości: koniec dnia zbierania, 23:59 London.
    END_OF_DAY_2359 = "friday_tuesday_2359_london"

    @property
    def cutoff(self) -> time:
        return time(18, 0) if self is ObservedAtRule.AFTERNOON_1800 else time(23, 59)


def kickoff_utc(day: str, clock: str) -> datetime:
    """``Date`` (dd/mm/yy albo dd/mm/yyyy) + ``Time`` (HH:MM, :data:`KICKOFF_TZ`) → UTC.

    Brak godziny to błąd, nie północ: granicą odcięcia jest gwizdek, nie
    data (reguła 2).
    """
    parts = day.strip().split("/")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"data spoza formatu dd/mm/yy: {day!r}")
    d, m, y = (int(p) for p in parts)
    year = 2000 + y if len(parts[2]) == 2 else y
    hm = clock.strip().split(":")
    if len(hm) != 2 or not all(p.isdigit() for p in hm):
        raise ValueError(f"godzina spoza formatu HH:MM: {clock!r}")
    local = datetime(year, m, d, int(hm[0]), int(hm[1]), tzinfo=KICKOFF_TZ)
    return local.astimezone(UTC)


def _collection_day(local_day: date) -> date:
    """Pt-Pn → piątek tego weekendu; Wt-Czw → wtorek tego tygodnia."""
    weekday = local_day.weekday()
    if weekday >= _WEEKEND_FIRST_DAY:
        return local_day - timedelta(days=weekday - _WEEKEND_FIRST_DAY)
    if weekday == 0:
        return local_day - timedelta(days=3)
    return local_day - timedelta(days=weekday - _TUESDAY)


def pre_match_observed_at(kickoff: datetime, *, rule: ObservedAtRule) -> datetime | None:
    """Najpóźniejszy możliwy moment zebrania kursów sprzed meczu, w UTC.

    ``None`` — gwizdek nie jest późniejszy niż ten moment (np. piątek 17:00
    przy regule 18:00): kurs mógł zostać zebrany po gwizdku albo tuż przed
    nim, więc mecz wypada ze strategii przedmeczowych (z licznikiem w raporcie).
    """
    if kickoff.tzinfo is None:
        raise ValueError("kickoff musi być timezone-aware (reguła 2)")
    local_day = kickoff.astimezone(COLLECTION_TZ).date()
    observed = datetime.combine(_collection_day(local_day), rule.cutoff, tzinfo=COLLECTION_TZ)
    observed_utc = observed.astimezone(UTC)
    return observed_utc if observed_utc < kickoff else None


# -- raport kolumn -----------------------------------------------------------

#: Grupy kursów 1X2: prefiks bukmachera → (przed meczem, zamknięcie).
#: Zamknięcie = prefiks + "C" przed wynikiem (notes.txt: ``B365CH``).
_BOOKS_1X2: tuple[str, ...] = ("PS", "B365", "BW", "WH", "IW", "VC", "BF", "1XB", "Max", "Avg")
#: Totale 2.5: prefiks → ``<p>>2.5``/``<p><2.5`` i zamknięcie ``<p>C>2.5``.
#: Pinnacle w totalach to ``P``, nie ``PS`` (notes.txt).
_BOOKS_OU: tuple[str, ...] = ("P", "B365", "Max", "Avg")


def _group_columns() -> dict[str, tuple[str, ...]]:
    groups: dict[str, tuple[str, ...]] = {}
    for book in _BOOKS_1X2:
        groups[f"{book}_pre"] = tuple(f"{book}{o}" for o in "HDA")
        groups[f"{book}_close"] = tuple(f"{book}C{o}" for o in "HDA")
    for book in _BOOKS_OU:
        groups[f"{book}_ou_pre"] = (f"{book}>2.5", f"{book}<2.5")
        groups[f"{book}_ou_close"] = (f"{book}C>2.5", f"{book}C<2.5")
    return groups


def read_csv_bytes(content: bytes) -> pd.DataFrame:
    """CSV football-data: UTF-8 (z BOM albo bez), w starszych plikach latin-1."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    return pd.read_csv(io.StringIO(text), low_memory=False)


def column_report(content: bytes, *, file: MainLeagueFile) -> dict[str, Any]:
    """Obecność i pokrycie grup kursów w jednym pliku sezonu.

    Pokrycie grupy = odsetek wierszy z kompletem kolumn grupy, każda > 1.0
    (kurs ≤ 1.0 to nie kurs). ``None`` = grupy nie ma w nagłówku — to co
    innego niż 0.0 (kolumny są, wartości puste).
    """
    frame = read_csv_bytes(content).dropna(how="all")
    n_rows = len(frame)
    groups: dict[str, float | None] = {}
    for name, columns in _group_columns().items():
        if not set(columns) <= set(frame.columns):
            groups[name] = None
            continue
        values = frame[list(columns)].apply(pd.to_numeric, errors="coerce")
        ok = (values > 1.0).all(axis=1)
        groups[name] = float(ok.mean()) if n_rows else 0.0
    time_coverage: float | None = None
    if "Time" in frame.columns:
        time_coverage = float(frame["Time"].notna().mean()) if n_rows else 0.0
    return {
        "league": file.league,
        "season": file.season,
        "n_rows": n_rows,
        "n_columns": len(frame.columns),
        "columns": [str(c) for c in frame.columns],
        "groups": groups,
        "time_coverage": time_coverage,
    }
