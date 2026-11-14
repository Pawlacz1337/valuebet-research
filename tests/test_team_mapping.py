"""Testy mapowania nazw drużyn.

Najważniejsze są dwa: że polskie diakrytyki i szum organizacyjny nie
rozbijają dopasowania, oraz że podobne nazwy różnych klubów NIE sklejają
się automatycznie.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from valuebet.ingest.team_mapping import AliasStore, TeamResolver, normalise_name

ALIASES_PATH = Path(__file__).resolve().parents[1] / "data" / "team_aliases.yaml"


@pytest.fixture
def store() -> AliasStore:
    return AliasStore.from_yaml(ALIASES_PATH)


@pytest.fixture
def resolver(store: AliasStore) -> TeamResolver:
    return TeamResolver(store)


# ---------------------------------------------------------------------------
# Normalizacja
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Górnik Zabrze", "gornik zabrze"),
        ("Gornik Zabrze", "gornik zabrze"),
        ("KS Górnik Zabrze S.A.", "gornik zabrze"),
        ("  LECH   POZNAŃ  ", "lech poznan"),
        ("Śląsk Wrocław", "slask wroclaw"),
        ("Łódź", "lodz"),
        ("Pogoń Szczecin", "pogon szczecin"),
        ("MKS Cracovia", "cracovia"),
    ],
)
def test_normalise_strips_diacritics_and_noise(raw: str, expected: str) -> None:
    assert normalise_name(raw) == expected


def test_normalise_keeps_real_words_that_look_like_noise() -> None:
    """'Ruch' i 'Stal' to nazwy, nie szum — nie wolno ich usunąć."""
    assert normalise_name("Ruch Chorzów") == "ruch chorzow"
    assert normalise_name("Stal Mielec") == "stal mielec"


def test_normalise_survives_pure_noise_name() -> None:
    """Nazwa z samych tokenów organizacyjnych nie może dać pustego klucza."""
    assert normalise_name("FC") != ""
    assert normalise_name("FC") != normalise_name("KS")


# ---------------------------------------------------------------------------
# Rozwiązywanie
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Lech Poznań", "lech-poznan"),
        ("Lech Poznan", "lech-poznan"),
        ("KKS Lech Poznan", "lech-poznan"),
        ("lech", "lech-poznan"),
        ("Legia Warsaw", "legia-warszawa"),
        ("Raków Częstochowa", "rakow-czestochowa"),
        ("Rakow", "rakow-czestochowa"),
        ("Śląsk Wrocław", "slask-wroclaw"),
        ("Slask Wroclaw", "slask-wroclaw"),
    ],
)
def test_resolves_known_variants(
    resolver: TeamResolver, name: str, expected: str
) -> None:
    assert resolver.resolve(name) == expected


def test_returns_none_for_unknown(resolver: TeamResolver) -> None:
    assert resolver.resolve("Nieistniejący Klub Sportowy") is None


def test_strict_raises_with_hints(resolver: TeamResolver) -> None:
    with pytest.raises(KeyError, match="nieznana drużyna"):
        resolver.resolve_strict("Lech Poznanski")


# ---------------------------------------------------------------------------
# Sedno: podobne nazwy różnych klubów
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("Ruch Chorzów", "Ruch Radzionków"),
        ("Górnik Zabrze", "Górnik Łęczna"),
        ("Stal Mielec", "Stal Rzeszów"),
        ("Wisła Kraków", "Wisła Płock"),
    ],
)
def test_similar_names_are_not_merged(
    resolver: TeamResolver, a: str, b: str
) -> None:
    """To jest powód, dla którego fuzzy nie zatwierdza automatycznie."""
    ra, rb = resolver.resolve(a), resolver.resolve(b)
    assert ra is not None and rb is not None
    assert ra != rb


@pytest.mark.parametrize(
    ("query", "a", "b"),
    [
        ("Ruch", "ruch-chorzow", "ruch-radzionkow"),
        ("Gornik", "gornik-zabrze", "gornik-leczna"),
        ("Stal", "stal-mielec", "stal-rzeszow"),
        ("Wisla", "wisla-krakow", "wisla-plock"),
    ],
)
def test_fuzzy_ties_between_different_clubs(
    resolver: TeamResolver, query: str, a: str, b: str
) -> None:
    """Dowód, dla którego automatyczny próg jest niebezpieczny.

    Sama nazwa klubu bez miasta daje IDENTYCZNY score dla dwóch różnych
    drużyn. Automatyczna akceptacja wybrałaby jedną z nich arbitralnie —
    kolejnością słownika — i nikt by tego nie zauważył przez pół roku.
    """
    suggestions = dict(resolver.suggest(query, limit=5))
    assert a in suggestions
    assert b in suggestions
    assert suggestions[a] == pytest.approx(suggestions[b])

    # A mimo wysokich score'ów resolve nie zwraca nic.
    assert resolver.resolve(query) is None


# ---------------------------------------------------------------------------
# Raport i pokrycie
# ---------------------------------------------------------------------------


def test_report_sorts_by_occurrences(resolver: TeamResolver) -> None:
    for _ in range(3):
        resolver.resolve("Klub A")
    resolver.resolve("Klub B")

    report = resolver.report_unresolved()
    assert report[0].raw == "Klub A"
    assert report[0].occurrences == 3
    assert report[1].occurrences == 1


def test_report_carries_suggestions(resolver: TeamResolver) -> None:
    resolver.resolve("Lech Poznanski")
    report = resolver.report_unresolved()
    assert report[0].suggestions
    assert report[0].suggestions[0][0] == "lech-poznan"


def test_coverage_tracks_hits_and_misses(resolver: TeamResolver) -> None:
    resolver.resolve("Lech Poznań")
    resolver.resolve("Legia Warszawa")
    resolver.resolve("Nieznany Klub")
    assert resolver.coverage() == pytest.approx(2 / 3)


def test_coverage_is_one_when_nothing_queried(resolver: TeamResolver) -> None:
    assert resolver.coverage() == 1.0


def test_reset_stats(resolver: TeamResolver) -> None:
    resolver.resolve("Nieznany")
    resolver.reset_stats()
    assert resolver.coverage() == 1.0
    assert not resolver.misses


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


def test_ambiguous_alias_is_rejected() -> None:
    """Ten sam alias na dwie drużyny to błąd konfiguracji, nie ostrzeżenie."""
    with pytest.raises(ValueError, match="dwie drużyny"):
        AliasStore(
            {
                "team-a": {"canonical_name": "Team A", "aliases": ["Wspolny"]},
                "team-b": {"canonical_name": "Team B", "aliases": ["Wspólny"]},
            }
        )


def test_add_alias_then_resolves(store: AliasStore) -> None:
    resolver = TeamResolver(store)
    assert resolver.resolve("Kolejorz") is None
    store.add_alias("lech-poznan", "Kolejorz")
    assert resolver.resolve("Kolejorz") == "lech-poznan"


def test_add_alias_rejects_unknown_team(store: AliasStore) -> None:
    with pytest.raises(KeyError, match="nieznane team_id"):
        store.add_alias("nie-ma-takiej", "X")


def test_add_team_rejects_duplicate(store: AliasStore) -> None:
    with pytest.raises(KeyError, match="już istnieje"):
        store.add_team("lech-poznan", "Lech Poznań")


def test_roundtrip_yaml(tmp_path: Path, store: AliasStore) -> None:
    out = tmp_path / "aliases.yaml"
    store.to_yaml(out)
    reloaded = AliasStore.from_yaml(out)
    assert set(reloaded.team_ids) == set(store.team_ids)
    assert TeamResolver(reloaded).resolve("Lech Poznań") == "lech-poznan"


def test_missing_file_yields_empty_store(tmp_path: Path) -> None:
    empty = AliasStore.from_yaml(tmp_path / "nie-ma.yaml")
    assert empty.team_ids == ()
    assert TeamResolver(empty).suggest("cokolwiek") == []


def test_shipped_yaml_is_valid_and_unambiguous() -> None:
    """Plik w repo musi się ładować bez kolizji aliasów."""
    raw = yaml.safe_load(ALIASES_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, dict) and raw
    store = AliasStore(raw)
    assert len(store.team_ids) >= 15
