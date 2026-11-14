import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from scipy.stats import chi2_contingency
from load import complete
df = pd.read_pickle("fd2.pkl"); df = df[df.FTHG.notna()]
df["res"] = np.where(df.FTHG > df.FTAG, "H", np.where(df.FTHG == df.FTAG, "D", "A"))
df["ps"] = complete(df, ["PSH","PSD","PSA"]); df["bw"] = complete(df, ["BWH","BWD","BWA"])
for lab, sub, col in [("2025/26: z PS vs bez PS", df[df.season=="2526"], "ps"), ("2024/25: z BW vs bez BW", df[df.season=="2425"], "bw"),
                      ("wszystkie: valid observed vs wyłączone", df, "valid_obs")]:
    t = pd.crosstab(sub[col], sub.res); chi, p, _, _ = chi2_contingency(t)
    print(lab, t.to_dict(), f"chi2={chi:.2f} p={p:.3f}")
