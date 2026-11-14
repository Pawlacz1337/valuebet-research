"""Niezależna kontrola podatku singli C: udział AKO po stawkach w oknie (T7) w chwili zakładu."""
import csv, warnings; warnings.filterwarnings("ignore")
import pandas as pd
B = "<user>/Desktop/value-bet/reports/backtest_fin/4599dca/strategie"
for name in ("C", "C_θ0.01", "C_θ0.05", "C_1000zł"):
    cps = {}
    for r in csv.DictReader(open(f"{B}/{name}/bets.csv", encoding="utf-8")):
        if "#" in r["bet_id"]: continue
        cps.setdefault(r["coupon_id"], (pd.Timestamp(r["placed_at"]), float(r["stake"]), int(r["n_legs"]), float(r["tax_factor_applied"]), r["mode"]))
    items = sorted(cps.items())  # kolejność id = kolejność zawierania
    start = items[0][1][0]
    bad = 0; n = 0; lo = []
    for i, (cid, (t, s, nl, tax, mode)) in enumerate(items):
        if nl != 1: continue
        n += 1
        prev = [v for _, v in items[:i] if v[4] == "real"]
        cut = t - pd.DateOffset(months=12)
        win = [v for v in prev if v[0] >= (cut if cut >= start else start)][-5000:]
        multi = sum(v[1] for v in win if v[2] > 1); tot = sum(v[1] for v in win) + 1000.0 + s  # mianownik: zewn. 1000 zł + kandydat (po stawkach)
        share = multi / tot if tot else 0
        exp = 1.0 if share >= 0.5 else 0.94
        lo.append(share)
        if abs(exp - tax) > 1e-9: bad += 1
    print(f"{name}: singli {n}, niezgodnych z niezależnym udziałem (≥50% → 1.00, inaczej 0.94): {bad}; min udziału {min(lo):.3f}")
