"""``scripts/ingest_football_data.py`` — raport kolumn z raw, bez sieci."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

from valuebet.ingest.football_data_main import RAW_SUBDIR
from valuebet.ingest.raw_store import RawStore

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def _script() -> ModuleType:
    path = ROOT / "scripts" / "ingest_football_data.py"
    spec = importlib.util.spec_from_file_location("ingest_football_data_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_report_lists_present_and_missing_files_and_notes_timezone_gap(tmp_path: Path) -> None:
    store = RawStore(root=tmp_path / "raw", manifest=tmp_path / "m.jsonl")
    csv = (
        b"Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,PSH,PSD,PSA,PSCH,PSCD,PSCA\n"
        b"E0,10/08/2019,15:00,A,B,1,0,2.0,3.4,3.9,2.1,3.3,3.8\n"
    )
    store.write_raw(RAW_SUBDIR, "E0-1920", ".csv", csv, now=NOW)
    notes = b"Betting odds for weekend games are collected Friday afternoons.\n"
    store.write_raw(RAW_SUBDIR, "notes", ".txt", notes, now=NOW)

    script = _script()
    report = script.build_report(store)
    assert [f"{r['league']}-{r['season']}" for r in report["files"]] == ["E0-1920"]
    assert len(report["missing"]) == 153
    assert report["notes"]["collection_rule"].startswith("Betting odds for weekend games")
    assert report["notes"]["timezone_lines"] == []

    report |= {"generated_by": "scripts/ingest_football_data.py", "generated_at": NOW.isoformat()}
    out = tmp_path / "COLUMNS.md"
    script.write_markdown(report, commit="abc1234", out=out)
    text = out.read_text(encoding="utf-8")
    assert "| E0-1920 | 1 | 1.000 | 1.000 | 1.000 | — |" in text
    assert "notes.txt jej nie podaje" in text
    assert "E0-1920 B365_pre: —" in text
    assert "## Brak pliku w raw" in text


def test_timezone_check_and_observed_at_exclusions(tmp_path: Path) -> None:
    store = RawStore(root=tmp_path / "raw", manifest=tmp_path / "m.jsonl")
    d1 = (
        b"Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG\n"
        # Bayern-Hertha: 20:30 CEST = 19:30 w Londynie -> OK
        b"D1,16/08/2019,19:30,Bayern Munich,Hertha,2,2\n"
        # sobota 14:30 -> zostaje przy obu regulach
        b"D1,17/08/2019,14:30,Dortmund,Augsburg,5,1\n"
        # piatek 17:00 -> wypada przy obu
        b"D1,23/08/2019,17:00,Schalke,Bayern Munich,0,3\n"
        # bez godziny -> zly Time
        b"D1,24/08/2019,,Koln,Dortmund,1,3\n"
    )
    store.write_raw(RAW_SUBDIR, "D1-1920", ".csv", d1, now=NOW)
    # Zly czas w pliku: Leipzig-Bayern zima, plik mowi 20:30 (czas lokalny, nie UK).
    d1_2223 = (
        b"Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG\n"
        b"D1,20/01/2023,20:30,RB Leipzig,Bayern Munich,1,1\n"
    )
    store.write_raw(RAW_SUBDIR, "D1-2223", ".csv", d1_2223, now=NOW)

    script = _script()
    checks = {c["file"] + c["date"]: c for c in script.timezone_check(store)}
    assert checks["D1-192016/08/2019"]["ok"] is True
    assert checks["D1-192016/08/2019"]["file_time"] == "19:30"
    assert checks["D1-222320/01/2023"]["ok"] is False
    assert checks["D1-222320/01/2023"]["why"] == "godzina niezgodna"
    # Brak pliku to nie zgodnosc.
    assert checks["D1-252622/08/2025"]["ok"] is False

    excl = {f"{e['league']}-{e['season']}": e for e in script.observed_at_exclusions(store)}
    row = excl["D1-1920"]
    assert row["n"] == 4
    assert row["bad_time"] == 1
    assert row["time_format_ok"] is False
    # Bayern-Hertha (piatek 19:30) wypada tylko przy 23:59; Schalke-Bayern (17:00) przy obu.
    assert row["friday_tuesday_1800_london"] == 1
    assert row["friday_tuesday_2359_london"] == 2

    report = script.build_report(store)
    report |= {"generated_by": "x", "generated_at": NOW.isoformat()}
    out = tmp_path / "COLUMNS.md"
    script.write_markdown(report, commit="abc1234", out=out)
    text = out.read_text(encoding="utf-8")
    assert "NIEZGODNOŚĆ — STOP" in text
    assert "| D1-1920 | 4 | 1 | 1 | 2 |" in text
