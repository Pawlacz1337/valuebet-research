"""Testy ingestu football-data.co.uk.

Sieć nie jest dotykana — pobranie idzie przez httpx.MockTransport, a
parsowanie dostaje CSV zbudowane w teście. Najważniejsze są testy czasu:
błąd o godzinę w kickoff_utc jest niewidoczny w danych, a przesuwa fakty
przez granicę odcięcia.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pandas as pd
import pytest

from helpers import fake_http
from valuebet.ingest.football_data import (
    SOURCE,
    SOURCE_NAME_OVERRIDES,
    ParseResult,
    download,
    load_raw_latest,
    main,
    parse_matches,
    read_raw_csv,
    write_interim,
    write_raw,
)
from valuebet.ingest.raw_store import RawStore
from valuebet.ingest.team_mapping import AliasStore, TeamResolver
from valuebet.net.http import HttpError
from valuebet.schema import Match, make_match_id

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)

HEADER = (
    "Country,League,Season,Date,Time,Home,Away,HG,AG,Res,"
    "PSCH,PSCD,PSCA,MaxCH,MaxCD,MaxCA,AvgCH,AvgCD,AvgCA,"
    "BFECH,BFECD,BFECA,B365CH,B365CD,B365CA"
)

#: Wiersz z kompletnym rynkiem u każdego bukmachera.
FULL_ODDS = "2.1,3.3,3.6,2.2,3.4,3.8,2.05,3.25,3.5,2.15,3.35,3.7,2.1,3.3,3.6"
#: Wiersz bez Pinnacle (jak sezon 2025/26 w prawdziwym pliku).
NO_PINNACLE = ",,,2.2,3.4,3.8,2.05,3.25,3.5,,,,,,"


def _row(
    date: str,
    time: str,
    home: str,
    away: str,
    hg: str = "1",
    ag: str = "0",
    res: str = "H",
    *,
    season: str = "2019/2020",
    odds: str = FULL_ODDS,
    league: str = "Ekstraklasa",
    country: str = "Poland",
) -> str:
    return f"{country},{league},{season},{date},{time},{home},{away},{hg},{ag},{res},{odds}"


def _csv(*rows: str, bom: bool = True) -> bytes:
    text = "\n".join([HEADER, *rows]) + "\n"
    if bom:
        text = "﻿" + text
    return text.encode("utf-8")


@pytest.fixture
def store() -> AliasStore:
    return AliasStore(
        {
            "lech-poznan": {
                "canonical_name": "Lech Poznań",
                "aliases": ["Lech Poznan"],
            },
            "legia-warszawa": {
                "canonical_name": "Legia Warszawa",
                "aliases": ["Legia"],
            },
            "wisla-krakow": {
                "canonical_name": "Wisła Kraków",
                "aliases": ["Wisla Krakow"],
            },
            "wisla-plock": {
                "canonical_name": "Wisła Płock",
                "aliases": ["Wisla Plock"],
            },
            "gornik-zabrze": {
                "canonical_name": "Górnik Zabrze",
                "aliases": ["Gornik Zabrze"],
            },
            "gornik-leczna": {"canonical_name": "Górnik Łęczna", "aliases": ["Leczna"]},
            "ruch-chorzow": {
                "canonical_name": "Ruch Chorzów",
                "aliases": ["Ruch Chorzow"],
            },
            "zaglebie-lubin": {
                "canonical_name": "Zagłębie Lubin",
                "aliases": ["Zaglebie Lubin"],
            },
            "zaglebie-sosnowiec": {
                "canonical_name": "Zagłębie Sosnowiec",
                "aliases": ["Zaglebie Sosnowiec"],
            },
        }
    )


@pytest.fixture
def resolver(store: AliasStore) -> TeamResolver:
    return TeamResolver(store)


def _parse(
    content: bytes, resolver: TeamResolver, *, strict: bool = True
) -> ParseResult:
    return parse_matches(read_raw_csv(content), resolver, strict=strict, now=NOW)


# ---------------------------------------------------------------------------
# Wczytanie surowe
# ---------------------------------------------------------------------------


def test_read_raw_csv_strips_bom_and_keeps_text() -> None:
    raw = read_raw_csv(_csv(_row("17/08/2019", "17:00", "Lech Poznan", "Legia")))
    assert raw.columns[0] == "Country"  # BOM nie wchodzi do nazwy kolumny
    assert raw["HG"].iloc[0] == "1"  # tekst, nie liczba
    assert raw["PSCH"].iloc[0] == "2.1"


def test_read_raw_csv_without_bom() -> None:
    raw = read_raw_csv(
        _csv(_row("17/08/2019", "17:00", "Lech Poznan", "Legia"), bom=False)
    )
    assert list(raw.columns[:3]) == ["Country", "League", "Season"]


def test_read_raw_csv_missing_required_column_is_loud() -> None:
    content = b"Country,League,Season,Date,Home,Away,HG,AG,Res\nPoland,Ekstraklasa,2019/2020,17/08/2019,A,B,1,0,H\n"
    with pytest.raises(ValueError, match=r"brak wymaganych kolumn.*Time"):
        read_raw_csv(content)


# ---------------------------------------------------------------------------
# Czas — najważniejsza część
# ---------------------------------------------------------------------------


def test_kickoff_in_british_summer_time_is_shifted_by_one_hour(
    resolver: TeamResolver,
) -> None:
    """17:00 BST (sierpień) to 16:00 UTC, nie 17:00 i nie 15:00."""
    result = _parse(_csv(_row("17/08/2019", "17:00", "Lech Poznan", "Legia")), resolver)
    assert result.matches["kickoff_utc"].iloc[0] == pd.Timestamp(
        "2019-08-17 16:00", tz="UTC"
    )


def test_kickoff_in_gmt_is_not_shifted(resolver: TeamResolver) -> None:
    """17:00 GMT (grudzień) to 17:00 UTC."""
    result = _parse(_csv(_row("14/12/2019", "17:00", "Lech Poznan", "Legia")), resolver)
    assert result.matches["kickoff_utc"].iloc[0] == pd.Timestamp(
        "2019-12-14 17:00", tz="UTC"
    )


def test_kickoff_dtype_is_tz_aware_utc(resolver: TeamResolver) -> None:
    result = _parse(_csv(_row("17/08/2019", "17:00", "Lech Poznan", "Legia")), resolver)
    dtype = result.matches["kickoff_utc"].dtype
    assert isinstance(dtype, pd.DatetimeTZDtype)
    assert str(dtype.tz) == "UTC"


def test_ambiguous_dst_hour_is_dropped_and_reported(
    resolver: TeamResolver, caplog: pytest.LogCaptureFixture
) -> None:
    """27/10/2019 01:30 w Londynie zdarza się dwa razy. Nie zgadujemy, które."""
    content = _csv(
        _row("27/10/2019", "01:30", "Lech Poznan", "Legia"),
        _row("27/10/2019", "17:00", "Wisla Krakow", "Wisla Plock"),
    )
    with caplog.at_level(logging.WARNING):
        result = _parse(content, resolver)
    assert result.report.rows_ambiguous_dst == 1
    assert result.report.rows_out == 1
    assert len(result.matches) == 1
    assert "DST" in caplog.text
    assert "Lech Poznan" in caplog.text


def test_nonexistent_dst_hour_is_dropped_and_reported(resolver: TeamResolver) -> None:
    """31/03/2019 01:30 w Londynie nie istnieje (skok 01:00 → 02:00)."""
    content = _csv(_row("31/03/2019", "01:30", "Lech Poznan", "Legia"))
    result = _parse(content, resolver)
    assert result.report.rows_ambiguous_dst == 1
    assert result.matches.empty


def test_row_without_time_is_dropped_and_counted(resolver: TeamResolver) -> None:
    content = _csv(
        _row("17/08/2019", "", "Lech Poznan", "Legia"),
        _row("18/08/2019", "17:00", "Wisla Krakow", "Wisla Plock"),
    )
    result = _parse(content, resolver)
    assert result.report.rows_without_time == 1
    assert result.report.rows_out == 1
    assert result.report.rows_dropped == 1


def test_malformed_date_is_loud(resolver: TeamResolver) -> None:
    content = _csv(_row("2019-08-17", "17:00", "Lech Poznan", "Legia"))
    with pytest.raises(ValueError):
        _parse(content, resolver)


# ---------------------------------------------------------------------------
# Drużyny
# ---------------------------------------------------------------------------


def test_source_overrides_expand_ambiguous_short_names(resolver: TeamResolver) -> None:
    content = _csv(
        _row("17/08/2019", "17:00", "Wisla", "Wisla Plock"),
        _row("18/08/2019", "17:00", "Ruch", "Zaglebie"),
        _row("19/08/2019", "17:00", "Gornik Z.", "Leczna"),
        _row("20/08/2019", "17:00", "Zaglebie Sosnowiec", "Legia"),
    )
    result = _parse(content, resolver)
    pairs = list(
        zip(result.matches["home_team_id"], result.matches["away_team_id"], strict=True)
    )
    assert pairs == [
        ("wisla-krakow", "wisla-plock"),
        ("ruch-chorzow", "zaglebie-lubin"),
        ("gornik-zabrze", "gornik-leczna"),
        ("zaglebie-sosnowiec", "legia-warszawa"),
    ]


def test_overrides_are_not_fuzzy() -> None:
    """Każdy override rozwija skrót do PEŁNEJ nazwy z miastem."""
    for short, full in SOURCE_NAME_OVERRIDES.items():
        assert len(full.split()) >= 2, (short, full)
        assert full != short


def test_unresolved_team_raises_in_strict_mode(resolver: TeamResolver) -> None:
    content = _csv(_row("17/08/2019", "17:00", "Lech Poznan", "Nieznany Klub"))
    with pytest.raises(KeyError, match="Nieznany Klub"):
        _parse(content, resolver)


def test_unresolved_team_is_dropped_and_counted_per_match(
    resolver: TeamResolver,
) -> None:
    """Nieznany klub kosztuje tyle meczów, ile zagrał — nie jedną pozycję."""
    content = _csv(
        _row("17/08/2019", "17:00", "Lech Poznan", "Nieznany Klub"),
        _row("24/08/2019", "17:00", "Nieznany Klub", "Legia"),
        _row("31/08/2019", "17:00", "Lech Poznan", "Legia"),
    )
    result = _parse(content, resolver, strict=False)
    assert result.report.rows_unresolved_team == 2
    assert result.report.unresolved_teams == {"Nieznany Klub": 2}
    assert result.report.rows_out == 1
    # 6 wystąpień nazw, 4 trafione
    assert result.report.team_coverage == pytest.approx(4 / 6)
    assert resolver.report_unresolved()[0].occurrences == 2


# ---------------------------------------------------------------------------
# Mecze
# ---------------------------------------------------------------------------


def test_match_id_uses_schema_helper(resolver: TeamResolver) -> None:
    result = _parse(_csv(_row("17/08/2019", "17:00", "Lech Poznan", "Legia")), resolver)
    expected = make_match_id(
        "ekstraklasa",
        datetime(2019, 8, 17, 16, 0, tzinfo=UTC),
        "lech-poznan",
        "legia-warszawa",
    )
    assert result.matches["match_id"].iloc[0] == expected


def test_season_is_normalised(resolver: TeamResolver) -> None:
    result = _parse(_csv(_row("17/08/2019", "17:00", "Lech Poznan", "Legia")), resolver)
    assert result.matches["season"].iloc[0] == "2019/20"


def test_output_rows_validate_as_match(resolver: TeamResolver) -> None:
    result = _parse(
        _csv(_row("17/08/2019", "17:00", "Lech Poznan", "Legia", "2", "2", "D")),
        resolver,
    )
    row = result.matches.iloc[0].to_dict()
    row["kickoff_utc"] = row["kickoff_utc"].to_pydatetime()
    row["ingested_at"] = row["ingested_at"].to_pydatetime()
    row["home_goals"] = int(row["home_goals"])
    row["away_goals"] = int(row["away_goals"])
    match = Match.model_validate(row)
    assert match.status == "finished"
    assert match.source == SOURCE
    assert match.ingested_at == NOW
    assert match.home_goals == 2


def test_matches_frame_has_no_odds_columns(resolver: TeamResolver) -> None:
    """Kurs zamknięcia nie może być obok cech — reguła 7 i 19."""
    result = _parse(_csv(_row("17/08/2019", "17:00", "Lech Poznan", "Legia")), resolver)
    assert not any(
        "odds" in c.lower() or c.startswith("PSC") for c in result.matches.columns
    )


def test_result_mismatch_is_loud(resolver: TeamResolver) -> None:
    content = _csv(_row("17/08/2019", "17:00", "Lech Poznan", "Legia", "0", "3", "H"))
    with pytest.raises(ValueError, match="Res niezgodnym"):
        _parse(content, resolver)


def test_unknown_competition_is_loud(resolver: TeamResolver) -> None:
    content = _csv(_row("17/08/2019", "17:00", "Lech Poznan", "Legia", league="I Liga"))
    with pytest.raises(ValueError, match="nieznane rozgrywki"):
        _parse(content, resolver)


def test_duplicate_match_is_loud(resolver: TeamResolver) -> None:
    content = _csv(
        _row("17/08/2019", "17:00", "Lech Poznan", "Legia"),
        _row("17/08/2019", "19:30", "Lech Poznan", "Legia"),
    )
    with pytest.raises(ValueError, match="powtórzonym match_id"):
        _parse(content, resolver)


def test_output_order_is_deterministic(resolver: TeamResolver) -> None:
    rows = [
        _row("17/08/2019", "19:30", "Lech Poznan", "Legia"),
        _row("17/08/2019", "17:00", "Wisla Krakow", "Wisla Plock"),
        _row("10/08/2019", "17:00", "Ruch Chorzow", "Zaglebie Lubin"),
    ]
    a = _parse(_csv(*rows), resolver).matches
    b = _parse(_csv(*reversed(rows)), resolver).matches
    pd.testing.assert_frame_equal(a, b)
    assert a["kickoff_utc"].is_monotonic_increasing


# ---------------------------------------------------------------------------
# Kursy zamknięcia
# ---------------------------------------------------------------------------


def test_closing_odds_are_separate_long_table(resolver: TeamResolver) -> None:
    result = _parse(_csv(_row("17/08/2019", "17:00", "Lech Poznan", "Legia")), resolver)
    closing = result.closing_odds
    assert set(closing["bookmaker"]) == {
        "pinnacle", "market_max", "market_avg", "betfair_exchange", "bet365"
    }  # fmt: skip
    pinnacle = closing[closing["bookmaker"] == "pinnacle"].iloc[0]
    assert (pinnacle["odds_home"], pinnacle["odds_draw"], pinnacle["odds_away"]) == (
        2.1,
        3.3,
        3.6,
    )
    assert pinnacle["match_id"] == result.matches["match_id"].iloc[0]
    assert closing["source"].eq(SOURCE).all()
    assert (closing["ingested_at"] == pd.Timestamp(NOW)).all()


def test_incomplete_closing_market_is_skipped_and_reported(
    resolver: TeamResolver,
) -> None:
    """2 z 3 kursów 1X2 to nie rynek — Shin wymaga kompletu (reguła 17)."""
    content = _csv(
        _row(
            "17/08/2019",
            "17:00",
            "Lech Poznan",
            "Legia",
            season="2025/2026",
            odds=NO_PINNACLE,
        ),
        _row("18/08/2019", "17:00", "Wisla Krakow", "Wisla Plock", season="2025/2026"),
    )
    result = _parse(content, resolver)
    closing = result.closing_odds
    assert (closing["bookmaker"] == "pinnacle").sum() == 1
    assert (closing["bookmaker"] == "market_avg").sum() == 2
    assert result.report.closing_incomplete["pinnacle"] == 1
    assert result.report.closing_incomplete["market_avg"] == 0
    assert result.report.pinnacle_missing_by_season == {"2025/26": 1}


def test_closing_odds_below_one_are_rejected(resolver: TeamResolver) -> None:
    odds = "0.9,3.3,3.6,2.2,3.4,3.8,2.05,3.25,3.5,,,,,,"
    result = _parse(
        _csv(_row("17/08/2019", "17:00", "Lech Poznan", "Legia", odds=odds)), resolver
    )
    assert "pinnacle" not in set(result.closing_odds["bookmaker"])
    assert result.report.closing_incomplete["pinnacle"] == 1


def test_missing_bookmaker_columns_are_tolerated(resolver: TeamResolver) -> None:
    """Starszy format bez Betfair/bet365 nie może wywalić parsera."""
    header = "Country,League,Season,Date,Time,Home,Away,HG,AG,Res,PSCH,PSCD,PSCA"
    content = (
        f"{header}\nPoland,Ekstraklasa,2019/2020,17/08/2019,17:00,Lech Poznan,Legia,1,0,H,2.1,3.3,3.6\n"
    ).encode()
    result = _parse(content, resolver)
    assert set(result.closing_odds["bookmaker"]) == {"pinnacle"}
    assert result.report.closing_incomplete["bet365"] == 1


# ---------------------------------------------------------------------------
# Zapis
# ---------------------------------------------------------------------------


def _store(root: Path) -> RawStore:
    return RawStore(root=root, manifest=root.parent / f"{root.name}-manifest.jsonl")


def test_write_raw_is_append_only_and_stamped(tmp_path: Path) -> None:
    content = _csv(_row("17/08/2019", "17:00", "Lech Poznan", "Legia"))
    raw = read_raw_csv(content)
    store = RawStore(root=tmp_path / "raw", manifest=tmp_path / "manifest.jsonl")
    first = write_raw(raw, store, content=content, now=NOW, subdir="")
    # FSA #0 F-12: ten sam zapis w tej samej chwili to wyjątek, nie druga
    # kopia z losowym sufiksem (zmiana specyfikacji, FSA0_NAPRAWY §3 F-12).
    with pytest.raises(FileExistsError):
        write_raw(raw, store, content=content, now=NOW, subdir="")
    second = write_raw(
        raw, store, content=content, now=NOW + timedelta(seconds=1), subdir=""
    )
    assert first != second
    assert first.exists() and second.exists()
    assert store.verify() == []

    stored = pd.read_parquet(first)
    assert stored["source"].iloc[0] == SOURCE
    assert stored["ingested_at"].iloc[0] == pd.Timestamp(NOW)
    assert stored["content_sha256"].iloc[0] == stored["content_sha256"].iloc[-1]
    assert stored["HG"].iloc[0] == "1"  # dalej tekst


def test_load_raw_latest_roundtrip(tmp_path: Path) -> None:
    content = _csv(_row("17/08/2019", "17:00", "Lech Poznan", "Legia"))
    raw = read_raw_csv(content)
    write_raw(raw, _store(tmp_path), content=content, now=NOW, subdir="")
    loaded = load_raw_latest(tmp_path)
    pd.testing.assert_frame_equal(loaded, raw, check_dtype=False)


def test_load_raw_latest_without_files_is_loud(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_raw_latest(tmp_path)


def test_write_interim_preserves_utc_dtype(
    tmp_path: Path, resolver: TeamResolver
) -> None:
    result = _parse(_csv(_row("17/08/2019", "17:00", "Lech Poznan", "Legia")), resolver)
    matches_path, closing_path = write_interim(result, tmp_path)
    matches = pd.read_parquet(matches_path)
    closing = pd.read_parquet(closing_path)
    assert str(matches["kickoff_utc"].dtype.tz) == "UTC"  # type: ignore[attr-defined]
    assert str(closing["kickoff_utc"].dtype.tz) == "UTC"  # type: ignore[attr-defined]
    assert matches["kickoff_utc"].iloc[0] == pd.Timestamp("2019-08-17 16:00", tz="UTC")


# ---------------------------------------------------------------------------
# Pobranie i CLI
# ---------------------------------------------------------------------------


def _transport(content: bytes, *, status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=content)

    return httpx.MockTransport(handler)


def _robots_ok(transport: httpx.MockTransport) -> object:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return transport.handle_request(request)

    return handler


def test_download_returns_bytes() -> None:
    content = _csv(_row("17/08/2019", "17:00", "Lech Poznan", "Legia"))
    http = fake_http(_robots_ok(_transport(content)))
    assert download(http, "https://example.invalid/POL.csv") == content


def test_download_http_error_is_loud() -> None:
    http = fake_http(_robots_ok(_transport(b"", status=500)))
    with pytest.raises(HttpError, match="500"):
        download(http, "https://example.invalid/POL.csv")


def test_main_no_download_uses_latest_raw(tmp_path: Path, store: AliasStore) -> None:
    content = _csv(_row("17/08/2019", "17:00", "Lech Poznan", "Legia"))
    raw_dir = tmp_path / "raw"
    write_raw(
        read_raw_csv(content), _store(raw_dir), content=content, now=NOW, subdir=""
    )
    aliases = tmp_path / "aliases.yaml"
    store.to_yaml(aliases)

    code = main(
        [
            "--no-download",
            "--raw-dir", str(raw_dir),
            "--interim-dir", str(tmp_path / "interim"),
            "--aliases", str(aliases),
        ]
    )  # fmt: skip
    assert code == 0
    assert (tmp_path / "interim" / "matches.parquet").exists()
    assert (tmp_path / "interim" / "closing_odds.parquet").exists()


def test_main_strict_fails_on_unresolved(tmp_path: Path, store: AliasStore) -> None:
    content = _csv(_row("17/08/2019", "17:00", "Lech Poznan", "Nieznany"))
    raw_dir = tmp_path / "raw"
    write_raw(
        read_raw_csv(content), _store(raw_dir), content=content, now=NOW, subdir=""
    )
    aliases = tmp_path / "aliases.yaml"
    store.to_yaml(aliases)
    args = [
        "--no-download",
        "--raw-dir",
        str(raw_dir),
        "--interim-dir",
        str(tmp_path / "i"),
        "--aliases",
        str(aliases),
    ]
    assert main(args) == 1
    assert main([*args, "--allow-unresolved"]) == 0


# ---------------------------------------------------------------------------
# Kontrakt z prawdziwym słownikiem aliasów
# ---------------------------------------------------------------------------

#: Wszystkie nazwy z prawdziwego POL.csv (stan 2026-09-21). Jeśli ktoś
#: usunie klub ze słownika, ten test to złapie — zanim zniknie 60 meczów.
REAL_SOURCE_NAMES = (
    "Arka Gdynia", "Cracovia", "GKS Belchatow", "GKS Katowice", "Gornik Z.",
    "Gornik Zabrze", "Jagiellonia", "Korona Kielce", "LKS Lodz", "Lech Poznan",
    "Lechia Gdansk", "Leczna", "Legia", "Legnica", "Motor Lublin", "Piast Gliwice",
    "Podbeskidzie", "Pogon Szczecin", "Polonia Warszawa", "Puszcza", "Radomiak Radom",
    "Rakow", "Ruch", "Ruch Chorzow", "Sandecja Nowy S.", "Slask Wroclaw", "Stal Mielec",
    "Termalica B-B.", "Warta Poznan", "Widzew Lodz", "Wieczysta Krakow", "Wisla",
    "Wisla Plock", "Zaglebie", "Zaglebie Sosnowiec", "Zawisza",
)  # fmt: skip

REAL_ALIASES = Path(__file__).resolve().parents[1] / "data" / "team_aliases.yaml"


@pytest.mark.skipif(not REAL_ALIASES.exists(), reason="brak data/team_aliases.yaml")
def test_real_aliases_cover_every_source_name() -> None:
    resolver = TeamResolver(AliasStore.from_yaml(REAL_ALIASES))
    unresolved = [
        name
        for name in REAL_SOURCE_NAMES
        if resolver.resolve(SOURCE_NAME_OVERRIDES.get(name, name)) is None
    ]
    assert unresolved == []
    assert resolver.coverage() == 1.0


@pytest.mark.skipif(not REAL_ALIASES.exists(), reason="brak data/team_aliases.yaml")
def test_real_aliases_keep_ambiguous_pairs_apart() -> None:
    """Pary, które fuzzy skleja, muszą dawać różne ID."""
    resolver = TeamResolver(AliasStore.from_yaml(REAL_ALIASES))
    assert resolver.resolve("Wisla Krakow") != resolver.resolve("Wisla Plock")
    assert resolver.resolve("Gornik Zabrze") != resolver.resolve("Leczna")
    assert resolver.resolve("Zaglebie Lubin") != resolver.resolve("Zaglebie Sosnowiec")
    assert resolver.resolve("Ruch Chorzow") != resolver.resolve("Ruch Radzionkow")
    # Same skróty NIE są w słowniku — rozwija je tylko football_data.
    assert resolver.resolve("Wisla") is None
    assert resolver.resolve("Ruch") is None
    assert resolver.resolve("Zaglebie") is None
