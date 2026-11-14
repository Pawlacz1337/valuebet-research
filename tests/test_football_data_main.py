"""Testy parsera głównych lig i solvera sumy goli z totali (§11.10 A)."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest

from valuebet.backtest.market_benchmark import (
    implied_total_from_over,
    over_probability,
)
from valuebet.ingest.football_data_main import (
    MAIN_LEAGUE_COLUMNS,
    parse_main_league,
    season_url,
)

HEADER = (
    "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,"
    "PSCH,PSCD,PSCA,PC>2.5,PC<2.5,Nieistotna\n"
)
ROW = "E0,17/08/2024,15:00,Arsenal,Chelsea,2,1,H,1.95,3.60,4.20,1.90,1.95,xyz\n"

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


def _csv(*rows: str, header: str = HEADER) -> str:
    return header + "".join(rows)


def test_parses_canonical_columns() -> None:
    out = parse_main_league(
        _csv(ROW), league="E0", season_code="2425", source_url="http://x/E0.csv", now=NOW
    )
    assert len(out) == 1
    row = out.iloc[0]
    assert row.home_team == "Arsenal"
    assert row.away_team == "Chelsea"
    assert row.home_goals == 2
    assert row.odds_home == 1.95
    assert row.odds_over25 == 1.90
    assert row.season == "2024/25"
    # Reguła 14.
    assert row.source == "http://x/E0.csv"
    assert row.ingested_at.tzinfo is not None


def test_missing_closing_totals_column_is_a_loud_error() -> None:
    """Cichy NaN w połowie analizy jest gorszy niż błąd na wejściu."""
    header = HEADER.replace("PC>2.5,PC<2.5,", "")
    row = ROW.replace("1.90,1.95,", "")
    with pytest.raises(ValueError, match=r"brak kolumn.*PC>2\.5"):
        parse_main_league(
            _csv(row, header=header),
            league="E0",
            season_code="2425",
            source_url="http://x", now=NOW,
        )


def test_rows_without_odds_are_dropped_and_counted() -> None:
    """Nic nie ginie po cichu — odrzucone są policzone."""
    incomplete = "E0,18/08/2024,15:00,Spurs,Everton,1,1,D,,,,,,\n"
    out = parse_main_league(
        _csv(ROW, incomplete),
        league="E0",
        season_code="2425",
        source_url="http://x", now=NOW,
    )
    assert len(out) == 1
    assert out.attrs["n_raw"] == 2
    assert out.attrs["n_dropped_incomplete"] == 1


def test_nonsense_odds_are_rejected() -> None:
    """Kurs <= 1.0 to nie kurs."""
    bad = "E0,18/08/2024,15:00,Spurs,Everton,1,1,D,1.00,3.60,4.20,1.90,1.95,x\n"
    out = parse_main_league(
        _csv(ROW, bad), league="E0", season_code="2425", source_url="http://x", now=NOW
    )
    assert len(out) == 1
    assert out.attrs["n_dropped_bad_odds"] == 1


def test_match_id_is_deterministic_and_date_based() -> None:
    """Ta sama konwencja co w ingest/football_data.py (CONTEXT §5.17)."""
    first = parse_main_league(
        _csv(ROW), league="E0", season_code="2425", source_url="http://x", now=NOW
    )
    # Inna godzina, ta sama data — to ten sam mecz.
    same_day = ROW.replace("15:00", "17:30")
    second = parse_main_league(
        _csv(same_day), league="E0", season_code="2425", source_url="http://y", now=NOW
    )
    assert first.iloc[0].match_id == second.iloc[0].match_id


def test_mixed_date_formats_in_one_file() -> None:
    """Football-data miesza %d/%m/%y i %d/%m/%Y w obrębie jednego pliku."""
    short_year = ROW.replace("17/08/2024", "18/08/24")
    out = parse_main_league(
        _csv(ROW, short_year), league="E0", season_code="2425", source_url="http://x", now=NOW
    )
    assert len(out) == 2
    assert out["date"].notna().all()


def test_season_code_is_validated() -> None:
    with pytest.raises(ValueError, match="4 cyfry"):
        parse_main_league(
            _csv(ROW), league="E0", season_code="24", source_url="http://x", now=NOW
        )


def test_season_url_shape() -> None:
    assert season_url("E0", "2425").endswith("/mmz4281/2425/E0.csv")


def test_canonical_column_map_covers_both_markets() -> None:
    assert MAIN_LEAGUE_COLUMNS["odds_home"] == "PSCH"
    assert MAIN_LEAGUE_COLUMNS["odds_over25"] == "PC>2.5"


# ---------------------------------------------------------------------------
# Solver sumy goli z rynku totali
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("total", [2.0, 2.6, 3.4, 4.2])
@pytest.mark.parametrize("ratio", [0.7, 1.0, 1.6, 2.4])
def test_total_from_over_round_trip(total: float, ratio: float) -> None:
    """Round-trip: ze znanego T policz q_over, potem odzyskaj T."""
    for rho in (0.0, -0.0702):
        lam = total * ratio / (1.0 + ratio)
        mu = total / (1.0 + ratio)
        q_over = over_probability(lam, mu, rho)
        assert implied_total_from_over(q_over, ratio, rho) == pytest.approx(
            total, abs=1e-6
        )


@pytest.mark.parametrize("bad", [0.0, 1.0, -0.2, 1.5])
def test_invalid_probability_gives_nan(bad: float) -> None:
    assert np.isnan(implied_total_from_over(bad, 1.3, 0.0))


def test_nonpositive_ratio_gives_nan() -> None:
    assert np.isnan(implied_total_from_over(0.5, 0.0, 0.0))
    assert np.isnan(implied_total_from_over(0.5, -1.0, 0.0))


def test_unbracketable_target_gives_nan_not_a_guess() -> None:
    """Poza zakresem zwracamy NaN — nigdy cichej liczby."""
    assert np.isnan(implied_total_from_over(1e-9, 1.0, 0.0))
    assert np.isnan(implied_total_from_over(1.0 - 1e-12, 1.0, 0.0))
