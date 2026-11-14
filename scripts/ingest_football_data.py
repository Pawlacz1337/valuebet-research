"""Filar 1, krok 2: football-data, 22 ligi x 7 sezonów, do raw + raport kolumn.

``BACKTEST_FIN_PLAN.md`` §1 i §7 krok 2. Każde zapytanie przez
``net/http.py`` (odstęp ≥ 10 s na host, robots.txt), zapis przez
``RawStore`` (manifest sum kontrolnych po każdym pliku). Ponowne
uruchomienie pomija pliki zweryfikowane sumą kontrolną — przerwany przebieg
wznawia się od pierwszego brakującego pliku.

Użycie::

    uv run python scripts/ingest_football_data.py               # pobierz brakujące + raport
    uv run python scripts/ingest_football_data.py --report-only # raport z raw, bez sieci

Kolektor (``valuebet-odds``) a ingest
-------------------------------------
Inne hosty (football-data vs The Odds API), więc odstęp per host jednego nie
spowalnia drugiego. Wspólna jest tylko blokada manifestu raw, trzymana przez
milisekundy na dopisanie wiersza. Ingest prawie nie zużywa procesora (czeka
10 s między plikami), więc nie jest ciężką fazą, przy której Avast włączał
tryb gry (to były pełne przebiegi ``pytest``). Ciężkiej fazy (pełny
``pytest``) nie uruchamiamy w oknach kotwic kolektora.

Raport: ``reports/ingest/<commit>/columns.json`` i ``COLUMNS.md``, etykieta
z ``frozen_commit()`` (odmowa przy brudnym drzewie).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from valuebet.ingest.football_data_main import (
    KICKOFF_TZ,
    NOTES_URL,
    RAW_SUBDIR,
    ObservedAtRule,
    column_report,
    fin_files,
    ingest_files,
    ingest_notes,
    kickoff_utc,
    pre_match_observed_at,
    read_csv_bytes,
)
from valuebet.ingest.raw_store import RawStore, sha256_file
from valuebet.net.http import HttpClient
from valuebet.provenance import frozen_commit, generated_by

SCRIPT = Path(__file__)
ROOT = SCRIPT.resolve().parents[1]
PROGRESS = Path("data/state/ingest/football_data_main.jsonl")
REPORTS = Path("reports/ingest")

#: Grupy w tabeli raportu — te, na których stoją strategie A-F (§3 planu).
TABLE_GROUPS: tuple[str, ...] = (
    "PS_pre", "PS_close", "B365_pre", "B365_close", "BW_pre", "BW_close",
    "WH_pre", "WH_close", "Max_pre", "Max_close", "Avg_pre",
    "P_ou_pre", "P_ou_close", "B365_ou_pre", "B365_ou_close",
)  # fmt: skip
#: Pokrycie poniżej progu → wiersz w sekcji „braki” raportu (bez decyzji).
COVERAGE_FLAG = 0.95

log = logging.getLogger("ingest_football_data")

#: Mecze o znanej godzinie gwizdka — test strefy kolumny ``Time`` (decyzja
#: Pawła 2026-10-08: lato, zima, najstarszy i najnowszy sezon ligi
#: kontynentalnej + Ekstraklasa). ``real_utc`` ze źródła w ``source``;
#: wynik i cytaty w ``docs/sources.md``. Reguła strefy obowiązuje tylko,
#: gdy zgadzają się wszystkie.
KNOWN_KICKOFFS: tuple[dict[str, str], ...] = (
    {
        "file": "D1-1920", "date": "16/08/2019", "home": "Bayern", "away": "Hertha",
        "real_local": "20:30 CEST", "real_utc": "2019-08-16T18:30:00+00:00",
        "case": "lato, najstarszy sezon",
        "source": "https://fcbayern.com/en/matches/profis/bundesliga/2019-2020/"
        "fc-bayern-muenchen-hertha-bsc-16-08-2019/statistics",
    },
    {
        "file": "D1-2223", "date": "20/01/2023", "home": "Leipzig", "away": "Bayern",
        "real_local": "20:30 CET", "real_utc": "2023-01-20T19:30:00+00:00",
        "case": "zima",
        "source": "https://www.bundesliga.com/de/bundesliga/news/"
        "tipico-blog-rb-leipzig-fc-bayern-munchen-topspiel-kracher-jahresstart-22190",
    },
    {
        "file": "D1-2526", "date": "22/08/2025", "home": "Bayern", "away": "Leipzig",
        "real_local": "20:30 CEST", "real_utc": "2025-08-22T18:30:00+00:00",
        "case": "najnowszy sezon",
        "source": "https://fcbayern.com/kidsclub/de/news/2025/08/"
        "vorbericht-1.-bundesliga-spieltag-fc-bayern---rb-leipzig",
    },
    {
        "file": "SP1-2425", "date": "26/10/2024", "home": "Real Madrid", "away": "Barcelona",
        "real_local": "21:00 CEST", "real_utc": "2024-10-26T19:00:00+00:00",
        "case": "druga liga kontynentalna",
        "source": "https://www.expreso.ec/deportes/"
        "real-madrid-vs-fc-barcelona-fecha-hora-ver-clasico-espana-218415.html",
    },
    {
        "file": "POL", "date": "26/10/2025", "home": "Legia", "away": "Lech",
        "real_local": "20:15 CET", "real_utc": "2025-10-26T19:15:00+00:00",
        "case": "Ekstraklasa, zima",
        "source": "https://www.meczyki.pl/newsy/pilka-nozna/"
        "legia-warszawa-lech-poznan-typy-i-kursy-na-mecz-26-10-2025/284292",
    },
    {
        "file": "POL", "date": "26/04/2026", "home": "Lech", "away": "Legia",
        "real_local": "17:30 CEST", "real_utc": "2026-04-26T15:30:00+00:00",
        "case": "Ekstraklasa, lato",
        "source": "https://www.fotmob.com/livescores/3346633",
    },
)  # fmt: skip
#: Ekstraklasa — plik „extra leagues” (``ingest/football_data.py``), już w raw.
POL_SUBDIR = "football_data"


def _frame(store: RawStore, file_label: str) -> pd.DataFrame | None:
    """Ramka pliku z raw: CSV głównej ligi albo parquet POL; kolumny Home/Away ujednolicone."""
    if file_label == "POL":
        path = store.latest(POL_SUBDIR, "POL", ".parquet")
        if path is None:
            return None
        return pd.read_parquet(path)
    path = store.latest(RAW_SUBDIR, file_label, ".csv")
    if path is None:
        return None
    frame = read_csv_bytes(path.read_bytes())
    return frame.rename(columns={"HomeTeam": "Home", "AwayTeam": "Away"})


def timezone_check(store: RawStore) -> list[dict[str, Any]]:
    """Godzina z pliku vs rzeczywisty gwizdek dla :data:`KNOWN_KICKOFFS`.

    ``ok`` tylko przy dokładnie jednym pasującym wierszu i zgodnej godzinie.
    """
    out: list[dict[str, Any]] = []
    for case in KNOWN_KICKOFFS:
        result: dict[str, Any] = dict(case)
        frame = _frame(store, case["file"])
        expected_local = (
            datetime.fromisoformat(case["real_utc"]).astimezone(KICKOFF_TZ).strftime("%H:%M")
        )
        result["expected_file_time"] = expected_local
        if frame is None or "Time" not in frame.columns:
            result |= {"file_time": None, "ok": False, "why": "brak pliku albo kolumny Time"}
            out.append(result)
            continue
        dates = pd.to_datetime(frame["Date"], format="mixed", dayfirst=True, errors="coerce")
        target = pd.to_datetime(case["date"], format="%d/%m/%Y")
        rows = frame[
            (dates == target)
            & frame["Home"].astype(str).str.contains(case["home"], regex=False)
            & frame["Away"].astype(str).str.contains(case["away"], regex=False)
        ]
        if len(rows) != 1:
            result |= {"file_time": None, "ok": False, "why": f"pasujących wierszy: {len(rows)}"}
        else:
            row = rows.iloc[0]
            file_time = str(row["Time"]).strip()
            result |= {
                "file_time": file_time,
                "file_teams": f"{row['Home']} - {row['Away']}",
                "ok": file_time == expected_local,
                "why": "" if file_time == expected_local else "godzina niezgodna",
            }
        out.append(result)
    return out


_TIME_FORMAT = r"^\d{2}:\d{2}$"


def observed_at_exclusions(store: RawStore) -> list[dict[str, Any]]:
    """Per liga i sezon: mecze, brak/zły format ``Time``, wyłączone przez obie reguły.

    Decyzja Pawła 2026-10-08 (a): liczba wyłączonych per liga i sezon, nie
    tylko łącznie; (d): oba warianty obok siebie, bez uśredniania.
    """
    rows: list[dict[str, Any]] = []
    for file in fin_files():
        frame = _frame(store, file.label)
        if frame is None:
            continue
        frame = frame.dropna(how="all")
        entry: dict[str, Any] = {"league": file.league, "season": file.season, "n": len(frame)}
        if "Time" not in frame.columns:
            entry |= {"bad_time": len(frame), "time_format_ok": False}
            entry |= {rule.value: None for rule in ObservedAtRule}
            rows.append(entry)
            continue
        times = frame["Time"].astype(str).str.strip()
        good = times.str.match(_TIME_FORMAT)
        entry |= {"bad_time": int((~good).sum()), "time_format_ok": bool(good.all())}
        kickoffs = [
            kickoff_utc(str(d), t)
            for d, t, ok in zip(frame["Date"], times, good, strict=True)
            if ok
        ]
        for rule in ObservedAtRule:
            entry[rule.value] = sum(pre_match_observed_at(k, rule=rule) is None for k in kickoffs)
        rows.append(entry)
    return rows


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def build_report(store: RawStore) -> dict[str, Any]:
    """Raport kolumn z plików w raw (bez sieci)."""
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for file in fin_files():
        path = store.latest(RAW_SUBDIR, file.label, ".csv")
        if path is None:
            missing.append(file.label)
            continue
        entry = column_report(path.read_bytes(), file=file)
        entry["raw_path"] = path.relative_to(store.root).as_posix()
        entry["sha256"] = sha256_file(path)
        rows.append(entry)
    notes = store.latest(RAW_SUBDIR, "notes", ".txt")
    notes_info: dict[str, Any] | None = None
    if notes is not None:
        text = notes.read_bytes().decode("utf-8", errors="replace")
        rule = next((ln.strip() for ln in text.splitlines() if "Betting odds for" in ln), None)
        timezone_lines = [
            ln.strip()
            for ln in text.splitlines()
            if any(w in ln.lower() for w in ("time zone", "timezone", "gmt", "uk time", "bst"))
        ]
        notes_info = {
            "url": NOTES_URL,
            "raw_path": notes.relative_to(store.root).as_posix(),
            "sha256": sha256_file(notes),
            "collection_rule": rule,
            "timezone_lines": timezone_lines,
        }
    return {
        "files": rows,
        "missing": missing,
        "notes": notes_info,
        "timezone_check": timezone_check(store),
        "observed_at_exclusions": observed_at_exclusions(store),
    }


def write_markdown(report: dict[str, Any], *, commit: str, out: Path) -> None:
    lines = [
        f"# Raport kolumn football-data — commit `{commit}`",
        "",
        f"Wygenerowane przez `{report['generated_by']}` o {report['generated_at']}.",
        f"Pliki w raw: {len(report['files'])} z {len(report['files']) + len(report['missing'])}.",
        "",
        "Pokrycie = odsetek wierszy z kompletem kolumn grupy, każdy kurs > 1.0;"
        " `—` = grupy nie ma w nagłówku.",
        "",
    ]
    notes = report["notes"]
    if notes:
        lines += [
            "## notes.txt",
            "",
            f"- raw: `{notes['raw_path']}` (sha256 `{notes['sha256']}`)",
            f"- reguła zbierania kursów sprzed meczu, dosłownie: „{notes['collection_rule']}”",
            "- strefa czasowa kolumny `Time`: "
            + (
                "; ".join(f"„{t}”" for t in notes["timezone_lines"])
                if notes["timezone_lines"]
                else "**notes.txt jej nie podaje**"
            ),
            "",
        ]
    lines += [
        "## Tabela",
        "",
        "| plik | wiersze | Time | " + " | ".join(TABLE_GROUPS) + " |",
        "|---|---|---|" + "---|" * len(TABLE_GROUPS),
    ]
    flags: list[str] = []
    for row in report["files"]:
        groups = row["groups"]
        label = f"{row['league']}-{row['season']}"
        cells = [_fmt(groups[g]) for g in TABLE_GROUPS]
        lines.append(f"| {label} | {row['n_rows']} | {_fmt(row['time_coverage'])} | {' | '.join(cells)} |")
        for g in TABLE_GROUPS:
            value = groups[g]
            if value is None or value < COVERAGE_FLAG:
                flags.append(f"{label} {g}: {_fmt(value)}")
    lines += ["", f"## Pokrycie < {COVERAGE_FLAG} albo brak grupy ({len(flags)})", ""]
    lines += [f"- {f}" for f in flags] or ["- brak"]
    if report["missing"]:
        lines += ["", "## Brak pliku w raw", ""] + [f"- {m}" for m in report["missing"]]
    checks = report.get("timezone_check", [])
    if checks:
        verdict = "ZGODNE WSZYSTKIE" if all(c["ok"] for c in checks) else "NIEZGODNOŚĆ — STOP"
        lines += [
            "",
            f"## Strefa kolumny `Time` — test na meczach o znanej godzinie: **{verdict}**",
            "",
            f"Hipoteza: `{KICKOFF_TZ.key}`. Godzina oczekiwana = rzeczywisty gwizdek (UTC)"
            " przeliczony na tę strefę.",
            "",
            "| przypadek | plik | mecz w pliku | data | godzina w pliku | oczekiwana"
            " | rzeczywista | wynik | źródło |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for c in checks:
            lines.append(
                f"| {c['case']} | {c['file']} | {c.get('file_teams', '—')} | {c['date']}"
                f" | {c['file_time'] or '—'} | {c['expected_file_time']} | {c['real_local']}"
                f" | {'OK' if c['ok'] else 'NIE: ' + c['why']} | {c['source']} |"
            )
    excl = report.get("observed_at_exclusions", [])
    if excl:
        rules = [r.value for r in ObservedAtRule]
        lines += [
            "",
            "## Mecze wyłączone przez regułę `observed_at` (gwizdek ≤ observed_at)",
            "",
            "Obie reguły obok siebie, bez uśredniania (decyzja Pawła 2026-10-08)."
            " `zły Time` = brak albo format inny niż HH:MM.",
            "",
            "| plik | mecze | zły Time | " + " | ".join(rules) + " |",
            "|---|---|---|" + "---|" * len(rules),
        ]
        for e in excl:
            cells = ["—" if e[r] is None else str(e[r]) for r in rules]
            lines.append(
                f"| {e['league']}-{e['season']} | {e['n']} | {e['bad_time']} | "
                + " | ".join(cells)
                + " |"
            )
        totals = [sum(e[r] or 0 for e in excl) for r in rules]
        lines.append(
            f"| **razem** | {sum(e['n'] for e in excl)} | {sum(e['bad_time'] for e in excl)} | "
            + " | ".join(str(t) for t in totals)
            + " |"
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest football-data (Filar 1, krok 2)")
    parser.add_argument("--report-only", action="store_true", help="raport z raw, bez sieci")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # Etykieta = fakt (FSA #0 F-24): odmowa przy brudnym drzewie, zanim cokolwiek pobierzemy.
    commit = frozen_commit(script=SCRIPT, root=ROOT)
    store = RawStore()
    problems = store.verify()
    if problems:
        for problem in problems:
            log.error("raw: %s", problem)
        return 1

    if not args.report_only:
        def now() -> datetime:
            return datetime.now(UTC)

        with HttpClient(clock=time.time, sleep=time.sleep) as client:
            ingest_notes(client=client, store=store, progress=PROGRESS, now=now)
            outcomes = ingest_files(
                fin_files(), client=client, store=store, progress=PROGRESS, now=now
            )
        counts: dict[str, int] = {}
        for outcome in outcomes:
            counts[outcome.status] = counts.get(outcome.status, 0) + 1
        print(json.dumps({"ingest": counts}, ensure_ascii=False), flush=True)
        if store.verify():
            log.error("raw niezgodne z manifestem po ingeście")
            return 1

    report = build_report(store)
    report["commit"] = commit
    report["generated_by"] = generated_by(script=SCRIPT, root=ROOT)
    report["generated_at"] = datetime.now(UTC).isoformat()
    out_dir = REPORTS / commit
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "columns.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    write_markdown(report, commit=commit, out=out_dir / "COLUMNS.md")
    print(
        json.dumps(
            {"report": (out_dir / "COLUMNS.md").as_posix(), "missing": report["missing"]},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
