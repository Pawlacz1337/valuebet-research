"""Reżim Betclica — po jednym teście na wiersz T1 do T12 z ``docs/promocje.md``.

T13 (podatek od wygranej) to osobny czynnik ``winnings_factor`` — testy w
``tests/regression/test_fsa0_a02_winnings_tax.py``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from valuebet.pricing.ev import (
    AKO_WINDOW_BETS,
    BETCLIC_READING,
    NO_TAX_TURNOVER_LIMIT,
    SHARE_BY_STAKES,
    SHARE_BY_STAKES_AND_COUPONS,
    BetclicTaxRegime,
    CouponLeg,
    PlacedBet,
    RegimeConfig,
    load_betclic_regime_config,
    months_before,
    qualifies_as_ako,
    real_turnover,
    warsaw_midnight_utc,
)

ROOT = Path(__file__).resolve().parents[1]
START = datetime(2025, 1, 1, tzinfo=UTC)
NOW = datetime(2025, 6, 15, 12, 0, tzinfo=UTC)


def _cfg(**kw: Any) -> RegimeConfig:
    base: dict[str, Any] = {
        "promo_active": True,
        "promo_valid_from": START,
        "join_date": START,
        "external_turnover_pln": 0.0,
        "external_coupons": 0,
        "share_condition_known": True,
        "min_stake_pln": 0.0,
        "excluded_markets": frozenset(),
        "share_basis": SHARE_BY_STAKES,
    }
    base.update(kw)
    return RegimeConfig(**base)


def _leg(match_id: str, odds: float = 2.0, *, void: bool = False, market: str = "h2h") -> CouponLeg:
    return CouponLeg(match_id=match_id, odds=odds, void=void, market=market)


_SEQ = iter(range(10**9))


def _bet(
    stake: float,
    legs: tuple[CouponLeg, ...],
    *,
    at: datetime = NOW - timedelta(days=1),
    mode: str = "real",
) -> PlacedBet:
    return PlacedBet(coupon_id=f"c{next(_SEQ)}", placed_at=at, stake=stake, legs=legs, mode=mode)


def _regime(bets: list[PlacedBet], *, now: datetime = NOW, **cfg: Any) -> BetclicTaxRegime:
    return BetclicTaxRegime(now=now, bets=bets, regime_config=_cfg(**cfg))


def test_reading_label_is_the_regulation() -> None:
    """F1-P01 (2026-10-11): pkt 1-3 wg brzmienia regulaminu, reszta pesymistycznie."""
    assert BETCLIC_READING == "regulamin-2026-10-11"


# T1 ---------------------------------------------------------------------


def test_t1_before_start_and_inactive_promo_are_statutory() -> None:
    assert _regime([], now=START - timedelta(seconds=1)).tax_for_single(10.0, market="h2h") == 0.88
    assert _regime([], promo_active=False).tax_for_single(10.0, market="h2h") == 0.88
    assert _regime([], promo_active=False).tax_for_multi(
        stake=10.0, legs=(_leg("a"), _leg("b"))
    ) == 0.88


def _yaml(tmp_path: Path, **values: object) -> Path:
    base: dict[str, object] = {
        "promo_valid_from": "2025-01-01",
        "promo_verified_on": "2025-06-01",
        "join_date": "2025-01-01",
        "external_turnover_pln": 0,
        "external_coupons": 0,
        "min_stake_pln": 0,
        "excluded_markets": "[]",
    }
    base.update(values)
    lines = ["betclic:"] + [
        f"  {k}: {'null' if v is None else v}" for k, v in base.items()
    ]
    path = tmp_path / "bookmakers.yaml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_t1_stale_verification_disables_promo(tmp_path: Path) -> None:
    fresh = load_betclic_regime_config(_yaml(tmp_path), now=NOW)
    assert fresh.promo_active
    stale = load_betclic_regime_config(_yaml(tmp_path, promo_verified_on="2025-03-01"), now=NOW)
    assert not stale.promo_active
    never = load_betclic_regime_config(_yaml(tmp_path, promo_verified_on=None), now=NOW)
    assert not never.promo_active


def test_t1_dates_are_warsaw_midnight(tmp_path: Path) -> None:
    cfg = load_betclic_regime_config(_yaml(tmp_path), now=NOW)
    assert cfg.promo_valid_from == datetime(2024, 12, 31, 23, 0, tzinfo=UTC)
    assert warsaw_midnight_utc(date(2025, 7, 1)) == datetime(2025, 6, 30, 22, 0, tzinfo=UTC)


def test_shipped_config_is_loadable_and_pessimistic() -> None:
    cfg = load_betclic_regime_config(ROOT / "config" / "bookmakers.yaml", now=NOW)
    # promo_verified_on: null -> promocja nieaktywna; brak obrotu spoza
    # dziennika -> próg wykorzystany; brak join_date -> udział niespełniony.
    assert not cfg.promo_active
    assert cfg.external_turnover_pln == NO_TAX_TURNOVER_LIMIT
    assert not cfg.share_condition_known


def test_loader_rejects_missing_section(tmp_path: Path) -> None:
    path = tmp_path / "x.yaml"
    path.write_text("inny: {}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="betclic"):
        load_betclic_regime_config(path, now=NOW)
    path.write_text("betclic:\n  promo_valid_from: null\n", encoding="utf-8")
    with pytest.raises(ValueError, match="promo_valid_from"):
        load_betclic_regime_config(path, now=NOW)
    with pytest.raises(ValueError, match="timezone"):
        load_betclic_regime_config(_yaml(tmp_path), now=NOW.replace(tzinfo=None))


# T2 ---------------------------------------------------------------------


def test_t2_below_limit_everything_free_exhausted_limit_is_not() -> None:
    # F1-P01 pkt 1 (2026-10-11): zakład przekraczający próg jest w ofercie, gdy
    # PRZED nim zostaje jakakolwiek kwota — test_f1p01_pkt1_* niżej.
    assert _regime([_bet(900.0, (_leg("x"),))]).tax_for_single(99.0, market="h2h") == 1.00
    assert _regime([_bet(1000.0, (_leg("x"),))]).tax_for_single(1.0, market="h2h") == 0.94


def test_t2_external_turnover_counts_towards_limit_and_share(tmp_path: Path) -> None:
    assert _regime([], external_turnover_pln=1000.0).tax_for_single(60.0, market="h2h") == 0.94
    missing = load_betclic_regime_config(_yaml(tmp_path, external_turnover_pln=None), now=NOW)
    assert missing.external_turnover_pln == NO_TAX_TURNOVER_LIMIT
    no_coupons = load_betclic_regime_config(_yaml(tmp_path, external_coupons=None), now=NOW)
    assert not no_coupons.share_condition_known
    ako = [_bet(3000.0, (_leg("a"), _leg("b")))]
    # bez obrotu spoza dziennika udział po stawkach 3000/3010 ≥ 50%; z 3000 zł spoza
    # dziennika jako nie-AKO: 3000/6010 < 50%.
    assert _regime(ako, external_turnover_pln=1000.0, external_coupons=0).tax_for_single(10.0, market="h2h") == 1.00
    assert _regime(ako, external_turnover_pln=3000.0).tax_for_single(10.0, market="h2h") == 0.94


def test_t2_turnover_counts_coupons_once_and_from_start() -> None:
    cfg = _cfg()
    bets = [
        _bet(100.0, (_leg("a"), _leg("b"))),
        _bet(50.0, (_leg("c"),)),
        _bet(500.0, (_leg("d"),), at=START - timedelta(days=1)),
        _bet(70.0, (_leg("e"),), mode="paper"),
        _bet(999.0, (_leg("f"),), at=NOW + timedelta(days=1)),
    ]
    assert real_turnover(bets=bets, now=NOW, regime_config=cfg) == 150.0


# T3 ---------------------------------------------------------------------


def test_t3_candidate_counts_and_later_candidates_see_earlier() -> None:
    ako = [_bet(600.0, (_leg("a"), _leg("b"))), _bet(400.0, (_leg("c"),))]
    # Wariant wrażliwości (po stawkach i po kuponach) — kupony rozróżniają tu kroki.
    regime = _regime(ako, external_coupons=0, share_basis=SHARE_BY_STAKES_AND_COUPONS)
    # 600/(1000+10) ≥ 50%, kupony 1/3 < 50% → 0.94 (kandydat wliczony).
    assert regime.tax_for_single(10.0, market="h2h") == 0.94
    more_ako = regime.assume(_bet(600.0, (_leg("d"), _leg("e")), at=NOW)).assume(
        _bet(600.0, (_leg("f"), _leg("g")), at=NOW)
    )
    # 1800/(2200+10) ≥ 50%, kupony 3/5 ≥ 50% → 1.00
    assert more_ako.tax_for_single(10.0, market="h2h") == 1.00
    assert regime.tax_for_single(10.0, market="h2h") == 0.94, "assume nie zmienia oryginału"


def test_t3_future_bets_are_invisible() -> None:
    future = [_bet(5000.0, (_leg("a"), _leg("b")), at=NOW + timedelta(hours=1))]
    regime = _regime([_bet(1000.0, (_leg("x"),)), *future])
    assert regime.tax_for_single(10.0, market="h2h") == 0.94


# T4 / T5 ----------------------------------------------------------------


def test_t4_sensitivity_variant_requires_both_shares() -> None:
    """Wariant „po stawkach i po kuponach” (margines Pawła 2026-10-02) — od
    2026-10-11 tylko wrażliwość C; regulamin — test_f1p01_pkt3_* niżej."""
    by_stake_only = [_bet(5000.0, (_leg("a"), _leg("b")))] + [
        _bet(10.0, (_leg(f"s{i}"),)) for i in range(5)
    ]
    both_basis = {"share_basis": SHARE_BY_STAKES_AND_COUPONS}
    assert _regime(by_stake_only, **both_basis).tax_for_single(10.0, market="h2h") == 0.94
    by_count_only = [_bet(2.0, (_leg(f"a{i}"), _leg(f"b{i}"))) for i in range(10)] + [
        _bet(2000.0, (_leg("s"),))
    ]
    assert _regime(by_count_only, **both_basis).tax_for_single(10.0, market="h2h") == 0.94
    both = [_bet(800.0, (_leg(f"a{i}"), _leg(f"b{i}"))) for i in range(3)] + [
        _bet(500.0, (_leg("s"),))
    ]
    assert _regime(both, **both_basis).tax_for_single(10.0, market="h2h") == 1.00


def test_t5_threshold_is_inclusive() -> None:
    bets = [_bet(1000.0, (_leg("a"), _leg("b"))), _bet(990.0, (_leg("s"),))]
    # z kandydatem 10 zł: po stawkach 1000/2000 = 50%, po kuponach 1/3 — nie.
    regime = _regime(bets)
    by_stake, _ = regime.ako_shares(candidate=_bet(10.0, (_leg("k"),), at=NOW))
    assert by_stake == pytest.approx(0.5)


def test_t4_unknown_share_condition_is_not_met() -> None:
    ako = [_bet(5000.0, (_leg("a"), _leg("b")))]
    assert _regime(ako, share_condition_known=False).tax_for_single(10.0, market="h2h") == 0.94


# T6 ---------------------------------------------------------------------


def test_t6_ako_definition() -> None:
    assert qualifies_as_ako([_leg("a", 1.20), _leg("b", 1.50)])
    assert not qualifies_as_ako([_leg("a", 1.19), _leg("b", 1.50)])
    assert not qualifies_as_ako([_leg("a"), _leg("a")]), "nogi z jednego meczu"
    assert not qualifies_as_ako([_leg("a")])
    assert not qualifies_as_ako([_leg("a"), _leg("b", void=True)]), "noga zwrócona"
    assert qualifies_as_ako([_leg("a"), _leg("b"), _leg("c", 1.05, void=True)])


# T7 ---------------------------------------------------------------------


def test_t7_calendar_months_and_5000_cap() -> None:
    now = datetime(2026, 3, 31, 12, 0, tzinfo=UTC)
    # Ta sama godzina ŚCIENNA w Warszawie: 14:00 CEST -> 14:00 CET = 13:00 UTC.
    assert months_before(now, 1) == datetime(2026, 2, 28, 13, 0, tzinfo=UTC)
    join = datetime(2024, 1, 1, tzinfo=UTC)
    in_window = _bet(5.0, (_leg("a"), _leg("b")), at=months_before(now, 12) + timedelta(minutes=1))
    out = _bet(5.0, (_leg("c"), _leg("d")), at=months_before(now, 12) - timedelta(minutes=1))
    regime = _regime([in_window, out], now=now, join_date=join, promo_valid_from=join)
    assert regime.window() == [in_window]
    # Przed upływem 12 miesięcy od przystąpienia — wszystko od przystąpienia.
    join_recent = datetime(2025, 10, 1, tzinfo=UTC)
    after_join = _bet(5.0, (_leg("g"),), at=datetime(2025, 11, 1, tzinfo=UTC))
    before_join = _bet(5.0, (_leg("h"),), at=datetime(2025, 9, 1, tzinfo=UTC))
    young = _regime(
        [after_join, before_join], now=now, join_date=join_recent, promo_valid_from=join
    )
    assert young.window() == [after_join]
    early = _bet(5.0, (_leg("e"),), at=START - timedelta(days=1))
    assert _regime([early]).window() == []


def test_t7_window_keeps_last_5000_coupons() -> None:
    bets = [
        _bet(1.0, (_leg(f"m{i}"),), at=NOW - timedelta(days=30) + timedelta(seconds=i))
        for i in range(AKO_WINDOW_BETS + 3)
    ]
    window = _regime(bets).window()
    assert len(window) == AKO_WINDOW_BETS
    assert window[0] is bets[3]


# T8 / T9 / T10 ------------------------------------------------------------


def test_t8_t9_t10_tax_levels() -> None:
    above = _regime([_bet(1000.0, (_leg("x"),))])
    assert above.tax_for_single(10.0, market="h2h") == 0.94  # T8
    assert above.tax_for_multi(stake=10.0, legs=(_leg("a"), _leg("b"))) == 1.00  # T9
    # T10 (F1-P01 pkt 2, 2026-10-11): jak singiel — 0.94 przy udziale < 50%.
    assert above.tax_for_multi(stake=10.0, legs=(_leg("a", 1.15), _leg("b"))) == 0.94
    below = _regime([])
    assert below.tax_for_multi(stake=10.0, legs=(_leg("a"), _leg("a"))) == 1.00  # limit
    with pytest.raises(ValueError):
        below.tax_for_multi(stake=10.0, legs=(_leg("a"),))


# T11 --------------------------------------------------------------------


def test_t11_paper_bets_are_outside() -> None:
    paper = [_bet(5000.0, (_leg("a"), _leg("b")), mode="paper")]
    regime = _regime([_bet(1000.0, (_leg("x"),)), *paper])
    assert regime.real_turnover == 1000.0
    assert regime.tax_for_single(10.0, market="h2h") == 0.94


# T12 --------------------------------------------------------------------


def test_t12_exclusions_are_statutory() -> None:
    regime = _regime([], min_stake_pln=5.0, excluded_markets=frozenset({"spreads"}))
    assert regime.tax_for_single(4.99, market="h2h") == 0.88
    assert regime.tax_for_single(5.0, market="h2h") == 1.00
    assert regime.tax_for_multi(
        stake=10.0, legs=(_leg("a"), _leg("b", market="spreads"))
    ) == 0.88


# walidacje ---------------------------------------------------------------


def test_validation() -> None:
    with pytest.raises(ValueError, match="timezone"):
        _cfg(join_date=START.replace(tzinfo=None))
    with pytest.raises(ValueError):
        _cfg(external_turnover_pln=-1.0)
    with pytest.raises(ValueError):
        _cfg(external_coupons=-1)
    with pytest.raises(ValueError):
        _cfg(min_stake_pln=float("nan"))
    with pytest.raises(ValueError, match="share_basis"):
        _cfg(share_basis="coupons")
    with pytest.raises(TypeError):
        BetclicTaxRegime(now=NOW, bets=[], regime_config=object())
    with pytest.raises(ValueError, match="timezone"):
        BetclicTaxRegime(now=NOW.replace(tzinfo=None), bets=[], regime_config=_cfg())
    with pytest.raises(ValueError):
        CouponLeg(match_id="a", odds=1.0, void=False, market="h2h")
    with pytest.raises(ValueError):
        PlacedBet(coupon_id="x", placed_at=NOW, stake=1.0, legs=(), mode="real")
    with pytest.raises(ValueError):
        PlacedBet(coupon_id="x", placed_at=NOW, stake=0.0, legs=(_leg("a"),), mode="real")
    with pytest.raises(ValueError):
        PlacedBet(coupon_id="x", placed_at=NOW, stake=1.0, legs=(_leg("a"),), mode="demo")


# F1-P01 (wariant B, decyzja Pawła 2026-10-11) — reżim wg brzmienia regulaminu ----
# Czerwone na kodzie sprzed naprawy (reguła 31); wynik przed/po w
# reports/audit/FIX_LOG_F1.md.


def test_f1p01_pkt1_any_remaining_limit_frees_the_whole_bet() -> None:
    """§3 ust. 4: „Jeżeli przed zawarciem Zakładu Użytkownikowi pozostaje do
    wykorzystania jakakolwiek kwota […] cały taki Zakład uznaje się za
    kwalifikujący się do Oferty, niezależnie od wysokości stawki.”"""
    regime = _regime([_bet(900.0, (_leg("x"),))])
    assert regime.tax_for_single(100.0, market="h2h") == 1.00  # osiąga próg
    assert regime.tax_for_single(5000.0, market="h2h") == 1.00  # przekracza próg
    almost = _regime([_bet(999.99, (_leg("x"),))])
    assert almost.tax_for_single(50.0, market="h2h") == 1.00  # zostaje 0,01 zł
    assert _regime([], external_turnover_pln=950.0).tax_for_single(60.0, market="h2h") == 1.00
    # wielokrotny niekwalifikujący się — też „cały taki Zakład”
    assert regime.tax_for_multi(stake=500.0, legs=(_leg("a", 1.15), _leg("b"))) == 1.00


def test_f1p01_pkt1_exhausted_limit_is_not_free() -> None:
    """Limit wyczerpany dokładnie (1000 zł przed zakładem) — nic nie zostaje."""
    exact = _regime([_bet(1000.0, (_leg("x"),))])
    assert exact.tax_for_single(0.5, market="h2h") == 0.94


def test_f1p01_pkt2_non_qualifying_multi_follows_the_share() -> None:
    """§3 ust. 11.1: wielokrotny niespełniający ust. 9 — 0.94 przy udziale < 50%;
    ust. 12: przy udziale ≥ 50% wszystkie Zakłady w ofercie (1.0). Nie 0.88."""
    low = _regime([_bet(1000.0, (_leg("x"),))])
    assert low.tax_for_multi(stake=10.0, legs=(_leg("a", 1.15), _leg("b"))) == 0.94
    assert low.tax_for_multi(stake=10.0, legs=(_leg("a"), _leg("a"))) == 0.94
    # udział z kandydatem dokładnie 0.50: AKO 1000 / (1000 + 990 + 10)
    half = _regime([_bet(1000.0, (_leg("p"), _leg("q"))), _bet(990.0, (_leg("s"),))])
    assert half.tax_for_multi(stake=10.0, legs=(_leg("a", 1.15), _leg("b"))) == 1.00
    # 0.4999: AKO 4999 / (4999 + 4991 + 10)
    under = _regime([_bet(4999.0, (_leg("p"), _leg("q"))), _bet(4991.0, (_leg("s"),))])
    assert under.tax_for_multi(stake=10.0, legs=(_leg("a", 1.15), _leg("b"))) == 0.94


def test_f1p01_pkt3_share_by_stakes_only() -> None:
    """§3 ust. 5: udział stawek, nie kuponów. Po stawkach ≥ 50%, po kuponach < 50%
    → singiel 1.00; przypadki graniczne 0.50 i 0.4999 (kandydat wliczony, T3)."""
    by_stake_only = [_bet(5000.0, (_leg("a"), _leg("b")))] + [
        _bet(10.0, (_leg(f"s{i}"),)) for i in range(5)
    ]
    assert _regime(by_stake_only).tax_for_single(10.0, market="h2h") == 1.00
    half = _regime([_bet(1000.0, (_leg("p"), _leg("q"))), _bet(990.0, (_leg("s"),))])
    assert half.tax_for_single(10.0, market="h2h") == 1.00  # 1000/2000 = 0.50
    under = _regime([_bet(4999.0, (_leg("p"), _leg("q"))), _bet(4991.0, (_leg("s"),))])
    assert under.tax_for_single(10.0, market="h2h") == 0.94  # 4999/10000 = 0.4999


def test_f1p01_pkt3_share_basis_is_required() -> None:
    """Reguła 30: podstawa udziału bez wartości domyślnej — pominięcie to błąd."""
    fields = {
        "promo_active": True, "promo_valid_from": START, "join_date": START,
        "external_turnover_pln": 0.0, "external_coupons": 0,
        "share_condition_known": True, "min_stake_pln": 0.0,
        "excluded_markets": frozenset(),
    }  # fmt: skip
    with pytest.raises(TypeError, match="share_basis"):
        RegimeConfig(**fields)


def test_f1p01_live_loader_uses_the_regulation_basis(tmp_path: Path) -> None:
    assert load_betclic_regime_config(_yaml(tmp_path), now=NOW).share_basis == SHARE_BY_STAKES
