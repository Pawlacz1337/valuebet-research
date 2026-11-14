"""Testy toru S: fair, ev, kelly, dziennik, CLV, digest (TOR_S_PLAN §9)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pytest

from helpers import fake_http
from valuebet.backtest.clv import CLOSING_TOLERANCE, ClvReport, clv_report, clv_rows
from valuebet.live.bets import BetJournal, BetRecord, coupons
from valuebet.live.digest import build_digest, send_digest
from valuebet.pricing.ev import (
    AKO_MIN_LEG_ODDS,
    NO_TAX_TURNOVER_LIMIT,
    BetclicTaxRegime,
    CouponLeg,
    PlacedBet,
    RegimeConfig,
    double_ev,
    ev,
    min_odds,
)
from valuebet.pricing.fair import MAX_AGE, FairPrice, MarketQuote, fair_prices
from valuebet.pricing.kelly import (
    DRAWDOWN_SWITCH,
    GK_MIN_REAL_BETS,
    HALF_KELLY_ENABLED,
    MAX_FRACTION_PER_BET,
    KellyPolicy,
    kelly_fraction,
)
from valuebet.pricing.shin import shin_forward

T0 = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
KICKOFF = datetime(2026, 10, 24, 17, 30, tzinfo=UTC)
#: Gwizdki dla wszystkich meczów z migawek w testach wyceny (F-20: wymagane).
KO = {"m1": KICKOFF, "m_bad": KICKOFF, "m_ok": KICKOFF}
#: Chwila CLV po meczu — mecz rozegrany, zamknięcie znane.
AFTER = KICKOFF + timedelta(hours=3)


# ---------------------------------------------------------------------------
# fair.py
# ---------------------------------------------------------------------------


def _quote(**kwargs: object) -> MarketQuote:
    base = {
        "match_id": "m1",
        "market": "1x2",
        "outcomes": ("home", "draw", "away"),
        "odds": (1.95, 3.60, 4.20),
        "observed_at": T0 - timedelta(hours=1),
    }
    base.update(kwargs)
    return MarketQuote(**base)  # type: ignore[arg-type]


def test_shin_round_trip_through_fair_prices() -> None:
    """Kursy wygenerowane ze znanych p muszą dać te p z powrotem."""
    truth = np.array([0.52, 0.27, 0.21])
    odds = tuple(float(k) for k in shin_forward(truth, z=0.03))
    prices = fair_prices([_quote(odds=odds)], decision_time=T0, kickoffs=KO).prices
    assert [p.p for p in prices] == pytest.approx(truth, abs=1e-6)
    assert all(p.source == "pinnacle" for p in prices)


def test_snapshot_older_than_limit_gives_no_price() -> None:
    """Starsza migawka => brak wyceny, nie stara cena."""
    old = _quote(observed_at=T0 - MAX_AGE - timedelta(minutes=1))
    assert fair_prices([old], decision_time=T0, kickoffs=KO).prices == []


def test_future_poison_snapshot_from_after_decision_is_ignored() -> None:
    """Wycena w chwili t używa WYŁĄCZNIE migawek z observed_at < t."""
    future = _quote(observed_at=T0 + timedelta(minutes=1))
    assert fair_prices([future], decision_time=T0, kickoffs=KO).prices == []


def test_incomplete_market_is_skipped_not_priced() -> None:
    """Reguła 17: 2 z 3 wyników 1X2 daje bezsensowny booksum."""
    partial = _quote(outcomes=("home", "away"), odds=(1.95, 4.20))
    assert fair_prices([partial], decision_time=T0, kickoffs=KO).prices == []


def test_nonsense_odds_are_skipped() -> None:
    assert fair_prices([_quote(odds=(1.0, 3.6, 4.2))], decision_time=T0, kickoffs=KO).prices == []


def test_naive_decision_time_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        fair_prices(
            [_quote()],
            decision_time=T0.replace(tzinfo=None),
            kickoffs=KO,
        )


def test_two_way_market_is_priced() -> None:
    quote = _quote(
        market="totals", outcomes=("over", "under"), odds=(1.90, 1.98), line=2.5
    )
    prices = fair_prices([quote], decision_time=T0, kickoffs=KO).prices
    assert len(prices) == 2
    assert sum(p.p for p in prices) == pytest.approx(1.0, abs=1e-9)
    assert all(p.line == 2.5 for p in prices)


# ---------------------------------------------------------------------------
# ev.py — EV i progi
# ---------------------------------------------------------------------------


def test_ev_computed_by_hand() -> None:
    # p = 0.55, k = 2.00, tax = 0.88  ->  0.55*2*0.88 - 1 = -0.032
    assert ev(0.55, 2.00, tax_factor=0.88, winnings_factor=1.0) == pytest.approx(-0.032, abs=1e-9)
    # bez podatku: 0.55*2 - 1 = +0.10
    assert ev(0.55, 2.00, tax_factor=1.00, winnings_factor=1.0) == pytest.approx(0.10, abs=1e-9)


def test_min_odds_computed_by_hand() -> None:
    # k_min = 1.02 / (0.55 * 0.88) = 2.10743801...
    assert min_odds(0.55, tax_factor=0.88, winnings_factor=1.0, edge_threshold=0.02) == pytest.approx(1.02 / (0.55 * 0.88), abs=1e-12)
    # Bez podatku ten sam próg jest o 12% niżej.
    assert min_odds(0.55, tax_factor=1.00, winnings_factor=1.0, edge_threshold=0.02) == pytest.approx(1.02 / 0.55, abs=1e-12)


def test_min_odds_shows_why_project_needs_the_promotion() -> None:
    """Przy 0.88 i progu 2% wymagana przewaga to ~16%."""
    p = 0.50
    required = min_odds(p, tax_factor=0.88, winnings_factor=1.0, edge_threshold=0.02) * p
    assert required == pytest.approx(1.1591, abs=1e-3)


def test_tax_factor_outside_allowed_set_is_rejected() -> None:
    with pytest.raises(ValueError, match="reguła 20"):
        ev(0.5, 2.0, tax_factor=0.91, winnings_factor=1.0)


def test_double_ev_rejects_two_legs_from_one_match() -> None:
    with pytest.raises(ValueError, match="tego samego meczu"):
        double_ev((("m1", 0.5, 2.1), ("m1", 0.6, 1.9)), tax_factor=1.00, winnings_factor=1.0)


def test_double_ev_by_hand() -> None:
    # 0.5*2.1 * 0.6*1.9 * 1.00 - 1 = 1.05*1.14 - 1 = 0.197
    assert double_ev((("m1", 0.5, 2.1), ("m2", 0.6, 1.9)), tax_factor=1.00, winnings_factor=1.0) == pytest.approx(
        0.197, abs=1e-9
    )


# ---------------------------------------------------------------------------
# ev.py — reżim Betclica
# ---------------------------------------------------------------------------


_COUPONS = iter(range(10**9))
#: Konfiguracja reżimu w testach: akcja od dawna, bez obrotu spoza dziennika.
REGIME = RegimeConfig(
    promo_active=True,
    promo_valid_from=T0 - timedelta(days=60),
    join_date=T0 - timedelta(days=60),
    external_turnover_pln=0.0,
    external_coupons=0,
    share_condition_known=True,
    min_stake_pln=0.0,
    excluded_markets=frozenset(),
    share_basis="stakes",
)


def _bet(
    stake: float, legs: tuple[float, ...], mode: str = "real", *, at: datetime = T0
) -> PlacedBet:
    """Kupon: nogi z różnych meczów, po jednej na kurs."""
    n = next(_COUPONS)
    return PlacedBet(
        coupon_id=f"c{n}",
        placed_at=at,
        stake=stake,
        legs=tuple(
            CouponLeg(match_id=f"m{n}-{i}", odds=k, void=False, market="h2h") for i, k in enumerate(legs)
        ),
        mode=mode,
    )


def _regime(bets: list[PlacedBet], *, now: datetime = T0) -> BetclicTaxRegime:
    return BetclicTaxRegime(now=now, bets=bets, regime_config=REGIME)


def test_below_turnover_limit_everything_is_tax_free() -> None:
    regime = _regime([_bet(100.0, (2.0,))])
    assert regime.real_turnover < NO_TAX_TURNOVER_LIMIT
    assert regime.tax_for_single(50.0, market="h2h") == 1.00


def test_above_limit_single_without_ako_share_is_penalised() -> None:
    regime = _regime([_bet(NO_TAX_TURNOVER_LIMIT, (2.0,))])
    assert regime.tax_for_single(50.0, market="h2h") == 0.94


def test_ako_share_above_half_keeps_singles_tax_free() -> None:
    # T4: udział po stawkach ≥ 50% (regulamin; tu oba udziały ≥ 50%).
    regime = _regime([_bet(900.0, (1.5, 1.6)), _bet(500.0, (1.5, 1.6)), _bet(200.0, (2.0,))])
    by_stake, by_coupons = regime.ako_shares(candidate=None)
    assert by_stake > 0.5 and by_coupons > 0.5
    assert regime.tax_for_single(10.0, market="h2h") == 1.00


def test_ako_share_is_by_turnover_not_by_count() -> None:
    """Dziesięć AKO po 2 zł i singiel na 1000 zł to 91% kuponów, 2% obrotu.

    Limit 1000 zł wyczerpany przed kandydatem (F1-P01 pkt 1: przy pozostałej
    kwocie limitu kandydat byłby w ofercie niezależnie od udziału)."""
    regime = _regime([_bet(2.0, (1.5, 1.6)) for _ in range(10)] + [_bet(1000.0, (2.0,))])
    by_stake, by_coupons = regime.ako_shares(candidate=None)
    assert by_stake < 0.05 and by_coupons > 0.9
    assert regime.tax_for_single(600.0, market="h2h") == 0.94


def test_what_if_a_single_pushes_itself_below_the_threshold() -> None:
    """Singiel potrafi sam zepchnąć udział AKO pod progiem — i swój podatek."""
    regime = _regime([_bet(1000.0, (1.5, 1.6))])
    assert regime.ako_shares(candidate=None) == (pytest.approx(1.0), pytest.approx(1.0))
    # Mały singiel: 1000/1010 i 1/2 — oba ≥ 50%.
    assert regime.tax_for_single(10.0, market="h2h") == 1.00
    # Duży singiel spycha udział po stawkach pod 50% i wycenia się na 0.94.
    assert regime.tax_for_single(2000.0, market="h2h") == 0.94


def test_ako_with_a_leg_below_minimum_odds_does_not_qualify() -> None:
    low = AKO_MIN_LEG_ODDS - 0.01
    assert not _bet(100.0, (low, 2.0)).qualifies_as_ako
    assert _bet(100.0, (AKO_MIN_LEG_ODDS, 2.0)).qualifies_as_ako


def test_single_never_qualifies_as_ako() -> None:
    assert not _bet(100.0, (5.0,)).qualifies_as_ako


def test_paper_bets_do_not_count_towards_the_regime() -> None:
    """Paper nie generuje obrotu u bukmachera — wliczanie dałoby fałszywe 1.00."""
    regime = _regime([_bet(5000.0, (1.5, 1.6), mode="paper"), _bet(1000.0, (2.0,))])
    assert regime.real_turnover == 1000.0
    assert regime.ako_shares(candidate=None) == (0.0, 0.0)
    assert regime.tax_for_single(10.0, market="h2h") == 0.94


def test_qualified_ako_is_always_tax_free() -> None:
    regime = _regime([_bet(5000.0, (2.0,))])
    assert regime.tax_for_single(100.0, market="h2h") == 0.94
    legs = (
        CouponLeg(match_id="a", odds=1.5, void=False, market="h2h"),
        CouponLeg(match_id="b", odds=1.6, void=False, market="h2h"),
    )
    assert regime.tax_for_multi(stake=100.0, legs=legs) == 1.00


# ---------------------------------------------------------------------------
# kelly.py
# ---------------------------------------------------------------------------


def test_kelly_by_hand() -> None:
    # p=0.55, k=2.0, tax=1.0: (1.1-1)/(2-1) = 0.1
    assert kelly_fraction(0.55, 2.0, tax_factor=1.0, winnings_factor=1.0) == pytest.approx(0.10, abs=1e-12)


def test_kelly_is_zero_on_nonpositive_ev() -> None:
    assert kelly_fraction(0.45, 2.0, tax_factor=1.0, winnings_factor=1.0) == 0.0
    assert kelly_fraction(0.55, 2.0, tax_factor=0.88, winnings_factor=1.0) == 0.0


#: Raport CLV bez zakładów — bramka G-K zamknięta.
NO_CLV = ClvReport(
    n_total=0, n_with_clv=0, n_missing=0, mean=None, ci_low=None, ci_high=None,
    n_clusters=0,
)  # fmt: skip
#: Raport CLV, który otwiera bramkę G-K (pokrycie, klastry, dodatnie CI).
SOLID_CLV = ClvReport(
    n_total=200, n_with_clv=195, n_missing=5, mean=0.01, ci_low=0.004,
    ci_high=0.016, n_clusters=14,
)  # fmt: skip


def _kelly(**kwargs: Any) -> KellyPolicy:
    """Jedyna droga: ``from_journal``, wszystkie bezpieczniki podane jawnie."""
    base: dict[str, Any] = {
        "bankroll": 1e4,
        "peak_bankroll": 1e4,
        "clv_report": NO_CLV,
        "n_real_bets": 0,
        "open_exposure": 0.0,
        "match_exposure": 0.0,
    }
    base.update(kwargs)
    return KellyPolicy.from_journal(**base)


def test_default_fraction_is_quarter_and_cap_is_two_percent() -> None:
    policy = _kelly()
    assert policy.c == 0.25
    decision = policy.stake(0.70, 2.0, tax_factor=1.00)
    assert decision.fraction == pytest.approx(MAX_FRACTION_PER_BET)
    assert "limit na zakład" in " ".join(decision.reasons)


def test_half_kelly_requires_the_gk_gate_not_a_flag() -> None:
    almost = _kelly(clv_report=SOLID_CLV, n_real_bets=GK_MIN_REAL_BETS - 1)
    assert not almost.gk_passed
    assert almost.c == 0.25

    no_ci = _kelly(clv_report=NO_CLV, n_real_bets=GK_MIN_REAL_BETS)
    assert not no_ci.gk_passed, "brak policzonego CI to nie przeszła, nie przeszła"

    negative = _kelly(
        clv_report=ClvReport(
            n_total=400, n_with_clv=400, n_missing=0, mean=-0.01, ci_low=-0.001,
            ci_high=0.002, n_clusters=20,
        ),
        n_real_bets=400,
    )  # fmt: skip
    assert not negative.gk_passed

    # Bramka liczona z RAPORTU CLV i raportowana; c zostaje 0.25 do Filaru 3
    # (CLAUDE.md reguła 21, FSA #0 F-06/F-19 — zmiana oczekiwania z 0.5).
    passed = _kelly(clv_report=SOLID_CLV, n_real_bets=GK_MIN_REAL_BETS)
    assert passed.gk_passed
    assert passed.c == 0.25
    assert passed.stake(0.55, 2.10, tax_factor=0.88).gk_would_unlock


def test_fraction_never_exceeds_quarter_before_pillar_three() -> None:
    policy = _kelly(
        clv_report=ClvReport(
            n_total=1000, n_with_clv=1000, n_missing=0, mean=0.5, ci_low=0.4,
            ci_high=0.6, n_clusters=50,
        ),
        n_real_bets=10_000,
    )  # fmt: skip
    assert not HALF_KELLY_ENABLED
    assert policy.c == 0.25, "c = ½ zablokowane do Filaru 3 (reguła 21)"


def test_match_and_exposure_limits_bind() -> None:
    policy = _kelly(match_exposure=0.025, open_exposure=0.0)
    decision = policy.stake(0.70, 2.0, tax_factor=1.00)
    assert decision.fraction == pytest.approx(0.005)
    assert "limit na mecz" in " ".join(decision.reasons)

    full = _kelly(open_exposure=0.15)
    assert full.stake(0.70, 2.0, tax_factor=1.00).fraction == 0.0


def test_drawdown_switch_forces_paper_mode() -> None:
    policy = _kelly(bankroll=7_500.0, peak_bankroll=10_000.0)
    assert policy.drawdown == pytest.approx(DRAWDOWN_SWITCH)
    decision = policy.stake(0.70, 2.0, tax_factor=1.00)
    assert decision.is_paper
    assert any("wyłącznik" in r for r in decision.reasons)


def test_dead_clv_correction_is_gone() -> None:
    """F-06: korekta CLV/EV była martwa (obie gałęzie dawały None) — usunięta.

    Wraca dopiero z implementacją ``e_użyte = e · min(1, CLV/EV)`` w Filarze 3.
    Dziś żadne pole ani argument nie może jej udawać.
    """
    assert not hasattr(_kelly(), "clv_to_ev_ratio")
    with pytest.raises(TypeError):
        _kelly(clv_to_ev_ratio=0.3)


# ---------------------------------------------------------------------------
# bets.py
# ---------------------------------------------------------------------------


def _record(**kwargs: object) -> BetRecord:
    base = {
        "bet_id": "b1",
        "placed_at": T0,
        "mode": "paper",
        "bookmaker": "betclic",
        "coupon_id": "c1",
        "coupon_type": "single",
        "n_legs": 1,
        "leg_index": 0,
        "match_id": "m1",
        "market": "1x2",
        "outcome": "home",
        "line": None,
        "odds_taken": 2.10,
        "stake": 50.0,
        "tax_factor_applied": 1.00,
        "p_fair_at_bet": 0.52,
        "snapshot_observed_at": T0 - timedelta(hours=1),
        "price_available": True,
        "ingested_at": T0,
        "source": "manual",
    }
    base.update(kwargs)
    if "bet_id" in kwargs and "coupon_id" not in kwargs:
        base["coupon_id"] = f"c-{kwargs['bet_id']}"
    return BetRecord(**base)  # type: ignore[arg-type]


def test_journal_round_trip(tmp_path: Path) -> None:
    journal = BetJournal(journal_path=tmp_path / "bets.csv")
    journal.add(_record())
    rows = journal.read()
    assert len(rows) == 1
    assert rows[0].odds_taken == 2.10
    assert rows[0].price_available is True
    assert rows[0].snapshot_observed_at == T0 - timedelta(hours=1)


def test_journal_is_append_only(tmp_path: Path) -> None:
    journal = BetJournal(journal_path=tmp_path / "bets.csv")
    journal.add(_record())
    with pytest.raises(ValueError, match="append-only"):
        journal.add(_record())


def test_settlement_adds_a_row_instead_of_editing(tmp_path: Path) -> None:
    journal = BetJournal(journal_path=tmp_path / "bets.csv")
    journal.add(_record())
    journal.settle("b1", "won", now=T0 + timedelta(hours=1))
    rows = journal.read()
    assert len(rows) == 2
    assert rows[0].settled == ""
    assert rows[1].settled == "won"
    assert rows[1].payout == 105.0


def test_snapshot_from_after_the_bet_is_rejected() -> None:
    with pytest.raises(ValueError, match="wycena z przyszłości"):
        _record(snapshot_observed_at=T0 + timedelta(minutes=1))


@pytest.mark.parametrize(
    ("field", "value", "pattern"),
    [
        ("mode", "demo", "paper albo real"),
        ("odds_taken", 1.0, "kurs"),
        ("stake", 0.0, "stawka"),
        ("p_fair_at_bet", 1.5, "p_fair"),
    ],
)
def test_record_validation(field: str, value: object, pattern: str) -> None:
    with pytest.raises(ValueError, match=pattern):
        _record(**{field: value})


# ---------------------------------------------------------------------------
# clv.py
# ---------------------------------------------------------------------------


def test_clv_computed_by_hand() -> None:
    bet = _record(odds_taken=2.20, tax_factor_applied=1.00)
    rows = clv_rows(
        bets=[bet],
        closing={("m1", "1x2", "home", None): (0.50, KICKOFF - timedelta(minutes=10))},
        kickoffs={"m1": KICKOFF},
        as_of=AFTER,
    )
    # 2.20 * 1.00 * 0.50 - 1 = +0.10
    assert rows[0].clv == pytest.approx(0.10, abs=1e-12)


def test_missing_closing_is_not_available_not_zero() -> None:
    rows = clv_rows(bets=[_record()], closing={}, kickoffs={"m1": KICKOFF}, as_of=AFTER)
    assert rows[0].clv is None
    assert "brak migawki" in rows[0].reason
    report = clv_report(rows)
    assert report.mean is None
    assert report.n_missing == 1


def test_closing_outside_tolerance_is_not_a_closing() -> None:
    too_early = KICKOFF - CLOSING_TOLERANCE - timedelta(minutes=1)
    rows = clv_rows(
        bets=[_record()],
        closing={("m1", "1x2", "home", None): (0.5, too_early)},
        kickoffs={"m1": KICKOFF},
        as_of=AFTER,
    )
    assert rows[0].clv is None
    assert "poza tolerancją" in rows[0].reason


def test_clv_report_needs_enough_clusters() -> None:
    bets = [_record(bet_id=f"b{i}") for i in range(4)]
    rows = clv_rows(
        bets=bets,
        closing={("m1", "1x2", "home", None): (0.50, KICKOFF - timedelta(minutes=5))},
        kickoffs={"m1": KICKOFF},
        as_of=AFTER,
    )
    report = clv_report(rows)
    assert report.mean is not None
    assert report.ci_low is None
    assert "za mało klastrów" in report.note
    assert not report.beats_closing


def test_clv_report_with_enough_clusters_gives_ci() -> None:
    bets = []
    closing = {}
    kickoffs = {}
    for week in range(8):
        match_id = f"m{week}"
        bets.append(_record(bet_id=f"b{week}", match_id=match_id, odds_taken=2.2))
        kickoff = KICKOFF + timedelta(weeks=week)
        kickoffs[match_id] = kickoff
        closing[(match_id, "1x2", "home", None)] = (0.50, kickoff - timedelta(minutes=5))
    report = clv_report(
        clv_rows(
            bets=bets,
            closing=closing,
            kickoffs=kickoffs,
            as_of=KICKOFF + timedelta(weeks=9),
        )
    )
    assert report.n_clusters >= 5
    assert report.ci_low is not None
    assert report.beats_closing


# ---------------------------------------------------------------------------
# digest.py
# ---------------------------------------------------------------------------


def _price(outcome: str, p: float) -> FairPrice:
    return FairPrice(
        match_id="m1",
        market="1x2",
        outcome=outcome,
        p=p,
        observed_at=T0 - timedelta(hours=1),
    )


def test_digest_contains_thresholds_and_mode() -> None:
    text = build_digest(
        [_price("home", 0.52), _price("draw", 0.27), _price("away", 0.21)],
        kickoffs={"m1": KICKOFF},
        labels={"m1": "Legia - Lech"},
        leagues={"m1": "Ekstraklasa"},
        decision_time=T0,
        tax_factor=1.00,
        mode="paper",
        edge_threshold=0.02,
        winnings_factor=1.0,
    )
    assert "PAPER" in text
    assert "Legia - Lech" in text
    assert "k_min" in text
    assert "Ekstraklasa" in text


def test_digest_warns_about_stale_snapshot() -> None:
    old = FairPrice(
        match_id="m1",
        market="1x2",
        outcome="home",
        p=0.5,
        observed_at=T0 - timedelta(hours=4),
    )
    text = build_digest(
        [old],
        kickoffs={"m1": KICKOFF},
        labels={"m1": "A - B"},
        leagues={"m1": "L"},
        decision_time=T0,
        tax_factor=1.00,
        mode="real",
        edge_threshold=0.02,
        winnings_factor=1.0,
    )
    assert "STARA MIGAWKA" in text


def test_digest_without_token_writes_a_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("VB_TELEGRAM_TOKEN", raising=False)
    monkeypatch.delenv("VB_TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setattr("valuebet.live.digest.DIGEST_DIR", tmp_path / "digest")
    path = send_digest(
        "tresc przegladu", now=T0, http=fake_http(lambda r: httpx.Response(500))
    )
    assert path is not None
    assert path.read_text(encoding="utf-8") == "tresc przegladu"


def test_digest_goes_to_telegram_through_the_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VB_TELEGRAM_TOKEN", "123:tajny")
    monkeypatch.setenv("VB_TELEGRAM_CHAT_ID", "999")
    monkeypatch.setattr("valuebet.live.digest.DIGEST_DIR", tmp_path / "digest")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    assert send_digest("x", now=T0, http=fake_http(handler)) is None
    assert seen[0].url.host == "api.telegram.org"
    rejected = send_digest("x", now=T0, http=fake_http(lambda r: httpx.Response(401)))
    assert rejected is not None


def test_digest_text_carries_no_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VB_TELEGRAM_TOKEN", "tajny-token-123")
    monkeypatch.setenv("VB_TELEGRAM_CHAT_ID", "999")
    text = build_digest(
        [_price("home", 0.5)],
        kickoffs={"m1": KICKOFF},
        labels={"m1": "A - B"},
        leagues={"m1": "L"},
        decision_time=T0,
        tax_factor=1.00,
        mode="real",
        edge_threshold=0.02,
        winnings_factor=1.0,
    )
    assert "tajny-token-123" not in text
    assert "999" not in text


def test_digest_skips_matches_outside_horizon() -> None:
    far = FairPrice(
        match_id="m2",
        market="1x2",
        outcome="home",
        p=0.5,
        observed_at=T0 - timedelta(hours=1),
    )
    text = build_digest(
        [far],
        kickoffs={"m2": T0 + timedelta(days=10)},
        labels={"m2": "Daleko - Stad"},
        leagues={"m2": "L"},
        decision_time=T0,
        tax_factor=1.00,
        mode="real",
        edge_threshold=0.02,
        winnings_factor=1.0,
    )
    assert "Daleko - Stad" not in text
    assert "Brak meczow" in text


# ---------------------------------------------------------------------------
# Regresje z audytu 2026-10-01 (AUDIT_REPORT_2.md)
# ---------------------------------------------------------------------------


def test_regression_h2h_market_name_is_validated() -> None:
    """KRYTYCZNE 1: nasz własny ingest nazywa 1X2 jako ``h2h``.

    Pierwotne ``MARKET_SIZE`` miało tylko ``1x2``, więc dla ``h2h``
    walidacja kompletności nie uruchamiała się wcale — rynek z czterema
    kursami przechodził przez Shina z booksumem 1.31 i dawał cztery wyceny
    sumujące się do 1.
    """
    from valuebet.ingest.odds_collector import DECISION_MARKETS

    assert "h2h" in DECISION_MARKETS
    four = _quote(
        market="h2h",
        outcomes=("home", "draw", "draw2", "away"),
        odds=(1.95, 3.60, 3.60, 4.20),
    )
    assert fair_prices([four], decision_time=T0, kickoffs=KO).prices == []
    assert len(fair_prices([_quote(market="h2h")], decision_time=T0, kickoffs=KO).prices) == 3


def test_regression_unknown_market_raises_instead_of_skipping_validation() -> None:
    """Nieznany rynek to błąd kontraktu, nie dana do cichej wyceny (reguła 17)."""
    with pytest.raises(ValueError, match="nieznany rynek"):
        fair_prices(
            [_quote(market="double_chance", odds=(1.28, 1.30, 2.10))],
            decision_time=T0,
            kickoffs=KO,
        )


def test_regression_shin_value_error_does_not_kill_the_batch() -> None:
    """Kontrakt mówi pomijanie z ostrzeżeniem, nie wysadzenie całego dnia."""
    underround = _quote(match_id="m_bad", odds=(2.5, 3.0, 4.0))
    good = _quote(match_id="m_ok")
    prices = fair_prices([underround, good], decision_time=T0, kickoffs=KO).prices
    assert {p.match_id for p in prices} == {"m_ok"}


def test_regression_pricing_refuses_after_kickoff() -> None:
    """Bez ``kickoffs`` nic nie wymuszało decision_time < kickoff (F-20)."""
    quote = _quote(observed_at=KICKOFF - timedelta(hours=1))
    after = KICKOFF + timedelta(minutes=10)
    assert fair_prices([quote], decision_time=after, kickoffs={"m1": KICKOFF}).prices == []
    # FSA #0 F-20: pominięcie kickoffs nie jest już ścieżką wyceny.
    with pytest.raises(TypeError):
        fair_prices([quote], decision_time=after)


def test_regression_future_bets_cannot_change_todays_tax() -> None:
    """KRYTYCZNE 2: okno AKO było obcięte tylko od dołu.

    Zmierzone przed naprawą: dziesięć AKO z przyszłości podniosło
    ``tax_for_single`` z 0.94 na 1.00, czyli o 6 pp stawki.
    """
    past = [_bet(100.0, (2.0,), at=T0 - timedelta(days=10)) for _ in range(10)]
    future = [_bet(200.0, (1.5, 1.6), at=T0 + timedelta(days=10)) for _ in range(10)]
    only_past = _regime(past)
    with_future = _regime(past + future)
    assert only_past.ako_shares(candidate=None) == with_future.ako_shares(candidate=None)
    assert only_past.tax_for_single(100.0, market="h2h") == with_future.tax_for_single(100.0, market="h2h")
    assert only_past.tax_for_single(100.0, market="h2h") == 0.94


def test_regression_turnover_also_respects_the_cutoff() -> None:
    regime = _regime([_bet(5000.0, (2.0,), at=T0 + timedelta(days=1))])
    assert regime.real_turnover == 0.0
    assert regime.tax_for_single(10.0, market="h2h") == 1.00


def test_regression_mode_has_no_default() -> None:
    """Domyślne real liczyło paper jako prawdziwy przy pominięciu argumentu."""
    with pytest.raises(TypeError):
        PlacedBet(
            coupon_id="x",
            placed_at=T0,
            stake=10.0,
            legs=(CouponLeg(match_id="a", odds=2.0, void=False, market="h2h"),),
        )


def test_regression_settlement_rows_do_not_double_count_turnover(tmp_path: Path) -> None:
    """``settle()`` dopisuje wiersz z tym samym stake i mode real — to nie kupon."""
    journal = BetJournal(journal_path=tmp_path / "bets.csv")
    journal.add(_record(mode="real", stake=500.0))
    journal.settle("b1", "won", now=T0 + timedelta(hours=1))
    later = T0 + timedelta(days=1)
    regime = _regime([c.to_placed_bet() for c in coupons(journal.read(), now=later)], now=later)
    assert regime.real_turnover == 500.0


def test_regression_journal_to_placed_bets_skips_settlements(tmp_path: Path) -> None:
    journal = BetJournal(journal_path=tmp_path / "bets.csv")
    journal.add(_record(mode="real", stake=100.0))
    journal.settle("b1", "won", now=T0 + timedelta(hours=1))
    found = coupons(journal.read(), now=T0 + timedelta(hours=2))
    assert len(found) == 1
    assert found[0].status == "won"
    assert sum(c.stake for c in found if c.is_real) == 100.0


def test_regression_gk_gate_needs_a_real_clv_report() -> None:
    """Reguła 21: flagi od wołającego to nie sprawdzanie kodem (F-19)."""
    with pytest.raises(RuntimeError, match="from_journal"):
        KellyPolicy(
            bankroll=1e4,
            peak_bankroll=1e4,
            n_real_bets=150,
            clv_report=SOLID_CLV,
            open_exposure=0.0,
            match_exposure=0.0,
        )


def test_regression_clv_report_unlocks_gk_only_with_coverage_and_clusters() -> None:
    from valuebet.backtest.clv import MIN_CLOSING_COVERAGE, ClvReport

    thin = ClvReport(
        n_total=100,
        n_with_clv=30,
        n_missing=70,
        mean=0.02,
        ci_low=0.01,
        ci_high=0.03,
        n_clusters=20,
    )
    assert thin.coverage < MIN_CLOSING_COVERAGE
    assert not thin.beats_closing
    assert not thin.unlocks_gk

    few_clusters = ClvReport(
        n_total=100,
        n_with_clv=100,
        n_missing=0,
        mean=0.02,
        ci_low=0.01,
        ci_high=0.03,
        n_clusters=5,
    )
    # F-22: żaden werdykt poniżej 8 klastrów — także „bije zamknięcie”.
    assert not few_clusters.beats_closing
    assert not few_clusters.unlocks_gk
    assert "poniżej progu wiarygodności" in few_clusters.describe()

    solid = ClvReport(
        n_total=100,
        n_with_clv=95,
        n_missing=5,
        mean=0.02,
        ci_low=0.01,
        ci_high=0.03,
        n_clusters=12,
    )
    assert solid.unlocks_gk
    policy = _kelly(clv_report=solid, n_real_bets=200)
    assert policy.gk_passed
    assert policy.c == 0.25  # c = ½ zablokowane do Filaru 3 (reguła 21)


def test_regression_clv_as_of_excludes_unplayed_matches() -> None:
    rows = clv_rows(
        bets=[_record()],
        closing={("m1", "1x2", "home", None): (0.5, KICKOFF - timedelta(minutes=5))},
        kickoffs={"m1": KICKOFF},
        as_of=KICKOFF - timedelta(days=1),
    )
    # FSA #0 F-04: mecz po as_of jest poza agregatem i liczony osobno.
    assert [r.excluded_future for r in rows] == [True]
    report = clv_report(rows)
    assert report.n_total == 0
    assert report.n_excluded_future == 1


def test_regression_shin_fallback_is_not_proportional() -> None:
    """Reguła 16: ścieżka awaryjna nie zwraca normalizacji proporcjonalnej (A-03)."""
    from valuebet.pricing.shin import shin_probabilities

    good = shin_probabilities(np.array([1.80, 3.60, 4.50]))
    assert good.method == "shin"
    bad = shin_probabilities(np.array([2.5, 3.0, 4.0]), allow_underround=True)
    assert bad.method == "none"
    assert np.isnan(bad.probabilities).all()
