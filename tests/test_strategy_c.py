"""Strategia C — reżim Betclica w działaniu (BACKTEST_FIN_PLAN §3, docs/promocje.md).

Konstrukcja (plan §3, zamrożona): nogi value z jednej migawki (EV ≥ θ przy
1.00), EV malejąco, potem ``match_id``; zachłannie pary z RÓŻNYCH meczów,
każda noga ≥ 1.20 → dublet; reszta → single. Stawka dubletu: Kelly ¼ na
``Π k`` przy ``p = Π p``, limit 2%; pełna stawka dubletu do ekspozycji obu
meczów. Kolejność wyceny podatku (T3): najpierw single, potem dublety.

Decyzja Pawła 2026-10-08: singiel C przechodzi ``k_min`` przy podatku z
``BetclicTaxRegime`` i jest rozliczany tym samym współczynnikiem; wariant
dosłowny planu (wybór 1.00 / stawka przy podatku reżimu) — diagnostyka;
T12: ``min_stake = 0``, bez wyłączonych rynków, etykieta „GÓRNA GRANICA, T12
nieznane”. Wariant kontrfaktyczny (promocje.md): próg 1000 zł wykorzystany.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pytest

from helpers.fin_world import T0, WorldMatch, build_replay
from valuebet.backtest.financial import RunResult, kelly_staker, threshold_selector
from valuebet.backtest.strategy_c import (
    C_LABEL,
    counterfactual_regime_config,
    run_regime,
)
from valuebet.live.bets import BetJournal, Coupon, coupons

INGESTED = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
B365 = {"1x2": ("bet365",)}


def _run(tmp_path: Path, world: list[WorldMatch], *, single_mode: str = "production") -> RunResult:
    return run_regime(
        build_replay(world),
        selector=threshold_selector(
            books=B365, tax_factor=1.0, edge_threshold=0.02, require_complete=True, excluded=Counter(),
            rejected=Counter(), margin_check=False,
        ),
        staker=kelly_staker,
        regime_config=counterfactual_regime_config(start=T0, share_basis="stakes", min_stake_pln=0.50),
        edge_threshold=0.02,
        single_mode=single_mode,
        journal_path=tmp_path / "bets.csv",
        run_id="c",
        start_capital=10_000.0,
        ingested_at=INGESTED,
        min_stake_pln=0.50,
    )


def _coupons(tmp_path: Path) -> list[Coupon]:
    rows = BetJournal(journal_path=tmp_path / "bets.csv").read()
    return list(coupons(rows, now=datetime.max.replace(tzinfo=UTC)))


def _value(match_id: str, e_home: float, *, home: int = 1, away: int = 0) -> WorldMatch:
    """Jeden wynik value (home, EV = e przy 1.00), reszta poniżej progu."""
    p = (0.5, 0.3, 0.2)
    return WorldMatch(match_id, p, ((1 + e_home) / 0.5, 0.9 / 0.3, 0.9 / 0.2), home, away)


def test_counterfactual_config_follows_promocje_and_the_t12_decision() -> None:
    cfg = counterfactual_regime_config(start=T0, share_basis="stakes", min_stake_pln=0.50)
    assert cfg.promo_active is True
    assert cfg.promo_valid_from == T0
    assert cfg.join_date == T0
    assert cfg.external_turnover_pln == 1000.0
    assert cfg.external_coupons == 0
    # T12 zamknięte 2026-10-09; wariant B (decyzja Pawła 2026-10-11).
    assert cfg.min_stake_pln == 0.50
    assert cfg.excluded_markets == frozenset()
    assert C_LABEL == (
        "kontrfaktyczny reżim Betclica (promocja od początku symulacji, limit 1000 zł "
        "wykorzystany), kursy zastępcze B365/BW"
    )


def test_two_value_legs_from_different_matches_become_one_double(tmp_path: Path) -> None:
    result = _run(tmp_path, [_value("m1", 0.05), _value("m2", 0.04)])
    (double,) = _coupons(tmp_path)
    assert double.coupon_type == "multi"
    assert {g.record.match_id for g in double.legs} == {"m1", "m2"}
    # AKO kwalifikowany → 1.00 (T9); Kelly ¼ na Π k przy p = Π p.
    assert double.tax_factor_applied == 1.0
    p, k = 0.25, 2.10 * 2.08
    expected = round(min(0.25 * (p * k - 1) / (k - 1), 0.02) * 10_000, 2)
    assert double.stake == pytest.approx(expected)
    # Oba wygrane: wypłata = stawka · Π k (T13 nieaktywne poniżej 2280 zł).
    assert result.cash == pytest.approx(10_000 - expected + round(expected * k, 2))
    assert result.label == C_LABEL


def test_single_in_production_mode_needs_k_min_at_regime_tax(tmp_path: Path) -> None:
    """Jedna noga (bez pary) → singiel. Próg 1000 zł wykorzystany, udział AKO 0%
    → podatek singla 0.94. EV 7% przy 1.00 → 1.07·0.94 = 1.006 < 1.02 → BRAK
    zakładu w produkcji; wariant dosłowny planu stawia (EV > 0 przy 0.94)."""
    world = [_value("m1", 0.07)]
    assert _run(tmp_path / "prod", world).n_coupons == 0
    literal = _run(tmp_path / "lit", world, single_mode="literal")
    (single,) = _coupons(tmp_path / "lit")
    assert literal.n_coupons == 1
    assert single.tax_factor_applied == 0.94


def test_single_with_enough_edge_is_placed_and_settled_at_the_same_tax(tmp_path: Path) -> None:
    result = _run(tmp_path, [_value("m1", 0.12)])
    (single,) = _coupons(tmp_path)
    assert single.tax_factor_applied == 0.94
    k = 1.12 / 0.5
    f = 0.25 * (0.5 * k * 0.94 - 1) / (k * 0.94 - 1)
    stake = round(min(f, 0.02) * 10_000, 2)
    assert single.stake == pytest.approx(stake)
    assert result.cash == pytest.approx(10_000 - stake + round(stake * k * 0.94, 2))


def test_fixed_094_sensitivity_mode(tmp_path: Path) -> None:
    _run(tmp_path, [_value("m1", 0.12)], single_mode="fixed_0.94")
    (single,) = _coupons(tmp_path)
    assert single.tax_factor_applied == 0.94


def test_legs_below_120_and_same_match_legs_are_not_paired(tmp_path: Path) -> None:
    low = WorldMatch("low", (0.88, 0.07, 0.05), (1.19, 1.01 / 0.07, 0.9 / 0.05), 1, 0)
    _run(tmp_path, [low, _value("m2", 0.12)])
    types = sorted(c.coupon_type for c in _coupons(tmp_path))
    assert "multi" not in types


def test_lost_leg_loses_the_double_and_exposure_counts_both_matches(tmp_path: Path) -> None:
    result = _run(tmp_path, [_value("m1", 0.05), _value("m2", 0.04, home=0, away=1)])
    (double,) = _coupons(tmp_path)
    assert result.cash == pytest.approx(10_000 - double.stake)
    (bet_id,) = {r.coupon_id for r in BetJournal(journal_path=tmp_path / "bets.csv").read()}
    capital, _open, match_exposure, _tax = result.stake_inputs[bet_id]
    assert capital == pytest.approx(10_000)
    assert match_exposure == 0.0


def test_pairing_is_by_ev_descending_then_match_id(tmp_path: Path) -> None:
    """Cztery nogi: EV 9%, 8%, 6%, 5% → pary (9,8) i (6,5)."""
    world = [_value("a", 0.05), _value("b", 0.09), _value("c", 0.06), _value("d", 0.08)]
    _run(tmp_path, world)
    pairs = sorted(sorted(g.record.match_id for g in c.legs) for c in _coupons(tmp_path))
    assert pairs == [["a", "c"], ["b", "d"]]


def test_mode_outside_domain_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="single_mode"):
        _run(tmp_path, [_value("m1", 0.05)], single_mode="cokolwiek")



def test_reconcile_matches_simulator_for_doubles(tmp_path: Path) -> None:
    """Podwójne księgowanie (§4 pkt 5) także dla kuponów wielonożnych C:
    wygrany, przegrany (przegrana noga kończy kupon), noga zwrócona (void)."""
    import importlib.util
    from datetime import timedelta

    world = []
    goals = [(1, 0), (1, 0), (0, 1), (1, 0), (None, None), (1, 0), (1, 0), (0, 2)]
    for i, (h, a) in enumerate(goals):
        at = T0 + timedelta(days=7 * (i // 2))
        m = _value(f"m{i}", 0.05 + 0.01 * (i % 2))
        world.append(
            WorldMatch(m.match_id, m.p_1x2, m.soft_1x2, h, a, observed_at=at,
                       kickoff=at + timedelta(hours=20 + i % 2))
        )  # fmt: skip
    result = _run(tmp_path, world)
    assert any(c.coupon_type == "multi" for c in _coupons(tmp_path))
    spec = importlib.util.spec_from_file_location(
        "reconcile_c", Path(__file__).resolve().parents[1] / "scripts" / "reconcile_bets.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ledger = module.reconcile(tmp_path / "bets.csv", start_capital=10_000.0)
    simulated = [(p.event, p.cash) for p in result.equity if p.event != "decision"]
    assert [c for c, _, _ in ledger] == [e for e, _ in simulated]
    for (_, _, cents), (_, sim) in zip(ledger, simulated, strict=True):
        assert cents == round(sim * 100)  # dokładnie, w groszach


def test_run_regime_refuses_two_different_minimum_stakes(tmp_path: Path) -> None:
    """Audyt wariantu B, DROBNE 6: min. stawka w konfiguracji reżimu i w pętli to ta
    sama liczba (wzorzec FSA4a-01 — jedno źródło); rozjazd → błąd."""
    with pytest.raises(ValueError, match="min_stake_pln"):
        run_regime(
            build_replay([_value("m1", 0.05)]),
            selector=threshold_selector(books=B365, tax_factor=1.0, edge_threshold=0.02, require_complete=True,
                                        excluded=Counter(), rejected=Counter(), margin_check=False),
            staker=kelly_staker,
            regime_config=counterfactual_regime_config(start=T0, share_basis="stakes", min_stake_pln=0.0001),
            edge_threshold=0.02, single_mode="production", journal_path=tmp_path / "b.csv", run_id="c",
            start_capital=10_000.0, ingested_at=INGESTED, min_stake_pln=0.50,
        )


def _flat(amount: float):
    from valuebet.pricing.kelly import StakeDecision

    def staker(_ctx: object) -> StakeDecision:
        return StakeDecision(fraction=0.0, stake=amount, mode="real", kelly_full=0.0, c=0.25, reasons=(),
                             gk_would_unlock=False, winnings_factor=1.0, ev=0.0)  # fmt: skip

    return staker


def test_ab9_c_group_dropped_for_stake_below_minimum_is_named(tmp_path: Path) -> None:
    """AB-9 (naprawa 4b-C, 2026-10-12): dublet C ze stawką 0,30 zł < 0,50 zł — reżim daje
    0.88 (T12) i grupa odpada; przyczyną ma być NAZWANA stawka poniżej minimum (wpis w
    ``RunResult.dropped_groups`` + licznik ``SKIP_BELOW_MIN_STAKE``), nie próg EV."""
    from valuebet.backtest.financial import DROP_BELOW_MIN_STAKE, SKIP_BELOW_MIN_STAKE

    result = run_regime(
        build_replay([_value("m1", 0.05), _value("m2", 0.04)]),
        selector=threshold_selector(books=B365, tax_factor=1.0, edge_threshold=0.02, require_complete=True,
                                    excluded=Counter(), rejected=Counter(), margin_check=False),
        staker=_flat(0.30),
        regime_config=counterfactual_regime_config(start=T0, share_basis="stakes", min_stake_pln=0.50),
        edge_threshold=0.02, single_mode="production", journal_path=tmp_path / "b.csv", run_id="c",
        start_capital=10_000.0, ingested_at=INGESTED, min_stake_pln=0.50,
    )
    assert result.n_coupons == 0
    (drop,) = result.dropped_groups
    assert drop.reason == DROP_BELOW_MIN_STAKE
    assert drop.stake == 0.30 and drop.capital == 10_000.0 and drop.mode == "real"
    assert [leg[0] for leg in drop.legs] == ["m1", "m2"]
    assert result.skipped[SKIP_BELOW_MIN_STAKE] == 1
    assert result.skipped["kupon poza progiem po podatku"] == 0
