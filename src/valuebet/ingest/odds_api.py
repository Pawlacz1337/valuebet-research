"""Klient The Odds API — jedyne legalne źródło kursów Pinnacle i exchange.

Po co to istnieje
-----------------
`POL.csv` z football-data ma wyłącznie 1X2 (30 kolumn, kursowe tylko
`PSC*`, `MaxC*`, `AvgC*`, `BFEC*`, `B365C*`). Nie ma ani O/U, ani
handicapów, więc kalibracji totali nie da się zweryfikować wobec rynku na
danych historycznych — STEP4_ENSEMBLE §11.7, bramka G5.

Pinnacle i Betfair nie mają polskiej licencji, więc ich strony są poza
grą. The Odds API to **udokumentowana, legalna usługa pośrednicząca** —
nie obchodzimy nią niczego i nie podszywamy się pod nikogo.

Budżet jest tu projektem, nie detalem
--------------------------------------
Plan darmowy to 500 kredytów na miesiąc, a jedno wywołanie `/odds` z
trzema rynkami kosztuje **3 kredyty**. Przy ~35 kredytach na kolejkę
wychodzi 150-180 miesięcznie, czyli zapas jest, ale nie jest duży.

Dlatego źródłem prawdy o zużyciu są **nagłówki odpowiedzi**, nie licznik
w pliku. Lokalny licznik rozjeżdża się po każdym nieudanym przebiegu,
restarcie albo ręcznym wywołaniu z konsoli, a wtedy albo przepalamy
budżet, albo wstrzymujemy zbieranie bez powodu.

Klucz w URL — stąd redakcja wszędzie
-------------------------------------
The Odds API przyjmuje klucz jako parametr zapytania ``apiKey``, nie
nagłówek. To znaczy, że klucz **domyślnie trafia** do logów, komunikatów
wyjątków i każdego zapisanego URL-a. ``httpx`` loguje pełne URL-e na
poziomie INFO, więc jedna linijka ``logging.basicConfig(level=INFO)`` w
cudzym skrypcie wystarczy, żeby sekret wyciekł do pliku.

Konsekwencje w kodzie, wszystkie celowe:

- ``redact_api_key`` przepuszcza każdy URL, który gdziekolwiek zapisujemy;
- wyjątki nigdy nie niosą surowego URL-a;
- ``silence_httpx_url_logging()`` podnosi logger ``httpx`` do WARNING i
  jest wołane w konstruktorze klienta.

Reguła 19 nienaruszona: te kursy są referencją i diagnostyką, nigdy cechą
modelu.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from valuebet.net.http import HttpClient, HttpError, Response

__all__ = [
    "CLOSINGS_ONLY_MARGIN",
    "MONTHLY_BUDGET",
    "BudgetExhaustedError",
    "BudgetSkipError",
    "CreditBudgetError",
    "EventsResponse",
    "OddsApiClient",
    "OddsApiError",
    "OddsApiSettings",
    "OddsResponse",
    "UsageCounters",
    "UsageGuard",
    "redact_api_key",
    "silence_httpx_url_logging",
]

log = logging.getLogger(__name__)

#: Budżet miesięczny projektu: 450 z 500 kredytów planu darmowego (50 zapasu).
#: Wymuszany przed KAŻDYM płatnym wywołaniem (FSA #0 F-15).
MONTHLY_BUDGET: Final = 450
#: Poniżej tylu kredytów zapasu do budżetu — wyłącznie zamknięcia (tryb oszczędny).
CLOSINGS_ONLY_MARGIN: Final = 60

#: Nagłówki licznika zużycia w API v4. To jest źródło prawdy — nie plik.
_HEADER_REMAINING = "x-requests-remaining"
_HEADER_USED = "x-requests-used"
#: Koszt OSTATNIEGO wywołania według dostawcy (F-16: nie zgadujemy).
_HEADER_LAST = "x-requests-last"

_REDACTED = "REDACTED"
_HTTP_OK = 200
#: Klucz bywa też w treści komunikatu błędu dostawcy, nie tylko w URL-u.
_KEY_IN_TEXT = re.compile(r"(apiKey=)[^&\s\"']+", re.IGNORECASE)


class OddsApiError(RuntimeError):
    """Błąd komunikacji albo kontraktu API. Nigdy nie niesie klucza.

    ``http_status`` — kod odpowiedzi innej niż 200 (``None``, gdy odpowiedzi
    nie było); ``error_kind`` — rodzaj awarii transportu z ``HttpError``
    (``"timeout"``, ``"connection"``, ``"other"``) albo ``None``.
    """

    def __init__(
        self, message: str, *, http_status: int | None = None, error_kind: str | None = None
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.error_kind = error_kind


class CreditBudgetError(OddsApiError):
    """Kredyty poniżej progu zatrzymania. Sufiks ``Error`` wymaga ruff N818."""


def redact_api_key(url: str) -> str:
    """Usuwa wartość ``apiKey`` z URL-a, zachowując resztę zapytania.

    Wołane przed każdym zapisem i każdym logowaniem. Zwraca URL w postaci
    nadającej się do wklejenia w raport — widać, o co pytaliśmy, nie widać
    czym.
    """
    parsed = urlparse(url)
    if not parsed.query:
        return _KEY_IN_TEXT.sub(rf"\1{_REDACTED}", url)
    pairs = [
        (key, _REDACTED if key.lower() == "apikey" else value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
    ]
    return urlunparse(parsed._replace(query=urlencode(pairs)))


def redact_text(text: str) -> str:
    """Redakcja klucza w dowolnym tekście — np. w treści błędu dostawcy."""
    return _KEY_IN_TEXT.sub(rf"\1{_REDACTED}", text)


def silence_httpx_url_logging() -> None:
    """Podnosi logger ``httpx`` do WARNING.

    ``httpx`` loguje na INFO pełny URL każdego zapytania, a nasz klucz
    siedzi w query stringu. Bez tego wywołania wystarczy, że ktoś ustawi
    globalnie INFO, i sekret ląduje w logu.
    """
    logging.getLogger("httpx").setLevel(logging.WARNING)


@dataclass(frozen=True)
class OddsApiSettings:
    """Konfiguracja z ``.env``. Brak klucza to głośny błąd, nie cichy pas."""

    api_key: str | None = None
    base_url: str = "https://api.the-odds-api.com/v4"
    sport_key: str = "soccer_poland_ekstraklasa"
    bookmakers: tuple[str, ...] = ("pinnacle", "betfair_ex_eu", "matchbook")
    markets: tuple[str, ...] = ("h2h", "totals", "spreads")
    timeout_seconds: float = 20.0

    @classmethod
    def from_env(cls) -> OddsApiSettings:
        return cls(
            api_key=os.environ.get("VB_ODDS_API_KEY") or None,
            sport_key=os.environ.get("VB_ODDS_SPORT", cls.sport_key),
        )

    def require_key(self) -> str:
        if not self.api_key:
            raise OddsApiError(
                "brak klucza API: ustaw VB_ODDS_API_KEY w .env. "
                "Kolektor, który po awarii konfiguracji grzecznie nic nie "
                "robi, to najgorszy tryb awarii w tym projekcie — "
                "dowiadujesz się po trzech miesiącach, patrząc w pusty katalog."
            )
        return self.api_key


@dataclass(frozen=True)
class UsageCounters:
    """Licznik zużycia odczytany z nagłówków odpowiedzi.

    ``None`` znaczy „dostawca nie podał" — traktujemy to jako nieznane, a
    nie jako zero. Zgadywanie w którąkolwiek stronę kończy się albo
    przepalonym budżetem, albo wstrzymanym zbieraniem bez powodu.
    """

    remaining: int | None
    used: int | None
    #: Koszt ostatniego wywołania według dostawcy (``x-requests-last``).
    last: int | None = None

    @classmethod
    def from_headers(cls, headers: Mapping[str, str]) -> UsageCounters:
        def read(name: str) -> int | None:
            raw = headers.get(name)
            if raw is None:
                return None
            try:
                return int(float(raw))
            except ValueError:
                log.warning("nieparsowalny nagłówek %s=%r", name, raw)
                return None

        return cls(
            remaining=read(_HEADER_REMAINING),
            used=read(_HEADER_USED),
            last=read(_HEADER_LAST),
        )


class BudgetSkipError(OddsApiError):
    """Wywołanie pominięte przez budżet — kredyt NIE został wydany."""


class BudgetExhaustedError(BudgetSkipError):
    """Pominięte, bo ``used + koszt > budżet`` — nie tryb oszczędny.

    Rozróżnienie dla ``closing_missed``: powód „budżet > 450” jest prawdziwy
    tylko wtedy, gdy budżet naprawdę by pękł (FSA #0e, niezmiennik kolektora).
    """


@dataclass(frozen=True)
class UsageGuard:
    """Bezpiecznik budżetu liczony z ``x-requests-used`` dostawcy (F-15).

    ``used = None`` (dostawca nie podał) blokuje płatne wywołania — nie
    wiemy, ile zostało, a zgadywanie w stronę „jest miejsce” przepala budżet.
    """

    used: int | None
    budget: int = MONTHLY_BUDGET
    margin: int = CLOSINGS_ONLY_MARGIN

    def skip_reason(self, *, cost: int, closing: bool) -> str | None:
        if self.used is None:
            return "licznik zużycia nieznany — brak nagłówka x-requests-used"
        if self.used + cost > self.budget:
            return f"used {self.used} + koszt {cost} > budżet {self.budget}"
        if self.budget - self.used < self.margin and not closing:
            return (
                f"tryb oszczędny: zapas {self.budget - self.used} < {self.margin} "
                "— wyłącznie zamknięcia"
            )
        return None


@dataclass(frozen=True)
class OddsResponse:
    """Odpowiedź ``/odds`` plus licznik i **zredagowany** URL.

    ``requested_url`` jest już po redakcji — pole istnieje właśnie po to,
    żeby dało się je bezpiecznie zapisać obok surowego payloadu (zasada
    „pobieraj głupio, parsuj później" z COLLECTOR_PLAN §3.1).
    """

    events: list[dict[str, Any]]
    usage: UsageCounters
    requested_url: str
    fetched_at: str
    #: Koszt według dostawcy (``x-requests-last``); brak nagłówka → liczba rynków.
    credits_spent: int

    def __post_init__(self) -> None:
        if "apiKey=" in self.requested_url and _REDACTED not in self.requested_url:
            raise OddsApiError(
                "requested_url zawiera niezredagowany apiKey — "
                "to pole jest zapisywane na dysk"
            )


@dataclass(frozen=True)
class EventsResponse:
    """Odpowiedź bezpłatnego ``/events`` — terminarz ligi bez kursów."""

    events: list[dict[str, Any]]
    usage: UsageCounters


@dataclass
class OddsApiClient:
    """Minimalny klient. Jedno zadanie: pobrać i nie zgubić klucza po drodze."""

    #: Jedyny klient sieciowy projektu — odstęp per host (FSA #0 F-26).
    http: HttpClient
    settings: OddsApiSettings = field(default_factory=OddsApiSettings.from_env)

    def __post_init__(self) -> None:
        silence_httpx_url_logging()

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> OddsApiClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _get(self, path: str, params: dict[str, str]) -> Response:
        url = f"{self.settings.base_url}{path}"
        full = dict(params)
        full["apiKey"] = self.settings.require_key()
        try:
            response = self.http.get(url, params=full)
        except HttpError as exc:
            # Komunikat HttpError jest już zredagowany; redagujemy jeszcze raz.
            raise OddsApiError(
                f"zapytanie do {path} nie powiodło się: {redact_text(str(exc))}",
                error_kind=exc.kind,
            ) from None
        if response.status_code != _HTTP_OK:
            raise OddsApiError(
                f"{path} zwróciło HTTP {response.status_code}: "
                f"{redact_text(response.text[:400])}",
                http_status=response.status_code,
            )
        return response

    @staticmethod
    def _json_list(response: Response, path: str) -> list[Any]:
        """Treść odpowiedzi 200 jako lista — inaczej błąd KONTRAKTU (decyzja 2026-10-07).

        Zły JSON albo inny kształt to nie awaria dostawcy ani kolektora:
        ``http_status = 200``, ``error_kind = "contract"``.
        """
        try:
            body = response.json()
        except ValueError:
            raise OddsApiError(
                f"{path}: odpowiedź 200 nie jest poprawnym JSON-em",
                http_status=_HTTP_OK,
                error_kind="contract",
            ) from None
        if not isinstance(body, list):
            raise OddsApiError(
                f"{path} miało zwrócić listę, zwróciło {type(body).__name__}",
                http_status=_HTTP_OK,
                error_kind="contract",
            )
        return body

    def list_sports(self) -> list[dict[str, Any]]:
        """``GET /sports`` — **darmowe**, zero kredytów.

        Jedyne wywołanie, którym wolno sprawdzić, czy klucz działa, bez
        uszczerbku dla budżetu. Zwraca też dokładne klucze lig i
        bukmacherów, których trzeba do ``/odds``.
        """
        response = self._get("/sports", {})
        return self._json_list(response, "/sports")

    def refresh_usage(self) -> UsageCounters:
        """Licznik zużycia z bezpłatnego ``/sports`` — prawda na początek przebiegu.

        Stary stan z pliku (np. z poprzedniego miesiąca) nie może ani blokować
        wszystkiego, ani udawać, że miejsca jest więcej, niż jest.
        """
        response = self._get("/sports", {})
        return UsageCounters.from_headers(response.headers)

    def fetch_odds(
        self,
        *,
        sport_key: str,
        markets: tuple[str, ...],
        usage_guard: UsageGuard,
        closing: bool,
        bookmakers: tuple[str, ...] | None = None,
    ) -> OddsResponse:
        """``GET /sports/{sport}/odds`` — kosztuje 1 kredyt za rynek.

        ``usage_guard`` jest **wymagany** (reguła 30). Przekroczenie budżetu
        albo tryb oszczędny dla kotwicy innej niż zamknięcie → ``BudgetSkipError``
        **przed** wydaniem kredytu.
        """
        reason = usage_guard.skip_reason(cost=len(markets), closing=closing)
        if reason is not None:
            used = usage_guard.used
            if used is not None and used + len(markets) > usage_guard.budget:
                raise BudgetExhaustedError(reason)
            raise BudgetSkipError(reason)
        params = {
            "regions": "eu",
            "bookmakers": ",".join(bookmakers or self.settings.bookmakers),
            "markets": ",".join(markets),
            "oddsFormat": "decimal",
            "dateFormat": "iso",
        }
        response = self._get(f"/sports/{sport_key}/odds", params)
        body = self._json_list(response, "/odds")
        if not all(isinstance(e, dict) and e.get("id") and e.get("commence_time") for e in body):
            raise OddsApiError(
                "/odds: zdarzenie bez pola id albo commence_time",
                http_status=_HTTP_OK,
                error_kind="contract",
            )
        usage = UsageCounters.from_headers(response.headers)
        return OddsResponse(
            events=body,
            usage=usage,
            requested_url=redact_api_key(str(response.url)),
            fetched_at=response.headers.get("date", ""),
            credits_spent=usage.last if usage.last is not None else len(markets),
        )

    def fetch_events(self, *, sport_key: str) -> EventsResponse:
        """``GET /sports/{sport}/events`` — terminarz, **bezpłatny**.

        Dokumentacja v4: „does not count against the usage quota”. Jedyne
        źródło terminarza kolektora (decyzja Pawła 2026-10-03, F0d-01):
        terminarz żywiony odpowiedziami płatnych wywołań milkł, gdy nic nie
        było należne. Koszt sprawdza wołający z ``usage.last``.
        """
        response = self._get(f"/sports/{sport_key}/events", {"dateFormat": "iso"})
        body = self._json_list(response, "/events")
        return EventsResponse(events=body, usage=UsageCounters.from_headers(response.headers))
