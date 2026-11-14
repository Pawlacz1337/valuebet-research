"""Testy walk-forward DC i bramki jakościowej.

Syntetyczna liga jak w ``test_elo_baseline``: znane ukryte siły drużyn,
gole losowane z zadanych parametrów DC. Dzięki temu wiadomo, jaki wynik
jest poprawny, a nie tylko jaki wyszedł.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from valuebet.backtest.dixon_coles_baseline import (
    DixonColesReport,
    build_xi_cache,
    quality_gate,
    run_dixon_coles_baseline,
    select_xi,
)
from valuebet.backtest.elo_baseline import run_elo_baseline
from valuebet.models.dixon_coles import (
    DixonColesParams,
    NumericalInstabilityError,
    PriorScales,
    score_matrix,
)
from valuebet.pricing.shin import shin_forward

T0 = datetime(2015, 8, 1, 16, 0, tzinfo=UTC)
TEAMS = ["A", "B", "C", "D", "E", "F"]


def _params() -> DixonColesParams:
    rng = np.random.default_rng(0)
    log_attack = rng.normal(0.0, 0.3, size=len(TEAMS))
    log_attack -= log_attack.mean()
    return DixonColesParams(
        attack=dict(zip(TEAMS, np.exp(log_attack).tolist(), strict=True)),
        defence=dict(
            zip(TEAMS, np.exp(rng.normal(0.0, 0.3, size=len(TEAMS))).tolist(), strict=True)
        ),
        home_advantage=1.35,
        rho=-0.07,
        xi=0.0,
        prior=PriorScales(None, None),
        n_fit=0,
        converged=True
    )


def _league(n_seasons: int = 6, *, seed: int = 0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Liga z prawdziwego DC + „rynek" z prawdziwych prawdopodobieństw."""
    params = _params()
    rng = np.random.default_rng(seed)
    matrices = {
        (h, a): score_matrix(params, h, a, max_goals=8).ravel()
        for h in TEAMS
        for a in TEAMS
        if h != a
    }
    side = 9
    rows: list[dict[str, object]] = []
    odds_rows: list[dict[str, object]] = []
    for s in range(n_seasons):
        season = f"{2015 + s}/{(16 + s) % 100:02d}"
        base = T0 + timedelta(days=365 * s)
        k = 0
        for _round in range(2):
            for home in TEAMS:
                for away in TEAMS:
                    if home == away:
                        continue
                    flat = matrices[home, away]
                    pick = int(rng.choice(len(flat), p=flat))
                    hg, ag = pick // side, pick % side
                    match_id = f"{season}-{k:03d}"
                    rows.append(
                        {
                            "match_id": match_id,
                            "season": season,
                            "kickoff_utc": base + timedelta(days=k),
                            "home_team_id": home,
                            "away_team_id": away,
                            "home_goals": float(hg),
                            "away_goals": float(ag),
                        }
                    )
                    matrix = flat.reshape(side, side)
                    grid = np.arange(side)
                    probs = np.array(
                        [
                            matrix[grid[:, None] > grid[None, :]].sum(),
                            float(np.trace(matrix)),
                            matrix[grid[:, None] < grid[None, :]].sum(),
                        ]
                    )
                    probs = probs / probs.sum()
                    for bookmaker in ("pinnacle", "betfair_exchange"):
                        odds = shin_forward(probs, z=0.02)
                        odds_rows.append(
                            {
                                "match_id": match_id,
                                "bookmaker": bookmaker,
                                "odds_home": float(odds[0]),
                                "odds_draw": float(odds[1]),
                                "odds_away": float(odds[2]),
                            }
                        )
                    k += 1
    return pd.DataFrame(rows), pd.DataFrame(odds_rows)


@pytest.fixture(scope="module")
def league() -> tuple[pd.DataFrame, pd.DataFrame]:
    return _league()


@pytest.fixture(scope="module")
def report(league: tuple[pd.DataFrame, pd.DataFrame]) -> DixonColesReport:
    matches, closing = league
    return run_dixon_coles_baseline(
        matches, closing, xi_grid=(0.0, 0.002)
    )


def test_same_split_as_elo(league: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """Bramka ma sens tylko wtedy, gdy oba modele stoją na tych samych meczach."""
    matches, closing = league
    dc = run_dixon_coles_baseline(
        matches, closing, xi_grid=(0.0,)
    )
    elo = run_elo_baseline(matches, closing)
    assert set(dc.predictions["match_id"]) == set(elo.predictions["match_id"])
    assert dc.n == elo.n


def test_gate_rejects_mismatched_splits(
    league: tuple[pd.DataFrame, pd.DataFrame]
    ) -> None:
    matches, closing = league
    dc = run_dixon_coles_baseline(
        matches, closing, min_train_seasons=3, xi_grid=(0.0,)
    )
    elo = run_elo_baseline(matches, closing, min_train_seasons=4)
    with pytest.raises(ValueError, match="różne zbiory"):
        quality_gate(dc, elo)


def test_probabilities_are_distributions(report: DixonColesReport) -> None:
    probs = report.predictions[["p_home", "p_draw", "p_away"]].to_numpy()
    assert np.allclose(probs.sum(axis=1), 1.0, atol=1e-9)
    assert (probs > 0.0).all()


def test_refits_once_per_match_day(report: DixonColesReport) -> None:
    """Świeżość parametrów jest warunkiem uczciwego porównania z Elo."""
    for season in report.seasons:
        assert season.n_fits > 1
        assert season.n_fits <= season.n


def test_future_poison_hyperparameter_selection(
    league: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Sezon testowy nie może brać udziału w wyborze xi (reguła 10).

    Wielosezonowe kryterium z §11.2 sumuje ``LL(V, xi)`` po sezonach
    walidacyjnych PRZED ``S``. Zatrucie ``S`` i wszystkiego po nim nie
    może ruszyć ani wpisów cache dla wcześniejszych ``V``, ani wyniku
    wyboru.
    """
    matches, _ = league
    frame = matches.copy()
    frame["outcome"] = np.where(
        frame["home_goals"] > frame["away_goals"],
        0,
        np.where(frame["home_goals"] == frame["away_goals"], 1, 2),
    )
    frame = frame.sort_values(["kickoff_utc", "match_id"]).reset_index(drop=True)
    seasons = sorted(frame["season"].unique())
    test_index = 4

    clean_cache = build_xi_cache(frame, seasons[:test_index], (0.0, 0.002), max_goals=8)
    clean_xi, clean_used = select_xi(clean_cache, seasons, test_index, (0.0, 0.002))

    poisoned = frame.copy()
    tainted = poisoned["season"].isin(seasons[test_index:])
    poisoned.loc[tainted, "home_goals"] = 99.0
    poisoned.loc[tainted, "away_goals"] = 0.0
    dirty_cache = build_xi_cache(
        poisoned, seasons[:test_index], (0.0, 0.002), max_goals=8
    )
    dirty_xi, dirty_used = select_xi(dirty_cache, seasons, test_index, (0.0, 0.002))

    assert clean_used == dirty_used
    assert clean_xi == dirty_xi
    assert clean_cache == dirty_cache


def test_xi_cache_entry_does_not_depend_on_test_season(
    league: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """LL(V, xi) liczone raz — to jest cała oszczędność z §11.2.

    Gdyby wpis zależał od sezonu testowego, cache byłby niepoprawny, a nie
    tylko wolniejszy.
    """
    matches, _ = league
    frame = matches.copy()
    frame["outcome"] = np.where(
        frame["home_goals"] > frame["away_goals"],
        0,
        np.where(frame["home_goals"] == frame["away_goals"], 1, 2),
    )
    frame = frame.sort_values(["kickoff_utc", "match_id"]).reset_index(drop=True)
    seasons = sorted(frame["season"].unique())

    short = build_xi_cache(frame, seasons[:4], (0.0,), max_goals=8)
    long = build_xi_cache(frame, seasons[:5], (0.0,), max_goals=8)
    for key, value in short.items():
        assert long[key] == pytest.approx(value)


def test_select_xi_uses_every_earlier_validation_season(
    league: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    matches, _ = league
    seasons = sorted(matches["season"].unique())
    cache = {(s, 0.0): -100.0 - i for i, s in enumerate(seasons)}
    cache.update({(s, 0.002): -200.0 for s in seasons})
    xi, used = select_xi(cache, seasons, 5, (0.0, 0.002))
    assert xi == 0.0
    assert used == seasons[2:5]


def test_future_poison_dixon_coles_walk_forward(
    league: tuple[pd.DataFrame, pd.DataFrame]
    ) -> None:
    """Test trucizny na całym walk-forward DC.

    Dopisanie absurdalnego meczu PO końcu zbioru nie może ruszyć żadnej
    wcześniejszej predykcji. Gdyby ruszyło, dopasowanie widziałoby
    przyszłość.
    """
    matches, closing = league
    baseline = run_dixon_coles_baseline(
        matches, closing, xi_grid=(0.0,)
    ).predictions

    last = matches["kickoff_utc"].max()
    poison = pd.DataFrame(
        [
            {
                "match_id": "POISON",
                "season": "2099/00",
                "kickoff_utc": last + timedelta(days=400),
                "home_team_id": "A",
                "away_team_id": "B",
                "home_goals": 99.0,
                "away_goals": 0.0,
            }
        ]
    )
    poisoned = pd.concat([matches, poison], ignore_index=True)
    after = run_dixon_coles_baseline(
        poisoned, closing, xi_grid=(0.0,)
    ).predictions
    after = after[after["match_id"] != "POISON"].reset_index(drop=True)
    pd.testing.assert_frame_equal(baseline, after)


def test_gate_result_requires_interval_not_just_sign(
    league: tuple[pd.DataFrame, pd.DataFrame]
    ) -> None:
    matches, closing = league
    dc = run_dixon_coles_baseline(
        matches, closing, xi_grid=(0.0,)
    )
    elo = run_elo_baseline(matches, closing)
    gate = quality_gate(dc, elo)
    assert gate.n == dc.n
    assert gate.diff.is_clustered
    if gate.passed:
        assert gate.diff.mean_diff < 0.0
        assert gate.diff.excludes_zero


def test_dc_beats_elo_when_data_really_comes_from_dc(
    league: tuple[pd.DataFrame, pd.DataFrame]
    ) -> None:
    """Kontrola samej bramki: na danych z DC model DC MUSI wygrać.

    Ten test jest odpowiednikiem ``test_future_poison_detects_a_real_leak``
    — bez niego nie wiadomo, czy bramka w ogóle potrafi kiedykolwiek
    przejść, czy zawsze zwraca „nie przeszła".
    """
    matches, closing = league
    dc = run_dixon_coles_baseline(
        matches, closing, xi_grid=(0.0,)
    )
    elo = run_elo_baseline(matches, closing)
    gate = quality_gate(dc, elo)
    assert gate.log_loss_dc < gate.log_loss_elo, (
        "gole pochodzą dokładnie z modelu DC, więc DC nie ma prawa przegrać; "
        "jeśli przegrywa, bramka albo implementacja jest zepsuta"
    )


def test_degenerate_xi_candidate_does_not_abort_the_run() -> None:
    """Kandydat z siatki a predykcja — dwie różne sytuacje (§11.9 pkt 5).

    Zdegenerowany ``xi`` w cache to informacja („niedopuszczalny dla
    każdego S > V"), nie awaria. Przebieg 2026-10-01 padł właśnie dlatego,
    że ten sam wyjątek przerywał budowę cache.
    """
    matches, _ = _league()
    frame = matches.copy()
    frame["outcome"] = np.where(
        frame["home_goals"] > frame["away_goals"],
        0,
        np.where(frame["home_goals"] == frame["away_goals"], 1, 2),
    )
    frame = frame.sort_values(["kickoff_utc", "match_id"]).reset_index(drop=True)
    seasons = sorted(frame["season"].unique())

    # 0.5/dzień wygasza wszystko poza ostatnim meczem — gwarantowana degeneracja.
    cache = build_xi_cache(frame, seasons[:4], (0.0, 0.5), max_goals=8)
    assert math.isinf(cache[seasons[2], 0.5]), "zdegenerowany kandydat ma dostać -inf"
    assert math.isfinite(cache[seasons[2], 0.0]), "zdrowy kandydat ma przeżyć"

    xi, _used = select_xi(cache, seasons, 4, (0.0, 0.5))
    assert xi == 0.0, "wybór nie może paść na odrzuconego kandydata"


def test_all_candidates_rejected_is_an_error_not_a_choice() -> None:
    matches, _ = _league()
    seasons = sorted(matches["season"].unique())
    cache = {(s, xi): -math.inf for s in seasons for xi in (0.0, 0.5)}
    with pytest.raises(NumericalInstabilityError, match="nie ma z czego"):
        select_xi(cache, seasons, 4, (0.0, 0.5))
