"""Warstwa cech odporna na look-ahead bias.

Zasada projektowa
-----------------
Nie egzekwujemy braku przecieku dyscypliną, tylko czynimy go **niemożliwym
konstrukcyjnie**. Builder cechy nigdy nie dostaje surowych danych —
dostaje je przez warstwę, która odfiltrowała przyszłość, zanim on
cokolwiek zobaczył.

Dwa mechanizmy, nie jeden
-------------------------
To jest rozróżnienie, na którym stoi cały moduł, i miejsce, gdzie ludzie
najczęściej wprowadzają przeciek — mieszając jedno z drugim:

**Fakty sekwencyjne** (wyniki, strzały, gole z własnych meczów drużyny).
Czas obserwacji jest sztywno związany z meczem: wynik znamy po końcowym
gwizdku. Mechanizm: oś czasu w formacie długim + ``shift(1)`` PRZED
``rolling()``. Przesunięcie gwarantuje poprawność — patrz ``rolling_prior``.

**Fakty egzogeniczne** (kontuzje, składy, zmiana trenera, wartości
rynkowe). Czas obserwacji jest niezależny od meczu i musi przyjść z
danymi. Mechanizm: ``merge_asof`` z ``allow_exact_matches=False`` — patrz
``PointInTimeStore.asof_join``.

asof_utc, nie kickoff_utc
-------------------------
Moment odcięcia to chwila, w której realnie postawiłbyś zakład, czyli
``kickoff_utc - bet_lead_time``. Nie gwizdek. Jeśli stawiasz 24h przed
meczem, nie masz potwierdzonych składów — a model wytrenowany na składach
jest wtedy bezużyteczny w produkcji. ``bet_lead_time`` jest osią
eksperymentu, nie stałą zaszytą w kodzie.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol, runtime_checkable

import pandas as pd

__all__ = [
    "FeatureBuilder",
    "PointInTimeStore",
    "build_keys",
    "build_timeline",
    "compose",
    "rolling_prior",
    "rolling_prior_sum",
]

log = logging.getLogger(__name__)

#: Kolumny, które każdy zestaw kluczy musi mieć.
KEY_COLUMNS = ("match_id", "team_id", "kickoff_utc", "asof_utc")


def _require_utc(frame: pd.DataFrame, column: str, *, label: str) -> None:
    if column not in frame.columns:
        raise ValueError(f"{label}: brak kolumny {column!r}")
    dtype = frame[column].dtype
    if not isinstance(dtype, pd.DatetimeTZDtype):
        raise ValueError(  # noqa: TRY004 - zły dtype kolumny to błąd danych, nie typu
            f"{label}: kolumna {column!r} musi być tz-aware "
            f"(jest {dtype}). Naiwny czas to look-ahead bias, którego "
            "nie widać w żadnym teście — patrz reguła 2 w CLAUDE.md."
        )
    if str(dtype.tz) != "UTC":
        raise ValueError(f"{label}: kolumna {column!r} musi być w UTC, jest {dtype.tz}")


# ---------------------------------------------------------------------------
# Oś czasu
# ---------------------------------------------------------------------------


def build_timeline(matches: pd.DataFrame) -> pd.DataFrame:
    """Zamienia mecze (format szeroki) na oś drużyna-mecz (format długi).

    Wejście: jeden wiersz na mecz, kolumny ``match_id, kickoff_utc,
    home_team_id, away_team_id`` oraz opcjonalnie ``home_goals,
    away_goals`` i dowolne ``home_<stat>`` / ``away_<stat>``.

    Wyjście: dwa wiersze na mecz, po jednym na drużynę, z kolumnami
    ``team_id, opponent_id, is_home, goals_for, goals_against, points``
    plus rozpakowane statystyki jako ``<stat>_for`` / ``<stat>_against``.

    Po co format długi: średnia krocząca formy musi być liczona wzdłuż
    sekwencji meczów JEDNEJ drużyny. W formacie szerokim kolejne mecze
    tej samej drużyny leżą raz w kolumnie home, raz w away — i każda
    próba policzenia tam rollingu kończy się przeciekiem albo bzdurą.
    """
    required = {"match_id", "kickoff_utc", "home_team_id", "away_team_id"}
    missing = required - set(matches.columns)
    if missing:
        raise ValueError(f"build_timeline: brak kolumn {sorted(missing)}")
    _require_utc(matches, "kickoff_utc", label="build_timeline")

    stat_names = sorted(
        {
            col.removeprefix("home_")
            for col in matches.columns
            if col.startswith("home_") and f"away_{col.removeprefix('home_')}" in matches.columns
        }
        - {"team_id"}
    )

    sides = []
    for side, other in (("home", "away"), ("away", "home")):
        frame = pd.DataFrame(
            {
                "match_id": matches["match_id"],
                "kickoff_utc": matches["kickoff_utc"],
                "team_id": matches[f"{side}_team_id"],
                "opponent_id": matches[f"{other}_team_id"],
                "is_home": side == "home",
            }
        )
        for stat in stat_names:
            frame[f"{stat}_for"] = matches[f"{side}_{stat}"]
            frame[f"{stat}_against"] = matches[f"{other}_{stat}"]
        for extra in ("competition", "season"):
            if extra in matches.columns:
                frame[extra] = matches[extra]
        sides.append(frame)

    timeline = pd.concat(sides, ignore_index=True)

    if "goals_for" in timeline.columns and "goals_against" in timeline.columns:
        diff = timeline["goals_for"] - timeline["goals_against"]
        timeline["points"] = pd.Series(
            pd.NA, index=timeline.index, dtype="Float64"
        ).mask(diff.notna(), (diff > 0).astype("Float64") * 3 + (diff == 0).astype("Float64"))

    # Stabilne sortowanie: czas, a przy remisie match_id i strona. Bez
    # deterministycznej kolejności rolling daje różne wyniki między
    # uruchomieniami i backtest przestaje być odtwarzalny.
    return (
        timeline.sort_values(
            ["kickoff_utc", "match_id", "is_home"], kind="mergesort"
        ).reset_index(drop=True)
    )


def build_keys(
    matches: pd.DataFrame, *, bet_lead_time: timedelta
) -> pd.DataFrame:
    """Klucze budowania cech: jeden wiersz na drużynę-mecz z ``asof_utc``.

    ``asof_utc = kickoff_utc - bet_lead_time``. To jedyne miejsce, w którym
    ten moment jest wyliczany — dzięki temu zmiana horyzontu stawiania jest
    zmianą jednego parametru, a nie polowaniem po całym kodzie.
    """
    if bet_lead_time < timedelta(0):
        raise ValueError("bet_lead_time nie może być ujemny")
    timeline = build_timeline(matches)
    keys = timeline[["match_id", "team_id", "kickoff_utc"]].copy()
    keys["asof_utc"] = keys["kickoff_utc"] - bet_lead_time
    return keys.sort_values(["asof_utc", "match_id"], kind="mergesort").reset_index(
        drop=True
    )


# ---------------------------------------------------------------------------
# Fakty sekwencyjne
# ---------------------------------------------------------------------------


def _validate_timeline(timeline: pd.DataFrame, column: str) -> None:
    if column not in timeline.columns:
        raise ValueError(f"rolling_prior: brak kolumny {column!r}")
    if "team_id" not in timeline.columns:
        raise ValueError("rolling_prior: brak kolumny 'team_id'")
    _require_utc(timeline, "kickoff_utc", label="rolling_prior")
    if not timeline["kickoff_utc"].is_monotonic_increasing:
        raise ValueError(
            "rolling_prior: oś czasu musi być posortowana rosnąco po "
            "kickoff_utc. Niesortowany rolling cicho miesza przyszłość z "
            "przeszłością i nic tego nie sygnalizuje."
        )


def rolling_prior(
    timeline: pd.DataFrame,
    column: str,
    *,
    window: int,
    min_periods: int = 1,
) -> pd.Series:
    """Średnia z ``window`` POPRZEDNICH meczów drużyny.

    ``shift(1)`` idzie PRZED ``rolling()``, nie po. Kolejność ma znaczenie
    i jest to najczęstszy pojedynczy błąd w tego typu kodzie: okno bez
    przesunięcia zawiera bieżący mecz, czyli wynik, który próbujesz
    przewidzieć.

    Wiersze z niedostateczną historią dostają NaN. **Nie wypełniaj ich
    średnią globalną** — to statystyka policzona na pełnym zbiorze, czyli
    przeciek (reguła 3 w CLAUDE.md).
    """
    _validate_timeline(timeline, column)
    if window < 1:
        raise ValueError("window musi być >= 1")
    return timeline.groupby("team_id", sort=False)[column].transform(
        lambda s: s.shift(1).rolling(window, min_periods=min_periods).mean()
    )


def rolling_prior_sum(
    timeline: pd.DataFrame,
    column: str,
    *,
    window: int,
    min_periods: int = 1,
) -> pd.Series:
    """Jak ``rolling_prior``, ale suma zamiast średniej."""
    _validate_timeline(timeline, column)
    if window < 1:
        raise ValueError("window musi być >= 1")
    return timeline.groupby("team_id", sort=False)[column].transform(
        lambda s: s.shift(1).rolling(window, min_periods=min_periods).sum()
    )


# ---------------------------------------------------------------------------
# Fakty egzogeniczne
# ---------------------------------------------------------------------------


class PointInTimeStore:
    """Jedyna droga do faktów egzogenicznych. Fizycznie nie zwraca przyszłości.

    Każda tabela musi mieć kolumnę ``observed_at`` (tz-aware UTC) mówiącą,
    kiedy MOGLIŚMY się o danym fakcie dowiedzieć. Tabela bez niej jest
    odrzucana przy konstrukcji, a nie przy użyciu — błąd ma wyjść przy
    ładowaniu danych, nie trzy godziny później w środku backtestu.
    """

    def __init__(self, tables: dict[str, pd.DataFrame]) -> None:
        for name, frame in tables.items():
            _require_utc(frame, "observed_at", label=f"tabela {name!r}")
        self._tables = {name: frame.copy() for name, frame in tables.items()}

    @property
    def tables(self) -> tuple[str, ...]:
        return tuple(self._tables)

    def raw(self, table: str) -> pd.DataFrame:
        """Surowa tabela. Do inspekcji i testów — NIE do budowania cech."""
        return self._tables[table].copy()

    def asof_join(
        self,
        keys: pd.DataFrame,
        table: str,
        *,
        by: str | Sequence[str] = "team_id",
        columns: Sequence[str] | None = None,
        suffix: str = "",
        tolerance: timedelta | None = None,
    ) -> pd.DataFrame:
        """Ostatnia obserwacja STRICTLY przed ``asof_utc``, per klucz.

        Parameters
        ----------
        keys:
            Musi zawierać ``asof_utc`` i kolumny z ``by``.
        tolerance:
            Maksymalny wiek obserwacji. Kontuzja sprzed pół roku nie jest
            informacją o dzisiejszym składzie — bez tolerancji ``merge_asof``
            chętnie ją podstawi.

        Notes
        -----
        ``allow_exact_matches=False`` jest tu kluczowe i bywa pomijane.
        Daje ostre ``<`` zamiast ``<=``: fakt zaobserwowany DOKŁADNIE w
        momencie odcięcia jest odrzucany. Przy równych znacznikach czasu
        (a te zdarzają się nagminnie, gdy źródło podaje tylko datę)
        ``<=`` wpuszcza do cechy informację z tej samej chwili co zakład.
        """
        if table not in self._tables:
            raise KeyError(f"nieznana tabela: {table!r}. Dostępne: {self.tables}")
        _require_utc(keys, "asof_utc", label="keys")

        by_cols = [by] if isinstance(by, str) else list(by)
        facts = self._tables[table]
        missing = set(by_cols) - set(facts.columns)
        if missing:
            raise ValueError(f"tabela {table!r}: brak kolumn {sorted(missing)}")

        wanted = (
            list(columns)
            if columns is not None
            else [c for c in facts.columns if c not in {*by_cols, "observed_at"}]
        )
        facts = facts[[*by_cols, "observed_at", *wanted]]
        if suffix:
            facts = facts.rename(columns={c: f"{c}{suffix}" for c in wanted})
            wanted = [f"{c}{suffix}" for c in wanted]

        merged = pd.merge_asof(
            keys.sort_values("asof_utc", kind="mergesort"),
            facts.sort_values("observed_at", kind="mergesort"),
            left_on="asof_utc",
            right_on="observed_at",
            by=by_cols,
            direction="backward",
            allow_exact_matches=False,  # ostre <, nie <=. To NIE jest detal.
            tolerance=pd.Timedelta(tolerance) if tolerance is not None else None,
        )
        return merged.rename(columns={"observed_at": f"observed_at_{table}"})


# ---------------------------------------------------------------------------
# Kompozycja
# ---------------------------------------------------------------------------


@runtime_checkable
class FeatureBuilder(Protocol):
    """Kontrakt buildera cechy.

    Builder dostaje wyłącznie klucze i store. Nie dostaje surowej tabeli
    meczów i nie ma jak sięgnąć po przyszłość — to jest cała pointa.
    """

    name: str

    def build(self, keys: pd.DataFrame, store: PointInTimeStore) -> pd.DataFrame:
        """Zwraca ramkę z ``match_id``, ``team_id`` i kolumnami cech."""
        ...


@dataclass(frozen=True)
class _Composed:
    builders: tuple[FeatureBuilder, ...]

    def build(self, keys: pd.DataFrame, store: PointInTimeStore) -> pd.DataFrame:
        out = keys[["match_id", "team_id"]].copy()
        for builder in self.builders:
            produced = builder.build(keys, store)
            overlap = (set(produced.columns) - {"match_id", "team_id"}) & set(
                out.columns
            )
            if overlap:
                raise ValueError(
                    f"builder {builder.name!r} nadpisuje kolumny {sorted(overlap)}"
                )
            out = out.merge(produced, on=["match_id", "team_id"], how="left")
            if len(out) != len(keys):
                raise ValueError(
                    f"builder {builder.name!r} zmienił liczbę wierszy "
                    f"({len(keys)} -> {len(out)}); prawdopodobnie duplikaty "
                    "w kluczu match_id+team_id"
                )
        return out


def compose(*builders: FeatureBuilder) -> _Composed:
    """Łączy buildery w jeden, pilnując kolizji nazw i liczby wierszy."""
    names = [b.name for b in builders]
    duplicates = {n for n in names if names.count(n) > 1}
    if duplicates:
        raise ValueError(f"zduplikowane nazwy builderów: {sorted(duplicates)}")
    return _Composed(builders=builders)
