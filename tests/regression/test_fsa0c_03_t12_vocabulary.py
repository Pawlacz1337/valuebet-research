"""FSA #0c F0c-03 — T12: jeden słownik rynków, walidacja typu i nazwy.

Ścieżki niebezpieczne (każda dawała singlowi na wyłączonym rynku 1.00
zamiast 0.88, czyli 12 pkt proc. stawki):

(a) ``excluded_markets: spreads`` (napis zamiast listy) → zbiór liter;
(b) nazwa z regulaminu („Handicap azjatycki”) nie pasuje do klucza nogi;
(c) dwa nazewnictwa w kodzie — kanoniczne (``asian_handicap``) i The Odds
    API (``spreads``): wyłączenie wpisane w jednym nie łapało nogi w drugim;
(d) noga z rynkiem spoza słownika przechodziła po cichu.

Klasa błędu: porównanie napisów bez słownika. Obiekty przez
``helpers.build`` — stary kod dochodzi do asercji o podatku.
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


def _yaml(tmp_path: Path, excluded: str, min_stake: str = "0") -> Path:
    path = tmp_path / "bookmakers.yaml"
    path.write_text(
        "betclic:\n"
        "  promo: bez_podatku_2_0\n"
        "  promo_valid_from: 2024-01-01\n"
        f"  promo_verified_on: {(NOW - timedelta(days=5)).date().isoformat()}\n"
        "  join_date: 2024-01-01\n"
        "  external_turnover_pln: 0\n"
        "  external_coupons: 0\n"
        f"  min_stake_pln: {min_stake}\n"
        f"  excluded_markets: {excluded}\n",
        encoding="utf-8",
    )
    return path


def _single_tax(config: Any, market: str) -> float:
    regime = build(ev.BetclicTaxRegime, now=NOW, bets=[], regime_config=config)
    return float(build(regime.tax_for_single, 100.0, market=market))


@pytest.mark.parametrize(
    "excluded",
    ["spreads", '"spreads, totals"', "[Handicap azjatycki]", "[spredas]", "{spreads: 1}"],
    ids=["napis", "napis-z-przecinkiem", "nazwa-regulaminu", "literowka", "mapa"],
)
def test_loader_rejects_malformed_excluded_markets(tmp_path: Path, excluded: str) -> None:
    """Zła postać T12 to głośny błąd, nie wariant najkorzystniejszy dla gracza."""
    with pytest.raises(ValueError, match="excluded_markets"):
        ev.load_betclic_regime_config(_yaml(tmp_path, excluded), now=NOW)


@pytest.mark.parametrize("min_stake", ['"5 zł"', "true", "-1"], ids=["napis", "bool", "ujemna"])
def test_loader_rejects_malformed_min_stake(tmp_path: Path, min_stake: str) -> None:
    with pytest.raises(ValueError, match="min_stake_pln"):
        ev.load_betclic_regime_config(_yaml(tmp_path, "[]", min_stake), now=NOW)


@pytest.mark.parametrize(
    ("excluded", "leg_market"),
    [
        ("[spreads]", "asian_handicap"),
        ("[asian_handicap]", "spreads"),
        ("[totals]", "over_under"),
        ("[over_under]", "totals"),
        ("[h2h]", "1x2"),
    ],
)
def test_exclusion_matches_across_both_vocabularies(
    tmp_path: Path, excluded: str, leg_market: str
) -> None:
    config = ev.load_betclic_regime_config(_yaml(tmp_path, excluded), now=NOW)
    assert _single_tax(config, leg_market) == 0.88


def test_regime_config_rejects_string_as_excluded_markets() -> None:
    with pytest.raises((TypeError, ValueError)):
        ev.RegimeConfig(
            promo_active=True,
            promo_valid_from=START,
            join_date=START,
            external_turnover_pln=0.0,
            external_coupons=0,
            share_condition_known=True,
            min_stake_pln=0.0,
            excluded_markets="spreads",
            share_basis=ev.SHARE_BY_STAKES,
        )


def test_coupon_leg_rejects_market_outside_vocabulary() -> None:
    with pytest.raises(ValueError, match="market"):
        ev.CouponLeg(match_id="m1", odds=2.0, void=False, market="Handicap azjatycki")
