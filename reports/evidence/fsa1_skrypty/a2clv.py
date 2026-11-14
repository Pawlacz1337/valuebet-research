import warnings, sys; warnings.filterwarnings("ignore")
import numpy as np
import recon
from recon import analyse, pclose, idx
def res_of(mid, mk, oc, ln):
    r = idx.loc[mid]; h, a = r.FTHG, r.FTAG
    if mk == "1x2": act = "home" if h > a else "away" if a > h else "draw"
    else:
        t = h + a; act = "over" if t > 2.5 else "under"
    return oc == act
for name in sys.argv[1:]:
    cps = recon.read(name)
    print("==", name)
    for label, f in [("wszystkie", lambda c: True), ("1x2", lambda c: all(l[1]=="1x2" for l in c["legs"])),
                     ("kurs<=2.5", lambda c: np.prod([l[4] for l in c["legs"]]) <= 2.5),
                     ("2.5<kurs<=5", lambda c: 2.5 < np.prod([l[4] for l in c["legs"]]) <= 5),
                     ("kurs>5", lambda c: np.prod([l[4] for l in c["legs"]]) > 5),
                     ("kurs>10", lambda c: np.prod([l[4] for l in c["legs"]]) > 10)]:
        o = analyse(name, methods=("shin","mult","power"), filt=f)
        sub = [c for c in cps if f(c) and len(c["legs"]) == 1]
        line = f"  {label:12s} n={o['clv_shin']['n']:5d} " + " ".join(
            f"{m}={o['clv_'+m]['mean']:+.4f}[{o['clv_'+m]['lo']:+.4f},{o['clv_'+m]['hi']:+.4f}]" for m in ("shin","mult","power"))
        if sub:  # single: przewidywane trafienia z p_close Shina vs obserwowane
            ps = np.array([pclose(c["legs"][0][0], c["legs"][0][1], c["legs"][0][2], "shin") for c in sub])
            pp = np.array([pclose(c["legs"][0][0], c["legs"][0][1], c["legs"][0][2], "power") for c in sub])
            pd_ = np.array([c["legs"][0][5] for c in sub])
            won = np.array([res_of(*c["legs"][0][:4]) for c in sub])
            line += f" | single: trafien obs={won.sum()} E[shin_close]={ps.sum():.1f} E[power_close]={pp.sum():.1f} E[p_decyzji]={pd_.sum():.1f}"
        print(line)
