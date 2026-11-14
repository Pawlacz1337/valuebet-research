"""Testy Elo.

Najważniejsze: że emitowany rating jest SPRZED meczu, że wynik meczu N nie
wpływa na cechę meczu N, i że dołożenie meczu w przyszłość nie zmienia
niczego wstecz.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from valuebet.features.elo import EloConfig, compute_elo, expected_score

T0 = datetime(2026, 3, 1, 18, 0, tzinfo=UTC)


def _frame(rows: list[tuple[int, str, str, float | None, float | None]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "match_id": [f"m{i}" for i in range(len(rows))],
            "kickoff_utc": pd.to_datetime(
                [T0 + timedelta(days=d) for d, *_ in rows], utc=True
            ),
            "home_team_id": [h for _, h, *_ in rows],
            "away_team_id": [a for _, _, a, *_ in rows],
            "home_goals": [hg for *_, hg, _ in rows],
            "away_goals": [ag for *_, ag in rows],
        }
    )


def _simple() -> pd.DataFrame:
    return _frame(
        [
            (0, "A", "B", 2.0, 0.0),
            (7, "B", "A", 1.0, 1.0),
            (14, "A", "B", 0.0, 3.0),
        ]
    )


# ---------------------------------------------------------------------------
# Podstawy
# ---------------------------------------------------------------------------


def test_expected_score_symmetry() -> None:
    assert expected_score(1500, 1500) == pytest.approx(0.5)
    assert expected_score(1700, 1500) + expected_score(1500, 1700) == pytest.approx(1.0)


def test_expected_score_monotone() -> None:
    assert expected_score(1600, 1500) > expected_score(1500, 1500)


def test_first_match_uses_initial_rating() -> None:
    result = compute_elo(_simple())
    first = result.features.iloc[0]
    assert first["home_elo_before"] == pytest.approx(1500.0)
    assert first["away_elo_before"] == pytest.approx(1500.0)


def test_rating_is_zero_sum() -> None:
    result = compute_elo(_simple())
    assert sum(result.final.values()) == pytest.approx(3000.0)


def test_winner_gains_loser_loses() -> None:
    result = compute_elo(_frame([(0, "A", "B", 3.0, 0.0)]))
    assert result.rating("A") > 1500.0
    assert result.rating("B") < 1500.0


# ---------------------------------------------------------------------------
# Sedno: rating sprzed gwizdka
# ---------------------------------------------------------------------------


def test_emitted_rating_precedes_the_match() -> None:
    """Cecha meczu N musi odpowiadać stanowi PO meczu N-1, nie po N."""
    result = compute_elo(_simple())
    feats = result.features.set_index("match_id")

    # Po m0 (A wygrywa 2:0) rating A rośnie. Cecha m1 (B vs A) musi już to
    # widzieć, a cecha m0 — jeszcze nie.
    assert feats.loc["m0", "home_elo_before"] == pytest.approx(1500.0)
    assert feats.loc["m1", "away_elo_before"] > 1500.0


def test_current_match_result_does_not_affect_its_own_feature() -> None:
    """Zmiana wyniku meczu N nie może zmienić cechy meczu N."""
    base = compute_elo(_simple()).features.set_index("match_id")

    tampered = _simple()
    tampered.loc[tampered["match_id"] == "m2", ["home_goals", "away_goals"]] = [9.0, 0.0]
    after = compute_elo(tampered).features.set_index("match_id")

    assert base.loc["m2", "home_elo_before"] == pytest.approx(
        after.loc["m2", "home_elo_before"]
    )
    assert base.loc["m2", "away_elo_before"] == pytest.approx(
        after.loc["m2", "away_elo_before"]
    )


def test_future_poison_elo() -> None:
    """Mecz dołożony w przyszłość nie zmienia żadnej przeszłej cechy."""
    base = compute_elo(_simple()).features

    poisoned = pd.concat(
        [
            _simple(),
            pd.DataFrame(
                {
                    "match_id": ["POISON"],
                    "kickoff_utc": pd.to_datetime(
                        [T0 + timedelta(days=99)], utc=True
                    ),
                    "home_team_id": ["A"],
                    "away_team_id": ["B"],
                    "home_goals": [99.0],
                    "away_goals": [0.0],
                }
            ),
        ],
        ignore_index=True,
    )
    after = compute_elo(poisoned).features
    after = after[after["match_id"] != "POISON"].reset_index(drop=True)

    pd.testing.assert_frame_equal(base, after)


def test_input_order_does_not_matter() -> None:
    """Przetasowane wejście musi dać identyczny wynik — sortujemy wewnątrz."""
    base = compute_elo(_simple()).features.sort_values("match_id").reset_index(drop=True)
    shuffled = _simple().sample(frac=1.0, random_state=7)
    after = (
        compute_elo(shuffled).features.sort_values("match_id").reset_index(drop=True)
    )
    pd.testing.assert_frame_equal(base, after)


# ---------------------------------------------------------------------------
# Atut własnego boiska
# ---------------------------------------------------------------------------


def test_home_advantage_enters_elo_diff() -> None:
    cfg = EloConfig(home_advantage=100.0)
    result = compute_elo(_frame([(0, "A", "B", 1.0, 0.0)]), cfg)
    assert result.features.loc[0, "elo_diff"] == pytest.approx(100.0)
    assert result.features.loc[0, "elo_expected_home"] > 0.5


def test_zero_home_advantage_gives_even_expectation() -> None:
    cfg = EloConfig(home_advantage=0.0)
    result = compute_elo(_frame([(0, "A", "B", 1.0, 0.0)]), cfg)
    assert result.features.loc[0, "elo_expected_home"] == pytest.approx(0.5)


def test_draw_against_stronger_opponent_gains_rating() -> None:
    """Remis na wyjeździe z faworytem to dobry wynik i musi podnieść rating."""
    cfg = EloConfig(home_advantage=100.0)
    result = compute_elo(
        _frame([(0, "A", "B", 1.0, 1.0)]), cfg, initial_ratings={"A": 1700, "B": 1500}
    )
    assert result.rating("B") > 1500.0


# ---------------------------------------------------------------------------
# Skalowanie różnicą bramek
# ---------------------------------------------------------------------------


def test_bigger_win_moves_rating_more() -> None:
    cfg = EloConfig(goal_diff_scaling=True)
    narrow = compute_elo(_frame([(0, "A", "B", 1.0, 0.0)]), cfg).rating("A")
    wide = compute_elo(_frame([(0, "A", "B", 5.0, 0.0)]), cfg).rating("A")
    assert wide > narrow


def test_scaling_can_be_disabled() -> None:
    cfg = EloConfig(goal_diff_scaling=False)
    narrow = compute_elo(_frame([(0, "A", "B", 1.0, 0.0)]), cfg).rating("A")
    wide = compute_elo(_frame([(0, "A", "B", 5.0, 0.0)]), cfg).rating("A")
    assert wide == pytest.approx(narrow)


# ---------------------------------------------------------------------------
# Mecze bez wyniku
# ---------------------------------------------------------------------------


def test_unplayed_match_gets_feature_but_no_update() -> None:
    """Tą samą funkcją liczymy cechy dla przyszłej kolejki."""
    frame = _frame([(0, "A", "B", 2.0, 0.0), (7, "B", "A", None, None)])
    result = compute_elo(frame)

    assert result.features["home_elo_before"].notna().all()
    # Rating po m0 nie może zostać ruszony przez nierozegrany m1.
    only_played = compute_elo(_frame([(0, "A", "B", 2.0, 0.0)]))
    assert result.rating("A") == pytest.approx(only_played.rating("A"))


def test_works_without_result_columns_at_all() -> None:
    frame = _frame([(0, "A", "B", 1.0, 0.0)]).drop(columns=["home_goals", "away_goals"])
    result = compute_elo(frame)
    assert result.features.loc[0, "home_elo_before"] == pytest.approx(1500.0)
    assert result.final == {}


# ---------------------------------------------------------------------------
# Carry-over międzysezonowy
# ---------------------------------------------------------------------------


def _two_seasons() -> pd.DataFrame:
    frame = _frame(
        [
            (0, "A", "B", 5.0, 0.0),
            (7, "A", "B", 5.0, 0.0),
            (200, "A", "B", 1.0, 0.0),  # nowy sezon
        ]
    )
    frame["season"] = ["2025/26", "2025/26", "2026/27"]
    return frame


def test_season_carry_pulls_towards_mean() -> None:
    result = compute_elo(_two_seasons(), EloConfig(season_carry=0.5))
    feats = result.features.set_index("match_id")

    # Po dwóch wygranych 5:0 A ma wysoki rating. Pierwszy mecz nowego
    # sezonu musi już widzieć rating ściągnięty do średniej.
    end_of_season = compute_elo(_two_seasons().iloc[:2]).rating("A")
    expected = 1500.0 + 0.5 * (end_of_season - 1500.0)
    assert feats.loc["m2", "home_elo_before"] == pytest.approx(expected)


def test_full_carry_changes_nothing() -> None:
    with_carry = compute_elo(_two_seasons(), EloConfig(season_carry=1.0))
    without_season = compute_elo(_two_seasons().drop(columns=["season"]))
    pd.testing.assert_frame_equal(with_carry.features, without_season.features)


# ---------------------------------------------------------------------------
# Walidacja i wznawianie
# ---------------------------------------------------------------------------


def test_rejects_naive_kickoff() -> None:
    frame = _simple()
    frame["kickoff_utc"] = frame["kickoff_utc"].dt.tz_localize(None)
    with pytest.raises(ValueError, match="tz-aware"):
        compute_elo(frame)


def test_rejects_missing_columns() -> None:
    with pytest.raises(ValueError, match="brak kolumn"):
        compute_elo(_simple().drop(columns=["home_team_id"]))


def test_rejects_invalid_config() -> None:
    with pytest.raises(ValueError, match="season_carry"):
        EloConfig(season_carry=1.5)
    with pytest.raises(ValueError, match="k musi"):
        EloConfig(k=0.0)


def test_resume_from_previous_state_matches_full_run() -> None:
    """Dokładanie nowych meczów bez przeliczania całej historii."""
    full = compute_elo(_simple())

    first = compute_elo(_simple().iloc[:2])
    rest = compute_elo(_simple().iloc[2:], initial_ratings=first.final)

    assert rest.rating("A") == pytest.approx(full.rating("A"))
    assert rest.features.loc[0, "home_elo_before"] == pytest.approx(
        full.features.set_index("match_id").loc["m2", "home_elo_before"]
    )


def test_history_is_recorded() -> None:
    hist = compute_elo(_simple()).history()
    assert len(hist) == 6  # 3 mecze x 2 drużyny
    assert set(hist.columns) == {"kickoff_utc", "team_id", "rating_after"}
