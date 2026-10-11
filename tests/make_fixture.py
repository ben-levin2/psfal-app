"""Synthetic dashboard_data.json for TESTS ONLY (the real data file is not in the repo). Values are placeholders and are never shown outside tests."""
import json
POS = ["QB", "RB", "WR", "TE", "DL", "LB", "DB"]


def fixture():
    return {
        "meta": {"through_week": 6, "snapshot": "TEST FIXTURE"},
        "games": [{"wk": i, "opp": f"Opp{i}", "pf": 30, "pa": 20, "res": "W", "o": 50, "d": 60, "note": "x"} for i in range(1, 4)],
        "schedule": [["Oct 1", "Opp", "Home"]],
        "watch": [{"label": "Metric", "now": 1.0, "ref": 0.5, "better": "high", "refLabel": "ref"}],
        "gap": [["Row", 1.0, 1.5, 2.0]],
        "loses": [["Top 10", "5-22", 20]],
        "seasons": [[2025, "10-3", 5, 12, 15]],
        "roster": [["QB", 10, 50, 20]],
        "forecast": [["QB", 5, 3.0, 2.0, 4.0]],
        "traj": {"years": [1, 2], "star45": [50, 60], "star3": [40, 50], "star2": [30, 40]},
        "ratingCorr": [[1, 0.3, 50]],
        "calib": {"pred": [0.1, 0.5], "act": [0.1, 0.4]},
        "watchClass": [["P", "QB", 90, 1.0, 0.5]],
        "transfers": [["P", "QB", "X", 1.0]],
        "programs": [["Penn State", 0.0, 1.9, -1.9, 5.6], ["Other", 0.1, 0.2, -1.0, 1.0]],
        "portalGroups": [["Group", 10, -3.0]],
        "weights": {p: 1.0 for p in POS},
        "openings": {p: 2.0 for p in POS},
        "yields": {p: [0.4, 0.6, 1.5, 1.0, 2.0] for p in POS},
        "modules": [["M", "Done", "Does"]],
    }


if __name__ == "__main__":
    import sys
    json.dump(fixture(), open(sys.argv[1], "w"))
