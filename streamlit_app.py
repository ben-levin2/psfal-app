"""Penn State Football Analytics Lab (Streamlit dashboard).

Data comes from dashboard_data.json next to this file. To update the numbers without touching the app, set PSFAL_DATA_URL (an environment
variable or a Streamlit secret named data_url) to a link that returns the same JSON; the app falls back to the bundled file if the link fails.

Navigation: Home, the five research families (Recruiting High Schoolers, Transfer Portal, Player Development, Roster Construction, Competitive
Edge Research), and two further destinations (2026 Games, Research & Methods). Shared styling is in ui.py and .streamlit/config.toml.
"""
import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import data_check
import ui
from ui import ACCENT, BADGE, BAD, INK, LIGHT, NEUTRAL, PSU

st.set_page_config(page_title=ui.APP_NAME, page_icon="🦁", layout="wide")

HERE = Path(__file__).parent
POS = ["QB", "RB", "WR", "TE", "DL", "LB", "DB"]
SEASON = 2026


def _today():
    """Today's date at Penn State (Eastern time), used to tell games already played from games still to come. PSFAL_TODAY (YYYY-MM-DD)
    overrides it; the tests use that to fix the date."""
    if os.environ.get("PSFAL_TODAY"):
        return date.fromisoformat(os.environ["PSFAL_TODAY"])
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date()
    except Exception:
        return datetime.now(timezone.utc).date()


def _secret(name):
    try:
        return st.secrets.get(name, "")
    except Exception:
        return ""


def _secret_names():
    try:
        return sorted(st.secrets.keys())
    except Exception:
        return []


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_ok(url):
    """A successful read is kept for 10 minutes, so an update to the linked file shows within 10 minutes. A failed read raises, and
    Streamlit does not cache a call that raises, so it is not remembered as data."""
    import urllib.request
    with urllib.request.urlopen(url, timeout=10) as r:
        d = json.loads(r.read().decode())
    if not isinstance(d, dict) or not d:  # e.g. {}: no dashboard data. Raising keeps it out of the 10-minute cache (the same rule as data_check)
        raise ValueError("not a non-empty JSON object")
    return d


@st.cache_resource
def _fetch_failures():
    return {}  # link -> when it last failed; shared by every viewer of this app process (see data_check.fetch_with_retry)


def load_data():
    """Order: a link (PSFAL_DATA_URL or secret data_url), then secret data_b64 or data_json, then dashboard_data.json next to this file.
    A failed link is tried again on a later page load (at most once every data_check.RETRY_WAIT seconds), so a fixed link or secret
    takes effect without a restart. No link or secret value is ever shown."""
    import time
    notes = []
    url = os.environ.get("PSFAL_DATA_URL", "") or _secret("data_url")
    if url:
        d, note = data_check.fetch_with_retry(url, _fetch_ok, _fetch_failures(), time.monotonic())
        if d is not None:
            return d, "live file", notes
        notes.append(note)
    b64 = _secret("data_b64")
    if b64:
        try:
            import base64
            return json.loads(base64.b64decode(b64).decode("utf-8")), "app secret", notes
        except Exception as ex:
            notes.append(f"data_b64 was found but could not be decoded ({type(ex).__name__})")
    raw = _secret("data_json")
    if raw:
        try:
            return json.loads(raw), "app secret", notes
        except Exception as ex:
            notes.append(f"data_json was found but could not be read as JSON ({type(ex).__name__})")
    f = HERE / "dashboard_data.json"
    if f.exists():
        return json.loads(f.read_text()), "bundled snapshot", notes
    return None, "none", notes


D, SOURCE, NOTES = load_data()

# Drop only stale schedule annotations that explicitly record a result already present in games.
# This keeps a hand-maintained/secret snapshot from showing an already-played game as still scheduled.
def _remove_result_annotated_schedule_rows(data):
    if not isinstance(data, dict) or not isinstance(data.get("schedule"), list) or not isinstance(data.get("games"), list):
        return
    results = set()
    for game in data["games"]:
        if not isinstance(game, dict):
            continue
        opponent = re.sub(r"\(.*?\)", "", str(game.get("opp", ""))).split(",", 1)[0].strip().lower()
        results.add((opponent, str(game.get("res", "")).upper(), game.get("pf"), game.get("pa")))
    cleaned = []
    for row in data["schedule"]:
        if isinstance(row, (list, tuple)) and len(row) > 1:
            opponent = str(row[1])
            note = re.search(r",\s*played:\s*([WL])\s+(\d+)[–-](\d+)", opponent, re.IGNORECASE)
            if note:
                base = re.sub(r"\(.*?\)", "", opponent).split(",", 1)[0].strip().lower()
                result = (base, note.group(1).upper(), int(note.group(2)), int(note.group(3)))
                if result in results:
                    continue
        cleaned.append(row)
    data["schedule"] = cleaned


_remove_result_annotated_schedule_rows(D)
ui.inject_css()


def _gate():
    """Optional passcode. If a Streamlit secret named app_password exists, nothing is shown until it is entered (a simple lock, not strong security)."""
    try:
        pw = st.secrets.get("app_password", "")
    except Exception:
        pw = ""
    if not pw or st.session_state.get("unlocked"):
        return
    st.title(ui.APP_NAME)
    entered = st.text_input("Passcode", type="password")
    if entered and entered == pw:
        st.session_state["unlocked"] = True
        st.rerun()
    elif entered:
        st.error("That passcode is not right.")
    st.stop()


_gate()
if D is None:
    st.title(ui.APP_NAME)
    st.error("No data found. Add dashboard_data.json next to this app, or set the secret data_b64 (or data_json) in the app settings.")
    with st.expander("What the app can see (names only, no values)", expanded=True):
        st.write({"secret names found": _secret_names(), "problems": NOTES or ["none"], "dashboard_data.json next to the app": (HERE / "dashboard_data.json").exists()})
    st.stop()


def style(fig, height=None, legend=True):
    # The legend sits above the plot area with its own top margin, so it never covers bars, markers or labels.
    fig.update_layout(margin=dict(l=10, r=10, t=48 if legend else 16, b=10), showlegend=legend,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
    if height:
        fig.update_layout(height=height)
    return fig


def grouped_dots(labels, series, colors, xrange=None, fmt="%{x:.2f}", height=None):
    """Signed values for several groups per row, as dots on thin stems from zero (less ink than grouped bars, and the value is where the dot is).
    Each group is one trace named after the group, with its values as x and its formatted labels as text. `fmt` is a Plotly-style format such
    as '%{x:+.2f}'; labels are formatted in Python (see ui.labels)."""
    fig = go.Figure()
    k = len(series)
    off = [(j - (k - 1) / 2) * 0.24 for j in range(k)]  # each group's place within a row
    rows = list(range(len(labels)))
    for j, ((name, vals), col) in enumerate(zip(series, colors)):
        ys = [r + off[j] for r in rows]
        sx, sy = [], []
        for x, y in zip(vals, ys):
            sx += [0, x, None]; sy += [y, y, None]
        fig.add_scatter(x=sx, y=sy, mode="lines", line=dict(color=col, width=2.5), hoverinfo="skip", showlegend=False, name=f"{name} (stem)")
        text = ui.labels(vals, fmt)
        fig.add_scatter(x=vals, y=ys, mode="markers+text", name=name, text=text, textposition=["middle right" if v >= 0 else "middle left" for v in vals],
                        textfont=dict(size=11, color=INK), cliponaxis=False,
                        marker=dict(color=col, size=11, line=dict(color=PSU if col == LIGHT else "white", width=1.5)),
                        customdata=labels, hovertemplate=f"%{{customdata}}<br>{name}: %{{text}}<extra></extra>")
    fig.update_layout(yaxis=dict(autorange="reversed", tickmode="array", tickvals=rows, ticktext=labels, showgrid=False, zeroline=False))
    for r in rows[1:]:  # light separators between rows
        fig.add_hline(y=r - 0.5, line=dict(color="#E6ECF3", width=1), layer="below")
    if xrange:
        fig.update_xaxes(range=xrange)
        fig.add_vrect(x0=xrange[0], x1=0, fillcolor="#F3F5F8", line_width=0, layer="below")
        for x, anchor, text in ((xrange[0], "left", "◀ Penn State behind"), (xrange[1], "right", "Penn State ahead ▶")):
            fig.add_annotation(x=x, y=1, yref="paper", yanchor="bottom", xanchor=anchor, showarrow=False, text=text, font=dict(size=11, color=ui.AXIS_INK))
    return style(fig, height or max(260, 30 * len(labels) * max(k, 1) + 80)).update_layout(margin=dict(t=76), legend=dict(y=1.08))


# ---------------------------------------------------------------- findings (wording unchanged; Home features four, Research & Methods lists all eight)
FINDINGS = [
    ("Penn State beats nearly everyone below the elite tier. It is 66–9 against teams outside the top 50 by SP+ and 5–22 against the top 10.", "descriptive"),
    ("The biggest gap to national champions is offense, and passing most of all. Defense is close to playoff level.", "descriptive"),
    ("This year's roster turnover is the largest in the data. Only 27% of last year's producers returned, against a previous low of 57%.", "descriptive"),
    ("The Northwestern loss was mostly one game of run defense (427 yards). The Wisconsin loss was an offense that could not move.", "descriptive"),
    ("Across 15 programs, no repeatable type of undervalued recruit showed up. Recruiting ratings explain only about a quarter of production.", "tested"),
    ("A transfer's portal rating predicts how he produces, and transfers from non-FBS schools produce less.", "tested"),
    ("The roster forecast did not beat a flat guess for any single position. Plan on about 64% of the roster returning.", "tested"),
    ("A transfer is the better use of a roster spot only if he costs less than about 1.5 times a recruit's spot. Nobody has the real cost.", "assumption"),
]


# Home cards: a shorter supporting line under each card's statistic. Each drops only what the statistic above it already says; the full
# wording is unchanged in FINDINGS and shown in Research & Methods.
CARD_TEXT = {
    0: "Penn State beats nearly everyone below the elite tier: 66–9 against teams outside the SP+ top 50.",
    1: "Offense is the biggest gap, passing most of all. Defense is close to playoff level.",
    4: "Recruiting ratings explain only about a quarter of production.",
    7: "A transfer is the better use of a spot only below that cost. Nobody has the real cost.",
}


# ---------------------------------------------------------------- decision-tool state (kept when the reader moves between pages)
def _set_weights():
    for p in POS:
        st.session_state[f"w_{p}"] = float(D["weights"][p]) if st.session_state.get("preset") == "Sized by the gap to champions" else 1.0


def _reset():
    st.session_state["preset"] = "Every position counts the same"
    for p in POS:
        st.session_state[f"s_{p}"] = round(float(D["openings"][p]), 1)
        st.session_state[f"w_{p}"] = 1.0


for p in POS:
    st.session_state.setdefault(f"s_{p}", round(float(D["openings"][p]), 1))
    st.session_state.setdefault(f"w_{p}", 1.0)
st.session_state.setdefault("preset", "Every position counts the same")
st.session_state.setdefault("cost", 2.0)

REC_SUBS = ["Recruiting Intelligence", "Recruit Development Forecast", "Market Inefficiency Model"]
TRN_SUBS = ["Transfer Production Translation", "Transfer Portal Analytics"]
DEV_SUBS = ["Player Development Analytics", "Development Trajectory & Breakout Forecast"]
ROS_SUBS = ["Roster Analytics", "Retention & Continuity Forecast", "Decision Tool"]
CER_SUBS = ["Championship Gap", "Big Ten Competitive Intelligence", "Game Analytics"]
RM_SUBS = ["All findings", "Module status", "Limitations & methods"]
ui.keep_state([f"s_{p}" for p in POS] + [f"w_{p}" for p in POS] + ["preset", "cost", "c15_window", "c15_fixed",
                                                                    "sub_rec", "sub_trn", "sub_dev", "sub_ros", "sub_cer", "sub_rm"])


def _status(*names):
    ui.module_status(D.get("modules", []), names)


# ================================================================ Home
def home():
    games = D["games"]
    missing, upcoming = _schedule_status()
    wins = sum(g.get("res") == "W" for g in games)
    losses = sum(g.get("res") == "L" for g in games)
    last, unclear = data_check.latest_game(games)

    st.subheader("Team snapshot")
    if missing:
        _missing_results_note(missing)
    c = st.columns(4)
    with c[0]:
        ui.stat_tile("record", "2026 record", f"{wins}–{losses}", f"Games through week {D['meta']['through_week']}"
                     + (f" in the data; {len(missing)} later {'game' if len(missing) == 1 else 'games'} not yet added" if missing else ""))
    with c[1]:
        if last:
            ui.stat_tile("last", "Latest result in the data" if missing else "Latest result", f"{last['res']} {last['pf']}–{last['pa']}", f"Week {last['wk']} · {last['opp']}")
        elif unclear:
            ui.stat_tile("last", "Latest result", "Unclear", f"Check the data: {unclear}")
    with c[2]:
        if upcoming:
            opp, note = ui.split_note(upcoming[0][1])
            ui.stat_tile("next", "Next game", opp, " · ".join(x for x in (upcoming[0][0], upcoming[0][2], note) if x))
        else:
            ui.stat_tile("next", "Next game", "None left", "No remaining games on the schedule in the data")
    with c[3]:
        ui.stat_tile("left", "Games left", len(upcoming), "On the remaining schedule")

    st.subheader("Key Findings")
    # (question, key statistic, what the statistic is, index into FINDINGS, sub-section to open, link text, page, sub-section key)
    cards = [
        ("How does Penn State do against elite teams?", "5–22", "Against the SP+ top 10", 0, "Championship Gap", "Open the championship gap analysis", CER, "sub_cer"),
        ("Where is the gap to champions largest?", "1.57 SD", "Behind champions in passing, 2021 to 2025", 1, "Championship Gap", "Open the championship gap analysis", CER, "sub_cer"),
        ("Do some recruits beat their ratings in a repeatable way?", "None found", "Repeatable undervalued recruit types, 15 programs", 4, "Market Inefficiency Model", "Open recruiting and portal results", REC, "sub_rec"),
        ("Recruit or transfer for an open roster spot?", "About 1.5×", "Break-even cost of a transfer spot vs a recruit's", 7, "Decision Tool", "Open the decision tool", ROS, "sub_ros"),
    ]
    for row in (cards[:2], cards[2:]):
        cols = st.columns(2)
        for col, (q, stat, stat_label, fi, sub, link, page, sub_key) in zip(cols, row):
            with col:
                with st.container(border=True, key=f"card_finding_{fi}"):
                    st.markdown(f"{BADGE[FINDINGS[fi][1]]}  **{q}**")
                    st.metric(stat_label, stat)
                    st.write(CARD_TEXT[fi])
                    ui.open_analysis(link, page, sub_key, sub, key=f"go_finding_{fi}")
    ui.open_analysis("All eight findings and what the evidence labels mean", RESEARCH, "sub_rm", "All findings", key="go_all_findings")

    st.subheader("This season: numbers to watch")
    w = st.columns(max(len(D["watch"]), 1))
    for i, (c, x) in enumerate(zip(w, D["watch"])):
        good = x["now"] >= x["ref"] if x["better"] == "high" else x["now"] <= x["ref"]
        unit = "%" if "rate" in x["label"].lower() else ""
        value = f"{x['now']:.1f}{unit}" if unit else f"{x['now']:.1f}"
        with c:
            with st.container(border=True, key=f"tile_watch_{i}"):
                st.markdown(f"{x['label']}: **{value}**  \n" + (":green[At or above the benchmark]" if good else ":red[Below the benchmark]")
                            + f" :gray[· benchmark {x['refLabel']}]")
                st.caption(data_check.watch_coverage_line(D, x["label"]))  # each card's own stated coverage; never taken from the snapshot date
    ui.open_analysis("Game-by-game analysis, schedule and results", GAMES, key="go_games")


def _schedule_status():
    """(played but missing a result, still to come). A past-dated schedule row whose opponent is already in the results is neither: the
    data check reports it as listed twice, so it is not also called a missing result."""
    missing, upcoming = ui.split_schedule(D["schedule"], _today(), SEASON)
    twice = data_check.played_and_listed(D["schedule"], D["games"], _today(), SEASON)
    return [r for r in missing if r not in twice], upcoming


def _missing_results_note(missing):
    """Games whose date has passed but whose result is not in this data snapshot. Their scores are not known to the app, so none is shown."""
    names = ", ".join(f"{ui.split_note(r[1])[0]} ({r[0]})" for r in missing)
    st.warning(f"Already played, result not in this data yet: {names}. The data snapshot is from {D['meta']['snapshot']}, so the record, latest result "
               f"and game charts stop at week {D['meta']['through_week']}. Add the result to the data file to bring them up to date.", icon=":material/update:")


# ================================================================ 2026 Games (standalone)
def games_2026():
    games = D["games"]
    st.subheader("Each game against Penn State's own history")
    st.write("Per-play efficiency scored against Penn State's 156 earlier games. 100 is the best Penn State game since 2014 and 0 is the worst.")
    charted = data_check.results_weeks(games)  # rows without a whole-number week are in the table below but cannot be placed on the chart
    if charted:
        by_week = {g["wk"]: g for g in charted}
        weeks = list(range(min(by_week), max(by_week) + 1))  # weeks without a game stay empty, so the lines break instead of bridging them
        fig = go.Figure()
        for name, key, other, col, sym in (("Offense", "o", "d", PSU, "circle"), ("Defense", "d", "o", ACCENT, "square")):
            ys = [by_week[w][key] if w in by_week else None for w in weeks]
            # in each week the higher of the two values is labelled above its point and the lower one below, so labels never sit on the other marker
            pos = ["top center" if w in by_week and (by_week[w][key] > by_week[w][other] or (by_week[w][key] == by_week[w][other] and key == "o")) else "bottom center" for w in weeks]
            cd = [[w, by_week[w]["opp"], f"{by_week[w]['res']} {by_week[w]['pf']}–{by_week[w]['pa']}"] if w in by_week else [w, "", ""] for w in weeks]
            fig.add_scatter(x=weeks, y=ys, name=name, mode="lines+markers+text", text=[("" if v is None else f"{v:.0f}") for v in ys],
                            textposition=pos, textfont=dict(size=12, color=INK), line=dict(color=col, width=2.5),
                            marker=dict(color=col, size=11, symbol=sym, line=dict(color="white", width=1.5)), connectgaps=False,
                            customdata=cd, hovertemplate=f"Week %{{customdata[0]}}: %{{customdata[1]}} (%{{customdata[2]}})<br>{name}: %{{y:.0f}} of 100<extra></extra>")
        def tick(w):  # week, opponent, result; an away game's "at" moves up to the week line so the labels stay narrow enough for phones
            if w not in by_week:
                return f"Wk {w}"
            g = by_week[w]
            away = str(g["opp"]).startswith("at ")
            res = f"<span style='color:{ui.GOOD if g['res'] == 'W' else ui.BAD}'><b>{g['res']} {g['pf']}–{g['pa']}</b></span>"  # the letter W or L carries the meaning too
            return f"Wk {w}{' · at' if away else ''}<br>{g['opp'][3:] if away else g['opp']}<br>{res}"
        fig.update_xaxes(tickvals=weeks, ticktext=[tick(w) for w in weeks], title=None, range=[weeks[0] - 0.5, weeks[-1] + 0.5],  # half a week of room so the first and last labels fit on phones
                         tickangle=0, tickfont=dict(size=11))  # kept level: Plotly turned these three-line labels sideways on narrow screens
        fig.update_yaxes(range=[-8, 108], title="Score against Penn State's earlier games (0 to 100)")  # room for labels below 0 and above 100
        # each score is the share of earlier games this one beat (the research code computes it that way), so 50 is the median earlier game
        fig.add_hrect(y0=50, y1=108, fillcolor=ui.SHADE, line_width=0, layer="below")  # better than half of the earlier games
        fig.add_hline(y=50, line=dict(color=NEUTRAL, width=1, dash="dot"), layer="below")
        fig.add_scatter(x=[None], y=[None], mode="markers", name="Shaded: better than half of the earlier games", hoverinfo="skip",
                        marker=dict(symbol="square", size=13, color=ui.SHADE, line=dict(color=LIGHT, width=1)))  # legend key for the shaded band
        ui.plot(style(fig, 410))
        st.caption("Above the dotted line at 50 (shaded), a game was better than half of Penn State's earlier games. Opponents differ in strength and the season is a handful of games, so a line moving up or down is not by itself proof that the team "
                   "is improving or slipping.")
    st.subheader("What stood out")
    ui.table(pd.DataFrame([{"Week": g["wk"], "Opponent": g["opp"], "Result": f"{g['res']} {g['pf']}–{g['pa']}", "What stands out": g["note"]} for g in games]), "results")
    st.subheader("Three numbers to watch")
    w = st.columns(max(len(D["watch"]), 1))
    for i, (c, x) in enumerate(zip(w, D["watch"])):
        good = x["now"] >= x["ref"] if x["better"] == "high" else x["now"] <= x["ref"]
        unit = "%" if "rate" in x["label"].lower() else ""
        with c:
            with st.container(border=True, key=f"tile_g26watch_{i}"):
                st.metric(x["label"], f"{x['now']:.1f}{unit}" if unit else f"{x['now']:.1f}")
                st.caption(f"Benchmark: {x['refLabel']}")
                st.markdown(":green[At or above the benchmark]" if good else ":red[Below the benchmark]")
                st.caption(data_check.watch_coverage_line(D, x["label"]))
    st.caption("Improvement across several games would point to a team still coming together. One game proves little.")
    missing, upcoming = _schedule_status()
    if missing:
        st.subheader("Played, result not in the data yet")
        _missing_results_note(missing)
        ui.table(pd.DataFrame([[r[0], ui.split_note(r[1])[0], r[2], "Not in this data snapshot"] for r in missing], columns=["Date", "Opponent", "Site", "Result"]), "missing")
    st.subheader("Games left")
    if upcoming:
        ui.table(pd.DataFrame(upcoming, columns=["Date", "Opponent", "Site"]), "schedule")
    else:
        st.write("No remaining games on the schedule in the data.")
    bye = ui.game_date("Oct 24", SEASON)
    st.caption(("There is a bye on October 24. " if _today() <= bye else "") + "Confirm the away dates on the official schedule.")


# ================================================================ 1. Recruiting High Schoolers
def _recruiting_intelligence():
    _status("Recruiting intelligence")
    st.markdown("**A rating matters most early**  " + BADGE["descriptive"])
    ui.table(pd.DataFrame(D["ratingCorr"], columns=["Year", "Correlation", "Players"]), "rating_corr", {"Correlation": "{:.2f}"})
    st.caption("Penn State's recruiting class rank for each season is in the season-by-season table under Competitive Edge Research. "
               "The recruiting module's class makeup, geography and retention results are not included in this dashboard's data.")
    ui.open_analysis("Season-by-season class ranks", CER, "sub_cer", "Championship Gap", key="go_class_ranks")


def _recruit_forecast():
    st.markdown("**Penn State's 2025 class: most likely strong producers by 2027**")
    wc = pd.DataFrame(D["watchClass"], columns=["Player", "Pos", "Rating", "2025 output", "Chance"])
    wc["Chance"] = (wc["Chance"] * 100).round(0).astype(int)  # same rounding as before; kept as a number so the column sorts numerically
    ui.table(wc, "watch_class", {"Rating": "{:.2f}", "Chance": "{:d}%"})
    st.caption("A ranking aid with wide uncertainty.")
    ui.open_analysis("Related: who becomes a strong producer by year 3, and its calibration check", DEV, "sub_dev", "Development Trajectory & Breakout Forecast", key="go_forecast_check")


def _market():
    _status("Market inefficiency")
    st.subheader("Do some programs get more from their recruits than ratings predict?  " + BADGE["tested"])
    st.write("Average gap between actual production and what a recruit's rating, year and position predict, in percentile points. The solid dot is the later classes (2020 to 2022) with its 95% range; the open dot is the earlier classes (2016 to 2019).")
    P = pd.DataFrame(D["programs"], columns=["Program", "Earlier", "Later", "Low", "High"])
    rng = [f"{lo:+.1f} to {hi:+.1f}" for lo, hi in zip(P["Low"], P["High"])]
    P["Rank"] = P["Later"].rank(ascending=False, method="min").astype(int)  # place among the programs on the later classes, as stated below
    fig = go.Figure()
    is_psu = P["Program"] == "Penn State"
    # Penn State's row on a Pugh Blue band, its dot in navy; the other programs in slate and grey
    fig.add_scatter(x=P["Later"], y=P["Program"], mode="markers", name="Later classes, 2020–22 (95% range)",
                    marker=dict(color=[PSU if p else ACCENT for p in is_psu], size=[13 if p else 10 for p in is_psu], line=dict(color="white", width=1.5)),
                    error_x=dict(type="data", symmetric=False, array=P["High"] - P["Later"], arrayminus=P["Later"] - P["Low"], color=NEUTRAL, thickness=2, width=4),
                    customdata=list(zip(ui.labels(P["Later"], "%{x:+.1f}"), rng, P["Rank"])),
                    hovertemplate="Later classes: %{customdata[0]} percentile points (95% range %{customdata[1]}), "
                                  f"rank %{{customdata[2]}} of {len(P)}<extra></extra>")
    fig.add_scatter(x=P["Earlier"], y=P["Program"], mode="markers", name="Earlier classes, 2016–19",
                    marker=dict(symbol="circle-open", size=10, color=[PSU if p else NEUTRAL for p in is_psu], line=dict(width=2)),
                    customdata=ui.labels(P["Earlier"], "%{x:+.1f}"), hovertemplate="Earlier classes: %{customdata} percentile points<extra></extra>")
    psu = P[is_psu]
    if len(psu):
        r = psu.iloc[0]
        fig.add_shape(type="rect", xref="paper", x0=0, x1=1, y0=r["Program"], y1=r["Program"], line=dict(color=ui.SHADE, width=32), layer="below")
    fig.add_vline(x=0, line_color=PSU, line_width=1.5)
    for x, anchor, text in ((-0.3, "right", "◀ Less than ratings predict"), (0.3, "left", "More ▶")):
        fig.add_annotation(x=x, y=1, yref="paper", yanchor="bottom", xanchor=anchor, showarrow=False, text=text, font=dict(size=11, color=ui.AXIS_INK))
    fig.update_layout(hovermode="y unified", yaxis=dict(autorange="reversed", tickmode="array", tickvals=P["Program"],
                                                        # Penn State's later-classes value and 95% range under its name
                                                        ticktext=[f"<b>{p}</b><br><span style='color:{PSU}'>{lt:+.1f} ({l:+.1f} to {h:+.1f})</span>" if p == "Penn State" else p
                                                                  for p, lt, l, h in zip(P["Program"], P["Later"], P["Low"], P["High"])]))
    lo = min(P["Low"].min(), P["Earlier"].min()); hi = max(P["High"].max(), P["Earlier"].max())
    fig.update_xaxes(title="Gap in percentile points", range=[lo - 1, hi + 1])
    fig = style(fig, 600).update_layout(margin=dict(t=74), legend=dict(y=1.075))
    ui.plot(fig)
    st.write("Programs' earlier and later gaps correlate weakly (**0.38** across 15 programs), so differences are suggestive and not conclusive. Penn State ranks 2nd of 15 in the later classes at +1.9, "
             "but its range (−1.9 to +5.6) includes zero. Size for position passed the test with a tiny effect (a correlation of 0.08), and in-state recruits showed nothing.")


def recruiting():
    sub = ui.subnav("sub_rec", REC_SUBS)
    {"Recruiting Intelligence": _recruiting_intelligence, "Recruit Development Forecast": _recruit_forecast, "Market Inefficiency Model": _market}[sub]()


# ================================================================ 2. Transfer Portal
def _transfer_translation():
    _status("Transfer portal")
    st.subheader("What predicts how a transfer produces at his new school?  " + BADGE["tested"])
    st.write("709 portal arrivals into Penn State and 14 peers (2021 to 2025); 544 could be matched to a roster. Gap = production percentile minus the average transfer at his position.")
    G = D["portalGroups"]
    # each origin group with its number of transfers under the name; above the average in navy, below it in slate (below average is not "bad", only lower)
    fig = go.Figure(go.Bar(y=[f"<b>{r[0]}</b><br><span style='color:{ui.AXIS_INK}'>{r[1]} transfers</span>" for r in G], x=[r[2] for r in G], orientation="h", width=0.55,
                           marker=dict(color=[PSU if r[2] >= 0 else ACCENT for r in G], cornerradius=4),
                           text=ui.labels([r[2] for r in G], "%{x:+.1f}"), texttemplate="<b>%{text}</b>", textposition="outside", cliponaxis=False, textfont=dict(size=13, color=INK),
                           customdata=[[r[0], r[1]] for r in G], hovertemplate="%{customdata[0]}: %{text} percentile points against the average transfer at his position "
                                                                              "(%{customdata[1]} transfers)<extra></extra>"))
    fig.add_vline(x=0, line_color=PSU, line_width=1.5)
    fig.add_annotation(x=0, y=1, yref="paper", yanchor="bottom", xanchor="right", xshift=-4, showarrow=False, text="0 = the average transfer at his position",
                       font=dict(size=11, color=ui.AXIS_INK))
    fig.update_layout(yaxis=dict(autorange="reversed"), bargap=0.35); fig.update_xaxes(range=[-18, 6], title="Gap in percentile points")
    ui.plot(style(fig, 300, legend=False).update_layout(margin=dict(t=30)))
    st.markdown("- **The portal rating carries information.** Rank correlation with production at the new school was 0.31, then 0.37 in the later classes (range 0.27 to 0.47).\n"
                "- **Step-up transfers produce less, mostly because of one group.** Transfers from outside the top 65 or from non-FBS schools produced 3.1 points less, then 8.6 less (range 2.8 to 14.4). Nearly all of it is the last row above.\n"
                "- **Within FBS the gap is small.** Lower-ranked FBS origins were 3.9 points lower than top-65 ones, which cannot be told apart from zero (range −9.9 to +2.3). After allowing for the rating, the overall gap is about 5 points. Those two checks were exploratory.")
    ui.open_analysis("Recruit or transfer for an open spot: the decision tool", ROS, "sub_ros", "Decision Tool", key="go_decision_from_portal")


def _transfer_analytics():
    st.markdown("**Penn State's 2026 transfers: highest production so far**")
    ui.table(pd.DataFrame(D["transfers"], columns=["Player", "Pos", "From", "So far"]), "transfers")
    cov = data_check.coverage(D).get("transfers")
    # how many games the statistics cover: from meta.coverage.transfers when the data state it; otherwise the count is not claimed
    games_part = (data_check.count_words(data_check.games_through(D, cov)).capitalize() if cov is not None
                  else "The number of games covered is not stated in the data")
    st.caption(f"{games_part}, ranked within Penn State's own position groups. Eight of the ten are Iowa State transfers; that does not show they are better than other transfers.")
    st.caption(data_check.coverage_note(D, "transfers"))
    st.caption("The transfer module's team-level study (how teams change from one year to the next after taking many portal arrivals) is not included in this dashboard's data.")


def transfer_portal():
    sub = ui.subnav("sub_trn", TRN_SUBS)
    {"Transfer Production Translation": _transfer_translation, "Transfer Portal Analytics": _transfer_analytics}[sub]()


# ================================================================ 3. Player Development
def _development_analytics():
    _status("Development")
    st.subheader("Production by year in the program, for recruits who stayed")
    st.write("Average production percentile among players at the same position. Later years include only players who stayed, so catching up is partly who remained.")
    T = D["traj"]
    fig = go.Figure()
    for name, key, col, sym in (("4 and 5 stars", "star45", PSU, "circle"), ("3 stars", "star3", LIGHT, "diamond"), ("2 stars or fewer", "star2", ACCENT, "square")):
        fig.add_scatter(x=T["years"], y=T[key], mode="lines+markers", name=name, line=dict(color=col, width=3.5),
                        marker=dict(symbol=sym, size=10, color=col, line=dict(color=PSU if col == LIGHT else "white", width=1.5)),
                        hovertemplate=f"{name}: percentile %{{y:.0f}}<extra></extra>")
        fig.add_annotation(x=T["years"][-1], y=T[key][-1], text=f"<b>{T[key][-1]:.0f}</b>", showarrow=False, xanchor="left", xshift=9, font=dict(size=12, color=INK))
    # the two upper lines end two points apart in year 5; nudge their names apart so they do not overlap
    ends = sorted(range(3), key=lambda i: -fig.layout.annotations[i].y)
    for rank, i in enumerate(ends[:2]):
        if abs(fig.layout.annotations[ends[0]].y - fig.layout.annotations[ends[1]].y) < 6:
            fig.layout.annotations[i].yshift = 9 if rank == 0 else -9
    fig.add_hline(y=50, line=dict(color=NEUTRAL, width=1, dash="dot"), layer="below")  # a percentile scale: 50 is the middle player at the position
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(title="Year in the program", tickvals=T["years"], range=[0.8, T["years"][-1] + 0.4], tickprefix="Year ", hoverformat="d")
    fig.update_yaxes(range=[0, 100], title="Production percentile (50 = middle of the position group)")
    ui.plot(style(fig, 360))
    st.markdown("**Production carries over, improvement does not**  " + BADGE["descriptive"])
    st.write("A player's production percentile correlates **0.71** with his next-year percentile. His year-to-year change correlates **−0.27** with the change the year before "
             "(partly because percentiles stop at 0 and 100). A score built on improvement is not supported. Some players do keep beating their recruiting profile (0.54).")


def _breakout_forecast():
    st.subheader("Who becomes a strong producer by year 3?  " + BADGE["tested"])
    st.write("**First-year production helps, modestly.** Accuracy (AUC; 0.5 is a coin flip) rose from 0.65 with rating and position to 0.73 once first-year production was added "
             "(gain +0.07, range +0.05 to +0.11). Among slow starters, top-third-rated recruits became strong producers 12 points more often than bottom-third ones (range +3.5 to +21.5).")
    C = D["calib"]
    fig = go.Figure()
    fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", name="Perfect match", line=dict(color=NEUTRAL, dash="dash"), hoverinfo="skip")
    fig.add_scatter(x=C["pred"], y=C["act"], mode="lines+markers", name="Five groups, least to most likely", line=dict(color=PSU, width=3),
                    marker=dict(size=10, color=PSU, line=dict(color="white", width=1.5)),
                    customdata=[[i + 1, a - p] for i, (p, a) in enumerate(zip(C["pred"], C["act"]))],
                    hovertemplate="Group %{customdata[0]} of 5: predicted %{x:.0%}, actually strong %{y:.0%} (%{customdata[1]:+.0%})<extra></extra>")
    # shaded: the area between the diagonal and the observed line, where the forecast said more than happened
    fig.add_scatter(x=list(C["pred"]) + list(C["pred"])[::-1], y=list(C["act"]) + list(C["pred"])[::-1], fill="toself", fillcolor=ui.SHADE, mode="none",
                    name="Shaded: forecast too high", hoverinfo="skip")
    for x, y in zip(C["pred"], C["act"]):  # the vertical distance to the diagonal is how far the forecast missed for that group
        fig.add_shape(type="line", x0=x, x1=x, y0=x, y1=y, line=dict(color=NEUTRAL, width=1.5, dash="dot"), layer="below")
    i = max(range(len(C["pred"])), key=lambda k: C["pred"][k] - C["act"][k])  # the largest overstatement, the one the caption below describes
    fig.add_annotation(x=C["pred"][i], y=C["act"][i], text=f"Predicted {C['pred'][i]:.0%},<br>actual {C['act'][i]:.0%}", showarrow=True, arrowhead=0, arrowcolor=NEUTRAL,
                       ax=24, ay=40, align="left", font=dict(size=12, color=INK), xanchor="left")
    fig.update_xaxes(range=[0, 1], title="Predicted chance of becoming a strong producer", tickformat=".0%", dtick=0.2, constrain="domain")
    fig.update_yaxes(range=[0, 1], title="Actually became strong producers", tickformat=".0%", dtick=0.2, scaleanchor="x", scaleratio=1, constrain="domain")
    c1, c2 = st.columns([3, 2], vertical_alignment="center")
    with c1:
        ui.plot(style(fig, 440))
    c2.caption("How to read it: each dot is one of five groups, from least to most likely. On the dashed line, the forecast matched what happened; "
               "below it, the forecast was too high. The dotted lines show each group's miss.")
    st.caption("The order held, but the middle overstated the chance (players predicted at 58% were strong 36% of the time), because more players left in the later classes. Use it as a ranking, not as odds.")
    ui.open_analysis("Related: Penn State's 2025 class, most likely strong producers by 2027", REC, "sub_rec", "Recruit Development Forecast", key="go_class_forecast")


def player_development():
    sub = ui.subnav("sub_dev", DEV_SUBS)
    {"Player Development Analytics": _development_analytics, "Development Trajectory & Breakout Forecast": _breakout_forecast}[sub]()


# ================================================================ 4. Roster Construction
def _roster_analytics():
    _status("Roster")
    st.subheader("Share of last year's roster and production that came back")
    st.write("The bar is 2026. The marks show the 2015 to 2025 average and the previous lowest.")
    R = D["roster"]
    fig = go.Figure()
    fig.add_bar(y=[r[0] for r in R], x=[r[1] for r in R], orientation="h", name="2026", marker=dict(color=PSU, cornerradius=3), texttemplate="%{x}%", textposition="outside", cliponaxis=False,
                hovertemplate="2026: %{x}% back<extra></extra>")
    fig.add_scatter(y=[r[0] for r in R], x=[r[2] for r in R], mode="markers", name="Average 2015 to 2025", marker=dict(symbol="line-ns", size=20, line=dict(width=3.5, color=ACCENT)),
                    hovertemplate="Average, 2015 to 2025: %{x}%<extra></extra>")
    fig.add_scatter(y=[r[0] for r in R], x=[r[3] for r in R], mode="markers", name="Previous lowest", marker=dict(symbol="diamond", size=11, color="white", line=dict(width=2, color=PSU)),
                    hovertemplate="Previous lowest: %{x}%<extra></extra>")
    # at the right: 2026 minus the 2015 to 2025 average, in percentage points (arithmetic on the two values shown)
    fig.add_scatter(x=[116] * len(R), y=[r[0] for r in R], mode="text", text=[f"<b>{r[1] - r[2]:+.0f}</b>" for r in R], textposition="middle left",
                    textfont=dict(size=12, color=[ui.BAD if r[1] < r[2] else ui.GOOD for r in R]), hoverinfo="skip", showlegend=False, cliponaxis=False)
    fig.add_annotation(x=116, y=1, xref="x", yref="paper", yanchor="bottom", xanchor="right", showarrow=False, text="<b>vs<br>average</b>", font=dict(size=11, color=INK))
    fig.update_layout(hovermode="y unified", yaxis=dict(autorange="reversed"), bargap=0.3)
    fig.update_xaxes(range=[0, 117], title="Percent back", tickvals=[0, 20, 40, 60, 80, 100])
    ui.plot(style(fig, 540))
    st.caption("Passing yards returning is 0% (previous low 8%). Last year's top two sack leaders, Dani Dennis-Sutton and Zane Durant, are gone, along with quarterbacks Drew Allar and Ethan Grunkemeyer and running backs Kaytron Allen and Nicholas Singleton.")


def _retention_forecast():
    st.subheader("Looking ahead to 2027 and 2028")
    st.write("About **64% of the 2026 roster (71 of 112 players)** is expected back in 2027. At a 105-player roster limit that leaves roughly 34 spots for the 2027 class and the portal. The limit is an assumption to confirm.")
    st.warning("Do not lean on the position-by-position numbers. In a backtest on 2022 to 2025, the models missed by 2.0 players per position group, the same as assuming everyone returns at the overall rate (1.97). "
               "The 2025 to 2026 step missed by about 4 for every approach, because a coaching change and rebuild cannot be predicted from history.")
    F = pd.DataFrame(D["forecast"], columns=["Group", "Players in 2026", "Expected back", "Low (80%)", "High (80%)"])
    st.markdown("**Expected returners in 2027 by position group (not validated)**")
    fig = go.Figure()
    cx, cy = [], []
    for g, n, e in zip(F["Group"], F["Players in 2026"], F["Expected back"]):
        cx += [e, n, None]; cy += [g, g, None]
    fig.add_scatter(x=cx, y=cy, mode="lines", name="Change from 2026", line=dict(color="#C9D3E0", width=2), hoverinfo="skip", showlegend=False)
    fig.add_scatter(x=F["Players in 2026"], y=F["Group"], mode="markers", name="Players in 2026", marker=dict(symbol="circle-open", size=11, color=ACCENT, line=dict(width=2)),
                    hovertemplate="Players in 2026: %{x}<extra></extra>")
    fig.add_scatter(x=F["Expected back"], y=F["Group"], mode="markers", name="Expected back in 2027 (band: the forecast's 80% range)", marker=dict(color=PSU, size=11, line=dict(color="white", width=1.5)),
                    error_x=dict(type="data", symmetric=False, array=F["High (80%)"] - F["Expected back"], arrayminus=F["Expected back"] - F["Low (80%)"], color=LIGHT, thickness=9, width=0),
                    customdata=F[["Low (80%)", "High (80%)"]].values,
                    hovertemplate="Expected back in 2027: %{x:.1f} (80% range %{customdata[0]:.1f} to %{customdata[1]:.1f})<extra></extra>")
    fig.update_layout(hovermode="y unified", yaxis=dict(autorange="reversed")); fig.update_xaxes(title="Players", rangemode="tozero")
    ui.plot(style(fig, max(260, 34 * len(F) + 110)))
    st.caption("Open circle: players in 2026. Dot: the forecast's expected returners; light blue band: its 80% range. The difference is a rough guide to where spots may open. "
               "In the backtest above, these position-group forecasts did no better than a flat guess.")
    ui.table(F, "forecast", {c: "{:.1f}" for c in ("Expected back", "Low (80%)", "High (80%)")})
    st.caption("Leaving for any reason counts: graduation, the NFL, transfer or a cut. Early NFL departures and portal exits cannot be predicted from this data.")


def _decision():
    _status("Resource allocation")
    st.subheader("Recruit or transfer?  " + BADGE["assumption"])
    st.write("The data show how often a roster spot ends up with a **strong producer** (67th percentile or better at the position): 43% of recruit player-seasons and 63% of transfer player-seasons, "
             "so a transfer yields about 1.5 times as much. Whether that is worth it depends on what a transfer costs, and **there is no public cost or NIL data**. Move the slider to try a cost.")
    cost = st.slider("A transfer spot costs this many times a recruit's spot", 1.0, 4.0, step=0.1, key="cost")
    rows = []
    for p in POS:
        r, t, be, lo, hi = D["yields"][p]
        rows.append({"Position": p, "Recruits strong": r, "Transfers strong": t, "Break-even cost": be, "Range low": lo, "Range high": hi, "Better use of a spot": "Transfer" if be > cost else "Recruit"})
    Y = pd.DataFrame(rows)
    n_t = int((Y["Better use of a spot"] == "Transfer").sum())
    if n_t == 0:
        st.success(f"At {cost:.1f}x, recruits give more strong seasons per unit cost at all seven positions.")
    elif n_t == len(POS):
        st.success(f"At {cost:.1f}x, transfers give more strong seasons per unit cost at all seven positions.")
    else:
        st.success(f"At {cost:.1f}x, transfers win at {n_t} of 7 positions. The position differences sit inside the ranges, so only the overall break-even of about 1.5x is solid.")
    fig = go.Figure()
    # Shaded: break-even above your cost, the tool's own rule for "Transfer" (break-even > cost). A dot exactly on the line counts as Recruit.
    fig.add_vrect(x0=cost, x1=4.2, fillcolor=ui.SHADE, line_width=0, layer="below")
    fig.add_annotation(x=cost, y=1.0, yref="paper", xanchor="center", yanchor="bottom", showarrow=False, font=dict(size=11, color=PSU), text="<b>Your cost</b>")
    fig.add_annotation(x=4.15, y=0, yref="paper", xanchor="right", yanchor="bottom", yshift=6, showarrow=False, text="Shaded: break-even above your cost (transfer)",
                       font=dict(size=11, color=PSU))
    fig.add_scatter(x=Y["Break-even cost"], y=Y["Position"], mode="markers", name="Break-even (95% range)",
                    marker=dict(color=[PSU if v == "Transfer" else ACCENT for v in Y["Better use of a spot"]], size=12, line=dict(color="white", width=1.5)),
                    error_x=dict(type="data", symmetric=False, array=Y["Range high"] - Y["Break-even cost"], arrayminus=Y["Break-even cost"] - Y["Range low"], color=NEUTRAL, thickness=3, width=5),
                    customdata=Y[["Range low", "Range high", "Better use of a spot"]].values,
                    hovertemplate="%{y}: break-even %{x:.2f}x (95% range %{customdata[0]:.2f} to %{customdata[1]:.2f}). At your cost: %{customdata[2]}<extra></extra>")
    fig.add_vline(x=cost, line_color=PSU, line_width=3)
    fig.update_layout(yaxis=dict(autorange="reversed", tickmode="array", tickvals=Y["Position"], ticktext=[f"{p} · {v}" for p, v in zip(Y["Position"], Y["Better use of a spot"])]))
    fig.update_xaxes(range=[0.8, 4.2], title="Cost of a transfer spot relative to a recruit spot")
    ui.plot(style(fig, 330, legend=False).update_layout(margin=dict(t=34)))  # room for the labels above the plot
    ui.table(Y[["Position", "Recruits strong", "Transfers strong", "Break-even cost", "Better use of a spot"]], "yields",
             {"Recruits strong": ui.pct, "Transfers strong": ui.pct, "Break-even cost": "{:.2f}"})
    st.caption("Dot color: navy where a transfer is the better use of a spot at your cost, slate where a recruit is.")
    st.caption("To the left of the dark dot, a transfer is the better use of a spot; to the right, a recruit. Transfers are counted only if they reached a roster, and they are signed to play right away, "
               "so part of the gap is playing time and not ability.")
    st.caption("Reading the chart: a position's verdict is next to its name. Where the dot sits in the shaded area, its break-even is above your cost, so a transfer is the better use "
               "of a spot under these assumptions. Where a position's 95% range crosses your cost line, its verdict is uncertain.")
    ui.open_analysis("Related transfer research: what predicts how a transfer produces", TRN, "sub_trn", "Transfer Production Translation", key="go_portal_from_decision")

    st.subheader("Which position gets the next spots?  " + BADGE["assumption"])
    st.write("The data **cannot** say how much a spot at one position is worth compared with another, because \"strong\" is measured within each position. This ranking comes only from the numbers you put in. "
             "The starting values are equal churn at every position, and weights sized by Penn State's gap to champions.")
    a, b = st.columns([3, 1])
    a.radio("Weights", ["Every position counts the same", "Sized by the gap to champions"], key="preset", horizontal=True, on_change=_set_weights)
    b.button("Reset to starting values", on_click=_reset)
    hdr = st.columns(3); hdr[0].markdown("**Position**"); hdr[1].markdown("**Spots expected to open**"); hdr[2].markdown("**Weight**")
    for p in POS:
        c = st.columns(3)
        c[0].write(p)
        c[1].number_input(f"Spots open at {p}", min_value=0.0, step=0.5, key=f"s_{p}", label_visibility="collapsed")
        c[2].number_input(f"Weight for {p}", min_value=0.0, step=0.1, key=f"w_{p}", label_visibility="collapsed")
    S = pd.DataFrame({"Position": POS, "Priority score": [st.session_state[f"s_{p}"] * st.session_state[f"w_{p}"] for p in POS]}).sort_values("Priority score", ascending=False)
    fig = go.Figure(go.Bar(y=S["Position"], x=S["Priority score"], orientation="h", marker_color=PSU, texttemplate="%{x:.1f}", textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: priority %{x:.1f} (spots times weight)<extra></extra>"))
    fig.update_layout(yaxis=dict(autorange="reversed")); fig.update_xaxes(title="Priority score (spots times weight)")
    ui.plot(style(fig, 330, legend=False))
    st.caption("Offensive line, special teams and athletes cannot be measured and are left out. Put in better numbers as you get them: spots from a depth chart and eligibility, weights from a coach's view.")


def roster_construction():
    sub = ui.subnav("sub_ros", ROS_SUBS)
    {"Roster Analytics": _roster_analytics, "Retention & Continuity Forecast": _retention_forecast, "Decision Tool": _decision}[sub]()


# ================================================================ 5. Competitive Edge Research
CLEANER, CIRCULAR = "Cleaner comparison: talent and recruiting", "Partly circular: record, SP+ and per-play"


def _gap_group(label):
    # The research note below the chart: talent and recruiting are the cleaner comparison; record, SP+ and per-play rows are partly circular.
    if re.search(r"talent|recruit", label, re.I):
        return CLEANER
    if re.search(r"sp\+|per play|win|record", label, re.I):
        return CIRCULAR
    return "Other measures"


def _gap_chart(rows):
    """Penn State, playoff teams and champions on each measure (all in standard deviations above the FBS average), in two panels by kind of comparison."""
    groups = [g for g in (CLEANER, CIRCULAR, "Other measures") if any(_gap_group(r[0]) == g for r in rows)]
    parts = {g: [r for r in rows if _gap_group(r[0]) == g] for g in groups}
    fig = make_subplots(rows=len(groups), cols=1, shared_xaxes=True, subplot_titles=groups, vertical_spacing=0.12,
                        row_heights=[len(parts[g]) for g in groups])
    xmax = max(max(r[1], r[2], r[3]) for r in rows)
    for i, g in enumerate(groups, start=1):
        R = parts[g]
        for r in R:
            fig.add_scatter(x=[min(r[1:4]), max(r[1:4])], y=[r[0], r[0]], mode="lines", line=dict(color="#DCE4EF", width=8), hoverinfo="skip", showlegend=False, row=i, col=1)
        # drawn champions first and Penn State last, so Penn State sits on top where markers overlap; the legend keeps Penn State first
        for rank, name, k, col, sym in ((3, "Champions", 3, ACCENT, "square"), (2, "Playoff teams", 2, LIGHT, "diamond"), (1, "Penn State", 1, PSU, "circle")):
            fig.add_scatter(x=[r[k] for r in R], y=[r[0] for r in R], mode="markers", name=name,
                            marker=dict(color=col, size=14 if k == 1 else 12, symbol=sym, line=dict(width=1.5, color=PSU if col == LIGHT else "white")),
                            showlegend=(i == 1), legendgroup=name, legendrank=rank, hovertemplate=f"{name}: %{{x:.2f}} SD<extra></extra>", row=i, col=1)
        fig.add_scatter(x=[xmax + 0.08] * len(R), y=[r[0] for r in R], mode="text", text=[f"<b>{r[1] - r[3]:+.2f}</b>" for r in R], textposition="middle right",
                        textfont=dict(size=12, color=[ui.BAD if r[1] < r[3] else ui.GOOD for r in R]), hoverinfo="skip", showlegend=False, row=i, col=1)
        fig.update_yaxes(autorange="reversed", row=i, col=1)
    fig.update_xaxes(range=[0, xmax + 0.4], title_text="SD above the FBS average (higher is better)", row=len(groups), col=1)
    fig.update_annotations(font=dict(size=13, color=INK), xanchor="left", x=0)
    fig.add_annotation(x=xmax + 0.08, y=1, xref="x", yref="paper", yanchor="bottom", xanchor="left", showarrow=False, text="<b>PSU minus<br>champions</b>",
                       font=dict(size=11, color=INK))
    fig.update_layout(hovermode="y unified")
    height = 110 + 46 * len(rows) + 40 * len(groups)
    style(fig, height).update_layout(margin=dict(t=78))
    fig.update_layout(legend=dict(y=1 + 44 / (height - 78 - 10)))  # 44px above the plot area, clear of the first panel title
    return fig


def _championship_gap():
    st.subheader("Average over 2014 to 2025, in standard deviations above the FBS average")
    st.write("Higher is better, and defense is shown so that higher means fewer points allowed per play.")
    ui.plot(_gap_chart(D["gap"]))
    st.caption("Numbers at the right: Penn State minus champions on that measure, in standard deviations (negative means Penn State is behind).")
    st.caption("Record, SP+ and per-play rows are partly circular because champions are chosen for winning. Talent and recruiting are the cleaner comparison. About 12 champions describe a profile and cannot predict a winner.")
    c1, c2 = st.columns(2)
    c1.info("Eight of 11 champions since 2015 ranked in the top 5 in talent. Penn State has ranked 10th to 21st. Every champion had a top-3 offense or defense by SP+; Penn State has had one once, the 2014 defense.")
    c2.info("From 2021 to 2025, Penn State trails champions by 1.57 standard deviations in passing and 1.49 on second down. Rushing is closer, at 0.81.")
    st.subheader("How Penn State loses")
    L = D["loses"]
    fig = go.Figure(go.Bar(y=[f"<b>{r[0]}</b><br><span style='color:{ui.AXIS_INK}'>{r[1]}</span>" for r in L], x=[r[2] for r in L], orientation="h", width=0.6,
                           marker=dict(color=PSU, cornerradius=3),
                           texttemplate="<b>%{x}%</b>", textposition="outside", cliponaxis=False, textfont=dict(size=13, color=INK),
                           customdata=[r[3] if len(r) > 3 else "" for r in L],
                           hovertemplate="Penn State won %{x}% of %{customdata} games<extra></extra>"))
    fig.add_vline(x=50, line=dict(color=NEUTRAL, width=1, dash="dot"), annotation=dict(text="Even (50%)", font=dict(size=11, color=ui.AXIS_INK), yanchor="bottom", y=1))
    fig.update_layout(yaxis=dict(autorange="reversed")); fig.update_xaxes(range=[0, 105], title="Win percentage by the opponent's SP+ rank that season")
    ui.plot(style(fig, 320, legend=False).update_layout(margin=dict(t=30)))
    st.caption("Ohio State and Michigan are 18 of Penn State's 48 losses (1–11 and 3–7). Close games are 26–29, about a coin flip, so luck in close games does not explain the pattern.")
    st.subheader("Season by season")
    S = pd.DataFrame(D["seasons"], columns=["Season", "Record", "SP+ rank", "Talent rank", "Class rank"])
    for c in ("SP+ rank", "Talent rank", "Class rank"):
        S[c] = pd.array(S[c], dtype="Int64")  # whole-number ranks; a missing rank stays missing rather than reading as the word None
    # A static table: every season shows without a scroll box, and a missing rank reads "—" (interactive tables in Streamlit 1.50 always show "None")
    st.table(S.set_index("Season").style.format(na_rep="—"))
    st.caption("— means the rank is missing from the data for that season.")


def _big_ten():
    try:
        from child15.page import render as _render_child15
    except Exception as ex:
        st.error(f"The Big Ten benchmark page could not be loaded ({type(ex).__name__}). The rest of the dashboard is unaffected.")
    else:
        _render_child15(PSU, LIGHT, ACCENT, style, grouped_dots)


def _game_analytics():
    _status("Game analytics")
    st.write("The dashboard's 2026 game-by-game results (each game against Penn State's own history, what stood out, and three numbers to watch) "
             "are on the 2026 Games page.")
    ui.open_analysis("Open 2026 Games", GAMES, key="go_games_from_cer")


def competitive_edge():
    sub = ui.subnav("sub_cer", CER_SUBS)
    {"Championship Gap": _championship_gap, "Big Ten Competitive Intelligence": _big_ten, "Game Analytics": _game_analytics}[sub]()


# ================================================================ Research & Methods
def _all_findings():
    st.subheader("All findings")
    for text, kind in FINDINGS:
        a, b = st.columns([6, 1])
        a.write(text)
        b.markdown(BADGE[kind])
    ui.evidence_legend()


def _modules():
    st.subheader("The eight modules")
    ui.table(pd.DataFrame(D["modules"], columns=["Module", "Where it stands", "What it does and does not do"]), "modules")


def _limits_methods():
    st.subheader("What this data cannot tell us")
    st.markdown("- **Missing data:** snap counts, injuries, depth charts, play-calling, pressure, missed tackles, red-zone results, cost and NIL. Playing time can only be approximated.\n"
                "- **Offensive line:** only 6% of offensive-line player-seasons have any recorded stat, so their production cannot be measured.\n"
                f"- **Small samples:** about 12 champions, {data_check.count_words(len(D['games']))} in 2026, and position groups of a few dozen players.\n"
                "- **Association, not cause:** a gap in talent or offense does not show that closing it would produce a title.\n"
                "- **Circular measures:** SP+, per-play efficiency and record are built from the results used to judge Penn State.\n"
                "- **Volume stats:** production mixes ability with opportunity and scheme.")
    st.subheader("How the tests were run")
    st.write("Hypotheses were written before looking at results. Models were fitted on earlier seasons and judged on later ones, so nothing from the future leaked in. A result counted as supported only if the effect pointed "
             "the same way in both groups and the later group's 95% range excluded zero. Several tests came back negative, and those are reported as findings.")


def research_methods():
    sub = ui.subnav("sub_rm", RM_SUBS)
    {"All findings": _all_findings, "Module status": _modules, "Limitations & methods": _limits_methods}[sub]()


# ================================================================ header and navigation
HOME = st.Page(home, title="Home", icon=":material/home:", default=True)
REC = st.Page(recruiting, title="Recruiting High Schoolers", icon=":material/school:", url_path="recruiting")
TRN = st.Page(transfer_portal, title="Transfer Portal", icon=":material/swap_horiz:", url_path="transfer-portal")
DEV = st.Page(player_development, title="Player Development", icon=":material/trending_up:", url_path="player-development")
ROS = st.Page(roster_construction, title="Roster Construction", icon=":material/groups:", url_path="roster-construction")
CER = st.Page(competitive_edge, title="Competitive Edge Research", icon=":material/insights:", url_path="competitive-edge")
GAMES = st.Page(games_2026, title="2026 Games", icon=":material/sports_football:", url_path="games-2026")
RESEARCH = st.Page(research_methods, title="Research & Methods", icon=":material/science:", url_path="research-methods")
current = st.navigation([HOME, REC, TRN, DEV, ROS, CER, GAMES, RESEARCH], position="hidden")

_SOURCE_LABEL = {"live file": "live data link", "app secret": "snapshot from the app settings", "bundled snapshot": "bundled snapshot"}
ui.brand_header("What public data say about Penn State football from 2014 to 2026, with the uncertainty shown.",
                f"<strong>Data through week {ui.esc(D['meta']['through_week'])} of 2026</strong> · snapshot {ui.esc(D['meta']['snapshot'])} · "
                f"source: {ui.esc(_SOURCE_LABEL.get(SOURCE, SOURCE))}", HOME, [REC, TRN, DEV, ROS, CER], [GAMES, RESEARCH], current)
if NOTES:
    st.warning("Data note: " + "; ".join(NOTES) + f". Showing the {_SOURCE_LABEL.get(SOURCE, SOURCE)} instead.")
try:
    CHECKS = data_check.check_data(D, _today(), SEASON)
except Exception as ex:  # a malformed file must not stop the dashboard from showing what it can
    CHECKS = [f"The data check could not finish ({type(ex).__name__}); the file may be malformed."]
if CHECKS:
    st.warning("**Data check:** the numbers below are shown as they are in the data file, but some parts look out of step. "
               "Fix these in the data file:\n" + "\n".join(f"- {m}" for m in CHECKS), icon=":material/fact_check:")
current.run()
