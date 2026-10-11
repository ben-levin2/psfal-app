"""Read-only reader for the validated PSFAL Child 15 report (child15/big_ten_benchmark.md).

This module only PARSES numbers that the validated Child 15 module already wrote into the saved report. It never recomputes a benchmark value,
never reads the team-season CSV, and makes no network calls. If the report is missing or does not have the expected structure it raises
ReportError so the dashboard can show a clear message instead of any substitute number.
"""
import hashlib
import re
from pathlib import Path

REPORT_PATH = Path(__file__).parent / "big_ten_benchmark.md"

METRICS = ["SP+ overall", "SP+ offense", "SP+ defense", "PPA offense", "PPA defense", "Win percentage", "Recruiting points (4-yr)", "Talent composite"]
GROUPS = {  # report heading -> short key
    "Season-specific Big Ten peers (primary)": "peers",
    "Fixed 18-team Big Ten set (sensitivity)": "fixed18",
    "National table average": "national",
    "National champions": "champions",
}
WINDOWS = {"Window 2014-2025": "2014-2025", "Window 2021-2025": "2021-2025"}
EXPECTED_HEADER = ["Metric", "Penn State", "Group mean", "Raw gap (PSU - group)", "Gap in SD (+ = PSU better)", "Distinct programs / team-seasons"]


class ReportError(Exception):
    """The saved Child 15 report is missing or not in the expected format."""


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_report(text):
    """Return {'windows': {win: {'groups': {key: {metric: row}}, 'champion_sample': (team_seasons, programs)}}, 'reproduction': {...}}."""
    windows, win, grp, hdr_seen = {}, None, None, False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("## "):
            title = s[3:].strip()
            win = next((v for k, v in WINDOWS.items() if title.startswith(k)), None)
            grp = None
            if win:
                windows[win] = {"groups": {}, "champion_sample": None, "heading": title}
            continue
        if win is None:
            continue
        if s.startswith("### "):
            grp = GROUPS.get(s[4:].strip())
            hdr_seen = False
            if grp:
                windows[win]["groups"][grp] = {}
            continue
        m = re.match(r"Champion sample in this window: (\d+) champion team-seasons across (\d+) distinct programs", s)
        if m:
            windows[win]["champion_sample"] = (int(m.group(1)), int(m.group(2)))
            continue
        if grp and s.startswith("|"):
            c = _cells(s)
            if c[0] == "Metric":
                if c != EXPECTED_HEADER:
                    raise ReportError(f"Unexpected table header in the Child 15 report: {c}")
                hdr_seen = True
            elif hdr_seen and not set(s) <= set("|-: "):
                if c[0] not in METRICS:
                    raise ReportError(f"Unexpected metric row in the Child 15 report: {c[0]!r}")
                m2 = re.fullmatch(r"(\d+) / (\d+)", c[5])
                if len(c) != 6 or not m2:
                    raise ReportError(f"Malformed row in the Child 15 report: {s}")
                windows[win]["groups"][grp][c[0]] = {
                    "penn_state": float(c[1]), "group_mean": float(c[2]), "raw_gap": float(c[3]), "gap_sd": float(c[4]),
                    "programs": int(m2.group(1)), "team_seasons": int(m2.group(2))}
    for w in WINDOWS.values():
        if w not in windows:
            raise ReportError(f"The Child 15 report has no section for {w}.")
        if windows[w]["champion_sample"] is None:
            raise ReportError(f"The Child 15 report has no champion sample line for {w}.")
        for g in GROUPS.values():
            got = windows[w]["groups"].get(g)
            if not got or list(got) != METRICS:
                raise ReportError(f"The Child 15 report is missing or has incomplete metrics for {w} / {g}.")
    rep = {}
    m = re.search(r"Cells matching published figures within rounding: (\d+) of (\d+)", text)
    if m:
        rep["match"] = (int(m.group(1)), int(m.group(2)))
    m = re.search(r"Membership: (14 programs labelled Big Ten for 2014-2023.*?)\n", text)
    if m:
        rep["membership"] = m.group(1).strip()
    return {"windows": windows, "reproduction": rep}


def load_report(path=None):
    """Read and parse the saved report. Returns (parsed, info) where info has the file's sha256 and size. Raises ReportError if unusable."""
    p = Path(path) if path else REPORT_PATH
    try:
        raw = p.read_bytes()
    except OSError as ex:
        raise ReportError(f"The saved Child 15 report could not be read ({p.name}: {type(ex).__name__}).") from ex
    try:
        parsed = parse_report(raw.decode("utf-8"))
    except UnicodeDecodeError as ex:
        raise ReportError("The saved Child 15 report is not valid text.") from ex
    return parsed, {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
