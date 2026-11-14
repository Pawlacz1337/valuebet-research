"""Mapowanie nazw drużyn na kanoniczne ID.

Dlaczego to jest krytyczne, mimo że wygląda na nudne
-----------------------------------------------------
Błąd matchowania nazw jest **cichy**. Jeśli "Górnik Zabrze" z
football-data nie skojarzy się z "Gornik Zabrze" z drugiego źródła,
nie dostaniesz wyjątku — dostaniesz mniej meczów w zbiorze. I to mniej
w sposób skorelowany z tym, które drużyny mają nietypowe nazwy, czyli
zwykle te mniejsze i słabsze. To jest survivorship bias wprowadzony
literówką.

Dlatego rapidfuzz jest tu **wyłącznie generatorem sugestii do ręcznego
zatwierdzenia**, nigdy automatycznym dopasowaniem (reguła 15 w
CLAUDE.md). ``resolve()`` zwraca None, kiedy nie ma pewnego trafienia, a
``report_unresolved()`` produkuje listę do przejrzenia. Automatyczne
dopasowanie przy progu 85 skleiłoby "Ruch Chorzów" z "Ruch Radzionków",
i nikt by tego nie zauważył przez pół roku.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from rapidfuzz import fuzz, process

__all__ = [
    "AliasStore",
    "TeamResolver",
    "UnresolvedName",
    "normalise_name",
]

log = logging.getLogger(__name__)

#: Tokeny organizacyjne bez wartości rozróżniającej. "Ruch" i "Zagłębie"
#: NIE mogą tu trafić — to są prawdziwe nazwy, a nie szum.
_NOISE_TOKENS = frozenset(
    {
        "fc", "sc", "ac", "afc", "cf", "fk", "sk",
        "ks", "mks", "gks", "lks", "zks", "rks", "wks", "ts", "kks", "oks",
        "sa", "spa", "sad", "klub", "sportowy", "miejski", "gminny",
        "stowarzyszenie", "team", "club",
    }
)  # fmt: skip

_PUNCT = re.compile(r"[^\w\s]", flags=re.UNICODE)
_SPACES = re.compile(r"\s+")

#: Litery, których NFKD NIE rozkłada, bo to osobne znaki alfabetu, a nie
#: litery z diakrytykiem. Polskie "ł" jest tu najważniejsze: bez tej mapy
#: Łódź, Wrocław, Zagłębie, Płock i Łęczna nie dopasowują się do swoich
#: bezogonkowych wariantów — i tracisz je ze zbioru bez żadnego błędu.
_LETTER_MAP = str.maketrans(
    {
        "ł": "l", "Ł": "L",
        "đ": "d", "Đ": "D",
        "ø": "o", "Ø": "O",
        "æ": "ae", "Æ": "AE",
        "œ": "oe", "Œ": "OE",
        "ß": "ss",
        "þ": "th", "Þ": "TH",
        "ð": "d", "Ð": "D",
        "ı": "i", "İ": "I",  # noqa: RUF001 - tureckie i bez kropki, celowo
    }
)  # fmt: skip


def normalise_name(name: str) -> str:
    """Kanoniczna postać nazwy do porównań.

    Usuwa diakrytyki, interpunkcję, tokeny organizacyjne, formy prawne i
    nadmiarowe spacje. "KS Górnik Zabrze S.A." i "Gornik Zabrze" dają to
    samo.
    """
    mapped = name.translate(_LETTER_MAP)
    nfkd = unicodedata.normalize("NFKD", mapped)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = _PUNCT.sub(" ", ascii_only.lower())

    raw_tokens = [t for t in _SPACES.split(cleaned) if t]
    tokens = [
        t
        for t in raw_tokens
        # Pojedyncze litery to resztki po formach prawnych ("S.A." -> "s","a").
        # Cyfry zostawiamy — bywają częścią nazwy (np. rok założenia).
        if t not in _NOISE_TOKENS and not (len(t) == 1 and t.isalpha())
    ]
    if not tokens:
        # Nazwa złożona wyłącznie z szumu — zachowaj oryginał, bo pusty
        # klucz skleiłby ze sobą wszystkie takie przypadki.
        tokens = raw_tokens
    return " ".join(tokens)


@dataclass(frozen=True)
class UnresolvedName:
    """Nazwa, której nie udało się skojarzyć — do ręcznego przejrzenia."""

    raw: str
    normalised: str
    occurrences: int
    suggestions: tuple[tuple[str, float], ...]

    def as_yaml_stub(self) -> str:
        """Gotowy fragment do wklejenia do pliku aliasów."""
        best = self.suggestions[0][0] if self.suggestions else "TODO-canonical-id"
        return f"  {best}:\n    aliases:\n      - {self.raw!r}  # score?"


class AliasStore:
    """Plik YAML z kanonicznymi drużynami i ich aliasami.

    Format::

        lech-poznan:
          canonical_name: Lech Poznań
          country: PL
          aliases:
            - Lech
            - KKS Lech Poznan
          external_ids:
            api_football: "341"
    """

    def __init__(self, entries: dict[str, dict[str, Any]]) -> None:
        self._entries = entries
        self._by_norm: dict[str, str] = {}
        self._build_index()

    def _build_index(self) -> None:
        for team_id, payload in self._entries.items():
            names = [payload.get("canonical_name", team_id), team_id]
            names.extend(payload.get("aliases", []) or [])
            for name in names:
                key = normalise_name(str(name))
                existing = self._by_norm.get(key)
                if existing is not None and existing != team_id:
                    raise ValueError(
                        f"alias {name!r} (znormalizowany: {key!r}) wskazuje na "
                        f"dwie drużyny: {existing!r} i {team_id!r}. "
                        "Niejednoznaczny alias musi zostać usunięty."
                    )
                self._by_norm[key] = team_id

    @classmethod
    def from_yaml(cls, path: Path) -> AliasStore:
        if not Path(path).exists():
            return cls({})
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError(  # noqa: TRY004 - zła zawartość pliku, nie typ argumentu
                f"{path}: oczekiwano mapowania na najwyższym poziomie"
            )
        return cls(raw)

    def to_yaml(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(
            yaml.safe_dump(self._entries, allow_unicode=True, sort_keys=True),
            encoding="utf-8",
        )

    @property
    def team_ids(self) -> tuple[str, ...]:
        return tuple(self._entries)

    def lookup(self, name: str) -> str | None:
        return self._by_norm.get(normalise_name(name))

    def canonical_name(self, team_id: str) -> str:
        return str(self._entries.get(team_id, {}).get("canonical_name", team_id))

    def add_alias(self, team_id: str, alias: str) -> None:
        """Dopisuje alias. Zatwierdzone ręcznie, nie automatycznie."""
        if team_id not in self._entries:
            raise KeyError(f"nieznane team_id: {team_id!r}")
        aliases = list(self._entries[team_id].get("aliases") or [])
        if alias not in aliases:
            aliases.append(alias)
        self._entries[team_id]["aliases"] = aliases
        self._build_index()

    def add_team(
        self,
        team_id: str,
        canonical_name: str,
        *,
        country: str | None = None,
        aliases: Iterable[str] = (),
    ) -> None:
        if team_id in self._entries:
            raise KeyError(f"team_id już istnieje: {team_id!r}")
        payload: dict[str, Any] = {"canonical_name": canonical_name}
        if country:
            payload["country"] = country
        if aliases:
            payload["aliases"] = list(aliases)
        self._entries[team_id] = payload
        self._build_index()


class TeamResolver:
    """Rozwiązuje nazwy na team_id. Fuzzy tylko jako sugestia.

    Parameters
    ----------
    store:
        Słownik aliasów.
    suggestion_cutoff:
        Minimalny score, żeby kandydat w ogóle trafił do sugestii. To NIE
        jest próg akceptacji — akceptacji automatycznej nie ma.
    """

    def __init__(self, store: AliasStore, *, suggestion_cutoff: float = 70.0) -> None:
        self.store = store
        self.suggestion_cutoff = suggestion_cutoff
        self._misses: Counter[str] = Counter()
        self._hits = 0

    def resolve(self, name: str) -> str | None:
        """Zwraca team_id albo None. Nigdy nie zgaduje."""
        hit = self.store.lookup(name)
        if hit is None:
            self._misses[name] += 1
        else:
            self._hits += 1
        return hit

    def resolve_strict(self, name: str) -> str:
        """Jak resolve, ale podnosi wyjątek zamiast zwracać None.

        Używaj w pipeline produkcyjnym, gdzie cicha strata meczu jest
        gorsza niż zatrzymanie przebiegu.
        """
        hit = self.resolve(name)
        if hit is None:
            hints = ", ".join(f"{t} ({s:.0f})" for t, s in self.suggest(name)[:3])
            raise KeyError(
                f"nieznana drużyna: {name!r}. Kandydaci: {hints or 'brak'}. "
                "Dopisz alias do pliku YAML — nie obchodź tego fuzzy-matchem."
            )
        return hit

    def suggest(self, name: str, limit: int = 5) -> list[tuple[str, float]]:
        """Kandydaci do RĘCZNEGO zatwierdzenia, posortowani malejąco."""
        candidates = {
            team_id: normalise_name(self.store.canonical_name(team_id))
            for team_id in self.store.team_ids
        }
        if not candidates:
            return []
        matches = process.extract(
            normalise_name(name),
            candidates,
            scorer=fuzz.WRatio,
            limit=limit,
            score_cutoff=self.suggestion_cutoff,
        )
        return [(team_id, float(score)) for _, score, team_id in matches]

    def resolve_many(self, names: Iterable[str]) -> dict[str, str | None]:
        return {name: self.resolve(name) for name in names}

    @property
    def misses(self) -> Counter[str]:
        return self._misses

    def report_unresolved(self, limit: int = 5) -> list[UnresolvedName]:
        """Raport do przejrzenia. Przejdź go, ZANIM ruszysz dalej.

        Nieskojarzone nazwy posortowane po liczbie wystąpień — najpierw te,
        które kosztują najwięcej meczów.
        """
        return [
            UnresolvedName(
                raw=raw,
                normalised=normalise_name(raw),
                occurrences=count,
                suggestions=tuple(self.suggest(raw, limit=limit)),
            )
            for raw, count in self._misses.most_common()
        ]

    def coverage(self) -> float:
        """Udział rozwiązanych zapytań w całości.

        Wartość poniżej 1.0 to mecze, które wypadną ze zbioru. Traktuj to
        jak metrykę jakości danych i pilnuj jej po każdym nowym źródle —
        spadek z 1.00 na 0.97 to trzy procent meczów, które znikną bez
        żadnego komunikatu.
        """
        total = self._hits + sum(self._misses.values())
        return 1.0 if total == 0 else self._hits / total

    def reset_stats(self) -> None:
        self._misses.clear()
        self._hits = 0
