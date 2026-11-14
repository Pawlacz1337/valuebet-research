"""Konfiguracja strategii (``config/strategy.yaml``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from valuebet.config import STRATEGY_PATH, load_strategy
from valuebet.ingest.football_data_main import ObservedAtRule

ROOT = Path(__file__).resolve().parents[1]
RULE = "fd_observed_at_rule: friday_tuesday_1800_london\n"


def test_shipped_strategy_has_two_percent_threshold() -> None:
    assert load_strategy(ROOT / STRATEGY_PATH).edge_threshold == pytest.approx(0.02)


def test_shipped_strategy_uses_afternoon_observed_at_rule() -> None:
    """Decyzja Pawła 2026-10-08: 18:00 London; 23:59 tylko jako wrażliwość."""
    rule = load_strategy(ROOT / STRATEGY_PATH).observed_at_rule
    assert rule is ObservedAtRule.AFTERNOON_1800


@pytest.mark.parametrize(
    "body",
    [
        "edge_threshold: 0.02\n",  # brak reguły — błąd, nie wartość domyślna
        "edge_threshold: 0.02\nfd_observed_at_rule: friday_1800\n",
        "edge_threshold: 0.02\nfd_observed_at_rule:\n",
    ],
)
def test_bad_observed_at_rule_is_rejected(tmp_path: Path, body: str) -> None:
    path = tmp_path / "strategy.yaml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(ValueError, match="fd_observed_at_rule"):
        load_strategy(path)


def test_end_of_day_variant_is_selectable_without_code_change(tmp_path: Path) -> None:
    path = tmp_path / "strategy.yaml"
    path.write_text(
        "edge_threshold: 0.02\nfd_observed_at_rule: friday_tuesday_2359_london\n"
        "backtest_start_capital_pln: 10000\nmin_stake_pln: 0.50\n",
        encoding="utf-8",
    )
    assert load_strategy(path).observed_at_rule is ObservedAtRule.END_OF_DAY_2359


@pytest.mark.parametrize(
    "body",
    ["{}", RULE + "edge_threshold: -0.1", RULE + "edge_threshold: .nan", "- 1"],
)
def test_bad_strategy_is_rejected(tmp_path: Path, body: str) -> None:
    path = tmp_path / "strategy.yaml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(ValueError):
        load_strategy(path)


# -- wariant B (decyzja Pawła 2026-10-11): kapitał live, kapitał backtestu, min. stawka --


def test_live_bankroll_is_the_fixed_project_capital_1000() -> None:
    """Stały kapitał projektu na Filar 3 (live) = 1000 PLN, w config/live.yaml."""
    from valuebet.config import LIVE_PATH, load_live

    assert load_live(ROOT / LIVE_PATH).bankroll_pln == 1000.0


@pytest.mark.parametrize(
    "body", ["{}", "bankroll_pln: 0", "bankroll_pln: -5", "bankroll_pln: .nan", "bankroll_pln: true", "- 1"]
)
def test_bad_live_config_is_rejected(tmp_path: Path, body: str) -> None:
    from valuebet.config import load_live

    path = tmp_path / "live.yaml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(ValueError, match="bankroll_pln"):
        load_live(path)


def test_backtest_capital_stays_10000_and_is_not_the_live_capital() -> None:
    """BACKTEST_FIN_PLAN §3: umowne 10 000 zł, zamrożone — kapitał live go nie zmienia."""
    import importlib.util
    import sys

    from valuebet.config import LIVE_PATH, load_live

    assert load_strategy(ROOT / STRATEGY_PATH).backtest_start_capital_pln == 10_000.0
    assert load_live(ROOT / LIVE_PATH).bankroll_pln != 10_000.0
    name = "engine_tests_capital_check"
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "engine_tests.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    assert module.START == 10_000.0


def test_min_stake_is_050_in_every_strategy_and_matches_betclic_t12() -> None:
    """Decyzja Pawła 2026-10-11: 0,50 zł we wszystkich strategiach (Szczegółowe
    zasady Betclic pkt 3.1, promocje.md T12) — ta sama liczba co w bookmakers.yaml."""
    import yaml

    assert load_strategy(ROOT / STRATEGY_PATH).min_stake_pln == 0.50
    betclic = yaml.safe_load((ROOT / "config" / "bookmakers.yaml").read_text(encoding="utf-8"))["betclic"]
    assert betclic["min_stake_pln"] == 0.50
    assert betclic["excluded_markets"] == []
    # pozostałe pola — zadanie Pawła przed Filarem 3; ładowacz live pesymistyczny
    for key in ("promo_verified_on", "join_date", "external_turnover_pln", "external_coupons"):
        assert betclic[key] is None, key


@pytest.mark.parametrize("value", ["0", "-0.5", ".nan", "true"])
def test_bad_min_stake_is_rejected(tmp_path: Path, value: str) -> None:
    path = tmp_path / "strategy.yaml"
    path.write_text(
        RULE + f"edge_threshold: 0.02\nbacktest_start_capital_pln: 10000\nmin_stake_pln: {value}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="min_stake_pln"):
        load_strategy(path)
