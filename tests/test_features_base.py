"""Testy warstwy cech.

Najważniejszy test w całym repo to ``test_future_poison_*``: wstrzykujemy
absurdalny mecz w przyszłość i sprawdzamy, że żadna cecha dla przeszłych
meczów się nie zmieniła. Jeśli przechodzi, nie ma look-ahead bias. Jeśli
pada, wiesz dokładnie w której kolumnie go masz.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from valuebet.features.base import (
    PointInTimeStore,
    build_keys,
    build_timeline,
    compose,
    rolling_prior,
    rolling_prior_sum,
)

T0 = datetime(2026, 3, 1, 18, 0, tzinfo=UTC)


def _matches() -> pd.DataFrame:
    """Sześć meczów, trzy drużyny, każda gra cztery razy."""
    rows = [
        # (dni, gospodarz, gość, gole_gosp, gole_gosc)
        (0, "A", "B", 2, 0),
        (7, "C", "A", 1, 1),
        (14, "B", "C", 3, 1),
        (21, "A", "C", 0, 2),
        (28, "B", "A", 1, 1),
        (35, "C", "B", 2, 2),
    ]
    return pd.DataFrame(
        {
            "match_id": [f"m{i}" for i in range(len(rows))],
            "kickoff_utc": [T0 + timedelta(days=d) for d, *_ in rows],
            "home_team_id": [h for _, h, *_ in rows],
            "away_team_id": [a for _, _, a, *_ in rows],
            "home_goals": [float(hg) for *_, hg, _ in rows],
            "away_goals": [float(ag) for *_, ag in rows],
        }
    )


# ---------------------------------------------------------------------------
# Oś czasu
# ---------------------------------------------------------------------------


def test_timeline_has_two_rows_per_match() -> None:
    tl = build_timeline(_matches())
    assert len(tl) == 12
    assert tl.groupby("match_id").size().eq(2).all()


def test_timeline_flips_goals_by_side() -> None:
    tl = build_timeline(_matches())
    m0 = tl[tl["match_id"] == "m0"].set_index("team_id")
    assert m0.loc["A", "goals_for"] == 2
    assert m0.loc["A", "goals_against"] == 0
    assert m0.loc["B", "goals_for"] == 0
    assert m0.loc["B", "goals_against"] == 2


def test_timeline_computes_points() -> None:
    tl = build_timeline(_matches())
    m0 = tl[tl["match_id"] == "m0"].set_index("team_id")
    assert m0.loc["A", "points"] == 3
    assert m0.loc["B", "points"] == 0
    m1 = tl[tl["match_id"] == "m1"].set_index("team_id")
    assert m1.loc["A", "points"] == 1


def test_timeline_is_time_sorted() -> None:
    tl = build_timeline(_matches())
    assert tl["kickoff_utc"].is_monotonic_increasing


def test_timeline_rejects_naive_kickoff() -> None:
    m = _matches()
    m["kickoff_utc"] = m["kickoff_utc"].dt.tz_localize(None)
    with pytest.raises(ValueError, match="tz-aware"):
        build_timeline(m)


def test_timeline_handles_missing_results() -> None:
    """Mecz przyszły nie ma wyniku — to nie może wysadzić budowania osi."""
    m = _matches()
    m.loc[5, ["home_goals", "away_goals"]] = None
    tl = build_timeline(m)
    future = tl[tl["match_id"] == "m5"]
    assert future["goals_for"].isna().all()
    assert future["points"].isna().all()


# ---------------------------------------------------------------------------
# Klucze
# ---------------------------------------------------------------------------


def test_asof_is_kickoff_minus_lead_time() -> None:
    keys = build_keys(_matches(), bet_lead_time=timedelta(hours=2))
    assert (keys["kickoff_utc"] - keys["asof_utc"]).eq(timedelta(hours=2)).all()


def test_lead_time_must_not_be_negative() -> None:
    with pytest.raises(ValueError, match="ujemny"):
        build_keys(_matches(), bet_lead_time=timedelta(hours=-1))


# ---------------------------------------------------------------------------
# rolling_prior — fakty sekwencyjne
# ---------------------------------------------------------------------------


def test_rolling_prior_excludes_current_match() -> None:
    """Sedno: okno NIE może zawierać meczu, który przewidujemy."""
    tl = build_timeline(_matches())
    tl["form"] = rolling_prior(tl, "goals_for", window=3)

    a = tl[tl["team_id"] == "A"].sort_values("kickoff_utc")
    # A: mecze m0(2), m1(1), m3(0), m4(1)
    assert pd.isna(a.iloc[0]["form"])              # brak historii
    assert a.iloc[1]["form"] == pytest.approx(2.0)  # średnia z [2]
    assert a.iloc[2]["form"] == pytest.approx(1.5)  # średnia z [2, 1]
    assert a.iloc[3]["form"] == pytest.approx(1.0)  # średnia z [2, 1, 0]


def test_rolling_prior_respects_window() -> None:
    tl = build_timeline(_matches())
    tl["form"] = rolling_prior(tl, "goals_for", window=2)
    a = tl[tl["team_id"] == "A"].sort_values("kickoff_utc")
    assert a.iloc[3]["form"] == pytest.approx(0.5)  # średnia z [1, 0], nie [2,1,0]


def test_rolling_prior_min_periods() -> None:
    tl = build_timeline(_matches())
    tl["form"] = rolling_prior(tl, "goals_for", window=3, min_periods=3)
    a = tl[tl["team_id"] == "A"].sort_values("kickoff_utc")
    assert a.iloc[:3]["form"].isna().all()
    assert not pd.isna(a.iloc[3]["form"])


def test_rolling_prior_does_not_mix_teams() -> None:
    tl = build_timeline(_matches())
    tl["form"] = rolling_prior(tl, "goals_for", window=5)
    first_per_team = tl.sort_values("kickoff_utc").groupby("team_id").head(1)
    assert first_per_team["form"].isna().all()


def test_rolling_prior_sum() -> None:
    tl = build_timeline(_matches())
    tl["total"] = rolling_prior_sum(tl, "goals_for", window=3)
    a = tl[tl["team_id"] == "A"].sort_values("kickoff_utc")
    assert a.iloc[3]["total"] == pytest.approx(3.0)  # 2 + 1 + 0


def test_rolling_prior_rejects_unsorted_timeline() -> None:
    tl = build_timeline(_matches()).sort_values("team_id")
    with pytest.raises(ValueError, match="posortowana"):
        rolling_prior(tl, "goals_for", window=3)


def test_rolling_prior_rejects_unknown_column() -> None:
    tl = build_timeline(_matches())
    with pytest.raises(ValueError, match="brak kolumny"):
        rolling_prior(tl, "nie_ma_takiej", window=3)


# ---------------------------------------------------------------------------
# PointInTimeStore — fakty egzogeniczne
# ---------------------------------------------------------------------------


def _injuries() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "team_id": ["A", "A", "A", "B"],
            "observed_at": pd.to_datetime(
                [
                    T0 - timedelta(days=1),   # przed m0
                    T0 + timedelta(days=10),  # między m1 a m3
                    T0 + timedelta(days=40),  # po wszystkim
                    T0 - timedelta(days=1),
                ],
                utc=True,
            ),
            "missing_value_share": [0.10, 0.35, 0.90, 0.05],
        }
    )


def _store() -> PointInTimeStore:
    return PointInTimeStore({"injuries": _injuries()})


def test_store_rejects_table_without_observed_at() -> None:
    with pytest.raises(ValueError, match="brak kolumny 'observed_at'"):
        PointInTimeStore({"bad": pd.DataFrame({"team_id": ["A"]})})


def test_store_rejects_naive_observed_at() -> None:
    frame = pd.DataFrame(
        {"team_id": ["A"], "observed_at": pd.to_datetime(["2026-03-01"])}
    )
    with pytest.raises(ValueError, match="tz-aware"):
        PointInTimeStore({"bad": frame})


def test_asof_join_takes_latest_prior_observation() -> None:
    keys = build_keys(_matches(), bet_lead_time=timedelta(hours=2))
    merged = _store().asof_join(keys, "injuries")

    a3 = merged[(merged["team_id"] == "A") & (merged["match_id"] == "m3")]
    # m3 jest w dniu 21; ostatnia obserwacja przed nim to ta z dnia 10.
    assert a3["missing_value_share"].iloc[0] == pytest.approx(0.35)


def test_asof_join_never_returns_future_observation() -> None:
    """Obserwacja z dnia 40 nie może trafić do żadnego meczu."""
    keys = build_keys(_matches(), bet_lead_time=timedelta(hours=2))
    merged = _store().asof_join(keys, "injuries")
    assert (merged["missing_value_share"] != 0.90).all()


def test_asof_join_is_null_before_first_observation() -> None:
    keys = build_keys(_matches(), bet_lead_time=timedelta(hours=2))
    merged = _store().asof_join(keys, "injuries")
    c = merged[merged["team_id"] == "C"]
    assert c["missing_value_share"].isna().all()  # brak danych dla C


def test_asof_join_uses_strict_inequality() -> None:
    """allow_exact_matches=False: obserwacja DOKŁADNIE w asof jest odrzucana.

    Przy źródłach podających samą datę równe znaczniki są nagminne, a
    '<=' wpuściłoby wtedy informację z tej samej chwili co zakład.
    """
    asof = T0
    keys = pd.DataFrame(
        {
            "match_id": ["x"],
            "team_id": ["A"],
            "kickoff_utc": pd.to_datetime([asof], utc=True),
            "asof_utc": pd.to_datetime([asof], utc=True),
        }
    )
    facts = pd.DataFrame(
        {
            "team_id": ["A"],
            "observed_at": pd.to_datetime([asof], utc=True),
            "value": [1.0],
        }
    )
    merged = PointInTimeStore({"f": facts}).asof_join(keys, "f")
    assert merged["value"].isna().all()


def test_asof_join_tolerance_rejects_stale_facts() -> None:
    """Kontuzja sprzed pół roku nie jest informacją o dzisiejszym składzie."""
    keys = build_keys(_matches(), bet_lead_time=timedelta(hours=2))
    merged = _store().asof_join(keys, "injuries", tolerance=timedelta(days=5))

    a3 = merged[(merged["team_id"] == "A") & (merged["match_id"] == "m3")]
    # Obserwacja z dnia 10 ma 11 dni w momencie m3 — poza tolerancją.
    assert a3["missing_value_share"].isna().all()


def test_asof_join_preserves_row_count() -> None:
    keys = build_keys(_matches(), bet_lead_time=timedelta(hours=2))
    merged = _store().asof_join(keys, "injuries")
    assert len(merged) == len(keys)


def test_asof_join_rejects_unknown_table() -> None:
    keys = build_keys(_matches(), bet_lead_time=timedelta(hours=2))
    with pytest.raises(KeyError, match="nieznana tabela"):
        _store().asof_join(keys, "nie_ma")


# ---------------------------------------------------------------------------
# TEST TRUCIZNY — najważniejszy w repo
# ---------------------------------------------------------------------------


def _build_all(matches: pd.DataFrame, store: PointInTimeStore) -> pd.DataFrame:
    """Pełny pipeline cech — dokładnie ten, który pójdzie do modelu."""
    tl = build_timeline(matches)
    tl["form_goals_3"] = rolling_prior(tl, "goals_for", window=3)
    tl["form_conceded_3"] = rolling_prior(tl, "goals_against", window=3)
    tl["form_points_5"] = rolling_prior(tl, "points", window=5)
    tl["total_goals_5"] = rolling_prior_sum(tl, "goals_for", window=5)

    keys = build_keys(matches, bet_lead_time=timedelta(hours=2))
    exog = store.asof_join(keys, "injuries", columns=["missing_value_share"])

    out = tl[
        [
            "match_id",
            "team_id",
            "form_goals_3",
            "form_conceded_3",
            "form_points_5",
            "total_goals_5",
        ]
    ].merge(
        exog[["match_id", "team_id", "missing_value_share"]],
        on=["match_id", "team_id"],
        how="left",
    )
    return out.sort_values(["match_id", "team_id"]).reset_index(drop=True)


def test_future_poison_sequential_facts() -> None:
    """Absurdalny mecz w przyszłości nie może zmienić ŻADNEJ przeszłej cechy."""
    matches = _matches()
    store = _store()
    baseline = _build_all(matches, store)

    poisoned_matches = pd.concat(
        [
            matches,
            pd.DataFrame(
                {
                    "match_id": ["POISON"],
                    "kickoff_utc": [T0 + timedelta(days=99)],
                    "home_team_id": ["A"],
                    "away_team_id": ["B"],
                    "home_goals": [99.0],
                    "away_goals": [99.0],
                }
            ),
        ],
        ignore_index=True,
    )
    after = _build_all(poisoned_matches, store)
    after = after[after["match_id"] != "POISON"].reset_index(drop=True)

    pd.testing.assert_frame_equal(baseline, after)


def test_future_poison_exogenous_facts() -> None:
    """To samo dla faktów egzogenicznych: kontuzja z przyszłości nie wycieka."""
    matches = _matches()
    baseline = _build_all(matches, _store())

    poisoned = _injuries().copy()
    poisoned = pd.concat(
        [
            poisoned,
            pd.DataFrame(
                {
                    "team_id": ["A"],
                    "observed_at": pd.to_datetime(
                        [T0 + timedelta(days=99)], utc=True
                    ),
                    "missing_value_share": [999.0],
                }
            ),
        ],
        ignore_index=True,
    )
    after = _build_all(matches, PointInTimeStore({"injuries": poisoned}))

    pd.testing.assert_frame_equal(baseline, after)


def test_future_poison_detects_a_real_leak() -> None:
    """Kontrola samego testu: celowo dziurawy pipeline MUSI go wywalić.

    Bez tego nie wiadomo, czy test trucizny cokolwiek sprawdza, czy tylko
    zawsze przechodzi.
    """

    def leaky(matches: pd.DataFrame) -> pd.DataFrame:
        tl = build_timeline(matches)
        # Brak shift(1) — okno zawiera bieżący mecz. Klasyczny przeciek.
        tl["form"] = tl.groupby("team_id", sort=False)["goals_for"].transform(
            lambda s: s.rolling(3, min_periods=1).mean()
        )
        return (
            tl[["match_id", "team_id", "form"]]
            .sort_values(["match_id", "team_id"])
            .reset_index(drop=True)
        )

    matches = _matches()
    baseline = leaky(matches)

    # Zmieniamy wynik OSTATNIEGO meczu. W poprawnym pipeline nie zmienia to
    # niczego wcześniejszego. W dziurawym — zmienia cechę tego meczu.
    tampered = matches.copy()
    tampered.loc[tampered["match_id"] == "m5", "home_goals"] = 99.0
    after = leaky(tampered)

    with pytest.raises(AssertionError):
        pd.testing.assert_frame_equal(baseline, after)


# ---------------------------------------------------------------------------
# Kompozycja
# ---------------------------------------------------------------------------


class _Dummy:
    def __init__(self, name: str, column: str) -> None:
        self.name = name
        self._column = column

    def build(self, keys: pd.DataFrame, store: PointInTimeStore) -> pd.DataFrame:
        out = keys[["match_id", "team_id"]].copy()
        out[self._column] = 1.0
        return out


def test_compose_merges_builders() -> None:
    keys = build_keys(_matches(), bet_lead_time=timedelta(hours=2))
    composed = compose(_Dummy("a", "x"), _Dummy("b", "y"))
    out = composed.build(keys, _store())
    assert {"x", "y"} <= set(out.columns)
    assert len(out) == len(keys)


def test_compose_rejects_duplicate_names() -> None:
    with pytest.raises(ValueError, match="zduplikowane nazwy"):
        compose(_Dummy("a", "x"), _Dummy("a", "y"))


def test_compose_rejects_column_collision() -> None:
    keys = build_keys(_matches(), bet_lead_time=timedelta(hours=2))
    composed = compose(_Dummy("a", "x"), _Dummy("b", "x"))
    with pytest.raises(ValueError, match="nadpisuje kolumny"):
        composed.build(keys, _store())
