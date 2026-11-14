import warnings; warnings.filterwarnings("ignore")
import pandas as pd
from load import complete
df = pd.read_pickle("fd.pkl")
v = df[df.valid_obs].copy()
v["ps"] = complete(v, ["PSH","PSD","PSA"]); v["psc"] = complete(v, ["PSCH","PSCD","PSCA"])
v["b365"] = complete(v, ["B365H","B365D","B365A"]); v["bw"] = complete(v, ["BWH","BWD","BWA"]); v["wh"] = complete(v, ["WHH","WHD","WHA"])
print("per sezon (mecze z valid observed):")
print(v.groupby("season")[["ps","psc","b365","bw","wh"]].mean().round(3).assign(n=v.groupby("season").size()))
s = v[v.season=="2526"].copy(); s["m"] = s.kickoff.dt.strftime("%Y-%m")
print(s.groupby("m")[["ps","psc","bw","wh"]].mean().round(3).assign(n=s.groupby("m").size()))
a = df.copy(); a["ps"] = complete(a, ["PSH","PSD","PSA"]); a["psc"]=complete(a,["PSCH","PSCD","PSCA"])
print("2526 wszystkie wiersze: ps", round(a[a.season=="2526"].ps.mean(),3), "psc", round(a[a.season=="2526"].psc.mean(),3), "n", (a.season=="2526").sum())
b = v[v.season=="2425"]; print("2425 bw brak:", round(1-b.bw.mean(),3), "per liga min/max", b.groupby("league").bw.mean().round(2).to_dict())
