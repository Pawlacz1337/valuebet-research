"""Testy klienta The Odds API. Zero sieci — wszystko na ``MockTransport``.

Najważniejsze są testy redakcji klucza. Klucz idzie w query stringu, więc
domyślnie trafia do logów, wyjątków i każdego zapisanego URL-a; jeden
nieuważny ``f"{response.url}"`` wystarczy, żeby wyciekł do repo.
"""

from __future__ import annotations

import logging

import httpx
import pytest

from helpers import fake_http
from valuebet.ingest.odds_api import (
    BudgetSkipError,
    OddsApiClient,
    OddsApiError,
    OddsApiSettings,
    OddsResponse,
    UsageCounters,
    UsageGuard,
    redact_api_key,
    redact_text,
    silence_httpx_url_logging,
)

SECRET = "zupelnie-tajny-klucz-123"
#: Budżet z dużym zapasem — testy kontraktu, nie bezpiecznika.
OPEN = UsageGuard(used=0)
EVENT = {
    "id": "abc123",
    "sport_key": "soccer_poland_ekstraklasa",
    "commence_time": "2026-10-24T15:30:00Z",
    "home_team": "Legia Warsaw",
    "away_team": "Lech Poznan",
    "bookmakers": [
        {
            "key": "pinnacle",
            "last_update": "2026-10-24T15:20:00Z",
            "markets": [
                {
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Legia Warsaw", "price": 1.95},
                        {"name": "Lech Poznan", "price": 3.80},
                        {"name": "Draw", "price": 3.55},
                    ],
                },
                {
                    "key": "totals",
                    "outcomes": [
                        {"name": "Over", "price": 1.90, "point": 2.5},
                        {"name": "Under", "price": 1.98, "point": 2.5},
                    ],
                },
            ],
        }
    ],
}


def _settings(**kwargs: object) -> OddsApiSettings:
    base = {"api_key": SECRET}
    base.update(kwargs)
    return OddsApiSettings(**base)  # type: ignore[arg-type]


def _client(
    handler: object, **kwargs: object
) -> tuple[OddsApiClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)  # type: ignore[operator]

    return (
        OddsApiClient(http=fake_http(wrapped), settings=_settings(**kwargs)),
        seen,
    )


# ---------------------------------------------------------------------------
# Redakcja klucza — najważniejsza część modułu
# ---------------------------------------------------------------------------


def test_redact_removes_key_but_keeps_rest_of_query() -> None:
    url = (
        "https://api.the-odds-api.com/v4/sports/soccer_poland_ekstraklasa/odds"
        f"?regions=eu&markets=h2h%2Ctotals&apiKey={SECRET}&oddsFormat=decimal"
    )
    out = redact_api_key(url)
    assert SECRET not in out
    assert "apiKey=REDACTED" in out
    assert "markets=h2h%2Ctotals" in out
    assert "oddsFormat=decimal" in out


@pytest.mark.parametrize("name", ["apiKey", "apikey", "APIKEY", "ApiKey"])
def test_redact_is_case_insensitive(name: str) -> None:
    assert SECRET not in redact_api_key(f"https://x.pl/v4?{name}={SECRET}")


def test_redact_handles_url_without_query() -> None:
    assert redact_api_key("https://x.pl/v4/sports") == "https://x.pl/v4/sports"


def test_redact_text_cleans_error_bodies() -> None:
    body = f'{{"message":"bad key","url":"/v4/sports?apiKey={SECRET}&x=1"}}'
    assert SECRET not in redact_text(body)


def test_response_refuses_unredacted_url() -> None:
    """Kontrakt na typie, nie na dyscyplinie wołającego."""
    with pytest.raises(OddsApiError, match="niezredagowany apiKey"):
        OddsResponse(
            credits_spent=0,
            events=[],
            usage=UsageCounters(None, None),
            requested_url=f"https://x.pl/v4/odds?apiKey={SECRET}",
            fetched_at="",
        )


def test_fetched_url_is_stored_redacted() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[EVENT], headers={"x-requests-remaining": "400"})

    client, _ = _client(handler)
    with client:
        result = client.fetch_odds(sport_key="soccer_poland_ekstraklasa", markets=("h2h", "totals", "spreads"), usage_guard=OPEN, closing=False)
    assert SECRET not in result.requested_url
    assert "apiKey=REDACTED" in result.requested_url


def test_http_error_message_has_no_key() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text=f"Invalid key apiKey={SECRET}")

    client, _ = _client(handler)
    with client, pytest.raises(OddsApiError) as info:
        client.list_sports()
    assert SECRET not in str(info.value)


def test_transport_error_message_has_no_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"nie poszlo: {request.url}", request=request)

    client, _ = _client(handler)
    with client, pytest.raises(OddsApiError) as info:
        client.list_sports()
    assert SECRET not in str(info.value)


def test_httpx_logger_is_silenced() -> None:
    """httpx loguje pełne URL-e na INFO, a w URL-u siedzi klucz."""
    logging.getLogger("httpx").setLevel(logging.INFO)
    silence_httpx_url_logging()
    assert logging.getLogger("httpx").level == logging.WARNING


# ---------------------------------------------------------------------------
# Kontrakt zapytań
# ---------------------------------------------------------------------------


def test_odds_request_asks_for_three_markets_and_decimal_odds() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[EVENT], headers={"x-requests-remaining": "400"})

    client, seen = _client(handler)
    with client:
        client.fetch_odds(sport_key="soccer_poland_ekstraklasa", markets=("h2h", "totals", "spreads"), usage_guard=OPEN, closing=False)
    query = dict(seen[0].url.params)
    assert query["markets"] == "h2h,totals,spreads"
    assert query["oddsFormat"] == "decimal"
    assert query["dateFormat"] == "iso"
    assert "pinnacle" in query["bookmakers"]
    assert seen[0].url.path.endswith("/soccer_poland_ekstraklasa/odds")


def test_list_sports_is_free_and_returns_list() -> None:
    payload = [{"key": "soccer_poland_ekstraklasa", "active": True}]

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client, seen = _client(handler)
    with client:
        assert client.list_sports() == payload
    assert seen[0].url.path.endswith("/sports")


def test_non_list_payload_is_a_contract_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": "nope"})

    client, _ = _client(handler)
    with client, pytest.raises(OddsApiError, match="zwrócić listę"):
        client.fetch_odds(sport_key="soccer_poland_ekstraklasa", markets=("h2h", "totals", "spreads"), usage_guard=OPEN, closing=False)


def test_missing_key_raises_loudly() -> None:
    client = OddsApiClient(
        http=fake_http(lambda r: httpx.Response(200)),
        settings=OddsApiSettings(api_key=None),
    )
    with client, pytest.raises(OddsApiError, match="VB_ODDS_API_KEY"):
        client.list_sports()


# ---------------------------------------------------------------------------
# Budżet kredytów
# ---------------------------------------------------------------------------


def test_usage_read_from_headers() -> None:
    usage = UsageCounters.from_headers(
        httpx.Headers({"x-requests-remaining": "137", "x-requests-used": "363"})
    )
    assert usage.remaining == 137
    assert usage.used == 363


def test_missing_usage_headers_are_unknown_not_zero() -> None:
    """Zgadywanie zera wstrzymałoby zbieranie bez powodu — ale nieznany licznik blokuje."""
    usage = UsageCounters.from_headers(httpx.Headers({}))
    assert usage.remaining is None
    assert usage.used is None
    assert UsageGuard(used=usage.used).skip_reason(cost=1, closing=True) is not None


def test_unparsable_usage_header_is_unknown() -> None:
    usage = UsageCounters.from_headers(httpx.Headers({"x-requests-remaining": "lots"}))
    assert usage.remaining is None


@pytest.mark.parametrize(
    ("used", "cost", "closing", "allowed"),
    [
        (0, 3, False, True),
        (389, 1, False, True),
        (391, 1, False, False),
        (391, 2, True, True),
        (448, 2, True, True),
        (449, 2, True, False),
        (450, 1, True, False),
    ],
)
def test_budget_thresholds(used: int, cost: int, closing: bool, allowed: bool) -> None:
    """Budżet 450, tryb oszczędny przy zapasie < 60 (FSA #0 F-15)."""
    reason = UsageGuard(used=used).skip_reason(cost=cost, closing=closing)
    assert (reason is None) is allowed


def test_guard_refuses_before_spending() -> None:
    """Wyjątek PRZED wydaniem kredytu, nie po."""
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=[EVENT])

    client, _ = _client(handler)
    with client, pytest.raises(BudgetSkipError, match="budżet"):
        client.fetch_odds(
            sport_key="soccer_epl",
            markets=("h2h", "totals"),
            usage_guard=UsageGuard(used=449),
            closing=True,
        )
    assert calls == [], "kredyt wydany mimo budżetu"


def test_credits_spent_comes_from_provider() -> None:
    """F-16: koszt z ``x-requests-last``, nie ze stałej 3."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=[EVENT], headers={"x-requests-remaining": "400", "x-requests-last": "2"}
        )

    client, _ = _client(handler)
    with client:
        response = client.fetch_odds(
            sport_key="soccer_epl", markets=("h2h", "totals"), usage_guard=OPEN, closing=True
        )
    assert response.credits_spent == 2


def test_credits_spent_falls_back_to_market_count() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[EVENT])

    client, _ = _client(handler)
    with client:
        response = client.fetch_odds(
            sport_key="soccer_epl", markets=("h2h", "totals"), usage_guard=OPEN, closing=True
        )
    assert response.credits_spent == 2


def test_refresh_usage_reads_free_sports_headers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/sports")
        return httpx.Response(200, json=[], headers={"x-requests-used": "12"})

    client, _ = _client(handler)
    with client:
        assert client.refresh_usage().used == 12


def test_settings_from_env_treats_blank_key_as_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VB_ODDS_API_KEY", "")
    assert OddsApiSettings.from_env().api_key is None


# ---------------------------------------------------------------------------
# Blokada sieci z conftest
# ---------------------------------------------------------------------------


def test_real_network_is_blocked_in_tests() -> None:
    """Kontrola samego zabezpieczenia — bez niej nie wiem, czy działa.

    Wyjątek łapiemy po komunikacie, nie po klasie: ``conftest.py`` nie jest
    modułem importowalnym, a dociąganie go po ścieżce byłoby obejściem
    tego, co pytest robi z konftestami.
    """
    with httpx.Client() as real, pytest.raises(RuntimeError) as info:
        real.get("https://api.the-odds-api.com/v4/sports")
    assert "próbował wyjść do sieci" in str(info.value)
