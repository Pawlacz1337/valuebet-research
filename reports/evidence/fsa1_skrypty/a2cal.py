import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from load import complete
from devig import shin, mult, power
df = pd.read_pickle("fd2.pkl")
ok = complete(df, ["PSCH","PSCD","PSCA"]) & df.FTHG.notna() & df.FTAG.notna()
d = df[ok]
print("mecze z PSC i wynikiem:", len(d), " (w tym z valid observed:", int(d.valid_obs.sum()), ")")
O = d[["PSCH","PSCD","PSCA"]].to_numpy()
res = np.where(d.FTHG > d.FTAG, 0, np.where(d.FTHG == d.FTAG, 1, 2))
for name, f in [("shin", shin), ("mult", mult), ("power", power)]:
    P = np.array([f(o) if f(o) is not None else [np.nan]*3 for o in O])
    good = ~np.isnan(P).any(1)
    ll = -np.log(P[good, :][np.arange(good.sum()), res[good]]).mean()
    Y = np.zeros_like(P); Y[np.arange(len(res)), res] = 1
    pf = P[good].ravel(); yf = Y[good].ravel()
    out = [f"{name}: n={good.sum()} logloss={ll:.5f}"]
    for lo, hi in [(0, .10), (0, .05), (.10, .20), (.20, .35), (.35, .5), (.5, 1)]:
        m = (pf >= lo) & (pf < hi)
        se = np.sqrt(yf[m].mean()*(1-yf[m].mean())/m.sum())
        out.append(f"p∈[{lo},{hi}): n={m.sum()} pred={pf[m].mean():.4f} obs={yf[m].mean():.4f}±{se:.4f}")
    print("\n   ".join(out))
