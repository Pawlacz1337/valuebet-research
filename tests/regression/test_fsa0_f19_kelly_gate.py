"""FSA #0 F-19 + F-06 — ułamek Kelly'ego nie przekracza ¼ na żadnej ścieżce.

Ścieżki niebezpieczne:
- ``KellyPolicy`` zbudowana wprost z ``clv_report_unlocks_gk=True`` dawała
  ``c = 0.5`` bez żadnego ``ClvReport`` (F-19, deklaracja z ``eac437c``
  nieprawdziwa);
- ``from_journal`` z raportem otwierającym G-K dawała ``c = 0.5``, a
  hamulec CLV/EV był martwy (F-06). Do Filaru 3 c = ½ jest zablokowane
  (CLAUDE.md reguła 21) — test oczekuje 0.25, nie 0.5;
- pominięte ``open_exposure`` w ``from_journal`` = 0, czyli limit 15%
  otwartej ekspozycji omijany po cichu.
"""

from __future__ import annotations

from typing import Any

import pytest

from helpers import assert_from_checkout, build
from valuebet.backtest.clv import ClvReport
from valuebet.pricing.kelly import KellyPolicy

assert_from_checkout(__file__)

SOLID = build(
    ClvReport,
    n_total=200,
    n_with_clv=200,
    n_missing=0,
    mean=0.02,
    ci_low=0.01,
    ci_high=0.03,
    n_clusters=12,
)
WEAK = build(
    ClvReport,
    n_total=10,
    n_with_clv=10,
    n_missing=0,
    mean=-0.01,
    ci_low=None,
    ci_high=None,
    n_clusters=3,
)


def test_direct_construction_is_refused() -> None:
    """Komplet argumentów, ale z pominięciem ``from_journal`` — nadal odmowa."""
    with pytest.raises(RuntimeError, match="from_journal"):
        build(
            KellyPolicy,
            bankroll=10_000.0,
            peak_bankroll=10_000.0,
            n_real_bets=150,
            clv_ci_low=0.0001,
            clv_report_unlocks_gk=True,
            clv_report=SOLID,
            open_exposure=0.0,
            match_exposure=0.0,
        )


def _policy(report: Any, n: int, open_exposure: float = 0.0) -> Any:
    return KellyPolicy.from_journal(
        bankroll=10_000.0,
        peak_bankroll=10_000.0,
        clv_report=report,
        n_real_bets=n,
        open_exposure=open_exposure,
        match_exposure=0.0,
    )


@pytest.mark.parametrize(("report", "n"), [(SOLID, 200), (SOLID, 10), (WEAK, 200)])
def test_fraction_is_quarter_on_every_path(report: Any, n: int) -> None:
    policy = _policy(report, n)
    assert policy.c <= 0.25
    decision = policy.stake(0.55, 2.10, tax_factor=0.88)
    assert decision.c <= 0.25
    # p = 0.55, k = 2.10, tax = 0.88: f* = 0.0193 < 2%, limit nie maskuje c.
    assert decision.stake == pytest.approx(0.25 * 0.019336 * 10_000.0, rel=1e-3)


def test_gate_is_reported_not_applied() -> None:
    decision = _policy(SOLID, 200).stake(0.55, 2.10, tax_factor=0.88)
    assert getattr(decision, "gk_would_unlock", None) is True
    weak = _policy(WEAK, 200).stake(0.55, 2.10, tax_factor=0.88)
    assert getattr(weak, "gk_would_unlock", None) is False


def test_open_exposure_cannot_be_omitted() -> None:
    with pytest.raises(TypeError):
        KellyPolicy.from_journal(
            bankroll=10_000.0,
            peak_bankroll=10_000.0,
            clv_report=WEAK,
            n_real_bets=0,
        )


def test_open_exposure_limit_binds() -> None:
    decision = _policy(WEAK, 0, open_exposure=0.149).stake(0.70, 2.0, tax_factor=1.0)
    assert decision.fraction == pytest.approx(0.001)


def test_report_must_be_a_real_clv_report() -> None:
    class Fake:
        unlocks_gk = True
        ci_low = 0.5
        mean = 0.5

    with pytest.raises(TypeError):
        _policy(Fake(), 500)
