"""Testy walk-forward baseline'u Elo — w tym test trucizny.

Syntetyczna liga: ukryte siły drużyn, wyniki losowane z ordered logit,
kursy zamknięcia z prawdziwych prawdopodobieństw przez ``shin_forward``.
Dzięki temu wiemy, że „rynek" jest tu idealnie skalibrowany, a każde
pobicie go przez Elo byłoby dowodem przecieku.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from valuebet.backtest.elo_baseline import (
    BaselineReport,
    format_report,
    main,
    run_elo_baseline,
)
from valuebet.features.elo import EloConfig
from valuebet.pricing.shin import shin_forward

T0 = datetime(2015, 8, 1, 16, 0, tzinfo=UTC)
TEAMS = ["A", "B", "C", "D", "E", "F"]


def _league(n_seasons: int, *, seed: int = 0) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    strength = dict(zip(TEAMS, rng.normal(0.0, 0.6, size=len(TEAMS)), strict=True))
    rows: list[dict[str, object]] = []
    odds_rows: list[dict[str, object]] = []
    for s in range(n_seasons):
        season = f"{2015 + s}/{(16 + s) % 100:02d}"
        base = T0 + timedelta(days=365 * s)
        k = 0
        for _round in range(2):
            for i, home in enumerate(TEAMS):
                for j, away in enumerate(TEAMS):
                    if i == j:
                        continue
                    latent = strength[home] - strength[away] + 0.3
                    p_away = 1 / (1 + np.exp(-(-0.45 - latent)))
                    p_home = 1 - 1 / (1 + np.exp(-(0.45 - latent)))
                    p_draw = 1 - p_home - p_away
                    probs = np.array([p_home, p_draw, p_away])
                    outcome = rng.choice(3, p=probs)
                    hg, ag = {0: (2, 0), 1: (1, 1), 2: (0, 2)}[int(outcome)]
                    kickoff = base + timedelta(days=k)
                    match_id = f"{season}-{k:03d}"
                    rows.append(
                        {
                            "match_id": match_id,
                            "season": season,
                            "kickoff_utc": kickoff,
                            "home_team_id": home,
                            "away_team_id": away,
                            "home_goals": hg,
                            "away_goals": ag,
                        }
                    )
                    odds = shin_forward(probs, z=0.02)
                    for bookmaker in ("pinnacle", "betfair_exchange"):
                        odds_rows.append(
                            {
                                "match_id": match_id,
                                "bookmaker": bookmaker,
                                "odds_home": odds[0],
                                "odds_draw": odds[1],
                                "odds_away": odds[2],
                            }
                        )
                    k += 1
    matches = pd.DataFrame(rows)
    matches["kickoff_utc"] = pd.to_datetime(matches["kickoff_utc"], utc=True)
    return matches, pd.DataFrame(odds_rows)


@pytest.fixture(scope="module")
def league() -> tuple[pd.DataFrame, pd.DataFrame]:
    return _league(7)


@pytest.fixture(scope="module")
def report(league: tuple[pd.DataFrame, pd.DataFrame]) -> BaselineReport:
    matches, closing = league
    return run_elo_baseline(matches, closing, min_train_seasons=3, seed=0)


def test_walk_forward_covers_only_seasons_after_train(report: BaselineReport) -> None:
    seasons = [r.season for r in report.seasons]
    assert seasons == ["2018/19", "2019/20", "2020/21", "2021/22"]
    # train rośnie o jeden sezon (60 meczów) na krok
    assert [r.n_train for r in report.seasons] == [180, 240, 300, 360]
    assert all(r.n == 60 for r in report.seasons)
    assert report.n == 240


def test_ordinal_is_fit_strictly_on_past_seasons(report: BaselineReport) -> None:
    for r in report.seasons:
        assert r.ordinal.n_fit == r.n_train


def test_calibrated_market_is_not_beaten(report: BaselineReport) -> None:
    """Rynek jest tu z definicji prawdą. Elo nie może być lepsze poza szumem."""
    for gap in report.pooled_gaps:
        assert gap.n == 240
        assert gap.diff.ci_high > 0.0  # przedział nie może leżeć całkiem po stronie Elo


def test_elo_beats_constant_on_synthetic_league(report: BaselineReport) -> None:
    assert report.pooled_log_loss_elo < report.pooled_log_loss_constant


def test_both_references_reported_separately(report: BaselineReport) -> None:
    assert {g.bookmaker for g in report.pooled_gaps} == {"pinnacle", "betfair_exchange"}
    for r in report.seasons:
        assert {g.bookmaker for g in r.gaps} == {"pinnacle", "betfair_exchange"}


def test_reliability_tables_present(report: BaselineReport) -> None:
    for table in (
        report.reliability_expected_score,
        report.reliability_home,
        report.reliability_draw,
        report.reliability_away,
    ):
        assert table["n"].sum() == report.n


def test_sanity_block(report: BaselineReport) -> None:
    s = report.sanity
    assert s.n_teams == 6
    assert s.n_matches_without_result == 0
    assert s.max_abs_step > 0
    assert len(s.top) == 6


def test_future_poison_elo_baseline(league: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """Absurdalny sezon w przyszłości nie może zmienić ŻADNEJ wcześniejszej predykcji.

    Sprawdza obie ścieżki naraz: Elo (rating sprzed meczu) i ordered logit
    (dopasowanie tylko na sezonach < S).
    """
    matches, closing = league
    baseline = run_elo_baseline(matches, closing, min_train_seasons=3)

    poison = pd.DataFrame(
        {
            "match_id": ["POISON-1", "POISON-2"],
            "season": ["2099/00", "2099/00"],
            "kickoff_utc": pd.to_datetime(
                [T0 + timedelta(days=365 * 80)] * 2, utc=True
            ),
            "home_team_id": ["A", "B"],
            "away_team_id": ["B", "A"],
            "home_goals": [99, 0],
            "away_goals": [0, 99],
        }
    )
    poisoned = run_elo_baseline(
        pd.concat([matches, poison], ignore_index=True), closing, min_train_seasons=3
    )

    before = baseline.predictions.set_index("match_id")
    after = poisoned.predictions.set_index("match_id").loc[before.index]
    pd.testing.assert_frame_equal(before, after)
    assert [r.season for r in poisoned.seasons][:-1] == [
        r.season for r in baseline.seasons
    ]


def test_matches_without_result_are_skipped_not_scored(
    league: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    matches, closing = league
    future = matches.tail(3).copy()
    future["match_id"] = ["F1", "F2", "F3"]
    future["home_goals"] = pd.array([None, None, None], dtype="Int64")
    future["away_goals"] = pd.array([None, None, None], dtype="Int64")
    future["kickoff_utc"] = future["kickoff_utc"] + pd.Timedelta(days=400)
    future["season"] = "2022/23"
    combined = pd.concat([matches, future], ignore_index=True)
    combined["home_goals"] = combined["home_goals"].astype("Int64")
    combined["away_goals"] = combined["away_goals"].astype("Int64")
    report = run_elo_baseline(combined, closing, min_train_seasons=3)
    assert report.sanity.n_matches_without_result == 3
    assert "F1" not in set(report.predictions["match_id"])


def test_duplicate_match_id_is_loud(league: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    matches, closing = league
    with pytest.raises(ValueError, match="powtórzone match_id"):
        run_elo_baseline(pd.concat([matches, matches.head(1)]), closing)


def test_too_few_seasons_is_loud() -> None:
    matches, closing = _league(3)
    with pytest.raises(ValueError, match="za mało sezonów"):
        run_elo_baseline(matches, closing, min_train_seasons=3)


def test_missing_reference_is_tolerated(
    league: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    matches, closing = league
    report = run_elo_baseline(
        matches, closing[closing["bookmaker"] == "pinnacle"], min_train_seasons=3
    )
    assert {g.bookmaker for g in report.pooled_gaps} == {"pinnacle"}


def test_format_report_mentions_n_and_ci(report: BaselineReport) -> None:
    text = format_report(report)
    assert "n=240" in text
    assert "luka=" in text and "[" in text
    assert "RELIABILITY" in text
    assert "accuracy" not in text.lower()


def test_main_runs_on_parquet(
    tmp_path: Path,
    league: tuple[pd.DataFrame, pd.DataFrame],
    capsys: pytest.CaptureFixture[str],
) -> None:
    matches, closing = league
    m, c = tmp_path / "m.parquet", tmp_path / "c.parquet"
    matches.to_parquet(m, index=False)
    closing.to_parquet(c, index=False)
    assert (
        main(["--matches", str(m), "--closing", str(c), "--min-train-seasons", "3"])
        == 0
    )
    assert "POOLED" in capsys.readouterr().out


def test_config_is_passed_through(league: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    matches, closing = league
    report = run_elo_baseline(
        matches, closing, config=EloConfig(k=10.0), min_train_seasons=3
    )
    assert report.config.k == 10.0


# ---------------------------------------------------------------------------
# Po audycie kroku 3: CI klastrowe i porównywalność referencji.
# ---------------------------------------------------------------------------


def test_pooled_gaps_use_clustered_ci(report: BaselineReport) -> None:
    """Liczba raportowana na zewnątrz nie może mieć CI iid (reguła 11)."""
    n_test_seasons = len(report.seasons)
    for gap in report.pooled_gaps:
        assert gap.diff.is_clustered
        assert gap.diff.n_groups == n_test_seasons


def test_season_gaps_use_iid_ci(report: BaselineReport) -> None:
    """Jeden sezon to jeden klaster — nie ma po czym klastrować."""
    for season in report.seasons:
        for gap in season.gaps:
            assert not gap.diff.is_clustered


def test_gap_carries_its_season_range(report: BaselineReport) -> None:
    """Bez ``seasons`` nie widać, że dwie luki stoją na różnych okresach."""
    test_seasons = {s.season for s in report.seasons}
    for gap in report.pooled_gaps:
        assert set(gap.seasons) <= test_seasons
        assert gap.seasons == tuple(sorted(gap.seasons))


def test_reference_overlap_compares_on_identical_matches(
    report: BaselineReport,
) -> None:
    assert report.reference_overlaps, "dwie referencje — musi być porównanie"
    for overlap in report.reference_overlaps:
        assert overlap.gap_a.n == overlap.n
        assert overlap.gap_b.n == overlap.n
        assert overlap.market_diff.n == overlap.n
        assert overlap.bookmaker_a != overlap.bookmaker_b


def test_reference_overlap_detects_equally_good_references(
    report: BaselineReport,
) -> None:
    """Obie referencje to ten sam ``shin_forward`` z tych samych p.

    Różnica log lossów musi być nieodróżnialna od zera — inaczej sekcja
    nie wykryłaby przypadku, dla którego powstała.
    """
    for overlap in report.reference_overlaps:
        assert not overlap.market_diff.excludes_zero


def test_single_reference_gives_no_overlap_section(
    league: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    matches, closing = league
    rep = run_elo_baseline(matches, closing, references=("pinnacle",))
    assert rep.reference_overlaps == ()


def test_report_labels_ci_kind_and_flags_few_clusters(
    report: BaselineReport,
) -> None:
    """Raport ma mówić, jakie CI pokazuje. Cztery sezony to za mało."""
    text = format_report(report)
    assert "CI klastrowe" in text
    assert "NIEWIARYGODNE" in text  # 4 sezony testowe < _MIN_GROUPS
    assert "CI iid, optymistyczne" in text
    assert "REFERENCJE NA WSPÓLNYM PODZBIORZE" in text
