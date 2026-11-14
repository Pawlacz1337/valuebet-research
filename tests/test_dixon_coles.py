"""Testy Dixona-Colesa. Najważniejszy jest ``test_recovers_known_parameters``.

Odpowiednik testu round-trip z ``test_shin.py``: generujemy mecze z
ZADANYCH parametrów i sprawdzamy, czy solver je odzyskuje. To dowodzi
poprawności matematycznej, a nie tylko tego, że liczby się sumują.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from numpy.typing import NDArray
from scipy.optimize import check_grad
from scipy.stats import poisson

from valuebet.models.dixon_coles import (
    MAX_GOALS_DEFAULT,
    MAX_STANDARD_ERROR,
    MIN_EFFECTIVE_FOR_FIT,
    MIN_EFFECTIVE_FOR_TAU,
    MIN_TAU_STRENGTH,
    RHO_BOUND,
    TRUNCATION_TOLERANCE,
    DixonColesParams,
    NumericalInstabilityError,
    PriorScales,
    _fisher_information,
    _marginal_likelihood_tau,
    _negative_loglik_and_grad,
    _prepare,
    _standard_errors,
    empirical_bayes_scales,
    fit_dixon_coles,
    log_likelihood,
    probabilities_1x2,
    score_matrix,
)

T0 = datetime(2018, 8, 1, 17, 0, tzinfo=UTC)


def _true_params(n_teams: int = 12, *, seed: int = 0) -> DixonColesParams:
    """Prawdziwe parametry, wycentrowane tak jak robi to solver."""
    rng = np.random.default_rng(seed)
    teams = [f"T{i:02d}" for i in range(n_teams)]
    log_attack = rng.normal(0.0, 0.25, size=n_teams)
    log_attack -= log_attack.mean()  # sum(log alpha) = 0, jak w ograniczeniu
    log_defence = rng.normal(0.0, 0.25, size=n_teams)
    return DixonColesParams(
        attack=dict(zip(teams, np.exp(log_attack).tolist(), strict=True)),
        defence=dict(zip(teams, np.exp(log_defence).tolist(), strict=True)),
        home_advantage=1.35,
        rho=-0.08,
        xi=0.0,
        prior=PriorScales(None, None),
        n_fit=0,
        converged=True
    )


def _simulate(
    params: DixonColesParams, n_matches: int, *, seed: int = 0
) -> pd.DataFrame:
    """Losuje wyniki z macierzy DC — czyli z dokładnie tego rozkładu, który fitujemy."""
    rng = np.random.default_rng(seed)
    teams = sorted(params.attack)
    # Macierz per para drużyn liczona raz; potem tylko losujemy z niej.
    cached: dict[tuple[str, str], np.ndarray] = {}
    rows: list[dict[str, object]] = []
    day = 0
    while len(rows) < n_matches:
        for home in teams:
            for away in teams:
                if home == away or len(rows) >= n_matches:
                    continue
                key = (home, away)
                if key not in cached:
                    cached[key] = score_matrix(params, home, away, max_goals=12).ravel()
                flat = cached[key]
                pick = rng.choice(len(flat), p=flat)
                side = int(np.sqrt(len(flat)))
                rows.append(
                    {
                        "kickoff_utc": T0 + timedelta(days=day),
                        "home_team_id": home,
                        "away_team_id": away,
                        "home_goals": int(pick // side),
                        "away_goals": int(pick % side),
                    }
                )
                day += 1
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def recovery() -> tuple[DixonColesParams, DixonColesParams]:
    true = _true_params()
    matches = _simulate(true, 5000)
    fitted = fit_dixon_coles(matches, xi=0.0, prior=PriorScales(None, None))
    return true, fitted


# ---------------------------------------------------------------------------
# Odzyskiwanie parametrów — test odniesienia modułu
# ---------------------------------------------------------------------------


def _rate_errors(
    true: DixonColesParams, fitted: DixonColesParams
) -> NDArray[np.float64]:
    teams = sorted(true.attack)
    return np.array(
        [
            abs(np.array(fitted.rates(h, a)) - np.array(true.rates(h, a))).max()
            for h in teams
            for a in teams
            if h != a
        ]
    )


def test_recovers_known_parameters(
    recovery: tuple[DixonColesParams, DixonColesParams]
    ) -> None:
    """Tolerancje są skalibrowane do n=5000, nie wzięte z sufitu.

    12 drużyn na 5000 meczów to ~833 mecze na drużynę. Statystyka
    ``max`` po 12 drużynach to wartość ekstremalna, więc tolerancja musi
    być luźniejsza niż typowy błąd. Dowodem poprawności estymatora jest
    ``test_recovery_error_shrinks_with_sample_size``, nie ta tolerancja.
    """
    true, fitted = recovery
    assert fitted.n_fit == 5000
    assert fitted.converged

    for team in true.attack:
        assert fitted.attack[team] == pytest.approx(true.attack[team], abs=0.12)
        assert fitted.defence[team] == pytest.approx(true.defence[team], abs=0.12)
    assert fitted.home_advantage == pytest.approx(true.home_advantage, abs=0.06)
    assert fitted.rho == pytest.approx(true.rho, abs=0.04)


def test_recovers_expected_goals(
    recovery: tuple[DixonColesParams, DixonColesParams]
    ) -> None:
    """``lambda`` i ``mu`` są tym, co naprawdę musi się zgadzać.

    Pojedyncze ``alpha`` może być przesunięte, dopóki iloczyny są dobre —
    i to właśnie iloczyny wchodzą do wyceny.
    """
    true, fitted = recovery
    errors = _rate_errors(true, fitted)
    assert float(errors.mean()) < 0.06
    assert float(errors.max()) < 0.30


def test_recovery_error_shrinks_with_sample_size() -> None:
    """Zgodność estymatora — mocniejszy dowód niż jakakolwiek tolerancja.

    Błąd obciążony NIE maleje z próbą. Jeśli ten test przechodzi, a
    tolerancje wyżej są luźne, to kwestia szumu, nie implementacji.
    """
    true = _true_params()
    small = _rate_errors(true, fit_dixon_coles(_simulate(true, 2000), xi=0.0, prior=PriorScales(None, None)))
    large = _rate_errors(true, fit_dixon_coles(_simulate(true, 20000), xi=0.0, prior=PriorScales(None, None)))
    assert float(large.mean()) < 0.5 * float(small.mean())


# ---------------------------------------------------------------------------
# Identyfikowalność (STEP4_PLAN §1.2)
# ---------------------------------------------------------------------------


def test_identifiability_constraint_enforced() -> None:
    """Dwa starty, te same lambda/mu. Bez centrowania solver dryfuje po grzbiecie."""
    true = _true_params(n_teams=8, seed=3)
    matches = _simulate(true, 1200, seed=3)
    n_teams = 8

    default_fit = fit_dixon_coles(matches, xi=0.0, prior=PriorScales(None, None))
    rng = np.random.default_rng(1)
    shifted = np.concatenate(
        [
            rng.normal(2.0, 0.5, size=n_teams),  # siła przesunięta o +2
            rng.normal(-2.0, 0.5, size=n_teams),  # otwartość o -2
            np.array([0.2, 0.1, 0.05]),
        ]
    )
    other_fit = fit_dixon_coles(matches, xi=0.0, prior=PriorScales(None, None), start=shifted)

    teams = sorted(true.attack)
    for home in teams:
        for away in teams:
            if home == away:
                continue
            assert default_fit.rates(home, away) == pytest.approx(
                other_fit.rates(home, away), abs=1e-4
            )


def test_log_attack_sums_to_zero(
    recovery: tuple[DixonColesParams, DixonColesParams]
    ) -> None:
    _, fitted = recovery
    total = float(np.log(np.array(list(fitted.attack.values()))).sum())
    assert total == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Gradient analityczny
# ---------------------------------------------------------------------------


def test_analytic_gradient_matches_numerical() -> None:
    """Zły gradient nie wywala solvera — daje cicho gorsze dopasowanie."""
    true = _true_params(n_teams=6, seed=7)
    matches = _simulate(true, 300, seed=7)
    data = _prepare(matches, pd.Timestamp(matches["kickoff_utc"].max()), 0.002)
    rng = np.random.default_rng(0)
    theta = np.concatenate(
        [rng.normal(0.0, 0.2, size=12), np.array([0.2, 0.25, -0.07])]
    )

    def value(t: np.ndarray) -> float:
        return _negative_loglik_and_grad(t, data)[0]

    def grad(t: np.ndarray) -> np.ndarray:
        return _negative_loglik_and_grad(t, data)[1]

    assert check_grad(value, grad, theta) < 1e-4


# ---------------------------------------------------------------------------
# Macierz wyników (STEP4_PLAN §1.7)
# ---------------------------------------------------------------------------


def test_matrix_sums_to_one() -> None:
    params = _true_params(n_teams=6, seed=2)
    matrix = score_matrix(params, "T00", "T01")
    assert matrix.shape == (MAX_GOALS_DEFAULT + 1, MAX_GOALS_DEFAULT + 1)
    assert matrix.sum() == pytest.approx(1.0, abs=1e-12)
    assert (matrix >= 0.0).all()


def test_matrix_1x2_matches_direct() -> None:
    """1X2 z macierzy musi zgadzać się z sumowaniem po trójkątach."""
    params = _true_params(n_teams=6, seed=2)
    matrix = score_matrix(params, "T00", "T03")
    grid = np.arange(matrix.shape[0])
    home = float(matrix[grid[:, None] > grid[None, :]].sum())
    draw = float(matrix[grid[:, None] == grid[None, :]].sum())
    away = float(matrix[grid[:, None] < grid[None, :]].sum())
    direct = probabilities_1x2(params, "T00", "T03")
    assert direct == pytest.approx([home, draw, away], abs=1e-12)
    assert float(direct.sum()) == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize(
    ("lam", "mu", "rho"),
    [(1.5, 1.1, -0.08), (2.4, 1.4, -0.10), (0.8, 0.6, 0.15), (3.0, 0.5, -0.20)]
    )
def test_tau_preserves_normalisation(lam: float, mu: float, rho: float) -> None:
    """STEP4_PLAN §1.7 twierdzi, że tau psuje sumę o ~1e-3. NIE psuje.

    Suma poprawek jest tożsamościowo zerowa — patrz docstring
    ``score_matrix``. Bez obcięcia odchyłka jest rzędu precyzji maszynowej
    przy dowolnym rho.
    """
    grid = np.arange(60)
    raw = np.outer(poisson.pmf(grid, lam), poisson.pmf(grid, mu))
    corrected = raw.copy()
    corrected[0, 0] *= 1.0 - lam * mu * rho
    corrected[0, 1] *= 1.0 + lam * rho
    corrected[1, 0] *= 1.0 + mu * rho
    corrected[1, 1] *= 1.0 - rho
    assert corrected.sum() - raw.sum() == pytest.approx(0.0, abs=1e-14)


def test_truncation_is_the_only_normalisation_loss() -> None:
    """Skoro tau jest neutralne, cała odchyłka musi znikać z rosnącym obcięciem."""
    lam, mu, rho = 3.0, 0.5, -0.2
    deviations = []
    for max_goals in (10, 15, 25):
        grid = np.arange(max_goals + 1)
        matrix = np.outer(poisson.pmf(grid, lam), poisson.pmf(grid, mu))
        matrix[0, 0] *= 1.0 - lam * mu * rho
        matrix[0, 1] *= 1.0 + lam * rho
        matrix[1, 0] *= 1.0 + mu * rho
        matrix[1, 1] *= 1.0 - rho
        deviations.append(abs(matrix.sum() - 1.0))
    assert deviations[0] > deviations[1] > deviations[2]
    assert deviations[2] < 1e-12


@pytest.mark.parametrize("lam", [1.5, 2.5, 3.5])
def test_default_truncation_meets_tolerance(lam: float) -> None:
    """Domyślne max_goals musi spełniać próg 1e-6 także dla mocnego gospodarza.

    Przy planowanych 10 warunek łamie się już od lambda ~ 2.0 — dlatego
    domyślna wartość to 15, a nie 10.
    """
    outside = 1.0 - float(
        poisson.cdf(MAX_GOALS_DEFAULT, lam) * poisson.cdf(MAX_GOALS_DEFAULT, 1.2)
    )
    assert outside < TRUNCATION_TOLERANCE


def test_truncation_warning_on_extreme_rates(
    caplog: pytest.LogCaptureFixture
    ) -> None:
    params = DixonColesParams(
        attack={"A": 5.0, "B": 5.0},
        defence={"A": 2.0, "B": 2.0},
        home_advantage=1.3,
        rho=0.0,
        xi=0.0,
        prior=PriorScales(None, None),
        n_fit=0,
        converged=True
    )
    with caplog.at_level("WARNING"):
        score_matrix(params, "A", "B", max_goals=4)
    assert "masa poza obcięciem" in caplog.text


def test_tau_positive_for_fitted_params(
    recovery: tuple[DixonColesParams, DixonColesParams]
    ) -> None:
    """Dopasowanie, które daje tau <= 0, podnosi wyjątek — więc tu go nie ma."""
    _, fitted = recovery
    assert -RHO_BOUND <= fitted.rho <= RHO_BOUND
    for home in list(fitted.attack)[:4]:
        for away in list(fitted.attack)[:4]:
            if home != away:
                assert (score_matrix(fitted, home, away) >= 0.0).all()


# ---------------------------------------------------------------------------
# Wygaszanie czasowe i granica odcięcia
# ---------------------------------------------------------------------------


def test_time_decay_shifts_fit_towards_recent_matches() -> None:
    """Drużyna, która przestała strzelać, ma niższy atak przy dużym xi."""
    rng = np.random.default_rng(0)
    rows: list[dict[str, object]] = []
    for day in range(600):
        # A strzela dużo przez pierwsze 300 dni, potem nic.
        home_goals = 4 if day < 300 else 0
        rows.append(
            {
                "kickoff_utc": T0 + timedelta(days=day),
                "home_team_id": "A" if day % 2 == 0 else "B",
                "away_team_id": "B" if day % 2 == 0 else "A",
                "home_goals": home_goals if day % 2 == 0 else 1,
                "away_goals": 1 if day % 2 == 0 else home_goals,
            }
        )
    for extra in range(200):
        rows.append(
            {
                "kickoff_utc": T0 + timedelta(days=extra * 3),
                "home_team_id": "C",
                "away_team_id": "D" if extra % 2 == 0 else "B",
                "home_goals": int(rng.integers(0, 3)),
                "away_goals": int(rng.integers(0, 3)),
            }
        )
    matches = pd.DataFrame(rows).sort_values("kickoff_utc").reset_index(drop=True)

    flat = fit_dixon_coles(matches, xi=0.0, prior=PriorScales(None, None))
    decayed = fit_dixon_coles(matches, xi=0.01, prior=PriorScales(None, None))
    assert decayed.attack["A"] < flat.attack["A"]


def test_future_match_is_rejected() -> None:
    """Wagi liczone względem daty z przyszłości to look-ahead bias."""
    true = _true_params(n_teams=4, seed=1)
    matches = _simulate(true, 200, seed=1)
    cutoff = pd.Timestamp(matches["kickoff_utc"].iloc[100])
    with pytest.raises(ValueError, match="po reference_date"):
        fit_dixon_coles(matches, reference_date=cutoff)


def test_reference_date_is_recorded() -> None:
    true = _true_params(n_teams=4, seed=1)
    matches = _simulate(true, 200, seed=1)
    cutoff = pd.Timestamp(matches["kickoff_utc"].max())
    fitted = fit_dixon_coles(matches, reference_date=cutoff)
    assert fitted.reference_date == cutoff


def test_zero_xi_weights_everything_equally() -> None:
    true = _true_params(n_teams=5, seed=4)
    matches = _simulate(true, 600, seed=4)
    early = fit_dixon_coles(matches, xi=0.0, prior=PriorScales(None, None))
    # Ta sama próba w odwrotnej kolejności musi dać to samo przy xi=0.
    reversed_dates = matches.copy()
    reversed_dates["kickoff_utc"] = matches["kickoff_utc"].to_numpy()[::-1]
    late = fit_dixon_coles(reversed_dates, xi=0.0, prior=PriorScales(None, None))
    assert late.attack == pytest.approx(early.attack, abs=1e-6)


# ---------------------------------------------------------------------------
# Walidacja wejścia
# ---------------------------------------------------------------------------


def test_naive_datetime_is_rejected() -> None:
    matches = pd.DataFrame(
        {
            "kickoff_utc": pd.to_datetime(["2020-01-01", "2020-01-02"]),
            "home_team_id": ["A", "B"],
            "away_team_id": ["B", "A"],
            "home_goals": [1, 2],
            "away_goals": [0, 1],
        }
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        fit_dixon_coles(matches)


def test_missing_result_is_rejected() -> None:
    true = _true_params(n_teams=4, seed=1)
    matches = _simulate(true, 100, seed=1)
    matches.loc[3, "home_goals"] = np.nan
    with pytest.raises(ValueError, match="bez wyniku"):
        fit_dixon_coles(matches)


def test_negative_xi_is_rejected() -> None:
    true = _true_params(n_teams=4, seed=1)
    matches = _simulate(true, 100, seed=1)
    with pytest.raises(ValueError, match="nieujemne"):
        fit_dixon_coles(matches, xi=-0.001)


def test_unknown_team_raises_by_default() -> None:
    params = _true_params(n_teams=4, seed=1)
    with pytest.raises(KeyError, match="nie występuje w dopasowaniu"):
        score_matrix(params, "T00", "NIEZNANA")


def test_unknown_team_gets_league_average_when_allowed() -> None:
    """Odpowiednik 1500 punktów startowych w Elo — beniaminek nie znika.

    Średnia ligowa, nie jedynka: atak wychodzi 1.0 z ograniczenia
    identyfikowalności, ale obrona ma własny poziom i to on jest
    wartością domyślną.
    """
    params = _true_params(n_teams=4, seed=1)
    lam, mu = params.rates("T00", "NIEZNANA", allow_unknown_teams=True)
    assert lam == pytest.approx(
        params.attack["T00"] * params.league_defence * params.home_advantage
    )
    assert mu == pytest.approx(params.league_attack * params.defence["T00"])
    assert params.league_attack == pytest.approx(1.0, abs=1e-9)


def test_log_likelihood_is_maximised_at_true_parameters() -> None:
    """Sanity: prawdziwe parametry biją losowo zaburzone na tych samych danych."""
    true = _true_params(n_teams=6, seed=5)
    matches = _simulate(true, 2000, seed=5)
    best = log_likelihood(true, matches)
    rng = np.random.default_rng(0)
    for _ in range(5):
        perturbed = DixonColesParams(
            attack={
                k: v * float(np.exp(rng.normal(0.0, 0.3)))
                for k, v in true.attack.items()
            },
            defence=dict(true.defence),
            home_advantage=true.home_advantage,
            rho=true.rho,
            xi=0.0,
            prior=PriorScales(None, None),
            n_fit=0,
            converged=True
    )
        assert log_likelihood(perturbed, matches) < best


# ---------------------------------------------------------------------------
# Regularyzacja — nieograniczona wiarygodność przy drużynie bez goli
# ---------------------------------------------------------------------------


def _league_with_goalless_newcomer() -> pd.DataFrame:
    """Normalna liga plus beniaminek z dwoma meczami 0:0.

    Odwzorowuje przypadek z prawdziwych danych: Sandecja Nowy Sącz miała
    przed meczem z Legią (2017/18) dokładnie dwa mecze, oba bezbramkowe.
    """
    true = _true_params(n_teams=8, seed=11)
    matches = _simulate(true, 900, seed=11)
    last_day = matches["kickoff_utc"].max()
    newcomer = pd.DataFrame(
        [
            {
                "kickoff_utc": last_day + timedelta(days=1),
                "home_team_id": "T00",
                "away_team_id": "NOWY",
                "home_goals": 0,
                "away_goals": 0,
            },
            {
                "kickoff_utc": last_day + timedelta(days=2),
                "home_team_id": "NOWY",
                "away_team_id": "T01",
                "home_goals": 0,
                "away_goals": 0,
            },
        ]
    )
    return pd.concat([matches, newcomer], ignore_index=True)


def test_unregularised_fit_collapses_on_goalless_team() -> None:
    """Dowód, że bez prioru estymator NIE ISTNIEJE — to nie jest przesada.

    Ten test opisuje zachowanie, którego nie chcemy. Gdyby kiedyś przestał
    przechodzić, znaczyłoby to, że ktoś usunął przyczynę i prior stał się
    zbędny — wtedy trzeba to sprawdzić, a nie usuwać test.
    """
    matches = _league_with_goalless_newcomer()
    params = fit_dixon_coles(matches, xi=0.0, prior=PriorScales(None, None))
    lam, mu = params.rates("T00", "NOWY")
    assert params.attack["NOWY"] < 1e-3
    assert min(lam, mu) < 1e-3
    probs = probabilities_1x2(params, "T00", "NOWY")
    assert probs[1] > 0.99  # P(remis) ~ 1, macierz zapadła się na 0:0


def test_prior_keeps_goalless_team_sane() -> None:
    matches = _league_with_goalless_newcomer()
    params = fit_dixon_coles(matches, xi=0.0, prior=PriorScales.uniform(0.5))
    assert 0.1 < params.attack["NOWY"] < 1.0
    lam, mu = params.rates("T00", "NOWY")
    assert 0.2 < lam < 5.0
    assert 0.2 < mu < 5.0
    probs = probabilities_1x2(params, "T00", "NOWY")
    assert probs.max() < 0.9
    assert probs.min() > 0.01


def test_prior_barely_moves_teams_with_long_history(
    recovery: tuple[DixonColesParams, DixonColesParams]
    ) -> None:
    """Regularyzacja ma ratować beniaminków, nie przesuwać całej ligi."""
    true, _ = recovery
    matches = _simulate(true, 5000)
    regularised = fit_dixon_coles(matches, xi=0.0, prior=PriorScales.uniform(0.5))
    errors = _rate_errors(true, regularised)
    assert float(errors.mean()) < 0.06


def test_prior_is_recorded_in_params() -> None:
    matches = _league_with_goalless_newcomer()
    used = fit_dixon_coles(matches, xi=0.0, prior=PriorScales(0.75, 0.05)).prior
    assert used.strength == 0.75
    assert used.openness == 0.05
    assert fit_dixon_coles(
        matches, xi=0.0, prior=PriorScales(None, None)
    ).prior == PriorScales(None, None)


def test_invalid_prior_scale_is_rejected() -> None:
    with pytest.raises(ValueError, match="strength musi być dodatnie"):
        PriorScales.uniform(0.0)
    with pytest.raises(ValueError, match="openness musi być dodatnie"):
        PriorScales(strength=0.3, openness=-1.0)


def test_analytic_gradient_matches_numerical_with_prior() -> None:
    true = _true_params(n_teams=6, seed=7)
    matches = _simulate(true, 300, seed=7)
    data = _prepare(matches, pd.Timestamp(matches["kickoff_utc"].max()), 0.002, PriorScales.uniform(0.5))
    rng = np.random.default_rng(0)
    theta = np.concatenate([rng.normal(0.0, 0.2, size=12), np.array([0.2, 0.25, -0.07])])

    def value(t: np.ndarray) -> float:
        return _negative_loglik_and_grad(t, data)[0]

    def grad(t: np.ndarray) -> np.ndarray:
        return _negative_loglik_and_grad(t, data)[1]

    assert check_grad(value, grad, theta) < 1e-4


def _league_with_goal_level(level: float, n_teams: int = 8) -> pd.DataFrame:
    """Liga o zadanym poziomie bramkowym plus drużyna bez historii."""
    true = _true_params(n_teams=n_teams, seed=21)
    scaled = DixonColesParams(
        attack=dict(true.attack),
        defence={k: v * level for k, v in true.defence.items()},
        home_advantage=true.home_advantage,
        rho=true.rho,
        xi=0.0,
        prior=PriorScales(None, None),
        n_fit=0,
        converged=True
    )
    matches = _simulate(scaled, 1200, seed=21)
    last = matches["kickoff_utc"].max()
    return pd.concat(
        [
            matches,
            pd.DataFrame(
                [
                    {
                        "kickoff_utc": last + timedelta(days=1),
                        "home_team_id": "T00",
                        "away_team_id": "NOWY",
                        "home_goals": 1,
                        "away_goals": 1,
                    }
                ]
            ),
        ],
        ignore_index=True
    )


def test_unknown_team_defaults_to_league_mean_defence() -> None:
    """Drużyna bez historii dostaje średnią LIGOWĄ obronę, nie beta = 1.

    Ta sama pułapka co w środku prioru: ograniczenie identyfikowalności
    pinuje tylko atak, więc 1.0 nie jest środkiem rozkładu obrony.
    W lidze o wysokim poziomie bramkowym beta = 1 dawałoby beniaminkowi
    obronę wyraźnie lepszą od ligowej i zaniżało gole w jego meczach.
    """
    matches = _league_with_goal_level(1.6)
    matches = matches[matches["away_team_id"] != "NOWY"]
    params = fit_dixon_coles(matches, xi=0.0, prior=PriorScales.uniform(0.5))

    assert "NOWY" not in params.teams
    assert params.league_attack == pytest.approx(1.0, abs=1e-9)
    assert params.league_defence > 1.3, "ta liga ma z założenia wysokie beta"

    _, mu = params.rates("T00", "NOWY", allow_unknown_teams=True)
    lam, _ = params.rates("NOWY", "T00", allow_unknown_teams=True)
    assert mu == pytest.approx(params.league_attack * params.defence["T00"])
    assert lam == pytest.approx(
        params.league_attack * params.defence["T00"] * params.home_advantage
    )

    league_goals = float((matches["home_goals"] + matches["away_goals"]).mean())
    neutral = params.league_attack * params.league_defence * (
        1.0 + params.home_advantage
    )
    assert neutral == pytest.approx(league_goals, rel=0.15)


def test_prior_penalty_ignores_league_goal_level() -> None:
    """Kara nie może rosnąć dlatego, że w lidze pada więcej goli.

    Przesunięcie wszystkich ``log beta`` o stałą to zmiana poziomu
    bramkowego, nie zmiana podobieństwa drużyn do siebie. Sprawdzamy na
    prawdziwej funkcji celu: różnica wartości między ligą a jej wersją
    z przesuniętym poziomem musi być identyczna z priorem i bez niego,
    bo prior nie wnosi wtedy nic.
    """
    true = _true_params(n_teams=6, seed=31)
    matches = _simulate(true, 400, seed=31)
    reference = pd.Timestamp(matches["kickoff_utc"].max())
    rng = np.random.default_rng(0)
    theta = np.concatenate([rng.normal(0.0, 0.2, size=12), np.array([0.2, 0.26, -0.06])])
    shifted = theta.copy()
    shifted[6:12] += 0.5

    with_prior = _prepare(matches, reference, 0.0, PriorScales.uniform(0.5))
    without_prior = _prepare(matches, reference, 0.0, None)
    delta_with = (
        _negative_loglik_and_grad(shifted, with_prior)[0]
        - _negative_loglik_and_grad(theta, with_prior)[0]
    )
    delta_without = (
        _negative_loglik_and_grad(shifted, without_prior)[0]
        - _negative_loglik_and_grad(theta, without_prior)[0]
    )
    assert delta_with == pytest.approx(delta_without, abs=1e-9)


# ---------------------------------------------------------------------------
# Empirical Bayes dla skal ściągania (STEP4_ENSEMBLE §10.3)
# ---------------------------------------------------------------------------


def _league_with_scales(
    sd_strength: float, sd_openness: float, *, n_teams: int = 16, seed: int = 0
) -> tuple[pd.DataFrame, DixonColesParams]:
    """Liga o ZADANYM rozrzucie siły i otwartości."""
    rng = np.random.default_rng(seed)
    teams = [f"T{i:02d}" for i in range(n_teams)]
    strength = rng.normal(0.0, sd_strength, size=n_teams)
    openness = rng.normal(0.0, sd_openness, size=n_teams)
    strength -= strength.mean()
    openness -= openness.mean()
    level = np.log(1.2)
    params = DixonColesParams(
        attack=dict(zip(teams, np.exp(openness + strength).tolist(), strict=True)),
        defence=dict(
            zip(teams, np.exp(openness - strength + level).tolist(), strict=True)
        ),
        home_advantage=1.32,
        rho=-0.06,
        xi=0.0,
        prior=PriorScales(None, None),
        n_fit=0,
        converged=True,
    )
    return _simulate(params, 2400, seed=seed), params


def test_empirical_bayes_separates_strength_from_openness() -> None:
    """Sedno §10.3: drużyny różnią się siłą dużo, otwartością mało.

    Empirical Bayes ma to wykryć z danych, a nie dostać w konfiguracji.
    Gdyby zwracał jedną wartość na oba wymiary, cała naprawa nachylenia
    sumy goli nie miałaby podstawy.
    """
    matches, _ = _league_with_scales(0.30, 0.06)
    result = empirical_bayes_scales(matches, xi=0.0)

    assert result.scales.strength is not None
    assert result.scales.openness is not None
    assert result.scales.strength > 3.0 * result.scales.openness
    assert result.scales.strength == pytest.approx(0.30, abs=0.12)
    assert result.scales.openness == pytest.approx(0.06, abs=0.06)


def test_empirical_bayes_discounts_estimation_noise() -> None:
    """Rozrzut oszacowań jest większy niż prawdziwy — tau musi być mniejsze.

    Po §11.3 nie obowiązuje już tożsamość momentów
    ``tau^2 == var - mean(SE^2)``; estymator waży precyzją, więc związek
    jest nierównością, nie równaniem. Kierunek zostaje ten sam i to on jest
    sednem: część obserwowanego rozrzutu to szum estymacji.
    """
    matches, _ = _league_with_scales(0.30, 0.06)
    r = empirical_bayes_scales(matches, xi=0.0)
    assert r.noise_strength > 0.0
    assert r.noise_openness > 0.0
    assert r.scales.strength is not None
    assert r.scales.openness is not None
    assert r.scales.strength**2 < r.var_strength
    assert r.scales.openness**2 < r.var_openness


def test_empirical_bayes_collapses_openness_when_teams_are_identical() -> None:
    """Zerowy prawdziwy rozrzut otwartości ma dać wartość bliską zeru.

    Estymator z marginalnej wiarygodności nie ma podłogi, więc nie ma
    „osiadania" — ma po prostu zwrócić małą liczbę. Przy prawdziwym zerze
    człon ``+ log tau`` daje lekkie zawyżenie (symulacja w §11.3: ~0.026),
    nieszkodliwe przy tej skali.
    """
    matches, _ = _league_with_scales(0.30, 0.0)
    r = empirical_bayes_scales(matches, xi=0.0)
    assert r.scales.openness is not None
    assert r.scales.strength is not None
    assert 0.0 < r.scales.openness < 0.05
    assert r.scales.openness < 0.25 * r.scales.strength
    assert r.openness_is_negligible or r.scales.openness < 0.05


def test_tau_estimator_never_returns_zero() -> None:
    """Człon ``+ log tau`` gwarantuje dodatniość bez podłogi.

    Nawet gdy wszystkie oszacowania są dokładnie zerowe, a błędy
    standardowe duże, estymator musi zwrócić coś dodatniego — inaczej
    kara dzieli przez zero.
    """
    zeros = np.zeros(20)
    big_errors = np.full(20, 0.5)
    tau = _marginal_likelihood_tau(zeros, big_errors)
    assert tau > 0.0
    assert np.isfinite(tau)


def test_tau_estimator_weights_by_precision() -> None:
    """Drużyna z ogromnym SE nie może przesuwać tau tak jak dokładna.

    To jest przewaga nad metodą momentów, która ważyła wszystkie drużyny
    tak samo.
    """
    rng = np.random.default_rng(0)
    truth = rng.normal(0.0, 0.10, size=30)
    precise_se = np.full(30, 0.02)
    tau_precise = _marginal_likelihood_tau(truth, precise_se)

    # Ta sama prawda, ale połowa drużyn zmierzona fatalnie i przez to
    # rozrzucona znacznie szerzej niż w rzeczywistości.
    noisy = truth.copy()
    noisy[15:] += rng.normal(0.0, 0.40, size=15)
    mixed_se = np.concatenate([np.full(15, 0.02), np.full(15, 0.40)])
    tau_mixed = _marginal_likelihood_tau(noisy, mixed_se)

    naive = float(np.sqrt(max(np.var(noisy, ddof=1) - np.mean(mixed_se**2), 1e-4)))
    assert abs(tau_mixed - tau_precise) < abs(naive - tau_precise)


def test_tau_estimator_recovers_known_spread() -> None:
    rng = np.random.default_rng(1)
    for true_tau in (0.04, 0.06, 0.13):
        errors = rng.uniform(0.01, 0.08, size=22)
        draws = rng.normal(0.0, true_tau, size=22) + rng.normal(0.0, errors)
        estimate = _marginal_likelihood_tau(draws, errors)
        assert estimate == pytest.approx(true_tau, abs=0.05)


def test_degenerate_strength_raises_instead_of_shrinking_silently() -> None:
    """Bezpiecznik z §11.3: tau_s < 0.05 to awaria, nie ustalenie.

    Liga, w której wszystkie drużyny są identyczne, jest fizycznie możliwa
    w symulacji i niemożliwa w rzeczywistości. Model ma wtedy krzyknąć,
    a nie po cichu zwrócić stałe prawdopodobieństwa — to właśnie stało się
    w sezonie 2019/20 przed tą poprawką.
    """
    matches, _ = _league_with_scales(0.0, 0.05, seed=3)
    with pytest.raises(RuntimeError, match="awaria estymacji"):
        empirical_bayes_scales(matches, xi=0.0)


def test_future_poison_empirical_bayes() -> None:
    """Zatrucie meczów PO oknie treningowym nie może ruszyć tau_s ani tau_o.

    Wymagane wprost przez STEP4_ENSEMBLE §10.3. Skale wchodzą do każdego
    dopasowania w sezonie testowym, więc przeciek tutaj skaziłby cały
    walk-forward, nie jeden fold.
    """
    matches, _ = _league_with_scales(0.30, 0.06)
    cutoff = pd.Timestamp(matches["kickoff_utc"].quantile(0.7))
    window = matches[matches["kickoff_utc"] <= cutoff]

    clean = empirical_bayes_scales(window, xi=0.002, reference_date=cutoff)

    poisoned_tail = matches[matches["kickoff_utc"] > cutoff].copy()
    poisoned_tail["home_goals"] = 99
    poisoned_tail["away_goals"] = 0
    poisoned_all = pd.concat([window, poisoned_tail], ignore_index=True)
    after = empirical_bayes_scales(
        poisoned_all[poisoned_all["kickoff_utc"] <= cutoff],
        xi=0.002,
        reference_date=cutoff,
    )
    assert clean.scales == after.scales


def test_empirical_bayes_scales_are_recorded_in_fit() -> None:
    matches, _ = _league_with_scales(0.30, 0.06)
    scales = empirical_bayes_scales(matches, xi=0.0).scales
    fitted = fit_dixon_coles(matches, xi=0.0, prior=scales)
    assert fitted.prior == scales


def test_separate_scales_shrink_openness_more_than_strength() -> None:
    """Efekt końcowy: rozrzut przewidywanej sumy goli maleje, siły nie."""
    matches, truth = _league_with_scales(0.30, 0.06)
    pairs = [(h, a) for h in truth.attack for a in truth.attack if h != a]

    def spreads(params: DixonColesParams) -> tuple[float, float]:
        rates = np.array([params.rates(h, a) for h, a in pairs])
        return float(np.std(rates.sum(axis=1))), float(
            np.std(rates[:, 0] - rates[:, 1])
        )

    uniform = fit_dixon_coles(matches, xi=0.0, prior=PriorScales.uniform(0.35))
    separate = fit_dixon_coles(
        matches, xi=0.0, prior=PriorScales(strength=0.35, openness=0.06)
    )
    total_uniform, diff_uniform = spreads(uniform)
    total_separate, diff_separate = spreads(separate)

    assert total_separate < total_uniform
    assert diff_separate == pytest.approx(diff_uniform, rel=0.15)


# ---------------------------------------------------------------------------
# Poprawka C: drużyny bez informacji i SE bez pinv (STEP4_ENSEMBLE §11.9)
# ---------------------------------------------------------------------------


def _league_with_dead_teams(
    n_active: int = 16, n_dead: int = 12, *, seed: int = 0
) -> pd.DataFrame:
    """Liga z rotacją: część drużyn grała tylko na początku okna.

    Odwzorowuje realny kształt z dev: w oknie dekady 11 z 30 drużyn miało
    ostatni mecz lata temu, więc przy silnym wygaszaniu ich ``n_eff``
    spada do 1e-8.
    """
    rng = np.random.default_rng(seed)
    active = [f"A{i:02d}" for i in range(n_active)]
    dead = [f"D{i:02d}" for i in range(n_dead)]

    def block(teams: list[str], day0: int, n_days: int) -> list[dict[str, object]]:
        rows = []
        for day in range(n_days):
            rng.shuffle(teams)
            for home, away in zip(teams[::2], teams[1::2], strict=False):
                rows.append(
                    {
                        "kickoff_utc": T0 + timedelta(days=day0 + day * 7),
                        "home_team_id": home,
                        "away_team_id": away,
                        "home_goals": int(rng.poisson(1.5)),
                        "away_goals": int(rng.poisson(1.2)),
                    }
                )
        return rows

    rows = block(dead + active[:4], 0, 90)  # dawno temu
    rows += block(active, 2600, 40)  # niedawno
    return pd.DataFrame(rows).sort_values("kickoff_utc").reset_index(drop=True)


def test_dead_teams_are_dropped_from_the_fit() -> None:
    """Drużyna bez informacji w oknie nie może zostać wolnym parametrem."""
    matches = _league_with_dead_teams()
    reference = pd.Timestamp(matches["kickoff_utc"].max())
    data = _prepare(matches, reference, 0.008, PriorScales.uniform(2.0))
    assert data.n_dropped_teams > 0
    assert data.n_dropped_matches > 0
    assert (data.effective_matches >= MIN_EFFECTIVE_FOR_FIT).all()
    assert all(team.startswith("A") for team in data.teams)


def test_regression_pinv_blew_up_standard_errors() -> None:
    """Regresja błędu z 2026-10-01 (§11.9).

    Stara ścieżka: ``pinv`` na informacji bez prioru, wszystkie drużyny.
    Zmierzone wtedy na dev: SE(s) aktywnych drużyn 9.02, cond 3.7e12.
    Nowa ścieżka ma dać SE <= 0.5 i sensowne ``tau_s``.
    """
    matches = _league_with_dead_teams()
    reference = pd.Timestamp(matches["kickoff_utc"].max())

    # Stara ścieżka, odtworzona wprost: bez progu n_eff, pinv, bez prioru.
    old = _prepare(
        matches, reference, 0.008, PriorScales.uniform(2.0), min_effective_matches=0.0
    )
    weak_old = fit_dixon_coles(
        matches,
        xi=0.008,
        prior=PriorScales.uniform(2.0),
        reference_date=reference,
        max_iter=500,
        min_effective_matches=0.0,
    )
    covariance = np.linalg.pinv(_fisher_information(old, weak_old), rcond=1e-9)
    n_eff_old = old.effective_matches
    se_old = np.sqrt(np.clip(np.diag(covariance)[: old.n_teams], 0.0, None))
    alive = n_eff_old >= MIN_EFFECTIVE_FOR_TAU
    assert se_old[alive].max() > 1.0, (
        "stara ścieżka miała rozlewać wariancję na aktywne drużyny; "
        "jeśli już tego nie robi, ten test stracił sens"
    )

    result = empirical_bayes_scales(matches, xi=0.008, reference_date=reference)
    assert result.max_se_strength <= 0.5
    assert result.condition_number < 1e6
    assert result.n_dropped_teams > 0


def test_tau_threshold_sensitivity_is_reported_not_applied() -> None:
    matches = _league_with_dead_teams()
    result = empirical_bayes_scales(matches, xi=0.004)
    assert set(result.tau_strength_sensitivity) == {3.0, 10.0}
    assert result.n_well_measured >= 6


def test_numerical_safeguard_fires_on_spread_variance() -> None:
    """Bezpiecznik numeryczny łapie PRZYCZYNĘ, nie skutek.

    Rozlana wariancja potrafi wypchnąć tau w górę albo w dół — kierunek
    zależy od szczegółów implementacji. Dlatego progiem jest SE dobrze
    zmierzonej drużyny, nie sama wartość tau.
    """
    data = _prepare(
        _league_with_dead_teams(),
        pd.Timestamp(_league_with_dead_teams()["kickoff_utc"].max()),
        0.0,
        PriorScales.uniform(0.5),
    )
    assert MAX_STANDARD_ERROR == 1.0
    assert MIN_TAU_STRENGTH == 0.03, "próg zmieniony z 0.05 w §11.9 pkt 4"
    assert data.n_teams > 0


def test_cholesky_refuses_non_positive_definite_matrix() -> None:
    """Żadnego cichego zejścia na pseudoodwrotność."""
    true = _true_params(n_teams=6, seed=2)
    matches = _simulate(true, 400, seed=2)
    reference = pd.Timestamp(matches["kickoff_utc"].max())
    # Bez prioru hesjan ma dwa kierunki zerowe i NIE jest dodatnio określony.
    data = _prepare(matches, reference, 0.0, PriorScales(None, None))
    params = fit_dixon_coles(
        matches, xi=0.0, prior=PriorScales(None, None), reference_date=reference
    )
    with pytest.raises(NumericalInstabilityError, match="Cholesky"):
        _standard_errors(data, params)


def test_future_poison_effective_counts() -> None:
    """``n_eff`` w chwili t nie może zależeć od meczów po t."""
    matches = _league_with_dead_teams()
    cutoff = pd.Timestamp(matches["kickoff_utc"].quantile(0.8))
    window = matches[matches["kickoff_utc"] <= cutoff]
    clean = _prepare(window, cutoff, 0.004, PriorScales.uniform(0.5))

    poisoned = matches.copy()
    later = poisoned["kickoff_utc"] > cutoff
    poisoned.loc[later, "home_goals"] = 99
    poisoned.loc[later, "away_goals"] = 0
    after = _prepare(
        poisoned[poisoned["kickoff_utc"] <= cutoff],
        cutoff,
        0.004,
        PriorScales.uniform(0.5),
    )
    assert clean.teams == after.teams
    assert np.allclose(clean.effective_matches, after.effective_matches)
