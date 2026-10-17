"""Build roster_snapshot.json: one season's Penn State roster (who is on it, by CFBD athlete id) from the PSFAL player-season table, which the
pipeline builds from the CFBD /roster endpoint. The dashboard uses it to decide which forecast players are still on the roster; it never
changes a forecast.

Usage (needs pandas and pyarrow; not run by the dashboard):
    python tools/build_roster_snapshot.py PLAYER_SEASONS.parquet --season 2026 --as-of YYYY-MM-DD [--check "..."]

--as-of is the date the roster data were pulled (the snapshot is no newer than that). --check records an independent cross-check, for
example against the official roster page, in the file's provenance. Rebuild after each pipeline refresh so departures are picked up.
"""
import argparse
import hashlib
import json
from datetime import date
from pathlib import Path


def build(player_seasons, season, as_of, checks):
    import pandas as pd
    p = pd.read_parquet(player_seasons)
    r = p[p["season"] == season]
    if r.empty:
        raise SystemExit(f"no roster rows for {season}")
    if r["athlete_id"].duplicated().any():
        raise SystemExit("duplicate athlete ids in the roster; fix the source before building")
    num = lambda v: None if pd.isna(v) else v
    players = [{"id": str(x.athlete_id), "name": f"{str(x.first_name).strip()} {str(x.last_name).strip()}", "position": num(x.position),
                "group": num(x.pos_group),  # the pipeline's position group (QB, RB, WR, TE, DL, LB, DB, OL, ST)
                "jersey": None if pd.isna(x.jersey) else int(x.jersey),  # secondary identity evidence only: numbers are shared
                "recruit_class": None if pd.isna(x.recruit_class_year) else int(x.recruit_class_year),
                "recruit_type": num(x.recruit_type)} for x in r.sort_values(["last_name", "first_name"]).itertuples()]
    return {"season": season, "as_of": as_of, "players": players,
            "provenance": {"source": "CFBD /roster, via the PSFAL pipeline's player-season table",
                           "data": f"{Path(player_seasons).name}, SHA-256 {hashlib.sha256(Path(player_seasons).read_bytes()).hexdigest()}",
                           "checks": checks, "built": date.today().isoformat()}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("player_seasons")
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--check", action="append", default=[])
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "roster_snapshot.json"))
    a = ap.parse_args()
    date.fromisoformat(a.as_of)
    res = build(a.player_seasons, a.season, a.as_of, a.check)
    Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(res['players'])} players, season {a.season}, as of {a.as_of}; written: {a.out}")
