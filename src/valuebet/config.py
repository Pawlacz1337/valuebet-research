"""Konfiguracja strategii (``config/strategy.yaml``) i trybu live (``config/live.yaml``).

Wartości bezpieczników (próg przewagi, podatek) nie mają domyślnych w
funkcjach wyceny (reguła 30). Czyta je punkt wejścia i przekazuje jawnie —
ten moduł jest jedynym miejscem odczytu, żeby backtest i live brały tę samą
liczbę (reguła 28).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from valuebet.ingest.football_data_main import ObservedAtRule
from valuebet.pricing.ev import validate_edge_threshold

__all__ = ["LIVE_PATH", "STRATEGY_PATH", "LiveConfig", "StrategyConfig", "load_live", "load_strategy"]

STRATEGY_PATH = Path("config/strategy.yaml")
LIVE_PATH = Path("config/live.yaml")


def _positive_amount(raw: Any, *, key: str, path: Path) -> float:
    """Kwota w złotych: liczba skończona > 0. Brak, ``bool`` albo NaN to błąd."""
    value = raw.get(key) if isinstance(raw, dict) else None
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{path}: {key} musi być liczbą skończoną > 0, jest {value!r}")
    return float(value)


@dataclass(frozen=True)
class StrategyConfig:
    edge_threshold: float
    #: Moment obserwacji kursów sprzed meczu football-data (Filar 1) — jedyne
    #: miejsce wyboru wariantu (decyzja Pawła 2026-10-08, warunek c).
    observed_at_rule: ObservedAtRule
    #: Umowny kapitał startowy backtestu Filaru 1 (BACKTEST_FIN_PLAN §3).
    backtest_start_capital_pln: float
    #: Minimalna stawka we wszystkich strategiach (decyzja Pawła 2026-10-11, T12).
    min_stake_pln: float


@dataclass(frozen=True)
class LiveConfig:
    #: Stały kapitał projektu w trybie live (decyzja Pawła 2026-10-11).
    bankroll_pln: float


def load_live(path: Path = LIVE_PATH) -> LiveConfig:
    """Wczytuje ``config/live.yaml``. Brak klucza to błąd, nie wartość domyślna."""
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    return LiveConfig(bankroll_pln=_positive_amount(raw, key="bankroll_pln", path=path))


def load_strategy(path: Path = STRATEGY_PATH) -> StrategyConfig:
    """Wczytuje i waliduje. Brak klucza to błąd, nie wartość domyślna."""
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "edge_threshold" not in raw:
        raise ValueError(f"{path}: brak klucza edge_threshold")
    threshold = validate_edge_threshold(edge_threshold=float(raw["edge_threshold"]))
    rule_value = raw.get("fd_observed_at_rule")
    allowed = sorted(r.value for r in ObservedAtRule)
    if rule_value not in allowed:
        raise ValueError(f"{path}: fd_observed_at_rule = {rule_value!r}, dozwolone: {allowed}")
    return StrategyConfig(
        edge_threshold=threshold,
        observed_at_rule=ObservedAtRule(rule_value),
        backtest_start_capital_pln=_positive_amount(raw, key="backtest_start_capital_pln", path=path),
        min_stake_pln=_positive_amount(raw, key="min_stake_pln", path=path),
    )
