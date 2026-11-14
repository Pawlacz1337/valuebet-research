"""Kanoniczne modele danych. Kontrakt między ingest, features i backtestem.

Dwie zasady, na których stoi cały projekt i które są tu egzekwowane
przez typy, a nie przez dyscyplinę:

1. **Każdy znacznik czasu jest tz-aware UTC.** Naiwny ``datetime`` jest
   odrzucany przez walidator. Porównanie naiwnego czasu publikacji z
   czasem meczu potrafi przesunąć wszystko o 2 godziny i wprowadzić
   look-ahead bias, którego nie widać w żadnym teście jednostkowym.

2. **``event_at`` to co innego niż ``observed_at``.** Pierwsze mówi,
   kiedy coś się stało. Drugie — kiedy MOGLIŚMY się o tym dowiedzieć.
   Cechy wolno budować wyłącznie z faktów o ``observed_at`` wcześniejszym
   niż moment stawiania zakładu. Fakt bez ``observed_at`` jest bezużyteczny
   w backteście, niezależnie od tego, jak cenny wygląda.
"""

from __future__ import annotations

import hashlib
import unicodedata
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    model_validator,
)

__all__ = [
    "MARKET_ALIASES",
    "MarketType",
    "Match",
    "MatchStatus",
    "OddsSnapshot",
    "Outcome",
    "Selection",
    "Sport",
    "Team",
    "UtcDatetime",
    "canonical_market",
    "canonical_outcome",
    "make_match_id",
    "utcnow",
]


# ---------------------------------------------------------------------------
# Czas
# ---------------------------------------------------------------------------


def _ensure_utc(value: datetime) -> datetime:
    """Odrzuca naiwny datetime, normalizuje wszystko do UTC."""
    if value.tzinfo is None:
        raise ValueError(
            "znacznik czasu musi być tz-aware; naiwny datetime jest zabroniony "
            "(patrz reguła 2 w CLAUDE.md)"
        )
    return value.astimezone(UTC)


UtcDatetime = Annotated[datetime, AfterValidator(_ensure_utc)]


def utcnow() -> datetime:
    """Jedyne dopuszczalne źródło 'teraz'. Nigdy datetime.now()."""
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Słowniki
# ---------------------------------------------------------------------------


class Sport(StrEnum):
    FOOTBALL = "football"
    BASKETBALL = "basketball"
    VOLLEYBALL = "volleyball"
    TENNIS = "tennis"
    TABLE_TENNIS = "table_tennis"
    HANDBALL = "handball"


class MatchStatus(StrEnum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


class MarketType(StrEnum):
    """Typ rynku. ``line`` w Selection jest wymagany dla AH/OU."""

    ONE_X_TWO = "1x2"
    DOUBLE_CHANCE = "double_chance"
    ASIAN_HANDICAP = "asian_handicap"
    OVER_UNDER = "over_under"
    BTTS = "btts"
    CORNERS_OVER_UNDER = "corners_ou"
    CARDS_OVER_UNDER = "cards_ou"


class Outcome(StrEnum):
    HOME = "home"
    DRAW = "draw"
    AWAY = "away"
    OVER = "over"
    UNDER = "under"
    YES = "yes"
    NO = "no"
    HOME_OR_DRAW = "1x"
    HOME_OR_AWAY = "12"
    DRAW_OR_AWAY = "x2"


#: Klucze rynków The Odds API (kolektor, dziennik) → kanoniczny ``MarketType``.
#: W kodzie żyją oba nazewnictwa; porównanie napisów bez tego słownika
#: przepuszczało wyłączenie T12 wpisane w jednym, a noga w drugim
#: (FSA #0c F0c-03). Nazwy z regulaminu po polsku celowo NIE są aliasami —
#: przepisuje je człowiek, świadomie, na klucz z tej listy.
MARKET_ALIASES: dict[str, MarketType] = {
    **{m.value: m for m in MarketType},
    "h2h": MarketType.ONE_X_TWO,
    "totals": MarketType.OVER_UNDER,
    "spreads": MarketType.ASIAN_HANDICAP,
}


def canonical_market(name: str) -> MarketType:
    """Rynek kanoniczny dla klucza z ``MARKET_ALIASES``; inny napis → ``ValueError``."""
    if not isinstance(name, str) or name not in MARKET_ALIASES:
        raise ValueError(
            f"market {name!r} spoza słownika — dozwolone: {sorted(MARKET_ALIASES)}"
        )
    return MARKET_ALIASES[name]


#: Komplet wyników dla każdego rynku. Shin wymaga KOMPLETNEGO rynku —
#: podanie 2 z 3 wyników 1X2 daje booksum bez interpretacji marży
#: (reguła 17 w CLAUDE.md). Walidator kompletności korzysta z tej mapy.
MARKET_OUTCOMES: dict[MarketType, frozenset[Outcome]] = {
    MarketType.ONE_X_TWO: frozenset({Outcome.HOME, Outcome.DRAW, Outcome.AWAY}),
    MarketType.DOUBLE_CHANCE: frozenset(
        {Outcome.HOME_OR_DRAW, Outcome.HOME_OR_AWAY, Outcome.DRAW_OR_AWAY}
    ),
    MarketType.ASIAN_HANDICAP: frozenset({Outcome.HOME, Outcome.AWAY}),
    MarketType.OVER_UNDER: frozenset({Outcome.OVER, Outcome.UNDER}),
    MarketType.BTTS: frozenset({Outcome.YES, Outcome.NO}),
    MarketType.CORNERS_OVER_UNDER: frozenset({Outcome.OVER, Outcome.UNDER}),
    MarketType.CARDS_OVER_UNDER: frozenset({Outcome.OVER, Outcome.UNDER}),
}

def canonical_outcome(market: str, outcome: str) -> Outcome:
    """Wynik kanoniczny rynku: wielkość liter bez znaczenia, spoza rynku → ``ValueError``.

    The Odds API podaje ``Draw``, ``Over``, ``Under`` i nazwy drużyn; dziennik
    przyjmował dowolny napis, więc ``Home``/``home`` to były dwa klucze CLV
    (FSA #0e F0e-03). Nazwę drużyny na ``home``/``away`` przekłada budujący
    mapę zamknięć — tu jest błędem, nie wynikiem.
    """
    kind = canonical_market(market)
    try:
        value = Outcome(str(outcome).strip().lower())
    except ValueError:
        raise ValueError(
            f"outcome {outcome!r} spoza wyników rynku {kind.value}: "
            f"{sorted(o.value for o in MARKET_OUTCOMES[kind])}"
        ) from None
    if value not in MARKET_OUTCOMES[kind]:
        raise ValueError(
            f"outcome {outcome!r} spoza wyników rynku {kind.value}: "
            f"{sorted(o.value for o in MARKET_OUTCOMES[kind])}"
        )
    return value


#: Rynki, w których ``line`` jest obowiązkowy.
_LINE_REQUIRED = frozenset(
    {
        MarketType.ASIAN_HANDICAP,
        MarketType.OVER_UNDER,
        MarketType.CORNERS_OVER_UNDER,
        MarketType.CARDS_OVER_UNDER,
    }
)


# ---------------------------------------------------------------------------
# Identyfikatory
# ---------------------------------------------------------------------------


def _slug(text: str) -> str:
    """Normalizacja do porównań: bez diakrytyków, lowercase, bez szumu."""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    return "".join(c if c.isalnum() else "-" for c in ascii_only.lower()).strip("-")


def make_match_id(
    competition: str,
    kickoff_utc: datetime,
    home_team_id: str,
    away_team_id: str,
) -> str:
    """Deterministyczne ID meczu, wspólne dla wszystkich źródeł.

    Klucz to DATA (nie pełny znacznik czasu) plus obie drużyny. Data, bo
    źródła podają godziny rozpoczęcia, które różnią się o kilka minut i
    bywają korygowane; drużyny, bo jedna para gra najwyżej raz dziennie.

    Przesunięcie meczu na inny dzień zmienia ID i tworzy duplikat — to
    świadomy kompromis: wolimy widoczny duplikat niż cichy merge dwóch
    różnych spotkań.
    """
    kickoff_utc = _ensure_utc(kickoff_utc)
    payload = "|".join(
        [
            _slug(competition),
            kickoff_utc.date().isoformat(),
            home_team_id,
            away_team_id,
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Modele
# ---------------------------------------------------------------------------


class _Base(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class Team(_Base):
    """Kanoniczna drużyna. ``team_id`` jest jedynym kluczem do joinów."""

    team_id: str = Field(min_length=1)
    canonical_name: str = Field(min_length=1)
    country: str | None = None
    sport: Sport = Sport.FOOTBALL
    aliases: tuple[str, ...] = ()

    #: Zewnętrzne ID per źródło: {"api_football": "341", "football_data": "Lech"}
    external_ids: dict[str, str] = Field(default_factory=dict)


class Match(_Base):
    """Jedno spotkanie. Wynik jest opcjonalny — mecz przyszły go nie ma."""

    match_id: str = Field(min_length=1)
    sport: Sport = Sport.FOOTBALL
    competition: str = Field(min_length=1)
    season: str = Field(min_length=1, description="np. '2025/26'")
    kickoff_utc: UtcDatetime
    home_team_id: str = Field(min_length=1)
    away_team_id: str = Field(min_length=1)
    status: MatchStatus = MatchStatus.SCHEDULED

    home_goals: int | None = Field(default=None, ge=0)
    away_goals: int | None = Field(default=None, ge=0)

    #: Statystyki meczowe dostępne PO meczu (strzały, xG, rożne, kartki).
    #: Wolno ich używać wyłącznie jako wejścia do rolling_prior — nigdy
    #: jako cechy tego samego meczu.
    stats: dict[str, float] = Field(default_factory=dict)

    #: Miejsce na przyszłe pola bez migracji schematu. Cokolwiek tu wpada,
    #: musi mieć własny observed_at, jeśli ma trafić do cech.
    extra: dict[str, Any] = Field(default_factory=dict)

    ingested_at: UtcDatetime = Field(default_factory=utcnow)
    source: str = "unknown"

    @model_validator(mode="after")
    def _check(self) -> Match:
        if self.home_team_id == self.away_team_id:
            raise ValueError("drużyna nie gra sama ze sobą")
        if self.status is MatchStatus.FINISHED and (
            self.home_goals is None or self.away_goals is None
        ):
            raise ValueError("mecz zakończony musi mieć oba wyniki")
        if (self.home_goals is None) != (self.away_goals is None):
            raise ValueError("wynik musi być kompletny albo pusty")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_result(self) -> bool:
        return self.home_goals is not None and self.away_goals is not None


class Selection(_Base):
    """Konkretny wynik na konkretnym rynku. Bez kursu — ten jest w snapshocie."""

    match_id: str = Field(min_length=1)
    market: MarketType
    outcome: Outcome
    line: float | None = Field(
        default=None, description="linia dla AH/OU, np. -0.5 albo 2.5"
    )

    @model_validator(mode="after")
    def _check(self) -> Selection:
        allowed = MARKET_OUTCOMES.get(self.market)
        if allowed is not None and self.outcome not in allowed:
            raise ValueError(
                f"wynik {self.outcome!r} nie należy do rynku {self.market!r}; "
                f"dozwolone: {sorted(allowed)}"
            )
        if self.market in _LINE_REQUIRED and self.line is None:
            raise ValueError(f"rynek {self.market!r} wymaga podania line")
        if self.market not in _LINE_REQUIRED and self.line is not None:
            raise ValueError(f"rynek {self.market!r} nie przyjmuje line")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def selection_key(self) -> str:
        """Stabilny klucz do joinów kursów między źródłami."""
        line = "" if self.line is None else f"@{self.line:g}"
        return f"{self.match_id}:{self.market.value}:{self.outcome.value}{line}"


class OddsSnapshot(_Base):
    """Kurs zaobserwowany w konkretnej chwili.

    ``observed_at`` to moment ODCZYTU, nie moment publikacji kursu przez
    bukmachera. Nie znamy tego drugiego i nie wolno go zgadywać.
    """

    match_id: str = Field(min_length=1)
    bookmaker: str = Field(min_length=1)
    market: MarketType
    outcome: Outcome
    line: float | None = None

    odds: float = Field(gt=1.0, description="kurs dziesiętny, zawsze > 1.0")
    observed_at: UtcDatetime

    #: Współczynnik podatkowy obowiązujący dla TEGO kuponu u TEGO bukmachera
    #: w momencie obserwacji: 1.00 bez podatku, 0.94 promocja 6%, 0.88 standard.
    #: Nigdy nie zaszywaj tego w kodzie liczącym EV (reguła 20).
    tax_factor: float = Field(default=0.88, gt=0.0, le=1.0)

    #: Maksymalna stawka, jeśli bukmacher ją podaje. Kurs, którego nie da
    #: się zagrać w rozsądnej wysokości, nie jest okazją.
    max_stake: float | None = Field(default=None, gt=0.0)

    is_live: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)
    source: str = "unknown"

    @model_validator(mode="after")
    def _check(self) -> OddsSnapshot:
        allowed = MARKET_OUTCOMES.get(self.market)
        if allowed is not None and self.outcome not in allowed:
            raise ValueError(
                f"wynik {self.outcome!r} nie należy do rynku {self.market!r}"
            )
        if self.market in _LINE_REQUIRED and self.line is None:
            raise ValueError(f"rynek {self.market!r} wymaga podania line")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def selection_key(self) -> str:
        line = "" if self.line is None else f"@{self.line:g}"
        return f"{self.match_id}:{self.market.value}:{self.outcome.value}{line}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def effective_odds(self) -> float:
        """Kurs po uwzględnieniu podatku — to, co realnie dostajesz.

        Polski podatek jest potrącany od STAWKI, więc efektywnie mnoży
        kurs: stawiasz 100, do gry idzie 88, wygrana to 88 * k.
        """
        return self.odds * self.tax_factor
