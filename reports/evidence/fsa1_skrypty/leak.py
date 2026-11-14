"""Czy kurs 'przedmeczowy' jest naprawdę przed zamknięciem? LL(PS) vs LL(PSC) per wyprzedzenie."""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from load import complete
from devig import shin
df = pd.read_pickle("fd2.pkl")
m = df.valid_obs & complete(df, ["PSH","PSD","PSA","PSCH","PSCD","PSCA"]) & df.FTHG.notna()
d = df[m].copy()
d["lead"] = (d.kickoff - d.observed).dt.total_seconds()/3600
res = np.where(d.FTHG > d.FTAG, 0, np.where(d.FTHG == d.FTAG, 1, 2))
def ll(cols):
    P = np.array([shin(o) if shin(o) is not None else [np.nan]*3 for o in d[cols].to_numpy()]); return -np.log(P[np.arange(len(P)), res])
d["ll_pre"] = ll(["PSH","PSD","PSA"]); d["ll_close"] = ll(["PSCH","PSCD","PSCA"])
d["mv"] = (d.PSH - d.PSCH).abs() / d.PSCH
for lo, hi in [(0, 3), (3, 6), (6, 24), (24, 48), (48, 99)]:
    s = d[(d.lead >= lo) & (d.lead < hi)]
    diff = (s.ll_pre - s.ll_close).dropna(); s = s.loc[diff.index]; se = diff.std() / np.sqrt(len(s))
    print(f"wyprzedzenie [{lo},{hi}) h: n={len(s)} LL(PS)={s.ll_pre.mean():.4f} LL(PSC)={s.ll_close.mean():.4f} różnica={diff.mean():+.4f}±{se:.4f}  |PSH-PSCH|/PSCH śr={s.mv.mean():.4f}  identyczne PS=PSC: {((s.PSH==s.PSCH)&(s.PSA==s.PSCA)).mean():.3f}")
# dni tygodnia meczów z krótkim wyprzedzeniem
s = d[d.lead < 6]; print("krótkie wyprzedzenie — dzień tyg. (London):", s.kickoff.dt.tz_convert("Europe/London").dt.day_name().value_counts().to_dict())
print("godziny gwizdka (London):", s.kickoff.dt.tz_convert("Europe/London").dt.hour.value_counts().sort_index().to_dict())
