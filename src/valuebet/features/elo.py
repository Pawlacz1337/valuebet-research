"""Rating Elo dla piłki nożnej — implementacja pętlowa, celowo niewektoryzowana.

Dlaczego pętla, a nie wektoryzacja
-----------------------------------
Elo jest z definicji rekurencyjny: rating przed meczem N+1 zależy od
wyniku meczu N. Nie da się tego policzyć jednym przebiegiem po kolumnie,
a każda próba kończy się jednym z dwóch błędów:

- ``groupby().shift()`` na gotowych ratingach — wygląda poprawnie, ale
  ratingi trzeba najpierw skądś wziąć, a biorą się z przyszłości;
- ``cumsum`` po zmianach ratingu — ignoruje to, że zmiana zależy od
  ratingu przeciwnika w TAMTYM momencie, nie dzisiejszego.

Zwektoryzowany Elo to prawie zawsze Elo powypadkowy. Pętla jest wolniejsza
o dwa rzędy wielkości i przy 50 tysiącach meczów wykonuje się w sekundy,
więc optymalizacja nie ma tu żadnego uzasadnienia — a ryzyko ma.

Kontrakt
--------
Funkcja emituje ``home_elo_before`` / ``away_elo_before``: stan SPRZED
gwizdka. Aktualizacja następuje dopiero po zapisaniu tych wartości, w tej
kolejności i nigdy odwrotnie.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import cast

import numpy as np
import pandas as pd

__all__ = ["EloConfig", "EloRatings", "compute_elo", "expected_score"]

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class EloConfig:
    """Parametry Elo.

    Attributes
    ----------
    initial:
        Rating drużyny bez historii.
    k:
        Szybkość adaptacji. 20 to rozsądny start dla ligi krajowej; wyżej
        = szybsza reakcja i więcej szumu.
    home_advantage:
        Przewaga własnego boiska w punktach Elo. ~65 odpowiada mniej
        więcej 0.35 gola w Ekstraklasie, ale **dostrój to na swoich
        danych** — atut własnego boiska wyraźnie osłabł po 2020.
    goal_diff_scaling:
        Czy skalować K różnicą bramek (jak ClubElo i FiveThirtyEight).
        Wygrana 4:0 niesie więcej informacji niż 1:0.
    season_carry:
        Ile ratingu ponad średnią przenosi się na nowy sezon. 0.75 oznacza
        ściągnięcie 25% odchylenia do średniej — transfery i zmiany kadrowe
        sprawiają, że drużyna z czerwca to nie ta sama drużyna co w lipcu.
        Wymaga kolumny ``season``.
    """

    initial: float = 1500.0
    k: float = 20.0
    home_advantage: float = 65.0
    goal_diff_scaling: bool = True
    season_carry: float = 0.75

    def __post_init__(self) -> None:
        if self.k <= 0:
            raise ValueError("k musi być dodatnie")
        if not 0.0 <= self.season_carry <= 1.0:
            raise ValueError("season_carry musi być w [0, 1]")


def expected_score(rating_a: float, rating_b: float) -> float:
    """Oczekiwany wynik A w skali [0, 1]. Remis liczy się jako 0.5."""
    return float(1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0)))


def _goal_multiplier(goal_diff: int) -> float:
    """Mnożnik K zależny od różnicy bramek (wzór FiveThirtyEight).

    Tłumi też autokorelację: bez tego wysokie zwycięstwa faworytów
    rozpędzają rating w nieskończoność.
    """
    if goal_diff == 0:
        return 1.0
    return float(np.log1p(abs(goal_diff)))


@dataclass
class EloRatings:
    """Wynik przebiegu: cechy per mecz plus końcowy stan ratingów."""

    features: pd.DataFrame
    final: dict[str, float]
    config: EloConfig
    _history: list[tuple[pd.Timestamp, str, float]] = field(default_factory=list)

    def rating(self, team_id: str) -> float:
        return self.final.get(team_id, self.config.initial)

    def history(self) -> pd.DataFrame:
        """Pełna ścieżka ratingów — do wykresów i diagnostyki."""
        return pd.DataFrame(
            self._history, columns=["kickoff_utc", "team_id", "rating_after"]
        )


def compute_elo(
    matches: pd.DataFrame,
    config: EloConfig | None = None,
    *,
    initial_ratings: dict[str, float] | None = None,
) -> EloRatings:
    """Liczy Elo chronologicznie, emitując rating SPRZED każdego meczu.

    Parameters
    ----------
    matches:
        Kolumny wymagane: ``match_id``, ``kickoff_utc`` (tz-aware UTC),
        ``home_team_id``, ``away_team_id``. Wynik (``home_goals``,
        ``away_goals``) opcjonalny — mecze bez wyniku dostają cechy, ale
        nie aktualizują ratingów. Dzięki temu tą samą funkcją liczysz
        cechy dla przyszłej kolejki.
        Kolumna ``season`` włącza carry-over międzysezonowy.
    initial_ratings:
        Stan startowy, np. z poprzedniego przebiegu. Pozwala dokładać
        nowe mecze bez przeliczania całej historii.

    Returns
    -------
    EloRatings
        ``features`` ma ``match_id``, ``home_elo_before``,
        ``away_elo_before``, ``elo_diff`` (z uwzględnieniem atutu boiska)
        oraz ``elo_expected_home``.
    """
    config = config or EloConfig()

    required = {"match_id", "kickoff_utc", "home_team_id", "away_team_id"}
    missing = required - set(matches.columns)
    if missing:
        raise ValueError(f"compute_elo: brak kolumn {sorted(missing)}")

    dtype = matches["kickoff_utc"].dtype
    if not isinstance(dtype, pd.DatetimeTZDtype):
        raise ValueError(  # noqa: TRY004 - zły dtype kolumny to błąd danych, nie typu
            f"compute_elo: kickoff_utc musi być tz-aware, jest {dtype}"
        )

    has_result = {"home_goals", "away_goals"} <= set(matches.columns)
    has_season = "season" in matches.columns

    # Sortowanie stabilne i deterministyczne. Bez tego dwa przebiegi na
    # tych samych danych mogą dać różne ratingi, a backtest przestaje być
    # odtwarzalny.
    ordered = matches.sort_values(
        ["kickoff_utc", "match_id"], kind="mergesort"
    ).reset_index(drop=True)

    ratings: dict[str, float] = dict(initial_ratings or {})
    last_season: dict[str, str] = {}
    history: list[tuple[pd.Timestamp, str, float]] = []

    out_home: list[float] = []
    out_away: list[float] = []

    for row in ordered.itertuples(index=False):
        home = str(row.home_team_id)
        away = str(row.away_team_id)
        kickoff = cast("pd.Timestamp", row.kickoff_utc)

        home_rating = ratings.get(home, config.initial)
        away_rating = ratings.get(away, config.initial)

        # Carry-over na starcie nowego sezonu, PRZED odczytem cechy —
        # pierwszy mecz sezonu ma już ściągnięty rating.
        if has_season:
            season = str(row.season)
            for team, rating in ((home, home_rating), (away, away_rating)):
                if last_season.get(team) not in (None, season):
                    ratings[team] = config.initial + config.season_carry * (
                        rating - config.initial
                    )
                last_season[team] = season
            home_rating = ratings.get(home, config.initial)
            away_rating = ratings.get(away, config.initial)

        # --- ZAPIS CECHY. Wszystko poniżej tej linii to już przyszłość. ---
        out_home.append(home_rating)
        out_away.append(away_rating)

        if not has_result:
            continue
        home_goals, away_goals = row.home_goals, row.away_goals
        if pd.isna(home_goals) or pd.isna(away_goals):
            # Mecz jeszcze nierozegrany — cecha policzona, rating bez zmian.
            continue

        home_goals, away_goals = int(float(home_goals)), int(float(away_goals))  # type: ignore[arg-type]
        if home_goals > away_goals:
            actual = 1.0
        elif home_goals == away_goals:
            actual = 0.5
        else:
            actual = 0.0

        expected = expected_score(
            home_rating + config.home_advantage, away_rating
        )
        multiplier = (
            _goal_multiplier(home_goals - away_goals)
            if config.goal_diff_scaling
            else 1.0
        )
        delta = config.k * multiplier * (actual - expected)

        # Gra o sumie zerowej: ile zyskuje jedna drużyna, tyle traci druga.
        ratings[home] = home_rating + delta
        ratings[away] = away_rating - delta

        history.append((kickoff, home, ratings[home]))
        history.append((kickoff, away, ratings[away]))

    features = pd.DataFrame(
        {
            "match_id": ordered["match_id"].to_numpy(),
            "home_elo_before": out_home,
            "away_elo_before": out_away,
        }
    )
    features["elo_diff"] = (
        features["home_elo_before"] + config.home_advantage
    ) - features["away_elo_before"]
    features["elo_expected_home"] = 1.0 / (
        1.0 + 10.0 ** (-features["elo_diff"] / 400.0)
    )

    return EloRatings(
        features=features,
        final=ratings,
        config=config,
        _history=history,
    )
