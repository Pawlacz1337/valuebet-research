import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, recon
df = pd.read_pickle("fd2.pkl").set_index("mid")
for name in ("A", "C"):
    print("==", name)
    for lo, hi in [(0, 6), (6, 24), (24, 48), (48, 99)]:
        def f(c, lo=lo, hi=hi):
            l = min((df.loc[x[0], "kickoff"] - df.loc[x[0], "observed"]).total_seconds()/3600 for x in c["legs"])
            return lo <= l < hi
        o = recon.analyse(name, methods=("shin",), filt=f)
        c = o["clv_shin"]; print(f"  wyprzedzenie [{lo},{hi}) h: n={c['n']} CLV={c['mean']:+.4f} [{c['lo']:+.4f}, {c['hi']:+.4f}]")
