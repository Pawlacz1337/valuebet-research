import warnings; warnings.filterwarnings("ignore")
import pandas as pd
from load import complete
df = pd.read_pickle("fd.pkl"); v = df[df.valid_obs].copy()
# replay: quote Pinnacle 1x2 albo O/U (P>2.5) wystarczy, by mecz miał notowanie Pinnacle
v["ps1"] = complete(v, ["PSH","PSD","PSA"]); v["psou"] = complete(v, ["P>2.5","P<2.5"])
v["anyps"] = v.ps1 | v.psou
g = v.groupby("observed").anyps.transform("any")
print("mecze bez zadnego notowania Pinnacle:", int((~v.anyps).sum()))
print("  w tym liczone przez silnik (cala chwila bez Pinnacle):", int((~g).sum()))
print("  niewidoczne w liczniku (inne mecze tej chwili maja Pinnacle):", int(((~v.anyps) & g).sum()))
print("bez PS 1x2:", int((~v.ps1).sum()))
