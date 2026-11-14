"""FSA #0 F-25 + F-08 — reżim Betclica w wariancie pesymistycznym (promocje.md).

Ścieżki niebezpieczne, każda dziś daje ``tax_factor`` korzystniejszy niż
regulamin w najmniej korzystnej lekturze (decyzja Pawła 2026-10-02):

(a) duże AKO + wiele małych singli: po stawkach 96%, po kuponach 9% —
    warunek T4 wymaga obu ≥ 50%, więc singiel 0.94, dziś 1.00;
(b) dwie nogi z jednego meczu — T6: nie AKO, dziś AKO;
(c) zakład sprzed 362 dni — T7: okno 12 miesięcy **kalendarzowych**, dziś
    360 dni (F-08) wyrzuca go z okna;
(d) kupon wielokrotny z nogą 1.15 — T10: nie AKO, dziś podatek singla;
(e) brak ``external_turnover_pln`` — T2: próg uznany za wykorzystany, dziś
    1.00 poniżej 1000 zł z samego dziennika;
(T1) zakład przed startem akcji — 0.88, dziś liczony jak w promocji.

Zmiana 2026-10-11 (F1-P01, wariant B, decyzja Pawła): (a) obowiązuje już
tylko w wariancie wrażliwości ``share_basis = "stakes_and_coupons"``
(regulamin liczy udział po stawkach); w (b) i (d) wielokrotny
niekwalifikujący się dostaje 0.94 przy udziale < 50% (§3 ust. 11.1), nie
0.88 — test nadal odróżnia „nie AKO” (0.94) od AKO (1.00).

Obiekty budowane przez ``helpers.build`` i ``getattr`` — stary kod dochodzi
do asercji o podatku, nie pada na sygnaturze.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from helpers import assert_from_checkout, build
from valuebet.pricing import ev

assert_from_checkout(__file__)

START = datetime(2024, 1, 1, tzinfo=UTC)
NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def _config(**overrides: Any) -> Any:
    cls = getattr(ev, "RegimeConfig", None)
    if cls is None:
        return None
    base = {
        "promo_active": True,
        "promo_valid_from": START,
        "join_date": START,
        "external_turnover_pln": 1000.0,
        "external_coupons": 0,
        "share_condition_known": True,
        "min_stake_pln": 0.0,
        "excluded_markets": frozenset(),
        "share_basis": "stakes",
    }
    base.update(overrides)
    return cls(**base)


def _coupon(placed_at: datetime, stake: float, legs: list[tuple[str, float]]) -> Any:
    leg_cls = getattr(ev, "CouponLeg", None)
    new_legs = (
        tuple(build(leg_cls, match_id=m, odds=k, void=False, market="h2h") for m, k in legs) if leg_cls else None
    )
    return build(
        ev.PlacedBet,
        placed_at=placed_at,
        stake=stake,
        mode="real",
        coupon_id=f"c{placed_at.timestamp()}-{stake}",
        leg_odds=tuple(k for _, k in legs),
        legs=new_legs,
    )


def _regime(bets: list[Any], **config: Any) -> Any:
    return build(ev.BetclicTaxRegime, now=NOW, bets=bets, regime_config=_config(**config))


def _tax_multi(regime: Any, stake: float, legs: list[tuple[str, float]]) -> float:
    leg_cls = getattr(ev, "CouponLeg", None)
    if hasattr(regime, "tax_for_multi") and leg_cls is not None:
        return float(
            regime.tax_for_multi(
                stake=stake,
                legs=tuple(build(leg_cls, match_id=m, odds=k, void=False, market="h2h") for m, k in legs),
            )
        )
    return float(regime.tax_for_ako(stake, tuple(k for _, k in legs)))


def test_a_share_by_coupons_also_required() -> None:
    week = NOW - timedelta(days=7)
    bets = [_coupon(week, 2400.0, [("m1", 1.5), ("m2", 1.6)])]
    bets += [_coupon(week + timedelta(minutes=i), 10.0, [(f"s{i}", 2.0)]) for i in range(10)]
    regime = _regime(bets, share_basis="stakes_and_coupons")
    # po stawkach 2400 / 2500 = 96%, po kuponach 1 / 11 = 9%
    assert build(regime.tax_for_single, 10.0, market="h2h") == 0.94


def test_b_two_legs_from_one_match_are_not_ako() -> None:
    regime = _regime([])
    assert _tax_multi(regime, 50.0, [("m1", 1.5), ("m1", 1.6)]) == 0.94


def test_c_window_is_twelve_calendar_months() -> None:
    old_ako = _coupon(NOW - timedelta(days=362), 5000.0, [("m1", 1.5), ("m2", 1.6)])
    singles = [
        _coupon(NOW - timedelta(days=3, minutes=i), 100.0, [(f"s{i}", 2.0)]) for i in range(1)
    ]
    # AKO 362 dni temu jest w 12 miesiącach kalendarzowych: udział po stawkach
    # 5000 / (5000 + 100 + 1000 spoza dziennika + 10) > 50%, po kuponach 1/3 —
    # warunek nie jest spełniony po kuponach, więc sprawdzamy samo okno:
    regime = _regime([old_ako, *singles], external_turnover_pln=1000.0)
    window = getattr(regime, "window", None) or regime._window
    included = window() if callable(window) else window
    assert any(b.stake == 5000.0 for b in included)


def test_d_multi_with_short_leg_pays_statutory_tax() -> None:
    regime = _regime([])
    assert _tax_multi(regime, 50.0, [("m1", 1.15), ("m2", 1.60)]) == 0.94


def test_e_unknown_external_turnover_means_threshold_used(tmp_path: Any) -> None:
    loader = getattr(ev, "load_betclic_regime_config", None)
    config = None
    if loader is not None:
        path = tmp_path / "bookmakers.yaml"
        path.write_text(
            "betclic:\n"
            "  promo: bez_podatku_2_0\n"
            "  promo_valid_from: 2024-01-01\n"
            f"  promo_verified_on: {(NOW - timedelta(days=5)).date().isoformat()}\n"
            "  join_date: 2024-01-01\n"
            "  external_turnover_pln: null\n"
            "  external_coupons: 0\n",
            encoding="utf-8",
        )
        config = loader(path, now=NOW)
    regime = build(ev.BetclicTaxRegime, now=NOW, bets=[], regime_config=config)
    assert build(regime.tax_for_single, 100.0, market="h2h") != 1.00


def test_t1_bet_before_promotion_start_is_statutory() -> None:
    regime = build(
        ev.BetclicTaxRegime,
        now=START - timedelta(days=1),
        bets=[],
        regime_config=_config(external_turnover_pln=0.0),
    )
    assert build(regime.tax_for_single, 10.0, market="h2h") == 0.88
