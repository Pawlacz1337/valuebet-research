"""Audyt ścieżki 4b-C: remis zaokrąglenia na pół grosza (naprawa 4b-C #2, 2026-10-15).

Bramka 27ae469: kupon c0-004274 — wiąże limit 15% otwartej ekspozycji, stawka =
0,15·15 467,10 - 2 314,24 = dokładnie 5,825 zł. Silnik (``cash + open_real``)
miał 5,82500000000592 → 5,83, checker (kapitał z księgi) 5,824999999999034 → 5,82;
kapitały różnią się o 4,5e-11 (kolejność sumowania floatów). Diagnoza: klasa A
(``docs/discovery/out_B/diag_4bC_2.md`` w drzewie value-bet).

Reguła po naprawie: przy remisie (surowa stawka z księgi < 1e-6 zł od x.xx5) stawka
silnika może być KTÓRYMKOLWIEK z dwóch sąsiednich groszy; poza remisem — równość jak
dotąd. Nowy twardy warunek: |kapitał z księgi - kapitał silnika| < 1e-6 dla każdego
kuponu (dotąd niesprawdzany wprost).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from test_engine_gate import _script

T0 = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
T1 = datetime(2025, 1, 1, 14, 0, tzinfo=UTC)
T2 = datetime(2025, 1, 2, 12, 0, tzinfo=UTC)
T3 = datetime(2025, 1, 2, 14, 0, tzinfo=UTC)


def _record(script: Any, cid: str, match: str, *, at: datetime, odds: float, p: float, stake: float) -> Any:
    from valuebet.live.bets import BetRecord

    return BetRecord(bet_id=cid, placed_at=at, mode="real", bookmaker="betclic", coupon_id=cid,
                     coupon_type="single", n_legs=1, leg_index=0, match_id=match, market="1x2",
                     outcome="home", line=None, odds_taken=odds, stake=stake, tax_factor_applied=1.0,
                     p_fair_at_bet=p, snapshot_observed_at=at - timedelta(minutes=5), price_available=True,
                     ingested_at=script.INGESTED, source="backtest:tie")  # fmt: skip


def _tie_world(tmp_path: Path, *, last: str = "other", cap_shift: float = 4.5e-11,
               first_b: float | None = None) -> tuple[Any, list[Any], Any, float]:
    """Mała księga z dokładnym remisem przy wiążącym limicie 15%.

    A (t0, 2% z 10 000 = 200 zł, kurs 1.0005) wygrywa w t1 → kapitał 10 000,10 zł.
    B1..B7 (t2) po 2% = 200,00 zł; B8 (t2): pokój 15% = 0,15·10 000,10 - 1400 =
    **100,015 zł** — remis. ``last``: ``other`` = stawka B8 to sąsiedni grosz INNY niż
    ``round`` checkera (jak c0-004274), ``same`` = ten sam, ``plus2`` = +2 grosze.
    ``cap_shift`` — kapitał silnika = kapitał z księgi + przesunięcie (dryf floatów)."""
    from valuebet.live.bets import BetJournal

    script = _script()
    journal = BetJournal(journal_path=tmp_path / "tie.csv")
    journal.add_coupon([_record(script, "t-000001", "m0", at=T0, odds=1.0005, p=0.9999, stake=200.0)])
    journal.settle("t-000001", "won", now=T1)
    for k in range(1, 8):
        stake = first_b if (k == 1 and first_b is not None) else 200.0
        journal.add_coupon([_record(script, f"t-{k + 1:06d}", f"m{k}", at=T2, odds=2.0, p=0.9, stake=stake)])
    # stawka B8 — dopiero po odczycie kapitału z księgi (ten sam algorytm co checker)
    probe = list(journal.read())
    cap = script.LedgerPath(script.ledger_coupons([*probe, *_settled_tail(script, probe)]), start=script.START
                            ).state(T2)[0]  # fmt: skip
    open_stake = sum(r.stake for r in probe if r.placed_at == T2)
    raw = (0.15 - open_stake / cap) * cap
    assert abs(raw * 100 - math.floor(raw * 100) - 0.5) < 1e-4, f"świat testu bez remisu: {raw!r}"
    checker = round(raw, 2)
    lo, hi = math.floor(raw * 100) / 100, math.floor(raw * 100 + 1) / 100
    stake8 = {"other": hi if checker == lo else lo, "same": checker, "plus2": round(checker + 0.02, 2)}[last]
    journal.add_coupon([_record(script, "t-000009", "m8", at=T2, odds=2.0, p=0.9, stake=stake8)])
    for k in range(2, 10):
        journal.settle(f"t-{k:06d}", "lost", now=T3)
    rows = journal.read()
    engine_cap = cap + cap_shift
    stake_inputs = {"t-000001": (10_000.0, 0.0, 0.0, 1.0)}
    for k in range(2, 10):
        before = sum(r.stake for r in rows if not r.is_settlement and r.placed_at == T2 and r.coupon_id < f"t-{k:06d}")
        stake_inputs[f"t-{k:06d}"] = (engine_cap, before / engine_cap, 0.0, 1.0)
    result = SimpleNamespace(stake_inputs=stake_inputs, candidates=[], dropped_groups=[])
    return script, rows, result, raw


def _settled_tail(script: Any, rows: list[Any]) -> list[Any]:
    """Wiersze rozliczeń dla kuponów jeszcze nierozliczonych (``ledger_coupons`` ich wymaga)."""
    from dataclasses import replace

    done = {r.bet_id.removesuffix("#settle") for r in rows if r.is_settlement}
    return [replace(r, bet_id=f"{r.bet_id}#settle", settled="lost", settled_at=T3) for r in rows
            if not r.is_settlement and r.bet_id not in done]  # fmt: skip


def _errors(tmp_path: Path, **kw: Any) -> tuple[list[str], Any]:
    script, rows, result, _raw = _tie_world(tmp_path, **kw)
    out = script.path_audit(rows, result, start=T0)
    return list(out[0]), out


# -- regresja c0-004274 -----------------------------------------------------------


def test_c0_004274_numbers_are_a_half_grosz_tie() -> None:
    """Liczby z bramki 27ae469: obie stawki są poprawnymi zaokrągleniami remisu 5,825."""
    script = _script()
    engine_cap, ledger_cap, open_stake = 15467.100000000042, 15467.099999999997, 2314.24
    assert abs(0.15 * 15467.10 - open_stake - 5.825) < 1e-9
    kw = {"p": 0.07083794308443746, "odds": 14.831387731680216, "tax": 1.0, "match_exposure": 0.0}
    engine = script.kelly_expected_stake(capital=engine_cap, open_exposure=open_stake / engine_cap, **kw)
    ledger = script.kelly_expected_stake(capital=ledger_cap, open_exposure=open_stake / ledger_cap, **kw)
    assert (engine, ledger) == (5.83, 5.82)
    raw = script.kelly_expected_raw(capital=ledger_cap, open_exposure=open_stake / ledger_cap, **kw)
    verdict = script.stake_verdict(engine_stake=5.83, raw=raw, engine_capital=engine_cap, ledger_capital=ledger_cap)
    assert verdict.error is None and verdict.tie and verdict.by_tie


def test_path_audit_accepts_the_other_grosz_at_a_tie(tmp_path: Path) -> None:
    """Regresja: księga z remisem przy wiążącym 15% — stawka silnika = sąsiedni grosz
    inny niż ``round`` checkera. Na 27ae469: „stawka … vs wzór z księgi …” (CZERWONY)."""
    errors, out = _errors(tmp_path, last="other")
    assert errors == []
    stats = out[2]
    assert (stats.checked, stats.ties, stats.tie_accepted, stats.rejected) == (9, 1, 1, 0)
    assert 0.0 < stats.max_dcap < 1e-6


# -- graniczne ---------------------------------------------------------------------


@pytest.mark.parametrize("raw", [5.825 - 1e-11, 5.825, 5.825 + 1e-11])
@pytest.mark.parametrize("stake", [5.82, 5.83])
def test_tie_accepts_both_neighbours(raw: float, stake: float) -> None:
    verdict = _script().stake_verdict(engine_stake=stake, raw=raw, engine_capital=1000.0, ledger_capital=1000.0)
    assert verdict.error is None and verdict.tie


@pytest.mark.parametrize(("raw", "stake"), [(5.8251, 5.82), (5.8249, 5.83), (5.8251, 5.84)])
def test_outside_the_tie_exact_equality_holds(raw: float, stake: float) -> None:
    """5,8251 nie jest remisem: tylko ``round`` = 5,83; grosz obok — ODRZUCONE."""
    verdict = _script().stake_verdict(engine_stake=stake, raw=raw, engine_capital=1000.0, ledger_capital=1000.0)
    assert verdict.error is not None and not verdict.tie


def test_two_grosze_off_at_a_tie_are_rejected(tmp_path: Path) -> None:
    errors, out = _errors(tmp_path, last="plus2")
    assert len(errors) == 1 and "t-000009: stawka" in errors[0], errors
    assert out[2].rejected == 1


# -- ścieżka niebezpieczna: kapitał silnika ≠ księga ------------------------------


def test_capital_mismatch_is_rejected_even_with_a_matching_stake(tmp_path: Path) -> None:
    """Twardy warunek |kapitał z księgi - kapitał silnika| < 1e-6: 1e-3 → ODRZUCONE,
    choć stawka równa ``round`` checkera (na 27ae469 nikt tego nie sprawdzał — zielone)."""
    errors, out = _errors(tmp_path, last="same", cap_shift=1e-3)
    assert errors and all("kapitał" in e for e in errors), errors
    assert out[2].rejected == 8
    assert out[2].max_dcap == pytest.approx(1e-3)


def test_capital_check_is_also_a_pure_verdict() -> None:
    verdict = _script().stake_verdict(engine_stake=5.83, raw=5.825, engine_capital=1000.001, ledger_capital=1000.0)
    assert verdict.error is not None and "kapitał" in verdict.error


# -- mutacja: +1 grosz poza remisem -------------------------------------------------


def test_one_grosz_off_outside_a_tie_is_rejected(tmp_path: Path) -> None:
    errors, _out = _errors(tmp_path, last="same", first_b=200.01)
    assert len(errors) == 1 and errors[0].startswith("t-000002: stawka 200.01"), errors


# -- spójność surowej stawki z dotychczasowym wzorem --------------------------------


def test_raw_stake_rounds_to_the_existing_formula() -> None:
    """``kelly_expected_raw`` zaokrąglone = ``kelly_expected_stake`` (niezmieniony,
    wspólny z 6-C i ``kelly_mismatches``) — na siatce z T13 i każdym limitem."""
    script = _script()
    for p in (0.06, 0.3, 0.55, 0.9):
        for odds in (1.3, 2.1, 3.9, 14.8, 40.0):
            for tax in (1.0, 0.94, 0.88):
                for cap in (37.0, 10_000.0, 15_467.1, 400_000.0):
                    for oe, me in ((0.0, 0.0), (0.149, 0.0), (0.05, 0.029)):
                        kw = {"tax": tax, "capital": cap, "open_exposure": oe, "match_exposure": me}
                        assert round(script.kelly_expected_raw(p, odds, **kw), 2) == \
                            script.kelly_expected_stake(p, odds, **kw), (p, odds, kw)
