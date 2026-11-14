import json, glob, warnings; warnings.filterwarnings("ignore")
from datetime import datetime
import numpy as np, pandas as pd
roots = [r"<user>\Desktop\value-bet\data\raw\odds", r"D:\vb-backup\vps-raw-2026-10-12", r"D:\vb-backup\vps-raw-2026-10-16"]
files = {}
for r in roots:
    for p in glob.glob(r + r"\**\*.json", recursive=True):
        files.setdefault(p.split("\\")[-1], p)
print("plików json (unikalne nazwy):", len(files))
snaps = []
for name, p in files.items():
    try: d = json.load(open(p, encoding="utf-8"))
    except Exception: continue
    if not isinstance(d, dict) or d.get("anchor") != "decision": continue
    at = datetime.fromisoformat(d["ingested_at"])
    for e in d.get("events", []):
        has_pin = any(b.get("key") == "pinnacle" for b in e.get("bookmakers", []))
        snaps.append((d["sport_key"], e["id"], datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00")), at, has_pin))
s = pd.DataFrame(snaps, columns=["sport", "event", "ko", "snap", "pin"])
s["lead_h"] = (s.ko - s.snap).dt.total_seconds() / 3600
print("migawek decyzyjnych (plików):", s.snap.nunique(), "wierszy zdarzeń:", len(s), "z Pinnacle:", int(s.pin.sum()))
pos = s[(s.lead_h > 0) & s.pin]
last = pos.sort_values("snap").groupby("event").tail(1)  # ostatnia migawka decyzyjna przed gwizdkiem
print("zdarzeń z migawką decyzyjną przed gwizdkiem:", len(last))
q = last.lead_h.quantile([0, .1, .25, .5, .75, .9, 1]).round(2).to_dict(); print("wyprzedzenie ostatniej migawki [h]:", q)
print("udział ≤ 48 h:", round((last.lead_h <= 48).mean(), 3), "≤ 12 h:", round((last.lead_h <= 12).mean(), 3))
print("per liga mediana:", last.groupby("sport").lead_h.median().round(1).to_dict(), last.groupby("sport").size().to_dict())
# backtest: wyprzedzenie decyzji (observed+1min) dla wszystkich meczów i dla zakładów A
df = pd.read_pickle("fd2.pkl"); v = df[df.valid_obs]
lead = (v.kickoff - v.observed).dt.total_seconds() / 3600 - 1/60
print("backtest wszystkie mecze — wyprzedzenie [h]:", lead.quantile([0, .1, .25, .5, .75, .9, 1]).round(2).to_dict())
import recon
a = recon.read("A"); ids = {l[0] for c in a for l in c["legs"]}
la = lead[v.mid.isin(ids)]
print("backtest zakłady A — wyprzedzenie [h]:", la.quantile([0, .1, .25, .5, .75, .9, 1]).round(2).to_dict(), "n", len(la))
end = s.snap.max()
print("migawki decyzyjne (czasy):", sorted(set(s.snap.dt.strftime("%Y-%m-%d %H:%M"))))
obs = last[last.ko <= end + pd.Timedelta(hours=24)]
print("zdarzenia z gwizdkiem ≤ ostatnia migawka + 24 h:", len(obs), "wyprzedzenie [h]:", obs.lead_h.quantile([0, .25, .5, .75, 1]).round(2).to_dict())
