"""Niezależny loader audytora FSA #1: surowe CSV football-data -> jedna ramka.
Bez importu valuebet. Tylko odczyt z data/raw."""
import io, re
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
RAW = Path(r"<user>\Desktop\value-bet\data\raw\football_data_main")
LEAGUES = ("E0","E1","E2","E3","EC","SC0","SC1","SC2","SC3","D1","D2","I1","I2","SP1","SP2","F1","F2","N1","B1","P1","T1","G1")
SEASONS = ("1920","2021","2122","2223","2324","2425","2526")
LON = ZoneInfo("Europe/London")
def _ts(name):
    m = re.search(r"(\d{8}T\d{6,12})Z", name); return m.group(1).ljust(21, "0")
def latest(lg, s):
    c = [p for p in RAW.iterdir() if p.name.startswith(f"{lg}-{s}") and p.suffix == ".csv"]
    return max(c, key=lambda p: _ts(p.name)) if c else None
def read(p):
    b = p.read_bytes()
    try: t = b.decode("utf-8-sig")
    except UnicodeDecodeError: t = b.decode("latin-1")
    return pd.read_csv(io.StringIO(t), low_memory=False)
def load():
    out = []
    for lg in LEAGUES:
        for s in SEASONS:
            p = latest(lg, s)
            if p is None: print("BRAK", lg, s); continue
            f = read(p).dropna(how="all"); f["league"] = lg; f["season"] = s; f["file"] = p.name; out.append(f)
    df = pd.concat(out, ignore_index=True)
    d = df["Date"].astype(str).str.strip(); t = df["Time"].astype(str).str.strip()
    dt = pd.to_datetime(d + " " + t, format="%d/%m/%Y %H:%M", errors="coerce")
    dt2 = pd.to_datetime(d + " " + t, format="%d/%m/%y %H:%M", errors="coerce")
    dt = dt.fillna(dt2)
    df["ko_local"] = dt
    df["kickoff"] = dt.dt.tz_localize(LON, ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    # reguła obserwacji: pt-pn -> piątek, wt-czw -> wtorek, 18:00 London
    loc = df["kickoff"].dt.tz_convert(LON)
    wd = loc.dt.weekday
    back = wd.map(lambda w: w-4 if w >= 4 else (3 if w == 0 else w-1))
    day = loc.dt.normalize().dt.tz_localize(None) - pd.to_timedelta(back, unit="D")
    obs = (day + pd.Timedelta(hours=18)).dt.tz_localize(LON).dt.tz_convert("UTC")
    df["observed"] = obs
    df["valid_obs"] = obs < df["kickoff"]
    for c in ["PSH","PSD","PSA","PSCH","PSCD","PSCA","B365H","B365D","B365A","BWH","BWD","BWA","WHH","WHD","WHA",
              "MaxH","MaxD","MaxA","P>2.5","P<2.5","PC>2.5","PC<2.5","B365>2.5","B365<2.5","FTHG","FTAG",
              "B365CH","B365CD","B365CA","BWCH","BWCD","BWCA","WHCH","WHCD","WHCA"]:
        if c in df: df[c] = pd.to_numeric(df[c], errors="coerce")
        else: df[c] = float("nan")
    return df
def complete(df, cols):
    ok = pd.Series(True, index=df.index)
    for c in cols: ok &= df[c].notna() & (df[c] > 1.0)
    return ok
if __name__ == "__main__":
    df = load()
    print("wierszy", len(df), "bez kickoff", df["kickoff"].isna().sum(), "valid_obs", int(df["valid_obs"].sum()), "invalid", int((~df["valid_obs"]).sum()))
    df.to_pickle(Path(__file__).with_name("fd.pkl"))
