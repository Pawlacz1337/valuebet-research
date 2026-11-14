import csv
from pathlib import Path
from collections import defaultdict
BASE = Path(r"<user>\Desktop\value-bet\reports\backtest_fin\4599dca\strategie")
def read(name):
    """-> lista kuponów: dict(coupon_id, mode, stake, tax, placed_at, legs=[(match_id,market,outcome,line,odds,p)], payout)"""
    rows = list(csv.DictReader(open(BASE/name/"bets.csv", encoding="utf-8")))
    cps = {}; pay = defaultdict(list)
    for r in rows:
        if r["bet_id"].endswith("#settle"):
            pay[r["coupon_id"]].append(r); continue
        c = cps.setdefault(r["coupon_id"], dict(coupon_id=r["coupon_id"], mode=r["mode"], stake=float(r["stake"]),
              tax=float(r["tax_factor_applied"]), placed_at=r["placed_at"], legs=[], book=set()))
        c["legs"].append((r["match_id"], r["market"], r["outcome"], r["line"], float(r["odds_taken"]), float(r["p_fair_at_bet"])))
        c["book"].add(r["bookmaker"])
    for cid, c in cps.items():
        st = pay.get(cid, [])
        c["settled"] = [s["settled"] for s in st]
        res = {s["bet_id"].split("#")[0]: s["settled"] for s in st}
        if len(res) < len(c["legs"]): c["payout"] = None; continue
        if any(v == "lost" for v in res.values()): c["payout"] = 0.0; continue
        odds = 1.0
        for i, l in enumerate(c["legs"]):
            bid = cid if len(c["legs"]) == 1 else f"{cid}.{i}"
            if res[bid] == "won": odds *= l[4]
        if all(v == "void" for v in res.values()): c["payout"] = c["stake"]; continue
        gross = c["stake"] * odds * c["tax"]
        c["payout"] = gross * (0.9 if gross > 2280 else 1.0)
    return list(cps.values())
