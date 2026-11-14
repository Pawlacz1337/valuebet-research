"""Niezależne podwójne księgowanie dziennika (BACKTEST_FIN_PLAN §2, §4 pkt 5).

Celowo **bez** importu ``valuebet``: kapitał liczony wprost z kolumn CSV
(``stake``, ``odds_taken``, ``tax_factor_applied``, wynik nogi). Zgodność z
symulatorem po każdym rozliczeniu jest dowodem, że ``backtest/financial.py``
prowadzi kasę zgodnie z kontraktem, a nie zgodnie z samym sobą.

Kontrakt wypłaty (``docs/promocje.md`` T13): wygrany kupon — ``stake · Π k ·
tax`` (nogi zwrócone pomijane), x0.90 przy brutto > 2280 zł; wszystkie nogi
zwrócone — ``stake · tax``; przegrana noga — 0. Kwoty do grosza. Kupon paper
nie rusza kasy, ale ma wiersz w księdze (kolejność jak w symulatorze).

Księga liczy w **całkowitych groszach** (bramka e66260a: 1.06e-9 zł różnicy z
samej kolejności sumowania float). Każda kwota (stawka, wypłata) jest
wielokrotnością grosza — inaczej ``ValueError``.

Użycie::

    uv run python scripts/reconcile_bets.py <bets.csv> --start-capital 10000
"""

from __future__ import annotations

import argparse
import bisect
import csv
import itertools
import math
import sys
from datetime import datetime
from pathlib import Path

WINNINGS_THRESHOLD = 2280.0
WINNINGS_FACTOR = 0.90
#: Tolerancja „to jest pełny grosz” dla kwoty z CSV (x·100 vs zaokrąglenie).
GROSZ_TOLERANCE = 1e-6


def to_grosze(amount: float, *, what: str) -> int:
    """Kwota w złotych → całkowite grosze; niewielokrotność grosza to błąd."""
    scaled = amount * 100
    cents = round(scaled)
    if abs(scaled - cents) >= GROSZ_TOLERANCE:
        raise ValueError(f"{what} {amount!r} nie jest wielokrotnością grosza")
    return int(cents)


def _payout(stake: float, tax: float, legs: list[tuple[float, str]]) -> float:
    results = [r for _, r in legs]
    if "lost" in results:
        return 0.0
    if all(r == "void" for r in results):
        return round(stake * tax, 2)
    gross = stake * math.prod(k for k, r in legs if r != "void") * tax
    factor = WINNINGS_FACTOR if gross > WINNINGS_THRESHOLD else 1.0
    return round(gross * factor, 2)


def reconcile(journal: Path, *, start_capital: float) -> list[tuple[str, datetime, int]]:
    """``(coupon_id, chwila, gotówka w groszach)`` po każdym rozliczeniu kuponu."""
    with journal.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    bets = {r["bet_id"]: r for r in rows if not r["settled"]}
    settles = sorted(
        (r for r in rows if r["settled"]),
        key=lambda r: (datetime.fromisoformat(r["settled_at"]), r["bet_id"]),
    )
    coupons: dict[str, list[dict[str, str]]] = {}
    for bet in bets.values():
        coupons.setdefault(bet["coupon_id"], []).append(bet)
    # Kasa w chwili rozliczenia: start - stawki prawdziwe postawione do tej chwili + wypłaty.
    placements = sorted(
        (datetime.fromisoformat(legs[0]["placed_at"]), to_grosze(float(legs[0]["stake"]), what="stawka"))
        for legs in coupons.values()
        if legs[0]["mode"] == "real"
    )
    times = [placed for placed, _ in placements]
    cumulative = [0, *itertools.accumulate(stake for _, stake in placements)]
    results: dict[str, str] = {}
    done: set[str] = set()
    start = to_grosze(start_capital, what="kapitał startowy")
    paid = 0
    out: list[tuple[str, datetime, int]] = []
    for row in settles:
        original = row["bet_id"].removesuffix("#settle")
        results[original] = row["settled"]
        coupon_id = bets[original]["coupon_id"]
        if coupon_id in done:
            continue
        legs = coupons[coupon_id]
        states = [results.get(leg["bet_id"]) for leg in legs]
        if "lost" not in states and None in states:
            continue  # kupon jeszcze otwarty
        done.add(coupon_id)
        at = datetime.fromisoformat(row["settled_at"])
        first = legs[0]
        if first["mode"] == "real":
            odds = [(float(leg["odds_taken"]), results.get(leg["bet_id"], "open")) for leg in legs]
            paid += to_grosze(
                _payout(float(first["stake"]), float(first["tax_factor_applied"]), odds), what="wypłata"
            )
        # Ściśle przed: przy równej chwili symulator rozlicza przed decyzją.
        staked = cumulative[bisect.bisect_left(times, at)]
        out.append((coupon_id, at, start - staked + paid))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Podwójne księgowanie dziennika")
    parser.add_argument("journal", type=Path)
    parser.add_argument("--start-capital", type=float, required=True)
    args = parser.parse_args(argv)
    ledger = reconcile(args.journal, start_capital=args.start_capital)
    final = ledger[-1][2] / 100 if ledger else args.start_capital
    print(f"kuponów rozliczonych: {len(ledger)}; gotówka końcowa: {final:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
