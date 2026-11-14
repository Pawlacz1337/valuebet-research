"""EV, progi kursowe i reżim podatkowy Betclica (TOR_S_PLAN §4).

Dlaczego reżim podatkowy jest tu, a nie w konfiguracji
------------------------------------------------------
Bo **nie jest stały** i zależy od historii własnych zakładów. Promocja
„Bez Podatku 2.0” (regulamin 21.05.2026 v2, ``docs/promocje.md``):

- jeśli przed zakładem zostaje jakakolwiek kwota limitu 1000 zł — cały
  zakład bez podatku (``tax = 1.00``), niezależnie od stawki (§3 ust. 4);
- potem single i wielokrotne niekwalifikujące się bez podatku tylko przy
  udziale stawek kwalifikujących się AKO ≥ 50%; mniej → 6% (``tax = 0.94``);
- kwalifikujący się AKO jest bez podatku zawsze.

Konsekwencja, której łatwo nie zauważyć: **pojedynczy zakład może sam
zepchnąć udział poniżej progu** i tym samym zmienić swój własny podatek.
Dlatego podatek kandydata liczony jest w wariancie „co jeśli” — z
kandydatem wliczonym do udziału (T3).

Tylko zakłady PRAWDZIWE
-----------------------
Paper trading nie generuje obrotu u bukmachera, więc nie wchodzi ani do
progu 1000 zł, ani do udziału AKO (T11). Wliczanie go dawałoby fałszywe 1.00.

Jednostka: kupon
----------------
``PlacedBet`` to **kupon** (singiel albo wielokrotny) z nogami. Dziennik
zapisuje kupon wielokrotny jako N wierszy z jedną stawką kuponu, a
``live.bets.coupons`` składa je z powrotem — wcześniej każdy wiersz był
osobnym „singlem”, więc udział AKO był strukturalnie zerowy, a obrót AKO
liczony N razy (FSA #0 F-02).
"""

from __future__ import annotations

import logging
import math
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any, Final
from zoneinfo import ZoneInfo

import yaml

from valuebet.schema import MarketType, canonical_market

__all__ = [
    "AKO_MIN_LEGS",
    "AKO_MIN_LEG_ODDS",
    "AKO_SHARE_THRESHOLD",
    "AKO_WINDOW_BETS",
    "AKO_WINDOW_MONTHS",
    "ALLOWED_TAX_FACTORS",
    "ALLOWED_WINNINGS_FACTORS",
    "BETCLIC_READING",
    "NO_TAX_TURNOVER_LIMIT",
    "SHARE_BASES",
    "SHARE_BY_STAKES",
    "SHARE_BY_STAKES_AND_COUPONS",
    "VERIFICATION_MAX_AGE_DAYS",
    "WINNINGS_TAX_THRESHOLD",
    "BetclicTaxRegime",
    "CouponLeg",
    "EvResult",
    "PlacedBet",
    "RegimeConfig",
    "double_ev",
    "ev",
    "evaluate",
    "load_betclic_regime_config",
    "min_odds",
    "qualifies_as_ako",
    "real_turnover",
    "settlement_payout",
    "validate_edge_threshold",
    "validate_tax_factor",
    "validate_winnings_factor",
    "warsaw_midnight_utc",
    "winnings_factor_for",
]

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# REGULAMIN 21.05.2026 v2, odczyt dosłowny z PDF (2026-10-08) — F1-P01 pkt 1-3
# naprawione 2026-10-11 (wariant B, decyzja Pawła, przed wynikiem). Tam, gdzie
# regulamin czegoś nie rozstrzyga (T3, T6, T7, T12), zostaje wariant najmniej
# korzystny dla gracza z decyzji 2026-10-02 (FSA #0 F-25). Każda stała ma
# wiersz w ``docs/promocje.md`` (cytat z paragrafu albo jawny wariant
# pesymistyczny).
# ---------------------------------------------------------------------------
BETCLIC_READING: Final = "regulamin-2026-10-11"

#: promocje.md T4 — §3 ust. 5: „procentowego udziału stawek” — regulamin.
SHARE_BY_STAKES: Final = "stakes"
#: promocje.md T4 — margines Pawła z 2026-10-02 (po stawkach I po kuponach).
#: Od 2026-10-11 wyłącznie raport wrażliwości strategii C.
SHARE_BY_STAKES_AND_COUPONS: Final = "stakes_and_coupons"
SHARE_BASES: Final = (SHARE_BY_STAKES, SHARE_BY_STAKES_AND_COUPONS)

#: promocje.md T2 — „łączna suma stawek … osiągnie kwotę 1,000 PLN”.
NO_TAX_TURNOVER_LIMIT: Final = 1000.0

#: promocje.md T5 — „co najmniej 50%”. Ten sam próg dla udziału po stawkach
#: (T4, regulamin) i po liczbie kuponów (T4, wariant wrażliwości).
AKO_SHARE_THRESHOLD: Final = 0.50

#: promocje.md T6 — „o kursie równym lub wyższym 1.20 każdy”.
AKO_MIN_LEG_ODDS: Final = 1.20

#: promocje.md T6 — „co najmniej dwóch zdarzeń”; wariant pesymistyczny: z
#: różnych meczów, nogi zwrócone się nie liczą.
AKO_MIN_LEGS: Final = 2

#: promocje.md T7 — „ostatnich 5000 (pięć tysięcy) Zakładów”; liczone kupony.
AKO_WINDOW_BETS: Final = 5000

#: promocje.md T7 — „po upływie 12 miesięcy … ostatnich 12 miesięcy”;
#: miesiące KALENDARZOWE, nie 360 dni (FSA #0 F-08).
AKO_WINDOW_MONTHS: Final = 12

#: promocje.md T1 — w live weryfikacja regulaminu starsza niż kwartał →
#: promocja uznana za nieaktywną (0.88). Sprawdza ładowacz, nie reżim.
VERIFICATION_MAX_AGE_DAYS: Final = 92

#: promocje.md T2 / T9 — bez podatku.
TAX_NO_TAX: Final = 1.00
#: promocje.md T8 — „ze Wskaźnikiem 0.94 (6%)”.
TAX_SINGLE_PENALTY: Final = 0.94
#: Podatek ustawowy: brak promocji (T1), warunek wyłączający z T12.
TAX_STATUTORY: Final = 0.88

WARSAW: Final = ZoneInfo("Europe/Warsaw")

# ---------------------------------------------------------------------------
# Podatek od wygranej — USTAWOWY, nie promocja (promocje.md T13, FSA0 A-02).
# Osobny czynnik ``winnings_factor``, nigdy wliczany w ``tax_factor``
# (reguła 20). Wariant pesymistyczny: wypłata kuponu ``stawka · k · tax``
# powyżej progu → 0.90 na CAŁEJ wypłacie.
# ---------------------------------------------------------------------------
#: CONTEXT.md §2 — „10% od wygranej powyżej 2280 PLN z jednego kuponu”.
WINNINGS_TAX_THRESHOLD: Final = 2280.0
WINNINGS_UNTAXED: Final = 1.00
WINNINGS_TAXED: Final = 0.90
ALLOWED_WINNINGS_FACTORS: Final = (WINNINGS_UNTAXED, WINNINGS_TAXED)


def warsaw_midnight_utc(day: date) -> datetime:
    """Data z YAML → północ Europe/Warsaw → UTC (promocje.md, „Konfiguracja”)."""
    return datetime.combine(day, time(0), tzinfo=WARSAW).astimezone(UTC)


def months_before(moment: datetime, months: int) -> datetime:
    """Ta sama chwila ``months`` miesięcy kalendarzowych wcześniej (czas warszawski).

    31 marca minus miesiąc to 28/29 lutego — dzień przycinany do długości
    miesiąca docelowego.
    """
    local = moment.astimezone(WARSAW)
    total = local.year * 12 + (local.month - 1) - months
    year, month0 = divmod(total, 12)
    day = local.day
    while True:
        try:
            shifted = local.replace(year=year, month=month0 + 1, day=day)
        except ValueError:
            day -= 1
            continue
        return shifted.astimezone(UTC)


@dataclass(frozen=True)
class CouponLeg:
    """Noga kuponu w zakresie potrzebnym reżimowi: mecz, kurs, czy zwrócona."""

    match_id: str
    odds: float
    void: bool
    #: Rynek nogi — do wyłączeń z T12. **Wymagany, ze słownika**
    #: ``schema.MARKET_ALIASES`` (reguła 30): domyślne ``""`` omijało T12
    #: (F0b-02), napis spoza słownika też (F0c-03).
    market: str

    def __post_init__(self) -> None:
        if self.odds <= 1.0:
            raise ValueError(f"kurs nogi musi być > 1.0, jest {self.odds}")
        canonical_market(self.market)


def qualifies_as_ako(legs: Iterable[CouponLeg]) -> bool:
    """Kupon jest kwalifikującym się AKO (promocje.md T6, wariant pesymistyczny).

    Liczą się nogi **niezwrócone**: co najmniej dwie, każda z kursem ≥ 1.20,
    wszystkie z **różnych** meczów. Jedna funkcja dla zapisu do dziennika
    (nogi postawione) i dla reżimu (stan kuponu w chwili ``now``).
    """
    valid = [leg for leg in legs if not leg.void]
    matches = [leg.match_id for leg in valid]
    return (
        len(valid) >= AKO_MIN_LEGS
        and len(set(matches)) == len(matches)
        and all(leg.odds >= AKO_MIN_LEG_ODDS for leg in valid)
    )


@dataclass(frozen=True)
class PlacedBet:
    """Kupon z dziennika, w zakresie potrzebnym do reżimu podatkowego."""

    coupon_id: str
    placed_at: datetime
    #: Stawka KUPONU — raz, nie per noga.
    stake: float
    legs: tuple[CouponLeg, ...]
    #: BEZ wartości domyślnej. Domyślne ``"real"`` powodowało, że zakład
    #: paper liczył się jako prawdziwy, gdy ktoś pominął argument — a to
    #: zawyża obrót i może dać fałszywe ``tax = 1.00``.
    mode: str

    def __post_init__(self) -> None:
        if self.mode not in ("paper", "real"):
            raise ValueError(f"mode musi być paper albo real, jest {self.mode!r}")
        if self.placed_at.tzinfo is None:
            raise ValueError("placed_at musi być timezone-aware (reguła 2)")
        if not self.legs:
            raise ValueError("kupon bez nóg")
        if self.stake <= 0.0:
            raise ValueError(f"stawka musi być dodatnia, jest {self.stake}")

    @property
    def is_real(self) -> bool:
        return self.mode == "real"

    @property
    def is_multi(self) -> bool:
        return len(self.legs) > 1

    @property
    def qualifies_as_ako(self) -> bool:
        return qualifies_as_ako(self.legs)


@dataclass(frozen=True, kw_only=True)
class RegimeConfig:
    """Parametry reżimu — **wszystkie wymagane**, bez ``None`` (reguła 30).

    Braki w ``config/bookmakers.yaml`` rozstrzyga ładowacz live
    (:func:`load_betclic_regime_config`) według promocje.md, zanim reżim
    powstanie. Backtest buduje ``RegimeConfig`` jawnie (wariant
    kontrfaktyczny, promocje.md „Wariant kontrfaktyczny”).
    """

    #: T1 — ``False``: promocja uznana za nieaktywną (np. weryfikacja
    #: regulaminu nieświeża) → wszystko 0.88.
    promo_active: bool
    #: T1/T2 — start akcji (UTC). Obrót do progu liczony od tej chwili.
    promo_valid_from: datetime
    #: T7 — chwila przystąpienia do oferty (UTC).
    join_date: datetime
    #: T2 — stawki u Betclica spoza dziennika od startu akcji. Wchodzą do
    #: progu 1000 zł i do mianownika udziału po stawkach jako nie-AKO.
    external_turnover_pln: float
    #: T2/T4 — kupony spoza dziennika; mianownik udziału po kuponach.
    external_coupons: int
    #: T4/T7 — ``False``: warunek udziału uznany za niespełniony (brak
    #: ``join_date`` albo ``external_coupons`` w konfiguracji).
    share_condition_known: bool
    #: T12 — minimalna stawka kwalifikująca; zakład poniżej → 0.88.
    min_stake_pln: float
    #: T12 — rynki wyłączone z oferty; noga na takim rynku → kupon 0.88.
    #: Przyjmuje klucze z ``schema.MARKET_ALIASES``, przechowuje kanoniczne.
    excluded_markets: frozenset[MarketType]
    #: T4 — podstawa udziału AKO: :data:`SHARE_BY_STAKES` (regulamin, §3 ust. 5)
    #: albo :data:`SHARE_BY_STAKES_AND_COUPONS` (tylko wrażliwość C). Wymagana,
    #: bez wartości domyślnej (reguła 30, F1-P01 pkt 3).
    share_basis: str

    def __post_init__(self) -> None:
        for name in ("promo_valid_from", "join_date"):
            if getattr(self, name).tzinfo is None:
                raise ValueError(f"{name} musi być timezone-aware (reguła 2)")
        if not math.isfinite(self.external_turnover_pln) or self.external_turnover_pln < 0:
            raise ValueError("external_turnover_pln musi być skończone i ≥ 0")
        if self.external_coupons < 0:
            raise ValueError("external_coupons nie może być ujemne")
        if (
            isinstance(self.min_stake_pln, bool)
            or not isinstance(self.min_stake_pln, int | float)
            or not math.isfinite(self.min_stake_pln)
            or self.min_stake_pln < 0
        ):
            raise ValueError("min_stake_pln musi być liczbą skończoną i ≥ 0")
        if not isinstance(self.excluded_markets, frozenset):
            # Napis to też iterowalne — frozenset("spreads") to zbiór liter (F0c-03).
            raise TypeError("excluded_markets musi być frozenset kluczy rynków")
        if self.share_basis not in SHARE_BASES:
            raise ValueError(f"share_basis {self.share_basis!r} spoza {SHARE_BASES}")
        object.__setattr__(
            self,
            "excluded_markets",
            frozenset(canonical_market(m) for m in self.excluded_markets),
        )


def real_turnover(
    *, bets: Iterable[PlacedBet], now: datetime, regime_config: RegimeConfig
) -> float:
    """Obrót prawdziwy od startu akcji do ``now`` — **jedyna** implementacja (F-03).

    Kupony, nie nogi: stawka kuponu wielokrotnego liczona raz.
    """
    start = regime_config.promo_valid_from
    return sum(b.stake for b in bets if b.is_real and start <= b.placed_at <= now)


@dataclass(frozen=True, kw_only=True)
class BetclicTaxRegime:
    """Reżim podatkowy liczony z dziennika kuponów. Tylko zakłady prawdziwe.

    ``now`` jest **wymagane**. Bez niego nie ma granicy czasowej, a wtedy
    zakłady postawione PO chwili decyzji wchodzą do udziału AKO i zmieniają
    podatek tej decyzji. Zmierzone: dziesięć AKO z przyszłości podniosło
    ``tax_for_single`` z 0.94 na 1.00, czyli o 6 punktów procentowych
    stawki — więcej niż cała przewaga, której szukamy (reguła 1).
    """

    now: datetime
    bets: Iterable[PlacedBet]
    regime_config: RegimeConfig
    _bets: tuple[PlacedBet, ...] = field(init=False, repr=False, default=())

    def __post_init__(self) -> None:
        if self.now.tzinfo is None:
            raise ValueError("now musi być timezone-aware (reguła 2)")
        if not isinstance(self.regime_config, RegimeConfig):
            raise TypeError("regime_config musi być RegimeConfig")
        object.__setattr__(self, "_bets", tuple(self.bets))

    # -- historia ---------------------------------------------------------

    def _eligible(self) -> list[PlacedBet]:
        """Kupony prawdziwe sprzed chwili decyzji. Góra i dół, nie tylko dół."""
        return [b for b in self._bets if b.is_real and b.placed_at <= self.now]

    def window(self) -> list[PlacedBet]:
        """Okno udziału (T7): od przystąpienia; po 12 mies. — ostatnie 12 mies.; ≤ 5000."""
        join = self.regime_config.join_date
        recent = [b for b in self._eligible() if b.placed_at >= join]
        cutoff = months_before(self.now, AKO_WINDOW_MONTHS)
        if cutoff >= join:
            recent = [b for b in recent if b.placed_at >= cutoff]
        return sorted(recent, key=lambda b: (b.placed_at, b.coupon_id))[-AKO_WINDOW_BETS:]

    @property
    def real_turnover(self) -> float:
        """Obrót narastająco od startu akcji (T2), odcięty na ``now``."""
        return real_turnover(
            bets=self._eligible(), now=self.now, regime_config=self.regime_config
        )

    def ako_shares(self, *, candidate: PlacedBet | None) -> tuple[float, float]:
        """(udział po stawkach, udział po kuponach) — T4, z kandydatem „co jeśli”.

        Obrót spoza dziennika wchodzi do obu mianowników jako nie-AKO (T2).
        """
        window = self.window()
        if candidate is not None:
            window = [*window, candidate]
        cfg = self.regime_config
        stake_total = sum(b.stake for b in window) + cfg.external_turnover_pln
        coupon_total = len(window) + cfg.external_coupons
        ako = [b for b in window if b.qualifies_as_ako]
        by_stake = sum(b.stake for b in ako) / stake_total if stake_total > 0 else 0.0
        by_coupons = len(ako) / coupon_total if coupon_total > 0 else 0.0
        return by_stake, by_coupons

    def share_condition_met(self, *, candidate: PlacedBet | None) -> bool:
        """T4 + T5: udział ≥ 50% — po stawkach (regulamin, §3 ust. 5); w wariancie
        wrażliwości :data:`SHARE_BY_STAKES_AND_COUPONS` także po kuponach."""
        if not self.regime_config.share_condition_known:
            return False
        by_stake, by_coupons = self.ako_shares(candidate=candidate)
        if self.regime_config.share_basis == SHARE_BY_STAKES:
            return by_stake >= AKO_SHARE_THRESHOLD
        return by_stake >= AKO_SHARE_THRESHOLD and by_coupons >= AKO_SHARE_THRESHOLD

    # -- podatek kandydata --------------------------------------------------

    def tax_for_coupon(self, *, stake: float, legs: tuple[CouponLeg, ...]) -> float:
        """Podatek kandydata — kupon postawiony teraz, wariant „co jeśli” (T3)."""
        cfg = self.regime_config
        if not cfg.promo_active or self.now < cfg.promo_valid_from:
            return TAX_STATUTORY  # T1
        if stake < cfg.min_stake_pln or any(
            canonical_market(leg.market) in cfg.excluded_markets for leg in legs
        ):
            return TAX_STATUTORY  # T12 — warunek wyłączający z oferty
        # T2 / §3 ust. 4 (F1-P01 pkt 1) — przed zakładem zostaje jakakolwiek kwota
        # limitu → cały zakład w ofercie, niezależnie od stawki i rodzaju.
        used = self.real_turnover + cfg.external_turnover_pln
        if used < NO_TAX_TURNOVER_LIMIT:
            return TAX_NO_TAX
        candidate = PlacedBet(
            coupon_id="kandydat", placed_at=self.now, stake=stake, legs=legs, mode="real"
        )
        # T9 / §3 ust. 11.2 — kwalifikujący się AKO bez podatku zawsze.
        if candidate.is_multi and candidate.qualifies_as_ako:
            return TAX_NO_TAX
        # T8, T10 / §3 ust. 11.1 i 12 (F1-P01 pkt 2) — singiel i wielokrotny
        # niekwalifikujący się: 1.00 przy udziale ≥ 50% z kandydatem, inaczej 0.94.
        if self.share_condition_met(candidate=candidate):
            return TAX_NO_TAX
        return TAX_SINGLE_PENALTY

    def tax_for_single(
        self, stake: float, *, market: str, match_id: str = "kandydat"
    ) -> float:
        """Singiel postawiony teraz. Kurs nogi nie wpływa na podatek singla.

        ``market`` wymagany — bez niego singiel na wyłączonym rynku dostawał
        1.00 zamiast 0.88 (T12, F0b-02).
        """
        return self.tax_for_coupon(
            stake=stake,
            legs=(CouponLeg(match_id=match_id, odds=2.0, void=False, market=market),),
        )

    def tax_for_multi(self, *, stake: float, legs: tuple[CouponLeg, ...]) -> float:
        if len(legs) < 2:
            raise ValueError("kupon wielokrotny ma co najmniej dwie nogi")
        return self.tax_for_coupon(stake=stake, legs=legs)

    def assume(self, bet: PlacedBet) -> BetclicTaxRegime:
        """Reżim po zawarciu kandydata — kolejni kandydaci z migawki widzą poprzednich (T3)."""
        return replace(self, bets=(*self._bets, bet))


def _yaml_date(raw: Any) -> date | None:
    """Data z YAML (``date``, ``datetime`` albo tekst ISO); ``None`` = brak."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    return date.fromisoformat(str(raw))


def load_betclic_regime_config(path: Path, *, now: datetime) -> RegimeConfig:
    """Ładowacz konfiguracji **live** — rozstrzyga braki według promocje.md.

    - T1: ``promo_verified_on`` brak albo starsze niż 92 dni → promocja
      nieaktywna (0.88) i ostrzeżenie; ``now`` przed ``promo_valid_from`` → 0.88
      (to sprawdza reżim).
    - T2: brak ``external_turnover_pln`` → próg uznany za wykorzystany (1000);
      brak ``external_coupons`` → warunek udziału niespełniony.
    - T7: brak ``join_date`` → warunek udziału niespełniony (single 0.94).
    - T12: ``min_stake_pln``, ``excluded_markets`` — z regulaminu (F-25b).
      Brak któregokolwiek (``null`` albo brak klucza) → promocja nieaktywna
      (0.88): nieznany warunek wyłączający to wariant najmniej korzystny, a
      nie „0 zł i żaden rynek” (F0b-02). Jawne ``[]`` = regulamin nie wyłącza
      żadnego rynku.

    Daty: północ Europe/Warsaw → UTC.
    """
    if now.tzinfo is None:
        raise ValueError("now musi być timezone-aware (reguła 2)")
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    found: Any = raw.get("betclic") if isinstance(raw, dict) else None
    section: dict[str, Any] | None = found if isinstance(found, dict) else None
    if section is None:
        raise ValueError(f"{path}: brak sekcji betclic")
    valid_from = _yaml_date(section.get("promo_valid_from"))
    if valid_from is None:
        raise ValueError(f"{path}: brak promo_valid_from (T1)")
    verified = _yaml_date(section.get("promo_verified_on"))
    join = _yaml_date(section.get("join_date"))
    turnover = section.get("external_turnover_pln")
    coupons = section.get("external_coupons")
    min_stake = section.get("min_stake_pln")
    excluded = section.get("excluded_markets")

    today = now.astimezone(WARSAW).date()
    fresh = verified is not None and (today - verified).days <= VERIFICATION_MAX_AGE_DAYS
    if not fresh:
        log.warning(
            "regulamin Betclica niezweryfikowany albo weryfikacja starsza niż %d dni "
            "— promocja traktowana jako nieaktywna, podatek 0.88 (promocje.md T1)",
            VERIFICATION_MAX_AGE_DAYS,
        )
    t12_known = min_stake is not None and excluded is not None
    # Zła postać to głośny błąd, nie wariant najkorzystniejszy (F0c-03).
    if min_stake is not None and (
        isinstance(min_stake, bool) or not isinstance(min_stake, int | float) or min_stake < 0
    ):
        raise ValueError(f"{path}: min_stake_pln musi być liczbą ≥ 0, jest {min_stake!r}")
    if excluded is not None:
        if not isinstance(excluded, list) or not all(isinstance(m, str) for m in excluded):
            raise ValueError(
                f"{path}: excluded_markets musi być listą kluczy rynków, jest {excluded!r}"
            )
        for name in excluded:
            try:
                canonical_market(name)
            except ValueError as exc:
                raise ValueError(f"{path}: excluded_markets — {exc}") from exc
    if not t12_known:
        log.warning(
            "T12 nieuzupełnione (min_stake_pln / excluded_markets) — promocja "
            "traktowana jako nieaktywna, podatek 0.88 (promocje.md T12)"
        )
    start = warsaw_midnight_utc(valid_from)
    return RegimeConfig(
        promo_active=fresh and t12_known,
        promo_valid_from=start,
        join_date=warsaw_midnight_utc(join) if join is not None else start,
        external_turnover_pln=NO_TAX_TURNOVER_LIMIT if turnover is None else float(turnover),
        external_coupons=0 if coupons is None else int(coupons),
        share_condition_known=join is not None and coupons is not None,
        # T12 — przy braku promocja i tak nieaktywna (wyżej); wartości bez znaczenia.
        min_stake_pln=float(min_stake) if min_stake is not None else 0.0,
        excluded_markets=frozenset(excluded) if excluded is not None else frozenset(),
        # T4 — live liczy wg regulaminu (§3 ust. 5). Brak ``external_coupons`` nadal
        # wyłącza warunek udziału (wyżej) — pesymistycznie, choć po stawkach
        # liczba kuponów nie wchodzi; pole uzupełnia Paweł przed Filarem 3.
        share_basis=SHARE_BY_STAKES,
    )


@dataclass(frozen=True)
class EvResult:
    p: float
    odds: float
    tax_factor: float
    winnings_factor: float
    ev: float
    min_odds: float
    edge_threshold: float

    @property
    def is_value(self) -> bool:
        return self.odds >= self.min_odds


#: Jedyne dopuszczalne wartości współczynnika podatkowego (reguła 20).
ALLOWED_TAX_FACTORS: tuple[float, ...] = (TAX_NO_TAX, TAX_SINGLE_PENALTY, TAX_STATUTORY)


def validate_tax_factor(*, tax_factor: float) -> float:
    """Jedna walidacja podatku dla całej wyceny (FSA #0 F-05).

    Wołana przez ``ev``, ``min_odds``, ``evaluate``, ``double_ev`` i
    ``kelly.kelly_fraction``. Wcześniej walidowało tylko ``ev``, a
    ``min_odds`` — jedyna funkcja wyceny w przeglądzie dnia — przyjmowało
    ``tax = -1`` i zwracało ujemny próg, przy którym każdy kurs jest value.
    """
    if (
        isinstance(tax_factor, bool)
        or not isinstance(tax_factor, int | float)
        or math.isnan(tax_factor)
        or tax_factor not in ALLOWED_TAX_FACTORS
    ):
        raise ValueError(
            f"tax_factor {tax_factor!r} poza {{1.00, 0.94, 0.88}} (reguła 20)"
        )
    return float(tax_factor)


def validate_winnings_factor(*, winnings_factor: float) -> float:
    """``winnings_factor`` ∈ {1.00, 0.90} (promocje.md T13)."""
    if (
        isinstance(winnings_factor, bool)
        or not isinstance(winnings_factor, int | float)
        or math.isnan(winnings_factor)
        or winnings_factor not in ALLOWED_WINNINGS_FACTORS
    ):
        raise ValueError(
            f"winnings_factor {winnings_factor!r} poza {{1.00, 0.90}} (promocje.md T13)"
        )
    return float(winnings_factor)


def winnings_factor_for(*, stake: float, odds: float, tax_factor: float) -> float:
    """Czynnik podatku od wygranej dla kuponu: wypłata ``stawka · k · tax`` > 2280 → 0.90."""
    gross = stake * odds * validate_tax_factor(tax_factor=tax_factor)
    return WINNINGS_TAXED if gross > WINNINGS_TAX_THRESHOLD else WINNINGS_UNTAXED


def settlement_payout(*, stake: float, odds: float, tax_factor: float) -> float:
    """Wypłata netto wygranego kuponu: brutto ``stawka · k · tax`` razy czynnik T13.

    ``odds`` to kurs kuponu (iloczyn kursów niezwróconych nóg). Jedno
    miejsce dla dziennika i backtestu (reguła 28); ``reconcile_bets.py``
    liczy to niezależnie, celowo.
    """
    gross = stake * odds * validate_tax_factor(tax_factor=tax_factor)
    return gross * winnings_factor_for(stake=stake, odds=odds, tax_factor=tax_factor)


def validate_edge_threshold(*, edge_threshold: float) -> float:
    """Próg przewagi: skończony i ≥ 0. Źródło: ``config/strategy.yaml``."""
    if not math.isfinite(edge_threshold) or edge_threshold < 0.0:
        raise ValueError(
            f"próg przewagi edge_threshold={edge_threshold!r} musi być skończony "
            "i nieujemny"
        )
    return float(edge_threshold)


def ev(p: float, odds: float, *, tax_factor: float, winnings_factor: float) -> float:
    """``p * k * tax * w - 1``. Reguła 20 — ``tax_factor`` zawsze jawnie; ``w`` z T13."""
    if not 0.0 < p <= 1.0:
        raise ValueError(f"p musi być w (0, 1], jest {p}")
    if odds <= 1.0:
        raise ValueError(f"kurs musi być > 1.0, jest {odds}")
    tax = validate_tax_factor(tax_factor=tax_factor)
    w = validate_winnings_factor(winnings_factor=winnings_factor)
    return p * odds * tax * w - 1.0


def min_odds(
    p: float, *, tax_factor: float, winnings_factor: float, edge_threshold: float
) -> float:
    """``k_min = (1 + theta) / (p * tax * w)`` — próg, od którego warto stawiać.

    To jest liczba, którą człowiek porównuje z tablicą u bukmachera. Przy
    ``tax = 0.88`` i progu 2% wymaga ``p * k >= 1.159``, czyli przewagi
    ~16% — stąd cały projekt stoi na promocji bez podatku.
    """
    if not 0.0 < p <= 1.0:
        raise ValueError(f"p musi być w (0, 1], jest {p}")
    tax = validate_tax_factor(tax_factor=tax_factor)
    w = validate_winnings_factor(winnings_factor=winnings_factor)
    theta = validate_edge_threshold(edge_threshold=edge_threshold)
    return (1.0 + theta) / (p * tax * w)


def evaluate(
    p: float,
    odds: float,
    *,
    tax_factor: float,
    winnings_factor: float,
    edge_threshold: float,
) -> EvResult:
    return EvResult(
        p=p,
        odds=odds,
        tax_factor=tax_factor,
        winnings_factor=winnings_factor,
        ev=ev(p, odds, tax_factor=tax_factor, winnings_factor=winnings_factor),
        min_odds=min_odds(
            p,
            tax_factor=tax_factor,
            winnings_factor=winnings_factor,
            edge_threshold=edge_threshold,
        ),
        edge_threshold=edge_threshold,
    )


def double_ev(
    legs: tuple[tuple[str, float, float], ...], *, tax_factor: float, winnings_factor: float
) -> float:
    """EV dubletu: ``prod(p_i * k_i) * tax * w - 1``.

    ``legs`` to ``(match_id, p, k)``. Zdarzenia z tego samego meczu
    podnoszą wyjątek — są skorelowane, a ten wzór zakłada niezależność
    i dałby zawyżone EV.
    """
    tax = validate_tax_factor(tax_factor=tax_factor)
    w = validate_winnings_factor(winnings_factor=winnings_factor)
    if len(legs) < 2:
        raise ValueError("dublet ma co najmniej dwie nogi")
    matches = [leg[0] for leg in legs]
    if len(set(matches)) != len(matches):
        raise ValueError(
            "dwie nogi z tego samego meczu — zdarzenia skorelowane, ten wzór "
            "zakłada niezależność i zawyżyłby EV"
        )
    product = 1.0
    for _match_id, p, odds in legs:
        if not 0.0 < p <= 1.0 or odds <= 1.0:
            raise ValueError(f"nieprawidłowa noga: p={p}, k={odds}")
        product *= p * odds
    return product * tax * w - 1.0
