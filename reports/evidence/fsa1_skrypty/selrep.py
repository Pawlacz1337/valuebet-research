"""Niezależna replika selekcji A (1X2 i O/U) i porównanie zbioru z dziennikiem."""
import warnings, csv; warnings.filterwarnings("ignore")
import pandas as pd
from a1a import run, v
from devig import shin
from load import complete
s = run(("bet365", "betandwin"), "strict")
OUT = ("home", "draw", "away")
mine = {(r.mid, "1x2", OUT[r.j]): r.k for r in s.itertuples()}
# O/U: tylko bet365, Shin(P>2.5,P<2.5)
for i, r in v[complete(v, ["P>2.5","P<2.5","B365>2.5","B365<2.5"])].iterrows():
    o = [r["B365>2.5"], r["B365<2.5"]]
    if sum(1/x for x in o) < 1: continue
    p = shin([r["P>2.5"], r["P<2.5"]])
    if p is None: continue
    for j, name in enumerate(("over", "under")):
        if p[j]*o[j]-1 <= 0.5 and o[j] >= 1.02/p[j]: mine[(r.mid, "over_under", name)] = o[j]
rows = [r for r in csv.DictReader(open("<user>/Desktop/value-bet/reports/backtest_fin/4599dca/strategie/A/bets.csv", encoding="utf-8")) if "#" not in r["bet_id"]]
eng = {(r["match_id"], r["market"], r["outcome"]): float(r["odds_taken"]) for r in rows}
only_mine = set(mine) - set(eng); only_eng = set(eng) - set(mine)
print("replika:", len(mine), "silnik:", len(eng), "tylko replika:", len(only_mine), "tylko silnik:", len(only_eng),
      "wspólne z innym kursem:", sum(1 for k in set(mine) & set(eng) if abs(mine[k]-eng[k]) > 1e-9))
print("pominięte przez silnik (stawka 0 + < min.): 22 + 2 = 24")
df = pd.read_pickle("fd2.pkl").set_index("mid")
for k in only_eng:
    r = df.loc[k[0]]; print("tylko silnik:", k, eng[k], r.league, r.season, r.kickoff, [r[c] for c in ("PSH","PSD","PSA","B365H","B365D","B365A","BWH","BWD","BWA","P>2.5","P<2.5","B365>2.5","B365<2.5")])
    e = [x for x in rows if (x["match_id"], x["market"], x["outcome"]) == k][0]; print("   p silnika", e["p_fair_at_bet"], "p*k", float(e["p_fair_at_bet"])*eng[k])
