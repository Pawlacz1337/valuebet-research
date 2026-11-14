"""Diagnoza alarmu oficjalnego backtestu 4599dca (CLI_task_alarm_4599dca.md, K2-K7).

Tylko odczyt: dzienniki ``reports/backtest_fin/4599dca/strategie/*/bets.csv`` i
``equity.csv`` oraz pliki football-data z ``data/raw/football_data_main``
(te same, które czyta ``fin_files()``). Nic nie zapisuje poza
``docs/discovery/out_B/diag_alarm_out.json``.

K4 (niezależne rozliczenie) nie woła żadnej funkcji ``valuebet`` — czysty
pandas/numpy/hashlib/zoneinfo. Silnik jest importowany leniwie wyłącznie w
``engine_clv`` (średnie CLV w K3 i kontrola zgodności z RAPORT.md).
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

REPO = Path(r"<user>\Desktop\value-bet")
RUNS_DIR = REPO / "reports" / "backtest_fin" / "4599dca" / "strategie"
RAW_FD = REPO / "data" / "raw" / "football_data_main"
OUT = REPO / "docs" / "discovery" / "out_B" / "diag_alarm_out.json"

RUNS = ("A", "A3", "B365", "B-BW", "B-WH", "C", "E")
SEED = 20261018
N_BOOT = 10_000
ODDS_BUCKETS = ((0.0, 2.0, "<2.0"), (2.0, 3.0, "2.0-3.0"), (3.0, 5.0, "3.0-5.0"), (5.0, math.inf, ">=5.0"))
# Kopia stałych z ev.py (T13) — do rekonstrukcji wypłaty kuponu C; K4 jej NIE używa.
WINNINGS_TAX_THRESHOLD = 2280.0

LEAGUES = ("E0", "E1", "E2", "E3", "EC", "SC0", "SC1", "SC2", "SC3", "D1", "D2", "I1", "I2",
           "SP1", "SP2", "F1", "F2", "N1", "B1", "P1", "T1", "G1")  # fmt: skip
SEASONS = ("1920", "2021", "2122", "2223", "2324", "2425", "2526")
LONDON = ZoneInfo("Europe/London")

PRE_1X2 = {"pinnacle": ("PSH", "PSD", "PSA"), "bet365": ("B365H", "B365D", "B365A"),
           "betandwin": ("BWH", "BWD", "BWA"), "williamhill": ("WHH", "WHD", "WHA"),
           "max": ("MaxH", "MaxD", "MaxA")}  # fmt: skip
PRE_OU = {"pinnacle": ("P>2.5", "P<2.5"), "bet365": ("B365>2.5", "B365<2.5"), "max": ("Max>2.5", "Max<2.5")}
IDX_1X2 = {"home": 0, "draw": 1, "away": 2}
IDX_OU = {"over": 0, "under": 1}


# -- dzienniki ------------------------------------------------------------------


def load_journal(run: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(nogi real z wynikiem nogi, kupony real). Wypłata singla z wiersza rozliczeniowego."""
    df = pd.read_csv(RUNS_DIR / run / "bets.csv", dtype=str, keep_default_na=False)
    is_settle = df["bet_id"].str.endswith("#settle")
    settle = df[is_settle].copy()
    settle["orig"] = settle["bet_id"].str.removesuffix("#settle")
    legs = df[~is_settle].copy()
    legs = legs.merge(
        settle[["orig", "settled", "settled_at", "payout"]].rename(
            columns={"orig": "bet_id", "settled": "leg_status", "settled_at": "leg_settled_at",
                     "payout": "settle_payout"}),
        on="bet_id", how="left", validate="one_to_one",
    )  # fmt: skip
    for c in ("odds_taken", "stake", "tax_factor_applied", "p_fair_at_bet"):
        legs[c] = legs[c].astype(float)
    legs["line"] = pd.to_numeric(legs["line"], errors="coerce")
    legs["placed_at"] = pd.to_datetime(legs["placed_at"], utc=True)
    legs["snapshot_observed_at"] = pd.to_datetime(legs["snapshot_observed_at"], utc=True)
    n_all_modes = legs["coupon_id"].nunique()
    legs = legs[legs["mode"] == "real"].copy()
    rows = []
    for cid, g in legs.groupby("coupon_id", sort=False):
        g = g.sort_values("leg_index")
        st = list(g["leg_status"])
        if any(s == "" or pd.isna(s) for s in st):
            status = "open"
        elif "lost" in st:
            status = "lost"
        elif all(s == "void" for s in st):
            status = "void"
        else:
            status = "won"
        stake = float(g["stake"].iloc[0])
        tax = float(g["tax_factor_applied"].iloc[0])
        odds = math.prod(g["odds_taken"])
        if g["coupon_type"].iloc[0] == "single":
            payout = float(g["settle_payout"].iloc[0])
        elif status == "lost":
            payout = 0.0
        elif status == "void":
            payout = round(stake * tax, 2)
        else:
            k = math.prod(o for o, s in zip(g["odds_taken"], st, strict=True) if s != "void")
            gross = stake * k * tax
            payout = round(gross * (0.9 if gross > WINNINGS_TAX_THRESHOLD else 1.0), 2)
        rows.append({
            "coupon_id": cid, "placed_at": g["placed_at"].iloc[0], "stake": stake, "tax": tax,
            "odds": odds, "p": math.prod(g["p_fair_at_bet"]), "n_legs": len(g), "status": status,
            "payout": payout, "match_ids": tuple(g["match_id"]),
            "t13": stake * odds * tax > WINNINGS_TAX_THRESHOLD,
        })  # fmt: skip
    cp = pd.DataFrame(rows)
    cp["profit"] = cp["payout"] - cp["stake"]
    cp.attrs["n_all_modes"] = n_all_modes
    return legs, cp


def raport_main_table() -> dict[str, dict[str, float]]:
    """Przebiegi główne z RAPORT.md: obrót, zysk, CLV (kontrola rekonstrukcji)."""
    text = (RUNS_DIR / "RAPORT.md").read_text(encoding="utf-8")
    section = text.split("## Przebiegi główne", 1)[1].split("## ", 1)[0]
    out = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 8 and cells[0] in RUNS:
            clv = re.match(r"([+-]\d+\.\d+)", cells[6])
            out[cells[0]] = {"n": int(cells[1]), "real": int(cells[2]), "turnover": float(cells[3]),
                             "profit": float(cells[4]), "clv": float(clv.group(1)) if clv else math.nan}  # fmt: skip
    return out


def equity_payouts(run: str) -> dict[str, float]:
    """Wypłata kuponu zapisana przez silnik: przyrost gotówki w wierszu zdarzenia kuponu."""
    eq = pd.read_csv(RUNS_DIR / run / "equity.csv", dtype={"event": str})
    cash = eq["cash"].astype(float).to_numpy()
    out: dict[str, float] = {}
    for i in range(1, len(eq)):
        ev = eq["event"].iat[i]
        if ev != "decision":
            out[ev] = round(cash[i] - cash[i - 1], 2)
    return out


# -- football-data, niezależnie od silnika --------------------------------------


def latest_raw(label: str) -> Path | None:
    """Nowy format ``<label>.<UTC>Z.<hash>.csv`` i stary ``<label>-<UTC>Z.csv`` (E0)."""
    files = sorted(p for p in RAW_FD.glob(f"{label}*.csv") if p.name[len(label)] in ".-")
    return files[-1] if files else None


def read_fd(path: Path) -> pd.DataFrame:
    content = path.read_bytes()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    return pd.read_csv(io.StringIO(text), low_memory=False).dropna(how="all")


def kickoff_utc(day: str, clock: str) -> datetime:
    d, m, y = (int(p) for p in day.strip().split("/"))
    year = 2000 + y if y < 100 else y
    hh, mm = (int(p) for p in clock.strip().split(":"))
    return datetime(year, m, d, hh, mm, tzinfo=LONDON).astimezone(UTC)


def num(row: pd.Series, col: str) -> float:
    if col not in row.index:
        return math.nan
    v = pd.to_numeric(row[col], errors="coerce")
    return math.nan if pd.isna(v) else float(v)


def match_index() -> tuple[dict[str, dict], dict[str, int]]:
    """match_id → wiersz meczu (kurs, wynik, gwizdek). Ten sam klucz co silnik, liczony od nowa."""
    idx: dict[str, dict] = {}
    stats = {"files": 0, "missing_files": 0, "rows": 0, "no_time": 0, "dup_ids": 0}
    cols = sorted({c for d in (PRE_1X2, PRE_OU) for v in d.values() for c in v})
    for lg in LEAGUES:
        for s in SEASONS:
            path = latest_raw(f"{lg}-{s}")
            if path is None:
                stats["missing_files"] += 1
                continue
            stats["files"] += 1
            for _, row in read_fd(path).iterrows():
                stats["rows"] += 1
                if "Time" not in row.index or pd.isna(row["Time"]):
                    stats["no_time"] += 1
                    continue
                ko = kickoff_utc(str(row["Date"]), str(row["Time"]))
                home, away = str(row["HomeTeam"]), str(row["AwayTeam"])
                mid = hashlib.sha1(f"{lg}|{ko.date().isoformat()}|{home}|{away}".encode()).hexdigest()[:16]
                if mid in idx:
                    stats["dup_ids"] += 1
                idx[mid] = {
                    "league": lg, "season": s, "kickoff": ko, "home": home, "away": away,
                    "FTHG": num(row, "FTHG"), "FTAG": num(row, "FTAG"),
                    "FTR": str(row["FTR"]) if "FTR" in row.index and not pd.isna(row["FTR"]) else "",
                    **{c: num(row, c) for c in cols},
                }  # fmt: skip
    return idx, stats


def shin_indep(odds: list[float]) -> list[float]:
    """Shin (z z sum p = 1) — bisekcja, własna implementacja; jak silnik: renormalizacja."""
    pi = np.array([1.0 / k for k in odds])
    big_p = pi.sum()

    def ps(z: float) -> np.ndarray:
        if z < 1e-10:
            return pi / math.sqrt(big_p)
        return (np.sqrt(z * z + 4 * (1 - z) * pi**2 / big_p) - z) / (2 * (1 - z))

    lo, hi = 0.0, 1.0 - 1e-12
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if ps(mid).sum() - 1.0 > 0:
            lo = mid
        else:
            hi = mid
    p = ps(0.5 * (lo + hi))
    return list(p / p.sum())


def leg_truth(leg: pd.Series, m: dict, run: str) -> dict:
    """Wynik, kurs miękki i p uczciwe nogi z wiersza football-data."""
    market, outcome = leg["market"], leg["outcome"]
    h, a = m["FTHG"], m["FTAG"]
    if market == "1x2":
        i = IDX_1X2[outcome]
        ftr = {"H": "home", "D": "draw", "A": "away"}.get(m["FTR"], "")
        goals = "" if math.isnan(h) else ("home" if h > a else "away" if a > h else "draw")
        actual = ftr or goals
        res = "void" if not actual else ("won" if outcome == actual else "lost")
        ftr_goals_agree = (ftr == goals) if ftr and goals else None
        pin = [m[c] for c in PRE_1X2["pinnacle"]]
        if run == "C":  # kursy jak A: najlepszy z B365/BW z booksum ≥ 1.00
            cands = []
            for b in ("bet365", "betandwin"):
                q = [m[c] for c in PRE_1X2[b]]
                if all(not math.isnan(x) for x in q) and sum(1 / x for x in q) >= 1.0:
                    cands.append(q[i])
            soft = max(cands) if cands else math.nan
        else:
            soft = m[PRE_1X2[leg["bookmaker"]][i]]
    else:
        i = IDX_OU[outcome]
        ftr_goals_agree = None
        if math.isnan(h):
            res = "void"
        else:
            tot = h + a
            res = "void" if tot == 2.5 else ("won" if (tot > 2.5) == (outcome == "over") else "lost")
        pin = [m[c] for c in PRE_OU["pinnacle"]]
        soft = m[PRE_OU["bet365"][i]]
    p = shin_indep(pin)[i] if all(not math.isnan(x) for x in pin) else math.nan
    return {"result": res, "soft": soft, "p": p, "ftr_goals_agree": ftr_goals_agree}


def k4(cps: dict[str, pd.DataFrame], legs: dict[str, pd.DataFrame], idx: dict[str, dict]) -> dict:
    rng = np.random.default_rng(SEED)
    a_cp = cps["A"].sort_values("coupon_id").reset_index(drop=True)
    c_cp = cps["C"].sort_values("coupon_id").reset_index(drop=True)
    pick_rand = list(a_cp["coupon_id"].iloc[np.sort(rng.choice(len(a_cp), 60, replace=False))])
    pick_top = list(a_cp.sort_values(["profit", "coupon_id"], ascending=[False, True])["coupon_id"].head(20))
    pick_c = list(c_cp["coupon_id"].iloc[np.sort(rng.choice(len(c_cp), 20, replace=False))])
    eq_c = equity_payouts("C")
    eq_a = equity_payouts("A")
    mismatches: list[str] = []
    checked = {"coupons": 0, "legs": 0}
    t13_notes = []
    for run, ids, tag in (("A", pick_rand, "A-los"), ("A", pick_top, "A-top20"), ("C", pick_c, "C-los")):
        lg = legs[run]
        cp = cps[run].set_index("coupon_id")
        for cid in ids:
            checked["coupons"] += 1
            g = lg[lg["coupon_id"] == cid].sort_values("leg_index")
            won_all = True
            any_lost = False
            k_prod = 1.0
            for _, leg in g.iterrows():
                checked["legs"] += 1
                m = idx.get(leg["match_id"])
                if m is None:
                    mismatches.append(f"{tag} {leg['bet_id']}: mecz {leg['match_id']} nieznaleziony w plikach")
                    won_all = False
                    continue
                t = leg_truth(leg, m, run)
                if not abs(t["soft"] - leg["odds_taken"]) <= 1e-9:
                    mismatches.append(f"{tag} {leg['bet_id']}: kurs plik={t['soft']} dziennik={leg['odds_taken']}")
                if not abs(t["p"] - leg["p_fair_at_bet"]) <= 1e-6:
                    mismatches.append(f"{tag} {leg['bet_id']}: p plik={t['p']:.9f} dziennik={leg['p_fair_at_bet']:.9f}")
                if t["result"] != leg["leg_status"]:
                    mismatches.append(f"{tag} {leg['bet_id']}: wynik plik={t['result']} dziennik={leg['leg_status']}")
                if t["ftr_goals_agree"] is False:
                    mismatches.append(f"{tag} {leg['bet_id']}: FTR ≠ FTHG/FTAG w pliku")
                if t["result"] == "lost":
                    any_lost = True
                if t["result"] != "won":
                    won_all = False
                k_prod *= leg["odds_taken"]
            stake = float(g["stake"].iloc[0])
            tax = float(g["tax_factor_applied"].iloc[0])
            mine = stake * k_prod * tax if (won_all and not any_lost) else 0.0
            engine = (eq_c if run == "C" else eq_a).get(cid)
            journal = float(cp.at[cid, "payout"]) if run == "A" else None
            for label, val in (("dziennik", journal), ("equity", engine)):
                if val is None:
                    continue
                if not abs(mine - val) <= 0.01 + 1e-9:
                    note = " (T13: brutto > 2280 → ×0.90)" if mine > WINNINGS_TAX_THRESHOLD else ""
                    mismatches.append(f"{tag} {cid}: wypłata niezależna={mine:.2f} {label}={val:.2f}{note}")
            if mine > WINNINGS_TAX_THRESHOLD:
                t13_notes.append(cid)
    return {"checked": checked, "n_mismatch": len(mismatches), "mismatches": mismatches,
            "overlap_rand_top": len(set(pick_rand) & set(pick_top)), "t13_coupons_in_sample": t13_notes,
            "pick_c_multi": int((cps["C"].set_index("coupon_id").loc[pick_c, "n_legs"] > 1).sum())}  # fmt: skip


# -- K2 -------------------------------------------------------------------------


def iso_week(ts: datetime) -> str:
    iso = ts.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def k2(cp: pd.DataFrame, idx: dict[str, dict]) -> dict:
    s, k, t, p = cp["stake"].to_numpy(), cp["odds"].to_numpy(), cp["tax"].to_numpy(), cp["p"].to_numpy()
    exp = s * (p * k * t - 1.0)
    var = (s**2) * (k * t) ** 2 * p * (1 - p)
    real = cp["profit"].to_numpy()
    turnover = s.sum()
    z = (real.sum() - exp.sum()) / math.sqrt(var.sum())
    # Klaster = tydzień ISO najwcześniejszego gwizdka kuponu (jak backtest/clv._cluster).
    clusters = []
    for mids in cp["match_ids"]:
        kos = [idx[m]["kickoff"] for m in mids if m in idx]
        clusters.append(iso_week(min(kos)) if kos else "brak")
    frame = pd.DataFrame({"c": clusters, "d": real - exp, "s": s}).groupby("c").sum()
    d, w = frame["d"].to_numpy(), frame["s"].to_numpy()
    rng = np.random.default_rng(SEED)
    draws = rng.integers(0, len(frame), size=(N_BOOT, len(frame)))
    stat = d[draws].sum(axis=1) / w[draws].sum(axis=1)
    lo, hi = np.quantile(stat, [0.025, 0.975])
    return {"n": len(cp), "turnover": turnover, "exp_profit": exp.sum(), "real_profit": real.sum(),
            "exp_yield": exp.sum() / turnover, "real_yield": real.sum() / turnover, "z": z,
            "diff_per_turnover": (real.sum() - exp.sum()) / turnover, "ci": [lo, hi],
            "n_clusters": len(frame), "flag": "flaga" if abs(z) > 2 else "zgodne z losowością",
            "n_t13": int(cp["t13"].sum()), "n_void": int((cp["status"] == "void").sum()),
            "n_open": int((cp["status"] == "open").sum())}  # fmt: skip


# -- K3 -------------------------------------------------------------------------


def engine_clv(runs: tuple[str, ...]) -> dict[str, dict[str, float]]:
    """CLV kuponu funkcjami silnika (replay_csv → closing_map → clv_rows), tylko odczyt."""
    from valuebet.backtest.financial import closing_map
    from valuebet.backtest.replay import merge_replays, replay_csv
    from valuebet.backtest.clv import clv_rows
    from valuebet.ingest.football_data_main import ObservedAtRule, fin_files
    from valuebet.ingest.raw_store import RawStore
    from valuebet.live.bets import BetJournal

    store = RawStore(root=REPO / "data" / "raw")
    rule = ObservedAtRule("friday_tuesday_1800_london")
    reps, paths = [], []
    for f in fin_files():
        path = store.latest("football_data_main", f"{f.league}-{f.season}", ".csv")
        if path is None:
            continue
        paths.append(path)
        reps.append(replay_csv(path.read_bytes(), league=f.league, season=f.season, rule=rule))
    replay = merge_replays(reps)
    closing = closing_map(replay)
    kickoffs = {m.match_id: m.kickoff for m in replay.matches}
    as_of = datetime(2100, 1, 1, tzinfo=UTC)
    out: dict[str, dict[str, float]] = {}
    for run in runs:
        rows = BetJournal(journal_path=RUNS_DIR / run / "bets.csv").read()
        out[run] = {r.bet_id: (math.nan if r.clv is None else r.clv)
                    for r in clv_rows(bets=rows, closing=closing, kickoffs=kickoffs, as_of=as_of)}  # fmt: skip
    same_paths = all(p == latest_raw(p.name.split(".")[0]) for p in paths)
    out["_meta"] = {"n_files": len(paths), "same_paths_as_indep": same_paths}  # type: ignore[assignment]
    return out


def season_of(ts: pd.Timestamp) -> str:
    """Sezon wg daty zakładu: cięcie 1 lipca UTC (2019-07-01 … 2020-06-30 → 2019/20)."""
    y = ts.year if ts.month >= 7 else ts.year - 1
    return f"{y}/{(y + 1) % 100:02d}"


def k3(cp: pd.DataFrame) -> dict:
    total = cp["profit"].sum()
    top = cp.sort_values(["profit", "coupon_id"], ascending=[False, True]).head(10)
    rest = cp.drop(top.index)
    out = {
        "top10_profit": top["profit"].sum(), "total_profit": total,
        "top10_share": top["profit"].sum() / total if total else math.nan,
        "yield_without_top10": rest["profit"].sum() / rest["stake"].sum(),
        "top10_odds": [round(x, 2) for x in top["odds"]],
    }  # fmt: skip

    def agg(g: pd.DataFrame) -> dict:
        return {"n": len(g), "turnover": g["stake"].sum(), "yield": g["profit"].sum() / g["stake"].sum(),
                "clv": float(np.nanmean(g["clv"])) if g["clv"].notna().any() else math.nan,
                "n_clv": int(g["clv"].notna().sum())}  # fmt: skip

    out["buckets"] = {lab: agg(cp[(cp["odds"] >= lo) & (cp["odds"] < hi)]) for lo, hi, lab in ODDS_BUCKETS}
    seasons = cp["placed_at"].map(season_of)
    out["seasons"] = {s: agg(cp[seasons == s]) for s in sorted(seasons.unique())}
    return out


# -- K5, K7 ---------------------------------------------------------------------


def k5c(legs: pd.DataFrame, idx: dict[str, dict]) -> dict:
    ko = legs["match_id"].map(lambda m: idx[m]["kickoff"] if m in idx else pd.NaT)
    known = ko.notna()
    ko_known = pd.to_datetime(ko[known], utc=True)
    lead_h = (ko_known - legs.loc[known, "placed_at"]).dt.total_seconds() / 3600
    return {"n_legs": len(legs), "unknown_kickoff": int((~known).sum()),
            "decision_ge_kickoff": int((legs.loc[known, "placed_at"] >= ko_known).sum()),
            "snapshot_ge_placed": int((legs["snapshot_observed_at"] >= legs["placed_at"]).sum()),
            "lead_h_min": float(lead_h.min()), "lead_h_median": float(lead_h.median()),
            "lead_h_max": float(lead_h.max())}  # fmt: skip


def k7(legs: dict[str, pd.DataFrame]) -> dict:
    def keys(df: pd.DataFrame) -> set[tuple]:
        return {(m, mk, o, None if pd.isna(ln) else float(ln))
                for m, mk, o, ln in zip(df["match_id"], df["market"], df["outcome"], df["line"], strict=True)}  # fmt: skip

    sets = {r: keys(legs[r]) for r in ("A", "A3", "B365", "B-BW", "B-WH", "C")}
    names = ("A", "A3", "B365", "B-BW", "B-WH")
    pairs = {}
    for i, x in enumerate(names):
        for y in names[i + 1 :]:
            inter = len(sets[x] & sets[y])
            pairs[f"{x}|{y}"] = {"inter": inter, "min": min(len(sets[x]), len(sets[y])),
                                 "ratio": inter / min(len(sets[x]), len(sets[y]))}  # fmt: skip
    c_legs = legs["C"]
    c_keys = [(m, mk, o, None if pd.isna(ln) else float(ln))
              for m, mk, o, ln in zip(c_legs["match_id"], c_legs["market"], c_legs["outcome"], c_legs["line"], strict=True)]  # fmt: skip
    in_a = sum(1 for k in c_keys if k in sets["A"])
    return {"pairs": pairs, "C_legs": len(c_keys), "C_legs_in_A": in_a, "C_share_in_A": in_a / len(c_keys)}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    legs: dict[str, pd.DataFrame] = {}
    cps: dict[str, pd.DataFrame] = {}
    for r in RUNS:
        legs[r], cps[r] = load_journal(r)
    rap = raport_main_table()
    recon = {r: {"n": len(cps[r]), "n_all_modes": cps[r].attrs["n_all_modes"],
                 "turnover": round(cps[r]["stake"].sum(), 2), "profit": round(cps[r]["profit"].sum(), 2),
                 "rap": rap.get(r)} for r in RUNS}  # fmt: skip
    idx, idx_stats = match_index()
    res: dict = {"reconstruction": recon, "match_index": idx_stats}
    res["K4"] = k4(cps, legs, idx)
    res["K2"] = {r: k2(cps[r], idx) for r in RUNS}
    res["K2b"] = "brak pola p_close / kursu zamknięcia w dzienniku (kolumny: " + ",".join(
        pd.read_csv(RUNS_DIR / "A" / "bets.csv", nrows=0).columns) + ")"
    clv = engine_clv(("A", "A3", "C"))
    res["clv_meta"] = clv.pop("_meta")
    res["K3"] = {}
    for r in ("A", "A3", "C"):
        cp = cps[r].copy()
        cp["clv"] = cp["coupon_id"].map(clv[r])
        res["K3"][r] = k3(cp)
        res["K3"][r]["clv_mean_all"] = float(np.nanmean(cp["clv"]))
        res["K3"][r]["clv_raport"] = rap[r]["clv"]
    res["K5c"] = {r: k5c(legs[r], idx) for r in RUNS}
    res["K7"] = k7(legs)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
