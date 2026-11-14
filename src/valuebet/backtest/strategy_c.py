"""Strategia C — reżim Betclica w działaniu (BACKTEST_FIN_PLAN §3, docs/promocje.md).

**Kontrfaktyczny reżim Betclica** (wariant B, decyzja Pawła 2026-10-11):
promocja od początku symulacji, limit 1000 zł wykorzystany, kursy zastępcze
B365/BW; T12 zamknięte 2026-10-09 — ``min_stake_pln = 0.50``, bez wyłączonych
rynków. C w bramce §4 (testy 1-7) i w werdykcie (część 2); reżim wg
regulaminu (udział po stawkach), wariant „po stawkach i kuponach” — tylko
wrażliwość. Alarm yield > 8% obowiązuje. Reguła produkcyjna
(``load_betclic_regime_config``) zostaje pesymistyczna przy pustych polach.

Konstrukcja (plan §3, zamrożona): nogi value z jednej migawki (EV ≥ θ przy
1.00 — selektor), EV malejąco, potem ``match_id``; zachłannie pary z RÓŻNYCH
meczów, każda noga ≥ 1.20 → dublet, gdy ``Π(p·k) - 1 ≥ θ``; reszta → single.
Wycena podatku w kolejności T3: najpierw single, potem dublety; każdy
kolejny kupon widzi poprzednie (``BetclicTaxRegime.assume``).

Singiel (decyzja Pawła 2026-10-08, rozbieżność z planem — FIX_LOG_F0):
``production`` — podatek z ``tax_for_single`` (wariant „co jeśli”), próg
``k_min`` i rozliczenie tym samym współczynnikiem; ``literal`` — wariant
dosłowny planu (wybór przy 1.00, stawka przy podatku reżimu), diagnostyka;
``fixed_0.94`` — wrażliwość: single zawsze 0.94 z progiem ``k_min``.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from valuebet.backtest.financial import (
    Candidate,
    RunResult,
    Selector,
    Staker,
    simulate,
)
from valuebet.backtest.replay import Replay
from valuebet.live.bets import Coupon
from valuebet.pricing.ev import (
    AKO_MIN_LEG_ODDS,
    TAX_NO_TAX,
    TAX_SINGLE_PENALTY,
    WINNINGS_UNTAXED,
    BetclicTaxRegime,
    CouponLeg,
    RegimeConfig,
    min_odds,
    validate_edge_threshold,
)
from valuebet.pricing.kelly import StakeDecision

__all__ = [
    "C_LABEL",
    "SINGLE_MODES",
    "RegimePlanner",
    "counterfactual_regime_config",
    "run_regime",
]

#: Wariant B (decyzja Pawła 2026-10-11) — zastępuje „GÓRNA GRANICA, T12
#: nieznane, nie zbadana bramką” z 2026-10-10.
C_LABEL = (
    "kontrfaktyczny reżim Betclica (promocja od początku symulacji, limit 1000 zł "
    "wykorzystany), kursy zastępcze B365/BW"
)
SINGLE_MODES = ("production", "literal", "fixed_0.94")
#: Ile razy wolno przeliczyć stawkę singla, zanim uznamy cykl podatku.
_MAX_TAX_ITERATIONS = 4


def counterfactual_regime_config(
    *, start: datetime, share_basis: str, min_stake_pln: float
) -> RegimeConfig:
    """Wariant kontrfaktyczny (promocje.md): start akcji = start symulacji,
    próg 1000 zł wykorzystany, zero kuponów spoza dziennika; T12 (zamknięte
    2026-10-09): ``min_stake_pln`` z ``config/strategy.yaml`` (0.50), bez
    wyłączonych rynków.

    ``share_basis`` wymagane (reguła 30): ``SHARE_BY_STAKES`` — regulamin,
    przebieg główny C; ``SHARE_BY_STAKES_AND_COUPONS`` — wrażliwość (F1-P01)."""
    return RegimeConfig(
        promo_active=True,
        promo_valid_from=start,
        join_date=start,
        external_turnover_pln=1000.0,
        external_coupons=0,
        share_condition_known=True,
        min_stake_pln=min_stake_pln,
        excluded_markets=frozenset(),
        share_basis=share_basis,
    )


def _legs(group: Sequence[Candidate]) -> tuple[CouponLeg, ...]:
    return tuple(CouponLeg(match_id=c.match_id, odds=c.odds, void=False, market=c.market) for c in group)


@dataclass
class RegimePlanner:
    """Planista C: pary → dublety, reszta → single; podatek z ``BetclicTaxRegime``."""

    regime_config: RegimeConfig
    edge_threshold: float
    single_mode: str
    _regime: BetclicTaxRegime | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.single_mode not in SINGLE_MODES:
            raise ValueError(f"single_mode {self.single_mode!r} spoza {SINGLE_MODES}")
        validate_edge_threshold(edge_threshold=self.edge_threshold)

    @property
    def regime(self) -> BetclicTaxRegime:
        if self._regime is None:
            raise RuntimeError("RegimePlanner.begin nie został wywołany")
        return self._regime

    def begin(self, *, t: datetime, current: Sequence[Coupon]) -> None:
        self._regime = BetclicTaxRegime(
            now=t,
            bets=[c.to_placed_bet() for c in current],
            regime_config=self.regime_config,
        )

    def groups(self, candidates: Sequence[Candidate]) -> list[tuple[Candidate, ...]]:
        """Kandydaci już w kolejności EV malejąco, potem ``match_id`` (``simulate``)."""
        used: set[int] = set()
        doubles: list[tuple[Candidate, Candidate]] = []
        for i, a in enumerate(candidates):
            if i in used or a.odds < AKO_MIN_LEG_ODDS:
                continue
            for j in range(i + 1, len(candidates)):
                b = candidates[j]
                if j in used or b.odds < AKO_MIN_LEG_ODDS or b.match_id == a.match_id:
                    continue
                if a.p * a.odds * b.p * b.odds * TAX_NO_TAX - 1.0 >= self.edge_threshold:
                    doubles.append((a, b))
                    used.update((i, j))
                    break
        singles = [(c,) for i, c in enumerate(candidates) if i not in used]
        return [*singles, *doubles]  # T3: najpierw single, potem dublety

    def _single(
        self, leg: Candidate, stake_at: Callable[[float], StakeDecision]
    ) -> tuple[float, StakeDecision] | None:
        if self.single_mode == "fixed_0.94":
            tax = TAX_SINGLE_PENALTY
            decision = stake_at(tax)
        else:
            tax = TAX_NO_TAX
            seen: list[float] = []
            decision = stake_at(tax)
            for _ in range(_MAX_TAX_ITERATIONS):
                if decision.stake <= 0.0:
                    return tax, decision  # stawka 0 — kupon odpada w simulate
                actual = self.regime.tax_for_single(
                    decision.stake, market=leg.market, match_id=leg.match_id
                )
                if actual == tax:
                    break
                seen.append(tax)
                tax = actual
                decision = stake_at(tax)
                if tax in seen:
                    # Cykl (stawka zmienia udział AKO, a ten podatek): wariant
                    # pesymistyczny — niższy współczynnik i stawka przy nim.
                    tax = min(seen)
                    decision = stake_at(tax)
                    break
        if self.single_mode == "literal":
            return tax, decision
        k_min = min_odds(
            leg.p, tax_factor=tax, winnings_factor=WINNINGS_UNTAXED,
            edge_threshold=self.edge_threshold,
        )  # fmt: skip
        return (tax, decision) if leg.odds >= k_min else None

    def _double(
        self, group: tuple[Candidate, ...], stake_at: Callable[[float], StakeDecision]
    ) -> tuple[float, StakeDecision] | None:
        decision = stake_at(TAX_NO_TAX)
        if decision.stake <= 0.0:
            return TAX_NO_TAX, decision  # stawka 0 — kupon odpada w simulate
        tax = self.regime.tax_for_multi(stake=decision.stake, legs=_legs(group))
        if tax != TAX_NO_TAX:
            decision = stake_at(tax)
        ev = math.prod(c.p * c.odds for c in group) * tax - 1.0
        return (tax, decision) if ev >= self.edge_threshold else None

    def price(
        self, legs: tuple[Candidate, ...], *, stake_at: Callable[[float], StakeDecision]
    ) -> tuple[float, StakeDecision] | None:
        if len(legs) == 1:
            return self._single(legs[0], stake_at)
        return self._double(legs, stake_at)

    def placed(self, coupon: Coupon) -> None:
        self._regime = self.regime.assume(coupon.to_placed_bet())


def run_regime(
    replay: Replay,
    *,
    selector: Selector,
    staker: Staker,
    regime_config: RegimeConfig,
    edge_threshold: float,
    single_mode: str,
    journal_path: Path,
    run_id: str,
    start_capital: float,
    ingested_at: datetime,
    min_stake_pln: float,
) -> RunResult:
    """Przebieg C. ``selector`` — nogi value przy 1.00 (plan §3)."""
    if regime_config.min_stake_pln != min_stake_pln:
        raise ValueError(
            f"C: min_stake_pln reżimu {regime_config.min_stake_pln} ≠ pętli {min_stake_pln} — jedno źródło "
            "minimalnej stawki (config/strategy.yaml, T12)"
        )
    if selector.selection_tax != TAX_NO_TAX:
        raise ValueError(
            f"C: selektor przy podatku {selector.selection_tax}, a nogi value wybiera się "
            "przy 1.00 (plan §3; FSA4a-01: jedno źródło podatku)"
        )
    return simulate(
        replay,
        selector=selector,
        staker=staker,
        planner=RegimePlanner(regime_config, edge_threshold, single_mode),
        order_tax=TAX_NO_TAX,
        journal_path=journal_path,
        run_id=run_id,
        start_capital=start_capital,
        ingested_at=ingested_at,
        min_stake_pln=min_stake_pln,
        label=C_LABEL,
    )
