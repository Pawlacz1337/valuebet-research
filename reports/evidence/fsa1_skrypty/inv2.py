"""Limity 2%/3%/15%, wzór Kelly'ego ¼ i wyłącznik z dzienników (bez valuebet)."""
import csv, math, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from collections import defaultdict
B = "<user>/Desktop/value-bet/reports/backtest_fin/4599dca/strategie"
for name in ("A", "A3", "B-WH", "E", "C", "D", "C_θ0.01", "E_θ0.05"):
    rows = list(csv.DictReader(open(f"{B}/{name}/bets.csv", encoding="utf-8")))
    cps = {}; end = defaultdict(list)
    for r in rows:
        if "#" in r["bet_id"]: end[r["coupon_id"]].append(pd.Timestamp(r["settled_at"])); continue
        c = cps.setdefault(r["coupon_id"], dict(t=pd.Timestamp(r["placed_at"]), s=float(r["stake"]), mode=r["mode"], tax=float(r["tax_factor_applied"]), legs=[]))
        c["legs"].append((r["match_id"], float(r["odds_taken"]), float(r["p_fair_at_bet"])))
    eq = pd.read_csv(f"{B}/{name}/equity.csv"); eq["at"] = pd.to_datetime(eq["at"])
    cap = eq[eq.event == "decision"].set_index("at")["capital"]
    order = sorted(cps.items(), key=lambda kv: kv[0])
    v2 = v3 = v15 = kel = keln = 0; dd_first = None; peak = None
    openl = []  # (end, stake, matches)
    for cid, c in order:
        t = c["t"]; K = cap[t]; e = max(end[cid]) if end[cid] else pd.NaT
        openl = [o for o in openl if o[0] > t]
        if c["s"] > 0.02 * K + 0.005: v2 += 1
        for m in {l[0] for l in c["legs"]}:
            if sum(o[1] for o in openl if m in o[2]) + c["s"] > 0.03 * K + 0.01: v3 += 1
        if sum(o[1] for o in openl) + c["s"] > 0.15 * K + 0.01: v15 += 1
        k = math.prod(l[1] for l in c["legs"]); p = math.prod(l[2] for l in c["legs"]); tax = 1.0 if name.startswith("D") else c["tax"]
        f = (p * k * tax - 1) / (k * tax - 1); q = min(0.25 * f, 0.02)
        room = min(0.03 * K - max(sum(o[1] for o in openl if m in o[2]) for m in {l[0] for l in c["legs"]}), 0.15 * K - sum(o[1] for o in openl))
        if q * K < room - 0.05 and q * K * k * tax < 2280 and c["mode"] == "real":
            keln += 1
            if abs(round(q * K, 2) - c["s"]) > 0.011: kel += 1
        openl.append((e, c["s"], {l[0] for l in c["legs"]}))
    paper = [c for _, c in order if c["mode"] == "paper"]
    first = min((c["t"] for c in paper), default=None)
    ddmax = None
    if first is not None:
        e2 = eq[eq["at"] <= first]; pk = max(10000.0 if not name.endswith("1000zł") else 1000.0, e2.capital.max()); ddmax = 1 - e2.capital.iloc[-1] / pk
    print(f"{name}: kuponów {len(cps)}; >2%: {v2}; >3%/mecz: {v3}; >15%: {v15}; Kelly ¼ (bez wiążących limitów) sprawdzonych {keln}, niezgodnych {kel}; pierwszy PAPER {first} obsunięcie wtedy {None if ddmax is None else round(ddmax,4)}")
