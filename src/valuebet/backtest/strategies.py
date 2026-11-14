"""Strategie Filaru 1 — tabela zamrożona przed wynikiem (BACKTEST_FIN_PLAN §3).

Zmiana względem §3 planu — **decyzja Pawła 2026-10-08**, dosłownie: „A =
najlepszy z B365 i BW tylko dla meczów z kompletem obu, reszta wyłączona z
licznikiem per liga i sezon; WH poza A; osobno A3 i B365-single.” Powód:
William Hill nie ma żadnego pliku 2025/26 i znika ok. 2025-03-16, Bet&Win
ma dziurę od lutego do końca 2024/25 (``reports/ingest/4e5c251/COLUMNS.md``)
— przesłanka planu „obecni we wszystkich sezonach” była fałszywa.

O/U 2.5: w plikach jedynym miękkim bukmacherem jest B365 (§3) — O/U idzie
przez B365 we wszystkich strategiach poza E (``Max``). Wymóg kompletu
dotyczy listy bukmacherów DANEGO rynku.

Zmiany 2026-10-10 po audycie 4a, przed jakimkolwiek wynikiem (decyzje Pawła):

- **Jedno źródło podatku** (FSA4a-01): ``Strategy`` ma ``selection_tax``
  (próg ``k_min`` i stawka) i ``settlement_tax`` (rozliczenie); selektor i
  przebieg wyprowadza :func:`run_strategy` z tego jednego obiektu.
- **D to kontrola podatku, nie strategia do zagrania**: zakłady A (wybór i
  stawka przy 1.00) rozliczone przy 0.88 — jawne odstępstwo od planu §3
  („jak A przy 0.88”); przy wyborze na 0.88 zysk D byłby oczekiwany przy
  działającej przewadze, więc alarm „zysk w D” byłby fałszywy.
- **Wiarygodność kursu** (A4a-01): ``margin_check`` — booksum bukmachera
  < 1.00 → poza best-of; wyłączone tylko dla E (``max``).

Strategia C (reżim Betclica, dublety) — ``backtest/strategy_c.py``; F
(Ekstraklasa, zamknięcie vs zamknięcie) — tylko raport (FIX_LOG_F0, 2026-10-08).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from valuebet.backtest.financial import (
    RunResult,
    Selector,
    Staker,
    run,
    threshold_selector,
)
from valuebet.backtest.replay import Replay
from valuebet.pricing.ev import validate_tax_factor

__all__ = ["STRATEGIES", "Strategy", "run_strategy", "selector_for"]


@dataclass(frozen=True)
class Strategy:
    name: str
    #: rynek → bukmacherzy, z których bierzemy najlepszy kurs.
    books: Mapping[str, tuple[str, ...]]
    #: podatek progu ``k_min`` i stawki Kelly'ego.
    selection_tax: float
    #: podatek rozliczenia (dziennik, wypłata, CLV).
    settlement_tax: float
    #: rynek meczu grany tylko przy komplecie u WSZYSTKICH bukmacherów rynku.
    require_complete: bool
    #: A4a-01 (a): booksum bukmachera < 1.00 → poza best-of. ``False`` tylko dla ``max``.
    margin_check: bool
    role: str

    def __post_init__(self) -> None:
        validate_tax_factor(tax_factor=self.selection_tax)
        validate_tax_factor(tax_factor=self.settlement_tax)


_OU_B365 = ("bet365",)
_A_1X2 = ("bet365", "betandwin")

STRATEGIES: dict[str, Strategy] = {
    s.name: s
    for s in (
        Strategy("A", {"1x2": _A_1X2, "over_under": _OU_B365}, 1.00, 1.00, True, True,
                 "główna: najlepszy z B365 i BW, tylko z kompletem obu"),
        Strategy("A3", {"1x2": (*_A_1X2, "williamhill"), "over_under": _OU_B365}, 1.00, 1.00, True, True,
                 "jak w planie: najlepszy z B365, BW, WH, tylko z kompletem trzech"),
        Strategy("B365", {"1x2": ("bet365",), "over_under": _OU_B365}, 1.00, 1.00, True, True,
                 "jeden bukmacher: B365 (proxy jednego konta)"),
        Strategy("B-BW", {"1x2": ("betandwin",)}, 1.00, 1.00, True, True, "jeden bukmacher: BW (1X2)"),
        Strategy("B-WH", {"1x2": ("williamhill",)}, 1.00, 1.00, True, True, "jeden bukmacher: WH (1X2)"),
        Strategy("D", {"1x2": _A_1X2, "over_under": _OU_B365}, 1.00, 0.88, True, True,
                 "kontrola podatku, nie strategia do zagrania: zakłady A rozliczone przy 0.88 — musi tracić"),
        Strategy("E", {"1x2": ("max",), "over_under": ("max",)}, 1.00, 1.00, True, False,
                 "górna granica: Max — tylko porównanie"),
    )
}  # fmt: skip


def selector_for(
    strategy: Strategy,
    *,
    edge_threshold: float,
    excluded: Counter[tuple[str, str, str]],
    rejected: Counter[tuple[str, str, str]],
) -> Selector:
    """Selektor progu ``k_min`` z ``pricing.ev`` przy podatku wyboru strategii."""
    return threshold_selector(
        books=strategy.books,
        tax_factor=strategy.selection_tax,
        edge_threshold=edge_threshold,
        require_complete=strategy.require_complete,
        excluded=excluded,
        rejected=rejected,
        margin_check=strategy.margin_check,
    )


def run_strategy(
    replay: Replay,
    *,
    strategy: Strategy,
    staker: Staker,
    edge_threshold: float,
    excluded: Counter[tuple[str, str, str]],
    rejected: Counter[tuple[str, str, str]],
    journal_path: Path,
    run_id: str,
    start_capital: float,
    ingested_at: datetime,
    min_stake_pln: float,
) -> RunResult:
    """Przebieg strategii z tabeli: selektor i podatki z jednego obiektu (FSA4a-01)."""
    return run(
        replay,
        selector=selector_for(strategy, edge_threshold=edge_threshold, excluded=excluded, rejected=rejected),
        staker=staker,
        selection_tax_factor=strategy.selection_tax,
        settlement_tax_factor=strategy.settlement_tax,
        journal_path=journal_path,
        run_id=run_id,
        start_capital=start_capital,
        ingested_at=ingested_at,
        min_stake_pln=min_stake_pln,
    )
