"""Stawkowanie — Kelly ułamkowy z limitami i wyłącznikiem (TOR_S_PLAN §5).

Reguły 21-23 z ``CLAUDE.md``, plus polityka z ``ROADMAP.md`` §3.1.

Dlaczego ułamek 0.5 jest sprawdzany kodem, nie flagą
----------------------------------------------------
Pełny Kelly na modelu z błędem estymacji prowadzi do ruiny — to nie jest
ostrożność, to matematyka. ``c = 0.25`` jest domyślne; ``c = 0.5`` wolno
**wyłącznie** po bramce G-K, czyli po ≥ 150 prawdziwych zakładach ze
średnim CLV, którego dolna granica CI jest dodatnia.

Do Filaru 3 ``c = 0.5`` jest **zablokowane w kodzie** (``CLAUDE.md`` reguła
21, FSA #0 F-06/F-19): bramka G-K jest liczona i raportowana
(``StakeDecision.gk_would_unlock``), ale ``c`` zostaje 0.25 na każdej
ścieżce. Odblokowanie wymaga implementacji korekty
``e_użyte = e · min(1, CLV/EV)`` (``TOR_S_PLAN.md`` §5), testu i FSA — nie
zmiany stałej ``HALF_KELLY_ENABLED``, która nie jest czytana ani z ``.env``,
ani z argumentu.

Jedyna droga konstrukcji to ``KellyPolicy.from_journal`` z typowanym
``ClvReport``. Poprzednia wersja miała publiczny konstruktor i trzy pola,
które wołający podawał wprost — „bramka” była trzema flagami (F-19). Martwa
gałąź korekty CLV/EV (obie odnogi ``if`` przypisywały ``None``) usunięta
(F-06).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Final

from valuebet.backtest.clv import ClvReport
from valuebet.pricing.ev import (
    WINNINGS_UNTAXED,
    ev,
    validate_tax_factor,
    validate_winnings_factor,
    winnings_factor_for,
)

__all__ = [
    "DRAWDOWN_SWITCH",
    "GK_MIN_REAL_BETS",
    "HALF_KELLY_ENABLED",
    "MAX_FRACTION_PER_BET",
    "MAX_FRACTION_PER_MATCH",
    "MAX_OPEN_EXPOSURE",
    "KellyPolicy",
    "StakeDecision",
    "kelly_fraction",
    "meets_min_stake",
]

log = logging.getLogger(__name__)

#: Reguła 23 — twardy limit na jeden zakład.
MAX_FRACTION_PER_BET = 0.02
#: Zakłady na jeden mecz są skorelowane (STEP4_PLAN §4.2).
MAX_FRACTION_PER_MATCH = 0.03
#: Łączna otwarta ekspozycja.
MAX_OPEN_EXPOSURE = 0.15

#: Bramka G-K: tyle PRAWDZIWYCH zakładów i dodatnia dolna granica CI CLV.
GK_MIN_REAL_BETS = 150

#: Obsunięcie od szczytu kapitału, które przełącza w tryb paper.
DRAWDOWN_SWITCH = 0.25

_DEFAULT_C = 0.25
_MAX_C = 0.5

#: c = ½ po bramce G-K. **Wyłączone do Filaru 3.** Włączenie wymaga
#: implementacji korekty ``e_użyte = e · min(1, CLV/EV)`` (TOR_S_PLAN §5),
#: testu i FSA w Filarze 3 — nie zmiany tej stałej. Nie jest czytana z
#: ``.env`` ani z argumentu.
HALF_KELLY_ENABLED: Final = False

#: Znacznik jedynej dozwolonej drogi konstrukcji (``from_journal``).
_FROM_JOURNAL: Final = object()


def kelly_fraction(
    p: float, odds: float, *, tax_factor: float, winnings_factor: float
) -> float:
    """``f* = (p*k*tax*w - 1) / (k*tax*w - 1)`` — reguła 22, na kursie efektywnym.

    ``w`` — podatek od wygranej (promocje.md T13), osobno od ``tax_factor``.

    Zwraca 0.0, gdy EV jest niedodatnie: Kelly nie stawia na przegrywające
    zakłady, a ujemny ułamek nie znaczy „postaw na przeciwny wynik", bo
    takiego zakładu u bukmachera nie ma.
    """
    if not 0.0 < p <= 1.0:
        raise ValueError(f"p musi być w (0, 1], jest {p}")
    if odds <= 1.0:
        raise ValueError(f"kurs musi być > 1.0, jest {odds}")
    effective = (
        odds
        * validate_tax_factor(tax_factor=tax_factor)
        * validate_winnings_factor(winnings_factor=winnings_factor)
    )
    if effective <= 1.0:
        # Kurs po podatku nie przekracza stawki — nie ma czego wygrać.
        return 0.0
    numerator = p * effective - 1.0
    if numerator <= 0.0:
        return 0.0
    return numerator / (effective - 1.0)


def meets_min_stake(stake: float, *, min_stake_pln: float) -> bool:
    """Czy stawka osiąga minimalną stawkę bukmachera (promocje.md T12).

    Jedno porównanie dla live i backtestu (reguła 28). Decyzja Pawła
    2026-10-11: stawka poniżej → zakład **pominięty**, nigdy zaokrąglony w
    górę (zaokrąglenie podnosiłoby ułamek Kelly'ego ponad wyliczony).
    ``min_stake_pln`` wymagane, > 0 (reguła 30: brak minimalnej stawki to nie
    „0 zł”).
    """
    if (
        isinstance(min_stake_pln, bool)
        or not isinstance(min_stake_pln, int | float)
        or not math.isfinite(min_stake_pln)
        or min_stake_pln <= 0.0
    ):
        raise ValueError(f"min_stake_pln musi być liczbą skończoną > 0, jest {min_stake_pln!r}")
    return stake >= min_stake_pln


@dataclass(frozen=True)
class StakeDecision:
    """Co postawić i dlaczego tyle. ``reasons`` niesie zadziałane ograniczenia."""

    fraction: float
    stake: float
    mode: str
    kelly_full: float
    c: float
    reasons: tuple[str, ...]
    #: Czy bramka G-K byłaby otwarta. Raportowane, nie stosowane — c = ¼.
    gk_would_unlock: bool
    #: Podatek od wygranej przy tej stawce (promocje.md T13).
    winnings_factor: float
    #: EV kuponu z ``tax_factor`` i ``winnings_factor`` tej stawki.
    ev: float

    @property
    def is_paper(self) -> bool:
        return self.mode == "paper"


@dataclass(frozen=True, kw_only=True)
class KellyPolicy:
    """Polityka stawek. Stan bramki G-K i wyłącznika liczony z dziennika.

    Wyłącznie przez :meth:`from_journal` — konstrukcja wprost podnosi
    ``RuntimeError``.
    """

    bankroll: float
    peak_bankroll: float
    #: Prawdziwe **kupony** z dziennika tego przebiegu (G-K liczy kupony).
    n_real_bets: int
    clv_report: ClvReport
    #: Ekspozycja już otwarta, jako ułamek kapitału.
    open_exposure: float
    #: Ekspozycja już otwarta na TYM meczu, jako ułamek kapitału.
    match_exposure: float
    _via: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._via is not _FROM_JOURNAL:
            raise RuntimeError(
                "KellyPolicy wyłącznie przez KellyPolicy.from_journal — konstrukcja "
                "wprost omijała bramkę G-K (FSA #0 F-19)"
            )
        if not isinstance(self.clv_report, ClvReport):
            raise TypeError(
                f"clv_report musi być ClvReport, jest {type(self.clv_report).__name__}"
            )
        for name in ("bankroll", "peak_bankroll", "open_exposure", "match_exposure"):
            value = getattr(self, name)
            if not isinstance(value, int | float) or value != value or value < 0:
                raise ValueError(f"{name} musi być liczbą ≥ 0, jest {value!r}")
        if self.n_real_bets < 0:
            raise ValueError("n_real_bets nie może być ujemne")

    @property
    def gk_passed(self) -> bool:
        """Bramka G-K — liczona, nie ustawiana. Dziś tylko raportowana.

        Wymaga ≥ 150 prawdziwych kuponów **i** raportu CLV, który ją otwiera
        (dodatnia dolna granica CI, pokrycie zamknięciami, dość klastrów).
        """
        return (
            self.n_real_bets >= GK_MIN_REAL_BETS
            and self.clv_report.unlocks_gk
            and self.clv_report.ci_low is not None
            and self.clv_report.ci_low > 0.0
        )

    @property
    def drawdown(self) -> float:
        if self.peak_bankroll <= 0.0:
            return 0.0
        return max(0.0, 1.0 - self.bankroll / self.peak_bankroll)

    @property
    def switched_to_paper(self) -> bool:
        """Wyłącznik: obsunięcie 25% od szczytu przełącza w tryb paper."""
        return self.drawdown >= DRAWDOWN_SWITCH

    @property
    def c(self) -> float:
        """Ułamek Kelly'ego: 0.25. c = ½ zablokowane do Filaru 3."""
        if HALF_KELLY_ENABLED and self.gk_passed:
            return _MAX_C
        return _DEFAULT_C

    @classmethod
    def from_journal(
        cls,
        *,
        bankroll: float,
        peak_bankroll: float,
        clv_report: ClvReport,
        n_real_bets: int,
        open_exposure: float,
        match_exposure: float,
    ) -> KellyPolicy:
        """Jedyna droga konstrukcji. Wszystko wymagane (reguła 30)."""
        return cls(
            bankroll=bankroll,
            peak_bankroll=peak_bankroll,
            n_real_bets=n_real_bets,
            clv_report=clv_report,
            open_exposure=open_exposure,
            match_exposure=match_exposure,
            _via=_FROM_JOURNAL,
        )

    def _fraction(
        self, p: float, odds: float, *, tax_factor: float, winnings_factor: float
    ) -> tuple[float, float, list[str]]:
        reasons: list[str] = []
        full = kelly_fraction(
            p, odds, tax_factor=tax_factor, winnings_factor=winnings_factor
        )
        fraction = self.c * full

        if fraction > MAX_FRACTION_PER_BET:
            reasons.append(f"limit na zakład {MAX_FRACTION_PER_BET:.0%}")
            fraction = MAX_FRACTION_PER_BET

        room_match = max(0.0, MAX_FRACTION_PER_MATCH - self.match_exposure)
        if fraction > room_match:
            reasons.append(f"limit na mecz {MAX_FRACTION_PER_MATCH:.0%}")
            fraction = room_match

        room_total = max(0.0, MAX_OPEN_EXPOSURE - self.open_exposure)
        if fraction > room_total:
            reasons.append(f"limit otwartej ekspozycji {MAX_OPEN_EXPOSURE:.0%}")
            fraction = room_total
        return fraction, full, reasons

    def stake(self, p: float, odds: float, *, tax_factor: float) -> StakeDecision:
        """Stawka w złotych i ułamek kapitału, z powodami ograniczeń.

        Podatek od wygranej (T13) zależy od stawki, więc liczymy go z
        wypłaty przy wyliczonej stawce: gdy przekracza 2280 zł, **jedno**
        przeliczenie z ``w = 0.90``; stawka nie rośnie.
        """
        fraction, full, reasons = self._fraction(
            p, odds, tax_factor=tax_factor, winnings_factor=WINNINGS_UNTAXED
        )
        w = winnings_factor_for(
            stake=round(fraction * self.bankroll, 2), odds=odds, tax_factor=tax_factor
        )
        if w != WINNINGS_UNTAXED:
            taxed, full, more = self._fraction(
                p, odds, tax_factor=tax_factor, winnings_factor=w
            )
            fraction = min(fraction, taxed)
            reasons = [*more, f"podatek od wygranej x{w:.2f} (T13)"]

        mode = "paper" if self.switched_to_paper else "real"
        if self.switched_to_paper:
            reasons.append(
                f"wyłącznik: obsunięcie {self.drawdown:.0%} >= {DRAWDOWN_SWITCH:.0%}"
            )
            # DEBUG, nie WARNING: w backteście ta linia szła przy KAŻDEJ stawce po
            # wyłączniku (tysiące identycznych linii, bramka 17a0759). Komunikat
            # raz na przebieg i licznik — ``backtest.financial.simulate``.
            log.debug(
                "tryb PAPER: obsunięcie %.1f%% od szczytu kapitału",
                100.0 * self.drawdown,
            )
        return StakeDecision(
            fraction=fraction,
            stake=round(fraction * self.bankroll, 2),
            mode=mode,
            kelly_full=full,
            c=self.c,
            reasons=tuple(reasons),
            gk_would_unlock=self.gk_passed,
            winnings_factor=w,
            ev=ev(p, odds, tax_factor=tax_factor, winnings_factor=w),
        )
