"""Niezależne przeliczenie liczb RAPORT 4599dca z dzienników + CLV własnym Shinem."""
import warnings, hashlib, json, sys; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from load import complete
from devig import shin, mult, power
from journal import read
df = pd.read_pickle("fd.pkl")
df["mid"] = [hashlib.sha1(f"{l}|{k.date().isoformat()}|{h}|{a}".encode()).hexdigest()[:16]
             for l,k,h,a in zip(df.league, df.kickoff, df.HomeTeam.astype(str), df.AwayTeam.astype(str))]
assert df.mid.is_unique
df.to_pickle("fd2.pkl")
idx = df.set_index("mid")
COLS = {"1x2": (["PSCH","PSCD","PSCA"], ["home","draw","away"]), "over_under": (["PC>2.5","PC<2.5"], ["over","under"])}
cache = {}
def pclose(mid, market, outcome, method):
    key = (mid, market, method)
    if key not in cache:
        cols, outs = COLS[market]; row = idx.loc[mid]
        odds = [row[c] for c in cols]
        if any(pd.isna(o) or o <= 1.0 for o in odds): cache[key] = None
        else:
            p = {"shin": shin, "mult": mult, "power": power}[method](odds)
            cache[key] = None if p is None else dict(zip(outs, p))
    d = cache[key]; return None if d is None else d[outcome]
def week(mid):
    k = idx.loc[mid, "kickoff"]; iso = k.isocalendar(); return f"{iso[0]}-W{iso[1]:02d}"
def boot_ratio(groups, n=4000, seed=0):
    keys = sorted(groups); num = np.array([groups[k][0] for k in keys]); den = np.array([groups[k][1] for k in keys])
    pick = np.random.default_rng(seed).integers(0, len(keys), size=(n, len(keys)))
    d = num[pick].sum(1)/den[pick].sum(1); return num.sum()/den.sum(), *np.quantile(d, [0.025, 0.975])
def analyse(name, methods=("shin",), filt=None):
    cps = read(name); out = {}
    real = [c for c in cps if c["mode"] == "real" and c["payout"] is not None]
    turn = sum(c["stake"] for c in real); prof = sum(c["payout"] - c["stake"] for c in real)
    g = {}
    for c in real:
        w = min(week(l[0]) for l in c["legs"]); a, b = g.get(w, (0, 0)); g[w] = (a + c["payout"] - c["stake"], b + c["stake"])
    y = boot_ratio(g)
    out["n"] = len(cps); out["real"] = len(real); out["turnover"] = round(turn, 2); out["profit"] = round(prof, 2)
    out["yield"] = [round(v, 4) for v in y]
    for m in methods:
        vals = {}; miss = 0
        for c in cps:
            if filt and not filt(c): continue
            prod = 1.0; ok = True
            for (mid, mk, oc, ln, k, p) in c["legs"]:
                pc = pclose(mid, mk, oc, m)
                if pc is None: ok = False; break
                prod *= k * pc
            if not ok: miss += 1; continue
            w = min(week(l[0]) for l in c["legs"]); vals.setdefault(w, []).append(prod * c["tax"] - 1)
        gg = {w: (sum(v), len(v)) for w, v in vals.items()}
        n = sum(len(v) for v in vals.values())
        if n:
            mean, lo, hi = boot_ratio(gg)
            out[f"clv_{m}"] = dict(n=n, mean=round(mean, 4), lo=round(lo, 4), hi=round(hi, 4), miss=miss, kl=len(gg))
    return out
if __name__ == "__main__":
    for name in sys.argv[1:]:
        print(name, json.dumps(analyse(name, methods=("shin", "mult", "power"))))
