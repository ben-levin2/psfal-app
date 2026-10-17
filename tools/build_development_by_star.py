"""Build development_by_star.json: production by year in the program for each recruit star group, one series per group (five-star and
four-star separate), from the PSFAL player-season table and the PSFAL pipeline's own production measure. Nothing is estimated or split:
each point is the mean production percentile of the recruits in that group and year, with the number of players behind it.

Usage (needs pandas and pyarrow; not run by the dashboard):
    python tools/build_development_by_star.py PLAYER_SEASONS.parquet PSFAL_PIPELINE_DIR [--last-season 2025]

The method is the pipeline's psfal.modules.development: production_table() (primary stat per position group, percentile among Penn State
players at that position in that season, seasons from 2016) and trajectories() (recruits only, year in the program capped at 5). The only
change is that four- and five-star recruits are separate groups instead of one "4-5 star" group; the combined series is also written so it
can be compared with the dashboard data file's own.
"""
import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

GROUPS = {"star5": "5 stars", "star4": "4 stars", "star45": "4 and 5 stars", "star3": "3 stars", "star2": "2 stars or fewer"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(player_seasons, pipeline_dir, last_season):
    import pandas as pd
    sys.path.insert(0, str(pipeline_dir))
    from psfal.modules.development import FIRST_SEASON, production_table
    p = pd.read_parquet(player_seasons)
    d = production_table({"player_seasons": p[p["season"] <= last_season]})
    rec = d[d["origin_type"] == "recruit"].copy()
    rec["year"] = rec["seasons_in_program"].clip(upper=5)
    s = rec["recruit_stars"]
    member = {"star5": s == 5, "star4": s == 4, "star45": s >= 4, "star3": s == 3, "star2": s <= 2}
    years = sorted(int(y) for y in rec["year"].dropna().unique())
    # players: distinct recruits behind each point; seasons: player-seasons averaged (year 5 is "5 or more", so a player can count twice there)
    out = {"years": years, "players": {}, "seasons": {}}
    for key, m in member.items():
        g = rec[m].groupby("year")
        mean, n, ns = g["prod_pct"].mean(), g["athlete_id"].nunique(), g.size()
        out[key] = [round(float(mean[y]), 1) if y in mean.index else None for y in years]
        out["players"][key] = [int(n[y]) if y in n.index else 0 for y in years]
        out["seasons"][key] = [int(ns[y]) if y in ns.index else 0 for y in years]
    pipeline_file = Path(pipeline_dir) / "psfal" / "modules" / "development.py"
    out["provenance"] = {
        "label": f"PSFAL player-seasons, complete seasons {FIRST_SEASON}–{last_season}",
        "data": f"{Path(player_seasons).name}, SHA-256 {sha256(player_seasons)} (CFBD data, pulled by 2026-10-14)",
        "method": f"psfal.modules.development production_table + trajectories (development.py SHA-256 {sha256(pipeline_file)[:16]}), "
                  "with four- and five-star recruits as separate groups",
        "seasons": [FIRST_SEASON, last_season],
        "built": date.today().isoformat(),
        "groups": GROUPS,
    }
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("player_seasons")
    ap.add_argument("pipeline_dir")
    ap.add_argument("--last-season", type=int, default=2025)  # the last complete season; an in-progress season is left out
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "development_by_star.json"))
    a = ap.parse_args()
    res = build(a.player_seasons, a.pipeline_dir, a.last_season)
    Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: res[k] for k in ("years", *GROUPS)}, ensure_ascii=False))
    print(json.dumps(res["players"]))
    print(json.dumps(res["seasons"]))
    print("written:", a.out)
