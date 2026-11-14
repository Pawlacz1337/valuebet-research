"""Uczciwe prawdopodobieństwa z migawek Pinnacle (TOR_S_PLAN §3).

Po M2 model nie wnosi informacji ponad rynek, więc wyceniaczem jest
**Pinnacle po Shinie w chwili decyzji**. To osobna strategia, nie cecha
modelu — reguła 19 z wyjątkiem dla toru S.

Dwie rzeczy, na których ten moduł stoi
---------------------------------------
**Wiek migawki jest częścią wyceny.** Kurs sprzed ośmiu godzin nie jest
kursem — jest historią. Powyżej ``MAX_AGE`` nie zwracamy wyceny, a nie
zwracamy starej ceny z adnotacją: wycena z adnotacją trafi do EV, a
adnotacja zostanie w logu.

**Shin osobno na każdym rynku, po walidacji kompletności** (reguła 17).
Rynek 1X2 z dwoma wynikami daje booksum bez interpretacji, a Shin nie ma
jak tego wykryć — nie wie, ilu wyników oczekiwać.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

from valuebet.pricing.shin import ShinNotConvergedError, shin_probabilities

__all__ = [
    "MAX_AGE",
    "STALE_WARNING_AGE",
    "FairPrice",
    "FairPricing",
    "MarketQuote",
    "StaleSnapshotError",
    "fair_prices",
]

log = logging.getLogger(__name__)

#: Starsza migawka nie daje wyceny. Sześć godzin to granica, za którą kurs
#: Pinnacle przestaje opisywać ten mecz — składy, kontuzje, pieniądze.
MAX_AGE = timedelta(hours=6)

#: Powyżej tego ostrzegamy, ale wyceniamy. Granica jest umowna; chodzi o to,
#: żeby człowiek widział w przeglądzie dnia, że patrzy na coś starszego.
STALE_WARNING_AGE = timedelta(hours=3)

#: Ile wyników ma komplet danego rynku (reguła 17).
#:
#: Klucze obejmują **oba nazewnictwa**: nasze kanoniczne i to z The Odds
#: API, bo cały własny ingest nazywa 1X2 jako ``h2h``
#: (``odds_collector.DECISION_MARKETS``). Pierwotna wersja miała tylko
#: ``1x2`` i przy ``h2h`` walidacja kompletności **nie uruchamiała się
#: wcale**: rynek z czterema kursami przechodził przez Shina z booksumem
#: 1.31, a ``double_chance`` z booksumem 2.03 dawał p(1X) = 0.41 i próg
#: k_min = 2.46. Jednostronnie w górę, mnożnik równy nadmiarowi booksumu.
MARKET_SIZE = {
    "1x2": 3,
    "h2h": 3,
    "totals": 2,
    "spreads": 2,
    "over_under": 2,
    "asian_handicap": 2,
}


class StaleSnapshotError(RuntimeError):
    """Migawka za stara, żeby wyceniać. Sufiks ``Error`` wymaga ruff N818."""


@dataclass(frozen=True)
class MarketQuote:
    """Jeden kompletny rynek z jednej migawki.

    ``outcomes`` i ``odds`` są równoległe i muszą być kompletne — walidację
    robi ``fair_prices``, bo Shin nie ma jak.
    """

    match_id: str
    market: str
    outcomes: tuple[str, ...]
    odds: tuple[float, ...]
    observed_at: datetime
    line: float | None = None


@dataclass(frozen=True)
class FairPrice:
    match_id: str
    market: str
    outcome: str
    p: float
    observed_at: datetime
    line: float | None = None
    source: str = "pinnacle"
    booksum: float = float("nan")
    z: float = float("nan")

    @property
    def fair_odds(self) -> float:
        """Kurs, przy którym EV = 0 bez podatku. Wygodny do czytania."""
        return 1.0 / self.p if self.p > 0 else float("inf")


@dataclass(frozen=True)
class FairPricing:
    """Wynik wyceny: ceny i licznik pominięć według powodu.

    Pominięcie jest daną, nie szumem w logu — backtest raportuje, ile rynków
    wypadło z każdego powodu (``brak gwizdka``, ``po gwizdku``, ``za stara``…).
    """

    prices: list[FairPrice]
    skipped: Counter[str]


def fair_prices(
    quotes: Iterable[MarketQuote],
    *,
    decision_time: datetime,
    kickoffs: Mapping[str, datetime],
    max_age: timedelta = MAX_AGE,
) -> FairPricing:
    """Migawki -> uczciwe prawdopodobieństwa. Pomija to, czego nie da się wycenić.

    Rynki niekompletne, z nieprawidłowymi kursami, przyszłe albo za stare są
    **pomijane z ostrzeżeniem**, nie wyceniane na siłę. Każde pominięcie
    trafia do ``FairPricing.skipped``.

    ``kickoffs`` jest **wymagane** (reguła 30, FSA #0 F-20): mecz bez
    znanego gwizdka nie jest wyceniany, a ``decision_time >= kickoff``
    oznacza kurs live, nie przedmeczowy. Wersja z ``kickoffs=None`` wyceniała
    migawkę z trwającego meczu jako przedmeczową.

    Raises
    ------
    ValueError
        Gdy ``decision_time`` jest naiwny (reguła 2) albo gdy rynek ma
        nieznaną nazwę (reguła 17).
    """
    if decision_time.tzinfo is None:
        raise ValueError("decision_time musi być timezone-aware (reguła 2)")

    out: list[FairPrice] = []
    skipped: Counter[str] = Counter()
    for quote in quotes:
        if quote.observed_at.tzinfo is None:
            raise ValueError(f"{quote.match_id}: observed_at bez strefy (reguła 2)")
        # Trucizna: wyceniamy WYŁĄCZNIE z migawek sprzed chwili decyzji.
        if quote.observed_at >= decision_time:
            log.warning(
                "%s/%s: migawka z %s nie jest sprzed decyzji %s — pomijam",
                quote.match_id,
                quote.market,
                quote.observed_at,
                decision_time,
            )
            skipped["migawka nie sprzed decyzji"] += 1
            continue
        kickoff = kickoffs.get(quote.match_id)
        if kickoff is None:
            log.warning(
                "%s/%s: brak gwizdka w terminarzu — brak wyceny",
                quote.match_id,
                quote.market,
            )
            skipped["brak gwizdka"] += 1
            continue
        if decision_time >= kickoff:
            log.warning(
                "%s/%s: decyzja %s nie jest przed gwizdkiem %s — to kurs live, "
                "nie przedmeczowy; pomijam",
                quote.match_id,
                quote.market,
                decision_time,
                kickoff,
            )
            skipped["po gwizdku"] += 1
            continue
        age = decision_time - quote.observed_at
        if age > max_age:
            log.warning(
                "%s/%s: migawka starsza niż %s (wiek %s) — brak wyceny",
                quote.match_id,
                quote.market,
                max_age,
                age,
            )
            skipped["za stara"] += 1
            continue
        if age > STALE_WARNING_AGE:
            log.warning(
                "%s/%s: migawka ma %s — wyceniam, ale to dużo",
                quote.match_id,
                quote.market,
                age,
            )

        # Nieznany rynek to błąd kontraktu, nie dana do pominięcia.
        # Cicha wycena rynku o nieznanym komplecie łamie regułę 17 w
        # najgorszy możliwy sposób: bez żadnego sygnału.
        if quote.market not in MARKET_SIZE:
            raise ValueError(
                f"{quote.match_id}: nieznany rynek {quote.market!r}. Dopisz go do "
                f"MARKET_SIZE razem z liczbą wyników, zanim zaczniesz wyceniać "
                f"(reguła 17). Znane: {sorted(MARKET_SIZE)}"
            )
        expected = MARKET_SIZE[quote.market]
        if len(quote.odds) != expected:
            log.warning(
                "%s/%s: niekompletny rynek, %d z %d wyników — Shin pominięty "
                "(reguła 17)",
                quote.match_id,
                quote.market,
                len(quote.odds),
                expected,
            )
            skipped["niekompletny rynek"] += 1
            continue
        if len(quote.outcomes) != len(quote.odds):
            raise ValueError(
                f"{quote.match_id}/{quote.market}: outcomes i odds różnej długości"
            )
        if any(k <= 1.0 for k in quote.odds):
            log.warning(
                "%s/%s: kurs <= 1.0 w %s — pomijam", quote.match_id, quote.market,
                quote.odds,
            )
            skipped["kurs <= 1.0"] += 1
            continue

        try:
            result = shin_probabilities(np.asarray(quote.odds, dtype=np.float64), strict=True)
        except ShinNotConvergedError:
            log.warning("%s/%s: Shin nie zbiegł — pomijam", quote.match_id, quote.market)
            skipped["Shin nie zbiegł"] += 1
            continue
        except ValueError as exc:
            # Książka bez marży (booksum <= 1) podnosi wyjątek z Shina.
            # Kontrakt tej funkcji mówi „pomijane z ostrzeżeniem", więc
            # jedna dziwna migawka nie może wysadzić wyceny całego dnia.
            log.warning(
                "%s/%s: Shin odrzucił książkę (%s) — pomijam",
                quote.match_id,
                quote.market,
                exc,
            )
            skipped["Shin odrzucił książkę"] += 1
            continue
        for outcome, p in zip(quote.outcomes, result.probabilities, strict=True):
            out.append(
                FairPrice(
                    match_id=quote.match_id,
                    market=quote.market,
                    outcome=outcome,
                    line=quote.line,
                    p=float(p),
                    observed_at=quote.observed_at,
                    booksum=result.booksum,
                    z=result.z,
                )
            )
    return FairPricing(prices=out, skipped=skipped)
