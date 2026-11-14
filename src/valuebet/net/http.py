"""Jedyny klient sieciowy projektu (``CLAUDE.md`` „Granice”, COLLECTOR_PLAN §2).

Każde zapytanie HTTP z kodu projektu idzie przez :class:`HttpClient`.
Bezpośrednie ``httpx``/``requests``/``urllib.request`` gdzie indziej są
zabronione — pilnuje tego test AST (FSA #0 F-26). Powód: tempo zapytań i
robots.txt mają być **własnością infrastruktury**, nie dyscypliną każdego
wołającego. Przed tą zmianą ``validate_instrument.py`` wysyłał sześć żądań w
1-3 s, 20-50 razy szybciej niż własna norma projektu.

Co gwarantuje klient
--------------------
- **Odstęp per host ≥ max(10 s, ``Crawl-delay``).** Stan (chwila ostatniego
  zapytania) w ``data/state/throttle/<host>.json`` pod blokadą plikową, więc
  dwa procesy (kolektor z Task Schedulera i ręczny skrypt) nie przyspieszają
  się nawzajem.
- **robots.txt per host**, cache 24 h w ``data/state/robots/``. Ścieżka
  zabroniona → :class:`RobotsDisallowedError`. robots.txt niedostępny (błąd
  inny niż 404) → też odmowa: nie wiemy, czy wolno. Hosty API
  (:data:`API_HOSTS`) robots nie dotyczy — to udokumentowane API, nie strony
  (``docs/sources.md``); odstęp tak.
- **User-Agent z nazwą projektu**, bez danych osobowych.
- **Redakcja sekretów** — ``apiKey`` w zapytaniu i token Telegrama w ścieżce
  ``/bot…/`` — w logach, wyjątkach i ``repr``.

Zegar i usypianie są **wstrzykiwane** (reguła 30: zegar tylko w punkcie
wejścia) — testy sprawdzają odstępy na fałszywym zegarze.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

from valuebet.fsutil import file_lock, write_atomic

__all__ = [
    "API_HOSTS",
    "MIN_INTERVAL_S",
    "USER_AGENT",
    "HttpClient",
    "HttpError",
    "Response",
    "RobotsDisallowedError",
    "redact",
]

log = logging.getLogger(__name__)

#: Hosty udokumentowanych API — robots.txt ich nie dotyczy, odstęp tak.
#: Odzwierciedlone w ``docs/sources.md``.
API_HOSTS: Final = frozenset({"api.the-odds-api.com", "api.telegram.org"})
#: Minimalny odstęp między zapytaniami do jednego hosta.
MIN_INTERVAL_S: Final = 10.0
#: robots.txt ważny tyle sekund.
ROBOTS_TTL_S: Final = 24 * 3600.0
USER_AGENT: Final = "valuebet/0.1 (projekt badawczy; tylko odczyt publicznych danych)"
STATE_DIR: Final = Path("data/state/throttle")
ROBOTS_DIR: Final = Path("data/state/robots")

#: Typ odpowiedzi — moduły korzystające z klienta nie importują ``httpx``.
Response = httpx.Response

_BOT_TOKEN = re.compile(r"/bot[^/\s]+/")
_API_KEY = re.compile(r"(apiKey=)[^&\s\"']+", re.IGNORECASE)
_REDACTED = "REDACTED"


class HttpError(RuntimeError):
    """Błąd zapytania. Komunikat nigdy nie niesie sekretu.

    ``kind`` — rodzaj awarii transportu: ``"timeout"``, ``"connection"``
    (zerwane / odrzucone połączenie) albo ``"other"``. Kolektor odróżnia po
    nim awarię dostawcy od własnej (decyzja Pawła 2026-10-04, F0e-05).
    """

    def __init__(self, message: str, *, kind: str = "other") -> None:
        super().__init__(message)
        self.kind = kind


def transport_kind(exc: httpx.HTTPError) -> str:
    """Rodzaj awarii transportu httpx: timeout, połączenie albo inna."""
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.NetworkError | httpx.RemoteProtocolError):
        return "connection"
    return "other"


class RobotsDisallowedError(HttpError):
    """robots.txt zabrania tej ścieżki albo jest niedostępny."""


def redact(text: str) -> str:
    """Usuwa ``apiKey=…`` i token z ``/bot<token>/`` z URL-a albo dowolnego tekstu."""
    parts = urlsplit(text)
    if parts.scheme and parts.netloc:
        query = urlencode(
            [
                (k, _REDACTED if k.lower() == "apikey" else v)
                for k, v in parse_qsl(parts.query, keep_blank_values=True)
            ]
        )
        text = urlunsplit(parts._replace(query=query))
    text = _API_KEY.sub(rf"\1{_REDACTED}", text)
    return _BOT_TOKEN.sub(f"/bot{_REDACTED}/", text)


def _host_file(folder: Path, host: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9.-]", "_", host)
    return folder / f"{safe}.json"


@dataclass
class HttpClient:
    """Klient z odstępem per host, robots.txt i redakcją sekretów."""

    #: Zegar ścienny w sekundach (``time.time`` z punktu wejścia).
    clock: Callable[[], float]
    #: Usypianie (``time.sleep`` z punktu wejścia).
    sleep: Callable[[float], None]
    transport: httpx.BaseTransport | None = None
    state_dir: Path = STATE_DIR
    robots_dir: Path = ROBOTS_DIR
    timeout_s: float = 30.0
    _client: httpx.Client = field(init=False, repr=False)

    def __post_init__(self) -> None:
        # httpx loguje pełne URL-e na INFO, a klucz The Odds API siedzi w zapytaniu.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        self._client = httpx.Client(
            timeout=self.timeout_s,
            transport=self.transport,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )

    def __repr__(self) -> str:
        return f"HttpClient(state_dir={self.state_dir!s}, robots_dir={self.robots_dir!s})"

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # -- tempo ------------------------------------------------------------

    def _wait_turn(self, host: str, interval: float) -> None:
        """Czeka na swoją kolej do hosta i odnotowuje zapytanie — pod blokadą."""
        path = _host_file(self.state_dir, host)
        with file_lock(path):
            last = 0.0
            if path.exists():
                last = float(json.loads(path.read_text(encoding="utf-8"))["last_request_at"])
            wait = last + interval - self.clock()
            if wait > 0:
                log.info("tempo: %s — czekam %.1f s", host, wait)
                self.sleep(wait)
            write_atomic(
                path,
                json.dumps({"host": host, "last_request_at": self.clock()}).encode("utf-8"),
            )

    # -- robots.txt ---------------------------------------------------------

    def _robots(self, scheme: str, host: str) -> tuple[RobotFileParser, float]:
        cache = _host_file(self.robots_dir, host)
        entry: dict[str, Any] | None = None
        if cache.exists():
            entry = json.loads(cache.read_text(encoding="utf-8"))
            if self.clock() - float(entry["fetched_at"]) > ROBOTS_TTL_S:
                entry = None
        if entry is None:
            url = f"{scheme}://{host}/robots.txt"
            self._wait_turn(host, MIN_INTERVAL_S)
            try:
                response = self._client.get(url)
            except httpx.HTTPError as exc:
                raise RobotsDisallowedError(
                    f"robots.txt {host} niedostępny ({type(exc).__name__}) — nie pobieram"
                ) from None
            entry = {
                "host": host,
                "fetched_at": self.clock(),
                "status": response.status_code,
                "text": response.text if response.status_code == httpx.codes.OK else "",
            }
            write_atomic(cache, json.dumps(entry, ensure_ascii=False).encode("utf-8"))
        status = int(entry["status"])
        if status not in (httpx.codes.OK, httpx.codes.NOT_FOUND):
            raise RobotsDisallowedError(
                f"robots.txt {host}: HTTP {status} — nie wiadomo, czy wolno; nie pobieram"
            )
        parser = RobotFileParser()
        parser.parse(str(entry["text"]).splitlines())
        delay = parser.crawl_delay(USER_AGENT) or parser.crawl_delay("*") or 0.0
        return parser, float(delay)

    def interval_for(self, url: str) -> float:
        """Odstęp dla hosta URL-a; dla stron sprawdza też robots.txt."""
        parts = urlsplit(url)
        host = parts.hostname or ""
        if host in API_HOSTS:
            return MIN_INTERVAL_S
        parser, delay = self._robots(parts.scheme or "https", host)
        if not parser.can_fetch(USER_AGENT, url):
            raise RobotsDisallowedError(f"robots.txt {host} zabrania {redact(url)}")
        return max(MIN_INTERVAL_S, delay)

    # -- zapytania ----------------------------------------------------------

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        json_body: Any = None,
    ) -> Response:
        full = str(httpx.URL(url, params=dict(params) if params else None))
        interval = self.interval_for(full)
        host = urlsplit(full).hostname or ""
        self._wait_turn(host, interval)
        try:
            response = self._client.request(method, full, json=json_body)
        except httpx.HTTPError as exc:
            raise HttpError(
                f"{method} {redact(full)} nieudane: "
                f"{redact(type(exc).__name__ + ': ' + str(exc))}",
                kind=transport_kind(exc),
            ) from None
        log.info("%s %s -> %s", method, redact(full), response.status_code)
        return response

    def get(self, url: str, *, params: Mapping[str, str] | None = None) -> Response:
        return self.request("GET", url, params=params)

    def post(self, url: str, *, json_body: Any) -> Response:
        return self.request("POST", url, json_body=json_body)
