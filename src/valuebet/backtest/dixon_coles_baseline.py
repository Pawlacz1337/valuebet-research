"""Walk-forward Dixon-Coles i bramka jakościowa DC vs Elo (STEP4_PLAN §2).

Co to liczy
-----------
Ten sam podział walk-forward co ``backtest/elo_baseline.py``: te same
sezony testowe, ten sam ``min_train_seasons``, te same mecze. Różni się
wyłącznie modelem. Dzięki temu porównanie jest parowane co do meczu, a
nie „mniej więcej na tym samym".

Dlaczego przefitowanie przed KAŻDYM dniem meczowym
---------------------------------------------------
To nie jest luksus, tylko warunek uczciwości porównania.

Elo w ``elo_baseline`` przechodzi chronologicznie przez całą historię:
rating przed meczem w kwietniu zawiera wyniki z marca **tego samego
sezonu testowego**. Gdyby DC był dopasowany raz, na starcie sezonu, to w
kwietniu operowałby na parametrach sprzed ośmiu miesięcy i przegrałby z
Elo z powodu nieświeżości, a nie z powodu modelu. Wniosek „DC nie bije
Elo" byłby wtedy artefaktem procedury.

Dlatego przed każdym dniem meczowym dopasowujemy DC od nowa na
**wszystkich** meczach z ``kickoff_utc`` wcześniejszym niż pierwszy
gwizdek tego dnia. Okno jest rozszerzające (expanding), tak jak u Elo,
a wygaszanie czasowe ``xi`` odpowiada za to, ile waży stara historia.

Odcięcie jest o włos konserwatywne: mecz grany tego samego dnia
wcześniej nie wchodzi do dopasowania dla meczu późniejszego. Wolimy
stracić kilka godzin informacji niż ryzykować, że kolejność w obrębie
dnia wpuści wynik do własnej predykcji.

Strojenie xi (STEP4_PLAN §1.5, reguła 10)
------------------------------------------
``xi`` jest hiperparametrem i **nigdy** nie jest wybierane na sezonie
testowym. Dla każdego sezonu testowego ``S``:

1. dopasuj DC na ``seasons[:i-1]`` dla każdego ``xi`` z siatki,
2. wybierz ``xi`` maksymalizujące log-wiarygodność na ``seasons[i-1]``
   (ostatni sezon okna treningowego = walidacja wewnętrzna),
3. użyj tego ``xi`` do wszystkich dopasowań w sezonie ``S``.

Sezon testowy nie bierze udziału w żadnym z tych kroków.

Beniaminkowie
-------------
Drużyna nieobecna w historii dostaje ``alpha = beta = 1`` (średnia
ligowa). To dokładny odpowiednik startowych 1500 punktów w Elo, więc oba
modele traktują beniaminka tak samo i porównanie zostaje uczciwe. Liczba
takich meczów jest raportowana — jeśli urośnie, przestaje być detalem.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from valuebet.backtest.elo_baseline import BaselineReport, MarketGap, _market_gap
from valuebet.backtest.metrics import (
    BootstrapDiff,
    log_loss_per_match,
    market_probabilities,
    paired_bootstrap_diff,
)
from valuebet.models.dixon_coles import (
    MAX_GOALS_DEFAULT,
    DixonColesParams,
    NumericalInstabilityError,
    PriorScales,
    empirical_bayes_scales,
    fit_dixon_coles,
    log_likelihood,
    probabilities_1x2,
)
from valuebet.models.elo_ordinal import outcome_index

__all__ = [
    "DEFAULT_XI_GRID",
    "MIN_VALIDATION_HISTORY",
    "DixonColesReport",
    "DixonColesSeasonResult",
    "GateResult",
    "build_xi_cache",
    "format_gate_report",
    "quality_gate",
    "run_dixon_coles_baseline",
    "select_xi",
]

log = logging.getLogger(__name__)

#: Siatka wygaszania ze STEP4_PLAN §1.5. Pół-okres = ln(2)/xi:
#: 0.001 -> 693 dni, 0.003 -> 231 dni, 0.008 -> 87 dni.
DEFAULT_XI_GRID: tuple[float, ...] = (0.0, 0.001, 0.002, 0.003, 0.005, 0.008)

_PROB_COLS = ["p_home", "p_draw", "p_away"]


@dataclass(frozen=True)
class DixonColesSeasonResult:
    season: str
    n: int
    n_train: int
    xi: float
    tau_strength: float
    tau_openness: float
    n_validation_seasons: int
    n_rejected_xi: int
    condition_number: float
    n_dropped_teams: int
    n_fits: int
    n_unknown_team_matches: int
    log_loss_dc: float


@dataclass
class DixonColesReport:
    seasons: list[DixonColesSeasonResult]
    #: match_id, season, outcome, ll_dc, p_home/p_draw/p_away oraz
    #: diagnostyka: lambda_home, mu_away, rho, history_home, history_away.
    predictions: pd.DataFrame
    pooled_gaps: tuple[MarketGap, ...]
    n_fits: int

    @property
    def n(self) -> int:
        return len(self.predictions)

    @property
    def pooled_log_loss(self) -> float:
        return float(self.predictions["ll_dc"].mean())


@dataclass(frozen=True)
class GateResult:
    """Bramka ze STEP4_PLAN §2. ``passed`` gdy DC ma istotnie niższy log loss."""

    n: int
    log_loss_dc: float
    log_loss_elo: float
    diff: BootstrapDiff

    @property
    def passed(self) -> bool:
        """DC lepsze i różnica nie zawiera zera.

        Sama ujemna wartość punktowa nie wystarcza — reguła 11 wymaga,
        żeby wniosek stał na przedziale, nie na środku.
        """
        return self.diff.mean_diff < 0.0 and self.diff.excludes_zero


def _predict_day(
    params: DixonColesParams, group: pd.DataFrame, *, max_goals: int
) -> tuple[np.ndarray, int]:
    """Prawdopodobieństwa 1X2 dla jednego dnia meczowego + licznik beniaminków."""
    known = params.teams
    rows: list[np.ndarray] = []
    unknown = 0
    for home, away in zip(
        group["home_team_id"].astype(str),
        group["away_team_id"].astype(str),
        strict=True,
    ):
        if home not in known or away not in known:
            unknown += 1
        rows.append(
            probabilities_1x2(
                params, home, away, max_goals=max_goals, allow_unknown_teams=True
            )
        )
    return np.vstack(rows), unknown


def _day_diagnostics(
    params: DixonColesParams, group: pd.DataFrame, history: pd.DataFrame
) -> dict[str, np.ndarray]:
    """lambda, mu, rho i długość historii obu drużyn — materiał do diagnozy.

    Bez tych kolumn nie da się policzyć ani tabeli kalibracji niskich
    wyników, ani podziału reliability na mecze z beniaminkiem — a obie
    rzeczy są potrzebne, żeby odróżnić przyczyny nadmiaru remisów
    (STEP4_ENSEMBLE §3). Trzy liczby na mecz, więc trzymamy je zawsze.
    """
    counts = pd.concat([history["home_team_id"], history["away_team_id"]]).value_counts()
    homes = group["home_team_id"].astype(str)
    aways = group["away_team_id"].astype(str)
    rates = [
        params.rates(h, a, allow_unknown_teams=True)
        for h, a in zip(homes, aways, strict=True)
    ]
    return {
        "lambda_home": np.array([r[0] for r in rates], dtype=np.float64),
        "mu_away": np.array([r[1] for r in rates], dtype=np.float64),
        "rho": np.full(len(group), params.rho, dtype=np.float64),
        "history_home": homes.map(counts).fillna(0).to_numpy(dtype=np.int64),
        "history_away": aways.map(counts).fillna(0).to_numpy(dtype=np.int64),
    }


#: Ile sezonów musi leżeć przed sezonem, żeby dało się go użyć jako
#: walidacyjny. Dwa, bo empirical Bayes potrzebuje okna, w którym błędy
#: standardowe parametrów drużyn mają sens.
MIN_VALIDATION_HISTORY = 2


def _scales_for_window(
    frame: pd.DataFrame,
    seasons_before: list[str],
    xi: float,
    *,
    max_iter: int,
) -> PriorScales:
    """Skale ściągania z empirical Bayes, **wyłącznie** z podanego okna.

    Zasada twarda ze STEP4_ENSEMBLE §11.3: tau danego okna pochodzi z
    danych tego okna i nigdy z późniejszych. Pożyczenie lepiej wyglądającej
    wartości z nowszego sezonu byłoby informacją z przyszłości.
    """
    window = frame[frame["season"].isin(seasons_before)]
    return empirical_bayes_scales(
        window,
        xi=xi,
        reference_date=pd.Timestamp(window["kickoff_utc"].max()),
        max_iter=max_iter,
    ).scales


@dataclass(frozen=True)
class _SeasonRun:
    predictions: pd.DataFrame
    goals_loglik: float
    n_fits: int
    n_unknown: int


def _walk_forward_season(
    frame: pd.DataFrame,
    test_season: str,
    xi: float,
    scales: PriorScales,
    *,
    max_goals: int,
    max_iter: int,
) -> _SeasonRun:
    """Jeden sezon testowy, przefitowanie przed każdym dniem meczowym.

    Odcięcie to pierwszy gwizdek danego dnia; dopasowanie widzi wyłącznie
    mecze wcześniejsze. Zwraca też log-wiarygodność goli tego sezonu —
    to jest ``LL(V, xi)`` z §11.2, wielkość niezależna od tego, dla którego
    sezonu testowego akurat wybieramy ``xi``.
    """
    test = frame[frame["season"] == test_season]
    day_parts: list[pd.DataFrame] = []
    goals_loglik = 0.0
    n_fits = 0
    n_unknown = 0

    for _day, group in test.groupby(
        test["kickoff_utc"].dt.floor("D"), sort=True, observed=True
    ):
        cutoff = pd.Timestamp(group["kickoff_utc"].min())
        history = frame[frame["kickoff_utc"] < cutoff]
        params = fit_dixon_coles(
            history, xi=xi, prior=scales, reference_date=cutoff, max_iter=max_iter
        )
        n_fits += 1
        goals_loglik += log_likelihood(params, group, allow_unknown_teams=True)
        probs, unknown = _predict_day(params, group, max_goals=max_goals)
        n_unknown += unknown
        y = group["outcome"].to_numpy()
        day_parts.append(
            pd.DataFrame(
                {
                    "match_id": group["match_id"].to_numpy(),
                    "season": test_season,
                    "outcome": y,
                    "ll_dc": log_loss_per_match(probs, y),
                    "p_home": probs[:, 0],
                    "p_draw": probs[:, 1],
                    "p_away": probs[:, 2],
                    **_day_diagnostics(params, group, history),
                }
            )
        )
    return _SeasonRun(
        predictions=pd.concat(day_parts, ignore_index=True),
        goals_loglik=goals_loglik,
        n_fits=n_fits,
        n_unknown=n_unknown,
    )


def build_xi_cache(
    frame: pd.DataFrame,
    seasons: list[str],
    xi_grid: tuple[float, ...],
    *,
    max_goals: int = MAX_GOALS_DEFAULT,
    max_iter: int = 500,
    progress: Callable[[str, float, float], None] | None = None,
) -> dict[tuple[str, float], float]:
    """``LL(V, xi)`` dla każdej pary (sezon walidacyjny, xi) — liczone RAZ.

    Sedno optymalizacji z §11.2: ``LL(V, xi)`` nie zależy od tego, dla
    którego sezonu testowego ``S`` wybieramy ``xi``. Naiwna implementacja
    przeliczałaby ten sam walk-forward dla każdego ``S`` z osobna.

    Szczelność: ``LL(V, xi)`` powstaje wyłącznie z meczów sprzed kolejnych
    kolejek ``V``, a wybór dla ``S`` sumuje tylko te ``V``, które leżą
    przed ``S``. Nic z ``S`` ani z przyszłości nie wchodzi.
    """
    cache: dict[tuple[str, float], float] = {}
    for index, season in enumerate(seasons):
        if index < MIN_VALIDATION_HISTORY:
            continue
        before = seasons[:index]
        for xi in xi_grid:
            # Kandydat z siatki a predykcja to DWIE różne sytuacje
            # (STEP4_ENSEMBLE §11.9 pkt 5). Tutaj liczymy kandydata:
            # zdegenerowany xi to informacja („niedopuszczalny dla każdego
            # S > V"), nie awaria przebiegu. Dostaje -inf i lecimy dalej.
            # W predykcji z WYBRANYM xi ten sam wyjątek leci w górę.
            try:
                scales = _scales_for_window(frame, before, xi, max_iter=max_iter)
                run = _walk_forward_season(
                    frame, season, xi, scales, max_goals=max_goals, max_iter=max_iter
                )
            except NumericalInstabilityError as exc:
                cache[season, xi] = -math.inf
                log.warning(
                    "kandydat xi=%.4f odrzucony dla walidacji %s: %s",
                    xi,
                    season,
                    exc,
                )
                continue
            cache[season, xi] = run.goals_loglik
            if progress is not None:
                progress(season, xi, run.goals_loglik)
    return cache


def select_xi(
    cache: dict[tuple[str, float], float],
    seasons: list[str],
    test_index: int,
    xi_grid: tuple[float, ...],
) -> tuple[float, list[str]]:
    """``argmax_xi sum_{V < S} LL(V, xi)`` — kryterium z wielu sezonów.

    Jeden sezon walidacyjny ma za mało sygnału; ta sama lekcja co przy
    ``prior_sd`` (§10.0) i przyczyna degeneracji 2019/20, gdzie pojedynczy
    sezon wybrał ``xi = 0.008``, a empirical Bayes ściągnął wtedy oba
    wymiary na podłogę.

    Zwraca też listę użytych sezonów walidacyjnych — bez niej nie widać,
    na ilu sezonach stoi wybór.
    """
    used = [
        season
        for index, season in enumerate(seasons[:test_index])
        if index >= MIN_VALIDATION_HISTORY and (season, xi_grid[0]) in cache
    ]
    if not used:
        raise ValueError(
            f"brak sezonów walidacyjnych przed indeksem {test_index} — "
            "zwiększ min_train_seasons albo dołóż historii"
        )
    totals = {xi: sum(cache[season, xi] for season in used) for xi in xi_grid}
    if all(math.isinf(v) for v in totals.values()):
        raise NumericalInstabilityError(
            f"każdy kandydat xi odrzucony na sezonach {used} — nie ma z czego "
            "wybierać; to awaria, nie wybór"
        )
    return max(totals, key=lambda k: totals[k]), used


def run_dixon_coles_baseline(
    matches: pd.DataFrame,
    closing: pd.DataFrame,
    *,
    min_train_seasons: int = 3,
    xi_grid: tuple[float, ...] = DEFAULT_XI_GRID,
    max_goals: int = MAX_GOALS_DEFAULT,
    max_iter: int = 500,
    references: tuple[str, ...] = ("pinnacle", "betfair_exchange"),
    seed: int = 0,
) -> DixonColesReport:
    """Walk-forward DC na tym samym podziale co ``run_elo_baseline``.

    ``min_train_seasons`` musi być identyczne z wywołaniem Elo, inaczej
    bramka porównuje różne zbiory testowe.
    """
    required = {
        "match_id",
        "season",
        "kickoff_utc",
        "home_team_id",
        "away_team_id",
        "home_goals",
        "away_goals",
    }
    missing = required - set(matches.columns)
    if missing:
        raise ValueError(f"run_dixon_coles_baseline: brak kolumn {sorted(missing)}")

    frame = matches.loc[
        matches["home_goals"].notna() & matches["away_goals"].notna()
    ].copy()
    frame["outcome"] = outcome_index(
        frame["home_goals"].to_numpy(dtype=np.float64),
        frame["away_goals"].to_numpy(dtype=np.float64),
    )
    frame = frame.sort_values(
        ["kickoff_utc", "match_id"], kind="mergesort"
    ).reset_index(drop=True)

    seasons = sorted(frame["season"].unique())
    if len(seasons) <= min_train_seasons:
        raise ValueError(
            f"za mało sezonów: {len(seasons)}, potrzeba > {min_train_seasons}"
        )

    season_results: list[DixonColesSeasonResult] = []
    parts: list[pd.DataFrame] = []
    total_fits = 0

    cache = build_xi_cache(
        frame, seasons, xi_grid, max_goals=max_goals, max_iter=max_iter
    )
    for i, test_season in enumerate(seasons):
        if i < min_train_seasons:
            continue
        train_seasons = seasons[:i]
        xi, used = select_xi(cache, seasons, i, xi_grid)
        rejected = sum(
            1
            for v in used
            for candidate in xi_grid
            if math.isinf(cache[v, candidate])
        )
        # Predykcja: bezpiecznik ma tu podnieść wyjątek, nie zostać zjedzony.
        eb = empirical_bayes_scales(
            frame[frame["season"].isin(train_seasons)],
            xi=xi,
            reference_date=pd.Timestamp(
                frame.loc[frame["season"].isin(train_seasons), "kickoff_utc"].max()
            ),
            max_iter=max_iter,
        )
        scales = eb.scales
        log.info(
            "sezon %s: xi=%.4f tau_s=%.4f tau_o=%.4f (wybor z %d sezonow: %s)",
            test_season,
            xi,
            scales.strength,
            scales.openness,
            len(used),
            ", ".join(used),
        )
        run = _walk_forward_season(
            frame, test_season, xi, scales, max_goals=max_goals, max_iter=max_iter
        )
        parts.append(run.predictions)
        total_fits += run.n_fits + 2
        season_results.append(
            DixonColesSeasonResult(
                season=test_season,
                n=int((frame["season"] == test_season).sum()),
                n_train=int(frame["season"].isin(train_seasons).sum()),
                xi=xi,
                tau_strength=float(scales.strength or 0.0),
                tau_openness=float(scales.openness or 0.0),
                n_validation_seasons=len(used),
                n_rejected_xi=rejected,
                condition_number=eb.condition_number,
                n_dropped_teams=eb.n_dropped_teams,
                n_fits=run.n_fits,
                n_unknown_team_matches=run.n_unknown,
                log_loss_dc=float(run.predictions["ll_dc"].mean()),
            )
        )

    predictions = pd.concat(parts, ignore_index=True)

    # Luki do rynku liczone dokładnie tak samo jak dla Elo — ``_market_gap``
    # oczekuje kolumny ``ll_elo``, więc podajemy DC pod tą nazwą.
    renamed = predictions.rename(columns={"ll_dc": "ll_elo"})
    markets = _market_frames(closing, references)
    pooled_gaps = tuple(
        gap
        for bookmaker, market in markets.items()
        if (
            gap := _market_gap(
                bookmaker, renamed, market, seed=seed, clustered=True
            )
        )
        is not None
    )
    return DixonColesReport(
        seasons=season_results,
        predictions=predictions,
        pooled_gaps=pooled_gaps,
        n_fits=total_fits,
    )


def _market_frames(
    closing: pd.DataFrame, references: tuple[str, ...]
) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for bookmaker in references:
        subset = closing.loc[
            closing["bookmaker"] == bookmaker,
            ["match_id", "odds_home", "odds_draw", "odds_away"],
        ]
        if subset.empty:
            continue
        out[bookmaker] = market_probabilities(subset)
    return out


def quality_gate(
    dc: DixonColesReport, elo: BaselineReport, *, seed: int = 0
) -> GateResult:
    """Parowane porównanie DC vs Elo na wspólnych meczach (STEP4_PLAN §2).

    DC używa liczby goli, Elo tylko wyniku W/R/P — to ściśle więcej
    informacji. Jeśli DC nie bije Elo, domyślnym wyjaśnieniem jest błąd
    implementacji, nie „taka uroda modelu".
    """
    joined = dc.predictions[["match_id", "season", "ll_dc"]].merge(
        elo.predictions[["match_id", "ll_elo"]],
        on="match_id",
        how="inner",
        validate="one_to_one",
    )
    if len(joined) != len(dc.predictions) or len(joined) != len(elo.predictions):
        raise ValueError(
            "bramka porównuje różne zbiory: DC ma "
            f"{len(dc.predictions)}, Elo {len(elo.predictions)}, wspólnych "
            f"{len(joined)} — sprawdź min_train_seasons w obu wywołaniach"
        )
    ll_dc = joined["ll_dc"].to_numpy()
    ll_elo = joined["ll_elo"].to_numpy()
    return GateResult(
        n=len(joined),
        log_loss_dc=float(ll_dc.mean()),
        log_loss_elo=float(ll_elo.mean()),
        diff=paired_bootstrap_diff(
            ll_dc, ll_elo, groups=joined["season"].to_numpy(), seed=seed
        ),
    )


def format_gate_report(
    dc: DixonColesReport, elo: BaselineReport, gate: GateResult
) -> str:
    out: list[str] = []
    out.append("=== DIXON-COLES walk-forward ===")
    out.append(
        "  sezon     n_train  n     xi      tau_s    tau_o    fitów  bez hist.  LL dc"
    )
    for r in dc.seasons:
        out.append(
            f"  {r.season:<9} {r.n_train:<8} {r.n:<5} {r.xi:<7.4f} "
            f"{r.tau_strength:<8.4f} {r.tau_openness:<8.4f} "
            f"{r.n_fits:<6} {r.n_unknown_team_matches:<13} {r.log_loss_dc:.4f}"
        )
    out.append(f"  dopasowań łącznie: {dc.n_fits}")
    out.append("")
    out.append("=== BRAMKA JAKOŚCIOWA: DC vs Elo (STEP4_PLAN §2) ===")
    out.append(f"  n={gate.n}  LL dc={gate.log_loss_dc:.4f}  LL elo={gate.log_loss_elo:.4f}")
    d = gate.diff
    kind = (
        f"CI klastrowe po {d.n_groups} sezonach"
        if d.is_clustered and d.reliable
        else f"CI klastrowe, tylko {d.n_groups} sezony - NIEWIARYGODNE"
    )
    out.append(
        f"  dc - elo = {d.mean_diff:+.4f} [{d.ci_low:+.4f}, {d.ci_high:+.4f}] ({kind})"
    )
    out.append(
        f"  BRAMKA: {'PRZESZŁA' if gate.passed else 'NIE PRZESZŁA'} "
        "(ujemna = DC lepsze, przedział musi omijać zero)"
    )
    out.append("")
    out.append("=== LUKI DO RYNKU: DC obok Elo ===")
    elo_by_book = {g.bookmaker: g for g in elo.pooled_gaps}
    for gap in dc.pooled_gaps:
        ref = elo_by_book.get(gap.bookmaker)
        out.append(
            f"  {gap.bookmaker:<17} n={gap.n:<5} "
            f"luka DC={gap.diff.mean_diff:+.4f} "
            f"[{gap.diff.ci_low:+.4f}, {gap.diff.ci_high:+.4f}]"
        )
        if ref is not None:
            delta = gap.diff.mean_diff - ref.diff.mean_diff
            out.append(
                f"  {'':<17} {'':<6} luka Elo={ref.diff.mean_diff:+.4f} "
                f"[{ref.diff.ci_low:+.4f}, {ref.diff.ci_high:+.4f}]  "
                f"zmiana={delta:+.4f}"
            )
    return "\n".join(out)
