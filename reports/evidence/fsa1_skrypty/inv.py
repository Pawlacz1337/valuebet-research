"""Niezmienniki dzienników 38 przebiegów vs surowe kolumny (bez valuebet)."""
import csv, os, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from devig import shin
from collections import Counter
B = "<user>/Desktop/value-bet/reports/backtest_fin/4599dca/strategie"
df = pd.read_pickle("fd2.pkl").set_index("mid")
PRE = {"1x2": {"bet365": ("B365H","B365D","B365A"), "betandwin": ("BWH","BWD","BWA"), "williamhill": ("WHH","WHD","WHA"), "max": ("MaxH","MaxD","MaxA")},
       "over_under": {"bet365": ("B365>2.5","B365<2.5"), "max": ("Max>2.5","Max<2.5")}}
CLO = {"1x2": {"bet365": ("B365CH","B365CD","B365CA"), "betandwin": ("BWCH","BWCD","BWCA"), "williamhill": ("WHCH","WHCD","WHCA")},
       "over_under": {"bet365": ("B365C>2.5","B365C<2.5")}}
PS = {"1x2": ("PSH","PSD","PSA"), "over_under": ("P>2.5","P<2.5")}
OUT = {"1x2": ("home","draw","away"), "over_under": ("over","under")}
shc = {}
tot = Counter()
for run in sorted(os.listdir(B)):
    p = f"{B}/{run}/bets.csv"
    if not os.path.exists(p) or run == "F": continue
    c = Counter()
    for r in csv.DictReader(open(p, encoding="utf-8")):
        if "#" in r["bet_id"]: continue
        m = df.loc[r["match_id"]]; mk = r["market"]; j = OUT[mk].index(r["outcome"]); k = float(r["odds_taken"])
        c["nogi"] += 1
        if not pd.Timestamp(r["placed_at"]) < m.kickoff: c["placed>=gwizdek"] += 1
        if not pd.Timestamp(r["snapshot_observed_at"]) < pd.Timestamp(r["placed_at"]): c["obs>=placed"] += 1
        if pd.Timestamp(r["placed_at"]) != m.observed + pd.Timedelta(minutes=1): c["placed!=obs+1min"] += 1
        books = PRE[mk] if r["bookmaker"] != "betclic" else {b: PRE[mk][b] for b in ("bet365", "betandwin") if b in PRE[mk]}
        pre_ok = any(abs(m[cols[j]] - k) < 1e-9 for b, cols in books.items() if r["bookmaker"] in (b, "betclic"))
        if not pre_ok: c["kurs≠kolumna przedmeczowa"] += 1
        clo_eq = any(pd.notna(m[cols[j]]) and abs(m[cols[j]] - k) < 1e-9 and abs(m[books[b][j]] - k) > 1e-9 for b, cols in CLO[mk].items() if b in books)
        if clo_eq: c["kurs=zamknięcie≠przed"] += 1
        key = (r["match_id"], mk)
        if key not in shc: shc[key] = shin([m[x] for x in PS[mk]])
        if abs(shc[key][j] - float(r["p_fair_at_bet"])) > 1e-6: c["p≠Shin(PS przed)"] += 1
        c[f"tax {r['tax_factor_applied']}"] += 1
    print(run, dict(c)); tot.update(c)
