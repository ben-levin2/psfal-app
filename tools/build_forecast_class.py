"""Build forecast_class.json: every high-school recruit of the forecast's recruiting class with the facts the Step 2 rules need (identity
link, position group, rating, first program season, first-season stat row and primary stat, independent roster check). Facts only: no
eligibility decision, state or probability is stored; data_check derives those, so the rules stay in one place.

Usage (needs pandas and pyarrow; not run by the dashboard):
    python tools/build_forecast_class.py PLAYER_SEASONS.parquet --class 2025 --as-of YYYY-MM-DD [--official-check FILE]

PRIMARY is the PSFAL pipeline's production measure (psfal.modules.development.PRIMARY), copied so this tool does not import the pipeline.
A missing stat row is written as has_stat_row: false with primary_value null; it is never written as zero.
"""
import argparse
import hashlib
import json
import math
from datetime import date
from pathlib import Path

PRIMARY = {"QB": "stat_passing_yds", "RB": "stat_rushing_yds", "WR": "stat_receiving_yds", "TE": "stat_receiving_yds",
           "DL": "stat_defensive_tfl", "LB": "stat_defensive_tot", "DB": "stat_defensive_tot"}


def _key(name):
    import re
    parts = re.sub(r"[^a-z0-9 ]+", " ", str(name).lower().replace("'", "")).split()
    while len(parts) > 2 and parts[-1] in {"jr", "sr", "ii", "iii", "iv", "v"}:
        parts.pop()
    return " ".join(parts)


def build(player_seasons, recruit_class, as_of, check):
    import pandas as pd
    p = pd.read_parquet(player_seasons)
    c = p[(p["recruit_class_year"] == recruit_class)]
    if c["athlete_id"].isna().any():
        raise SystemExit("recruits without an athlete id; fix the source before building")
    # the check lists each player found, with jersey and position as shown (secondary identity evidence, never a key)
    listed = {_key(e["name"] if isinstance(e, dict) else e): (e if isinstance(e, dict) else {"name": e}) for e in (check or {}).get("listed", [])}
    val = lambda v: None if v is None or (isinstance(v, float) and math.isnan(v)) or pd.isna(v) else v
    players = []
    for aid, rows in c.groupby("athlete_id", sort=False):
        first = rows.sort_values("season").iloc[0]
        year1 = rows[rows["season"] == recruit_class]
        y1 = year1.iloc[0] if len(year1) else None
        col = PRIMARY.get(first["pos_group"])
        name = f"{str(first['first_name']).strip()} {str(first['last_name']).strip()}"
        players.append({
            "id": str(aid), "name": name, "position": val(first["position"]), "group": val(first["pos_group"]),
            "recruit_class": int(first["recruit_class_year"]), "recruit_type": val(first["recruit_type"]),
            "recruit_ids": val(first["recruit_ids"]), "match_method": val(first["recruit_match_method"]),
            "rating": val(first["recruit_rating"]), "stars": None if val(first["recruit_stars"]) is None else int(first["recruit_stars"]),
            "first_roster_season": int(first["first_roster_season"]), "arrival_uncertain": bool(first["arrival_uncertain"]),
            "first_season": None if y1 is None else {
                "season": recruit_class, "has_stat_row": bool(y1["has_stat_row"]), "primary_stat": col,
                "primary_value": None if col is None or not bool(y1["has_stat_row"]) else val(y1[col])},
            "official_roster_check": None if not check else {"source": check["source"], "date": check["date"], "season": check["season"],
                                                              "listed": _key(name) in listed,
                                                              "jersey": listed.get(_key(name), {}).get("jersey"),
                                                              "position": listed.get(_key(name), {}).get("position")},
        })
    players.sort(key=lambda x: x["name"])
    return {"recruit_class": recruit_class, "as_of": as_of, "players": players,
            "provenance": {"source": "CFBD roster, recruiting and season-stat data via the PSFAL pipeline's player-season table",
                           "data": f"{Path(player_seasons).name}, SHA-256 {hashlib.sha256(Path(player_seasons).read_bytes()).hexdigest()}",
                           "primary_stats": PRIMARY, "official_roster_check": None if not check else
                           {k: check[k] for k in ("source", "date", "season", "scope")},
                           "built": date.today().isoformat()}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("player_seasons")
    ap.add_argument("--class", dest="recruit_class", type=int, required=True)
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--official-check")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "forecast_class.json"))
    a = ap.parse_args()
    date.fromisoformat(a.as_of)
    check = json.loads(Path(a.official_check).read_text()) if a.official_check else None
    res = build(a.player_seasons, a.recruit_class, a.as_of, check)
    Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str) + "\n")
    print(f"{len(res['players'])} recruits of the {a.recruit_class} class, as of {a.as_of}; written: {a.out}")
