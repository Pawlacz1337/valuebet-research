import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from load import complete
from devig import shin
import recon
df = pd.read_pickle("fd2.pkl")
ok = complete(df, ["PSCH","PSCD","PSCA"]) & df.FTHG.notna()
d = df[ok]
P = np.array([shin(o) if shin(o) is not None else [np.nan]*3 for o in d[["PSCH","PSCD","PSCA"]].to_numpy()])
res = np.where(d.FTHG > d.FTAG, 0, np.where(d.FTHG == d.FTAG, 1, 2)); Y = np.zeros_like(P); Y[np.arange(len(res)), res] = 1
g = ~np.isnan(P).any(1); pf, yf = P[g].ravel(), Y[g].ravel()
edges = np.quantile(pf, np.linspace(0, 1, 41)); b = np.clip(np.searchsorted(edges, pf, side="right") - 1, 0, 39)
xp = np.array([pf[b == i].mean() for i in range(40)]); fp = np.array([yf[b == i].mean() for i in range(40)])
class _I:
    def predict(self, x): return np.interp(x, xp, fp)
iso = _I()
print("kalibracja: najniższe biny", [(round(a,4), round(c,4)) for a, c in zip(xp[:4], fp[:4])])
for name in ("A", "C"):
    cps = recon.read(name); vals = {}
    for c in cps:
        prod = 1.0
        for (mid, mk, oc, ln, k, p) in c["legs"]:
            pc = recon.pclose(mid, mk, oc, "shin")
            if mk == "1x2": pc = float(iso.predict([pc])[0])   # korekta izotoniczna tylko 1X2 (totale bez zmian)
            prod *= k * pc
        w = min(recon.week(l[0]) for l in c["legs"]); vals.setdefault(w, []).append(prod * c["tax"] - 1)
    m, lo, hi = recon.boot_ratio({w: (sum(v), len(v)) for w, v in vals.items()})
    print(name, f"CLV vs zamknięcie Shin + izotoniczna (w próbie): {m:+.4f} [{lo:+.4f}, {hi:+.4f}]")
for name in ("A", "C"):
    cps = recon.read(name)
    for lab, lo in (("kurs>5", 5), ("kurs>10", 10)):
        vals = {}
        for c in cps:
            K = np.prod([l[4] for l in c["legs"]])
            if K <= lo: continue
            prod = 1.0
            for (mid, mk, oc, ln, k, p) in c["legs"]:
                pc = recon.pclose(mid, mk, oc, "shin")
                if mk == "1x2": pc = float(iso.predict([pc])[0])
                prod *= k * pc
            w = min(recon.week(l[0]) for l in c["legs"]); vals.setdefault(w, []).append(prod * c["tax"] - 1)
        m, l_, h = recon.boot_ratio({w: (sum(v), len(v)) for w, v in vals.items()})
        print(name, lab, f"n={sum(len(v) for v in vals.values())} CLV kalibrowane {m:+.4f} [{l_:+.4f}, {h:+.4f}]")
