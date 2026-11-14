import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, recon
df = pd.read_pickle("fd2.pkl").set_index("mid")
for name in ("A", "C", "A3"):
    cps = recon.read(name); real = [c for c in cps if c["payout"] is not None]
    st = sum(c["stake"] for c in real)
    exp = sum(c["stake"] * (np.prod([l[5] for l in c["legs"]]) * np.prod([l[4] for l in c["legs"]]) * c["tax"] - 1) for c in real) / st
    prof = sorted((c["payout"] - c["stake"] for c in real), reverse=True); P = sum(prof)
    top10 = sum(prof[:10]); rest = [c for c in real]
    y_wo = (P - top10) / (st - sum(c["stake"] for c in sorted(real, key=lambda c: c["payout"] - c["stake"], reverse=True)[:10]))
    print(f"{name}: yield oczekiwany przy decyzji {exp:+.4f}; top10 = {top10/P:.0%} zysku; yield bez top10 {y_wo:+.4f}")
    if name == "A":
        by = {}
        for c in cps:
            s = df.loc[c["legs"][0][0], "season"]; by.setdefault(s, []).append(c)
        for s in sorted(by):
            o = recon.analyse(name, methods=("shin",), filt=lambda c, s=s: df.loc[c["legs"][0][0], "season"] == s)
            print(f"   sezon {s}: zakładów {len(by[s])}, CLV {o['clv_shin']['mean']:+.4f} [{o['clv_shin']['lo']:+.4f}, {o['clv_shin']['hi']:+.4f}]")
