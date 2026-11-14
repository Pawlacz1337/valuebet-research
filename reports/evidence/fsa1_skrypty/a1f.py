import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from load import complete
from devig import shin
import recon
df = pd.read_pickle("fd2.pkl"); v = df[df.valid_obs].copy()
for b, cols in {"PS": ["PSH","PSD","PSA"], "B365": ["B365H","B365D","B365A"], "BW": ["BWH","BWD","BWA"], "WH": ["WHH","WHD","WHA"]}.items():
    m = complete(v, cols); bs = sum(1/v.loc[m, c] for c in cols)
    print(f"marża 1X2 {b}: średnia {bs.mean()-1:.4f} mediana {bs.median()-1:.4f} (n={m.sum()})")
for s in ("1920","2122","2324","2526"):
    m = complete(v, ["B365CH","B365CD","B365CA"]) & (v.season == s); print("B365C dostępne", s, int(m.sum()), "/", int((v.season==s).sum()))
# dryf kursu miękkiego dla zakładów A: kurs zamknięcia tego samego bukmachera / kurs wzięty
idx = df.set_index("mid"); C = {"bet365": ("B365CH","B365CD","B365CA"), "betandwin": ("BWCH","BWCD","BWCA")}
import csv
rows = [r for r in csv.DictReader(open("<user>/Desktop/value-bet/reports/backtest_fin/4599dca/strategie/A/bets.csv", encoding="utf-8")) if "#" not in r["bet_id"] and r["market"] == "1x2"]
ratios = []
for r in rows:
    j = ("home","draw","away").index(r["outcome"]); col = C[r["bookmaker"]][j]; kc = idx.loc[r["match_id"], col]
    if pd.notna(kc) and kc > 1: ratios.append(kc / float(r["odds_taken"]))
ratios = np.array(ratios)
print(f"A 1X2: kurs zamknięcia tego samego bukmachera / kurs wzięty: n={len(ratios)} średnia={ratios.mean():.4f} mediana={np.median(ratios):.4f} udział <1: {(ratios<1).mean():.3f}")
# haircut: kurs miękki × (booksum B365 / 1.0734) — marża Betclica 7.34% z 11 odczytów (FIX_LOG_F1)
for target in (1.0734, 1.06):
    out = []
    for i, r in v[complete(v, ["PSH","PSD","PSA","B365H","B365D","B365A","BWH","BWD","BWA"])].iterrows():
        p = shin([r.PSH, r.PSD, r.PSA]);
        if p is None: continue
        best = []
        for cols in (["B365H","B365D","B365A"], ["BWH","BWD","BWA"]):
            o = np.array([r[c] for c in cols]); bs = (1/o).sum()
            if bs < 1: continue
            best.append(o * bs / target)  # ten sam profil, marża docelowa
        if not best: continue
        k = np.max(best, axis=0)
        close = shin([r.PSCH, r.PSCD, r.PSCA]) if all(pd.notna([r.PSCH, r.PSCD, r.PSCA])) else None
        for j in range(3):
            if k[j] >= 1.02 / p[j] and p[j]*k[j]-1 <= 0.5 and close is not None: out.append(k[j]*close[j]-1)
    out = np.array(out); print(f"A 1X2 przy marży {target-1:.2%} (profil B365/BW przeskalowany): zakładów {len(out)}, śr. CLV {out.mean():+.4f}, suma {out.sum():.1f}")
