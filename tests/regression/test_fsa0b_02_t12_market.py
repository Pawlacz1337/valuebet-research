"""FSA #0b F0b-02 — wyłączenie rynku z T12 nie da się ominąć.

Ścieżki niebezpieczne (promocje.md T12: „warunek, który wyłącza zakład z
oferty (… rynek …) → ten zakład 0.88”; reguła 30):

(a) ``tax_for_single`` nie przyjmował rynku — singiel na wyłączonym rynku
    dostawał 1.00 zamiast 0.88 (EV -7.6% widziane jako +5.0%);
(b) ``CouponLeg`` bez ``market`` miał domyślne ``""`` = „nie wyłączony”;
(c) ładowacz zamieniał brak ``min_stake_pln`` i ``excluded_markets`` na
    wariant najkorzystniejszy dla gracza (0 zł, zbiór pusty).

Obiekty przez ``helpers.build`` — stary kod dochodzi do asercji o podatku.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from helpers import assert_from_checkout, build
from valuebet.pricing import ev

assert_from_checkout(__file__)

START = datetime(2024, 1, 1, tzinfo=UTC)
NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def _config(**overrides: Any) -> Any:
    base = {
        "promo_active": True,
        "promo_valid_from": START,
        "join_date": START,
        "external_turnover_pln": 0.0,
        "external_coupons": 0,
        "share_condition_known": True,
        "min_stake_pln": 0.0,
        "excluded_markets": frozenset({"spreads"}),
        "share_basis": ev.SHARE_BY_STAKES,
    }
    base.update(overrides)
    return ev.RegimeConfig(**base)


def _regime(config: Any) -> Any:
    return build(ev.BetclicTaxRegime, now=NOW, bets=[], regime_config=config)


def test_single_on_excluded_market_is_statutory() -> None:
    regime = _regime(_config())
    assert build(regime.tax_for_single, 100.0, market="spreads") == 0.88


def test_coupon_leg_without_market_is_rejected() -> None:
    with pytest.raises((TypeError, ValueError)):
        ev.CouponLeg(match_id="m1", odds=2.0, void=False)


def test_coupon_leg_with_empty_market_is_rejected() -> None:
    with pytest.raises(ValueError, match="market"):
        ev.CouponLeg(match_id="m1", odds=2.0, void=False, market="")


def _yaml(tmp_path: Path, t12: str) -> Path:
    path = tmp_path / "bookmakers.yaml"
    path.write_text(
        "betclic:\n"
        "  promo: bez_podatku_2_0\n"
        "  promo_valid_from: 2024-01-01\n"
        f"  promo_verified_on: {(NOW - timedelta(days=5)).date().isoformat()}\n"
        "  join_date: 2024-01-01\n"
        "  external_turnover_pln: 0\n"
        "  external_coupons: 0\n" + t12,
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    "t12",
    [
        "  min_stake_pln: null\n  excluded_markets: null\n",
        "  min_stake_pln: 5\n  excluded_markets: null\n",
        "  min_stake_pln: null\n  excluded_markets: []\n",
        "",
    ],
    ids=["oba-null", "rynki-null", "stawka-null", "brak-kluczy"],
)
def test_loader_unknown_t12_is_least_favourable(tmp_path: Path, t12: str) -> None:
    config = ev.load_betclic_regime_config(_yaml(tmp_path, t12), now=NOW)
    regime = _regime(config)
    leg = build(ev.CouponLeg, match_id="m1", odds=2.0, void=False, market="h2h")
    assert regime.tax_for_coupon(stake=100.0, legs=(leg,)) == 0.88
