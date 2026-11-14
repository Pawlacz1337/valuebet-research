import csv, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from collections import defaultdict
B = "<user>/Desktop/value-bet/reports/backtest_fin/4599dca/strategie"
for name in ("A", "A3", "C", "E", "B-WH"):
    rows = list(csv.DictReader(open(f"{B}/{name}/bets.csv", encoding="utf-8")))
    placed = {}; settled = defaultdict(list)
    for r in rows:
        if r["bet_id"].endswith("#settle"): settled[r["coupon_id"]].append(pd.Timestamp(r["settled_at"]))
        else: placed.setdefault(r["coupon_id"], (pd.Timestamp(r["placed_at"]), float(r["stake"]), r["mode"]))
    eq = pd.read_csv(f"{B}/{name}/equity.csv"); eq["at"] = pd.to_datetime(eq["at"])
    cap = eq[eq.event == "decision"].set_index("at")["capital"]  # kapitał PO decyzjach chwili (gotówka + otwarte)
    cps = pd.DataFrame([(cid, t, s, max(settled[cid]) if settled[cid] else pd.NaT) for cid, (t, s, m) in placed.items()], columns=["cid", "t", "s", "end"])
    res = []
    for t, g in cps.groupby("t"):
        prior = cps[(cps.t < t) & (cps.end > t)].s.sum()
        c = cap.get(t, np.nan)
        res.append((t, prior / c, g.s.sum() / c, len(g)))
    r = pd.DataFrame(res, columns=["t", "prior", "new", "n"])
    r["after"] = r.prior + r.new
    for mult in (1, 2):
        need = r.prior + mult * r.new
        cut = np.clip(need - 0.15, 0, None); frac_cut = (cut / (mult * r.new)).clip(0, 1)
        lost = (frac_cut * mult * r.new).sum() / (mult * r.new).sum()
        print(f"{name} x{mult} Kelly: chwil {len(r)}, ekspozycja po decyzji med={r.after.median():.3f} p90={r.after.quantile(.9):.3f} max={r.after.max():.3f}; "
              f"chwil ≥14.5%: {(need >= 0.145).mean():.3f}; obrót obcięty limitem 15%: {lost:.3%}")
