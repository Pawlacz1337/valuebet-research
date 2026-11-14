import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from load import complete
from devig import shin, power
df = pd.read_pickle("fd2.pkl"); v = df[df.valid_obs & complete(df, ["PSH","PSD","PSA"])].copy()
BOOKS = {"bet365": ["B365H","B365D","B365A"], "betandwin": ["BWH","BWD","BWA"], "williamhill": ["WHH","WHD","WHA"]}
pc = complete(v, ["PSCH","PSCD","PSCA"])
def run(books, mode, theta=0.02):
    out = []
    for i, r in v.iterrows():
        avail = {b: [r[c] for c in cols] for b, cols in BOOKS.items() if b in books and all(pd.notna(r[c]) and r[c] > 1 for c in cols)}
        if mode == "strict" and len(avail) < len(books): continue
        avail = {b: o for b, o in avail.items() if sum(1/x for x in o) >= 1.0}
        if not avail: continue
        p = shin([r.PSH, r.PSD, r.PSA])
        if p is None: continue
        close = shin([r.PSCH, r.PSCD, r.PSCA]) if pc[i] else None
        for j in range(3):
            best = max(o[j] for o in avail.values())
            if p[j]*best - 1 > 0.5: continue
            if best >= (1+theta)/p[j]:
                out.append((r.mid, j, best, p[j], None if close is None else best*close[j]-1, len(avail)))
    return pd.DataFrame(out, columns=["mid","j","k","p","clv","nbooks"])
for books in (("bet365","betandwin"), ("bet365","betandwin","williamhill")):
    s = run(books, "strict"); l = run(books, "relaxed")
    add = l[~l.set_index(["mid","j"]).index.isin(s.set_index(["mid","j"]).index)]
    print(books, f"strict n={len(s)} sumaCLV={s.clv.sum():.1f} śr={s.clv.mean():+.4f} | relaxed n={len(l)} sumaCLV={l.clv.sum():.1f} śr={l.clv.mean():+.4f} | dodane n={len(add)} śrCLV={add.clv.mean():+.4f} (bez zamkn. {add.clv.isna().sum()})")
    ss = s.set_index(["mid","j"]); ll = l.set_index(["mid","j"]); common = ss.index.intersection(ll.index)
    print("   wspólne z innym kursem (relaxed lepszy?):", int((ll.loc[common].k != ss.loc[common].k).sum()))
