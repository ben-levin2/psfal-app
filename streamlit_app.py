"""PSFAL: Penn State football analytics lab (Streamlit dashboard).

Data comes from dashboard_data.json next to this file. To update the numbers without touching the app, set PSFAL_DATA_URL (an environment
variable or a Streamlit secret named data_url) to a link that returns the same JSON; the app falls back to the bundled file if the link fails.
"""
import json
import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="PSFAL: Penn State football analytics lab", page_icon="🦁", layout="wide")

BLUE, GRAY, GOLD, GOOD, BAD = "#1E407C", "#A3AEC2", "#D4A63C", "#2A7A58", "#AE4337"
HERE = Path(__file__).parent
BADGE = {"tested": ":blue-background[Tested]", "descriptive": ":gray-background[Descriptive]", "assumption": ":orange-background[Assumption]"}
POS = ["QB", "RB", "WR", "TE", "DL", "LB", "DB"]


@st.cache_data(ttl=600, show_spinner=False)
def load_data():
    """Order: a link (PSFAL_DATA_URL or secret data_url), then a secret named data_json, then dashboard_data.json next to this file."""
    url = os.environ.get("PSFAL_DATA_URL", "")
    secret_json = ""
    try:
        url = url or st.secrets.get("data_url", "")
        secret_json = st.secrets.get("data_json", "")
    except Exception:
        pass
    if url:
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=10) as r:
                return json.loads(r.read().decode()), "live file"
        except Exception:
            pass
    if secret_json:
        try:
            return json.loads(secret_json), "app secret"
        except Exception:
            pass
    f = HERE / "dashboard_data.json"
    if f.exists():
        return json.loads(f.read_text()), "bundled snapshot"
    return None, "none"


D, SOURCE = load_data()


def _gate():
    """Optional passcode. If a Streamlit secret named app_password exists, nothing is shown until it is entered (a simple lock, not strong security)."""
    try:
        pw = st.secrets.get("app_password", "")
    except Exception:
        pw = ""
    if not pw or st.session_state.get("unlocked"):
        return
    st.title("Penn State football analytics lab")
    entered = st.text_input("Passcode", type="password")
    if entered and entered == pw:
        st.session_state["unlocked"] = True
        st.rerun()
    elif entered:
        st.error("That passcode is not right.")
    st.stop()


_gate()
if D is None:
    st.title("Penn State football analytics lab")
    st.error("No data found. Add dashboard_data.json next to this app, or set the secret data_json (the same contents) in the app settings.")
    st.stop()


def style(fig, height=None, legend=True):
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=1.08, x=0), showlegend=legend,
                      font=dict(family="Barlow, system-ui, sans-serif"))
    if height:
        fig.update_layout(height=height)
    return fig


def grouped_hbar(labels, series, colors, xrange=None, fmt="%{x:.2f}", height=None):
    fig = go.Figure()
    for (name, vals), col in zip(series, colors):
        fig.add_bar(y=labels, x=vals, name=name, orientation="h", marker_color=col, texttemplate=fmt, textposition="outside", cliponaxis=False)
    fig.update_layout(barmode="group", yaxis=dict(autorange="reversed"))
    if xrange:
        fig.update_xaxes(range=xrange)
    return style(fig, height or max(260, 38 * len(labels) * max(len(series), 1) // 2 + 80))


# ---------------------------------------------------------------- header
st.title("Penn State football analytics lab")
st.caption(f"What public data say about Penn State football from 2014 to 2026, with the uncertainty shown. Snapshot through week {D['meta']['through_week']} of 2026 "
           f"({D['meta']['snapshot']}). Data source: {SOURCE}.")

cols = st.columns(len(D["games"]))
for c, g in zip(cols, D["games"]):
    with c:
        with st.container(border=True):
            st.caption(f"Week {g['wk']}")
            st.markdown(f"**{g['opp']}**")
            st.markdown(f"### {g['pf']}–{g['pa']}")
            st.markdown((":green[**Win**]" if g["res"] == "W" else ":red[**Loss**]"))

tabs = st.tabs(["Overview", "2026 season", "Gap to champions", "Roster", "Players", "Market and portal", "Decision tool", "Status and limits"])

# ---------------------------------------------------------------- overview
with tabs[0]:
    st.subheader("What the data say")
    findings = [
        ("Penn State beats nearly everyone below the elite tier. It is 66–9 against teams outside the top 50 by SP+ and 5–22 against the top 10.", "descriptive"),
        ("The biggest gap to national champions is offense, and passing most of all. Defense is close to playoff level.", "descriptive"),
        ("This year's roster turnover is the largest in the data. Only 27% of last year's producers returned, against a previous low of 57%.", "descriptive"),
        ("The Northwestern loss was mostly one game of run defense (427 yards). The Wisconsin loss was an offense that could not move.", "descriptive"),
        ("Across 15 programs, no repeatable type of undervalued recruit showed up. Recruiting ratings explain only about a quarter of production.", "tested"),
        ("A transfer's portal rating predicts how he produces, and transfers from non-FBS schools produce less.", "tested"),
        ("The roster forecast did not beat a flat guess for any single position. Plan on about 64% of the roster returning.", "tested"),
        ("A transfer is the better use of a roster spot only if he costs less than about 1.5 times a recruit's spot. Nobody has the real cost.", "assumption"),
    ]
    for text, kind in findings:
        a, b = st.columns([6, 1])
        a.write(text)
        b.markdown(BADGE[kind])
    st.caption("Tested: the question was written down before running it and checked on later seasons. Descriptive: what happened, with no cause claimed. "
               "Assumption: the answer depends on a number nobody has measured.")
    st.subheader("Games left")
    st.dataframe(pd.DataFrame(D["schedule"], columns=["Date", "Opponent", "Site"]), hide_index=True, width="stretch")
    st.caption("There is a bye on October 24. Confirm the away dates on the official schedule.")

# ---------------------------------------------------------------- season
with tabs[1]:
    st.subheader("Each game against Penn State's own history")
    st.write("Per-play efficiency scored against Penn State's 156 earlier games. 100 is the best Penn State game since 2014 and 0 is the worst.")
    labels = [f"Wk {g['wk']} {g['opp']}" for g in D["games"]]
    st.plotly_chart(grouped_hbar(labels, [("Offense", [g["o"] for g in D["games"]]), ("Defense", [g["d"] for g in D["games"]])], [BLUE, GOLD], xrange=[0, 110], fmt="%{x:.0f}"),
                    width="stretch")
    st.subheader("What stood out")
    st.dataframe(pd.DataFrame([{"Week": g["wk"], "Opponent": g["opp"], "Result": f"{g['res']} {g['pf']}–{g['pa']}", "What stands out": g["note"]} for g in D["games"]]),
                 hide_index=True, width="stretch")
    st.subheader("Three numbers to watch")
    w = st.columns(len(D["watch"]))
    for c, x in zip(w, D["watch"]):
        good = x["now"] >= x["ref"] if x["better"] == "high" else x["now"] <= x["ref"]
        unit = "%" if "rate" in x["label"].lower() else ""
        with c:
            with st.container(border=True):
                st.metric(x["label"], f"{x['now']:.1f}{unit}" if unit else f"{x['now']:.1f}")
                st.caption(f"Benchmark: {x['refLabel']}")
                st.markdown(":green[At or above the benchmark]" if good else ":red[Below the benchmark]")
    st.caption("Improvement across several games would point to a team still coming together. One game proves little.")

# ---------------------------------------------------------------- gap
with tabs[2]:
    st.subheader("Average over 2014 to 2025, in standard deviations above the FBS average")
    st.write("Higher is better, and defense is shown so that higher means fewer points allowed per play.")
    g = D["gap"]
    st.plotly_chart(grouped_hbar([r[0] for r in g], [("Penn State", [r[1] for r in g]), ("Playoff teams", [r[2] for r in g]), ("Champions", [r[3] for r in g])], [BLUE, GRAY, GOLD],
                                 xrange=[0, 2.7], height=520), width="stretch")
    st.caption("Record, SP+ and per-play rows are partly circular because champions are chosen for winning. Talent and recruiting are the cleaner comparison. About 12 champions describe a profile and cannot predict a winner.")
    c1, c2 = st.columns(2)
    c1.info("Eight of 11 champions since 2015 ranked in the top 5 in talent. Penn State has ranked 10th to 21st. Every champion had a top-3 offense or defense by SP+; Penn State has had one once, the 2014 defense.")
    c2.info("From 2021 to 2025, Penn State trails champions by 1.57 standard deviations in passing and 1.49 on second down. Rushing is closer, at 0.81.")
    st.subheader("How Penn State loses")
    L = D["loses"]
    fig = go.Figure(go.Bar(y=[f"{r[0]} ({r[1]})" for r in L], x=[r[2] for r in L], orientation="h", marker_color=BLUE, texttemplate="%{x}%", textposition="outside", cliponaxis=False))
    fig.update_layout(yaxis=dict(autorange="reversed")); fig.update_xaxes(range=[0, 105], title="Win percentage by the opponent's SP+ rank that season")
    st.plotly_chart(style(fig, 280, legend=False), width="stretch")
    st.caption("Ohio State and Michigan are 18 of Penn State's 48 losses (1–11 and 3–7). Close games are 26–29, about a coin flip, so luck in close games does not explain the pattern.")
    st.subheader("Season by season")
    st.dataframe(pd.DataFrame(D["seasons"], columns=["Season", "Record", "SP+ rank", "Talent rank", "Class rank"]), hide_index=True, width="stretch")

# ---------------------------------------------------------------- roster
with tabs[3]:
    st.subheader("Share of last year's roster and production that came back")
    st.write("The bar is 2026. The marks show the 2015 to 2025 average and the previous lowest.")
    R = D["roster"]
    fig = go.Figure()
    fig.add_bar(y=[r[0] for r in R], x=[r[1] for r in R], orientation="h", name="2026", marker_color=BLUE, texttemplate="%{x}%", textposition="outside", cliponaxis=False)
    fig.add_scatter(y=[r[0] for r in R], x=[r[2] for r in R], mode="markers", name="Average 2015 to 2025", marker=dict(symbol="line-ns", size=16, line=dict(width=3, color="#12203A")))
    fig.add_scatter(y=[r[0] for r in R], x=[r[3] for r in R], mode="markers", name="Previous lowest", marker=dict(symbol="line-ns", size=16, line=dict(width=3, color=GRAY)))
    fig.update_layout(yaxis=dict(autorange="reversed")); fig.update_xaxes(range=[0, 100], title="Percent back")
    st.plotly_chart(style(fig, 520), width="stretch")
    st.caption("Passing yards returning is 0% (previous low 8%). Last year's top two sack leaders, Dani Dennis-Sutton and Zane Durant, are gone, along with quarterbacks Drew Allar and Ethan Grunkemeyer and running backs Kaytron Allen and Nicholas Singleton.")
    st.subheader("Looking ahead to 2027 and 2028")
    st.write("About **64% of the 2026 roster (71 of 112 players)** is expected back in 2027. At a 105-player roster limit that leaves roughly 34 spots for the 2027 class and the portal. The limit is an assumption to confirm.")
    st.warning("Do not lean on the position-by-position numbers. In a backtest on 2022 to 2025, the models missed by 2.0 players per position group, the same as assuming everyone returns at the overall rate (1.97). "
               "The 2025 to 2026 step missed by about 4 for every approach, because a coaching change and rebuild cannot be predicted from history.")
    F = pd.DataFrame(D["forecast"], columns=["Group", "Players in 2026", "Expected back", "Low (80%)", "High (80%)"])
    st.markdown("**Expected returners in 2027 by position group (not validated)**")
    st.dataframe(F, hide_index=True, width="stretch")
    st.caption("Leaving for any reason counts: graduation, the NFL, transfer or a cut. Early NFL departures and portal exits cannot be predicted from this data.")

# ---------------------------------------------------------------- players
with tabs[4]:
    st.subheader("Production by year in the program, for recruits who stayed")
    st.write("Average production percentile among players at the same position. Later years include only players who stayed, so catching up is partly who remained.")
    T = D["traj"]
    fig = go.Figure()
    for name, key, col in (("4 and 5 stars", "star45", BLUE), ("3 stars", "star3", GOLD), ("2 stars or fewer", "star2", GRAY)):
        fig.add_scatter(x=T["years"], y=T[key], mode="lines+markers", name=name, line=dict(color=col, width=3))
    fig.update_xaxes(title="Year in the program", dtick=1); fig.update_yaxes(range=[0, 100], title="Production percentile")
    st.plotly_chart(style(fig, 360), width="stretch")
    a, b = st.columns(2)
    with a:
        st.markdown("**A rating matters most early**  " + BADGE["descriptive"])
        st.dataframe(pd.DataFrame(D["ratingCorr"], columns=["Year", "Correlation", "Players"]), hide_index=True, width="stretch")
    with b:
        st.markdown("**Production carries over, improvement does not**  " + BADGE["descriptive"])
        st.write("A player's production percentile correlates **0.71** with his next-year percentile. His year-to-year change correlates **−0.27** with the change the year before "
                 "(partly because percentiles stop at 0 and 100). A score built on improvement is not supported. Some players do keep beating their recruiting profile (0.54).")
    st.subheader("Who becomes a strong producer by year 3?  " + BADGE["tested"])
    st.write("**First-year production helps, modestly.** Accuracy (AUC; 0.5 is a coin flip) rose from 0.65 with rating and position to 0.73 once first-year production was added "
             "(gain +0.07, range +0.05 to +0.11). Among slow starters, top-third-rated recruits became strong producers 12 points more often than bottom-third ones (range +3.5 to +21.5).")
    C = D["calib"]
    fig = go.Figure()
    fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", name="Perfect match", line=dict(color=GRAY, dash="dash"))
    fig.add_scatter(x=C["pred"], y=C["act"], mode="lines+markers", name="Five groups, least to most likely", line=dict(color=BLUE, width=3))
    fig.update_xaxes(range=[0, 1], title="Predicted chance of becoming a strong producer", tickformat=".0%"); fig.update_yaxes(range=[0, 1], title="Actual", tickformat=".0%")
    st.plotly_chart(style(fig, 360), width="stretch")
    st.caption("The order held, but the middle overstated the chance (players predicted at 58% were strong 36% of the time), because more players left in the later classes. Use it as a ranking, not as odds.")
    a, b = st.columns(2)
    with a:
        st.markdown("**Penn State's 2025 class: most likely strong producers by 2027**")
        wc = pd.DataFrame(D["watchClass"], columns=["Player", "Pos", "Rating", "2025 output", "Chance"]); wc["Chance"] = (wc["Chance"] * 100).round(0).astype(int).astype(str) + "%"
        st.dataframe(wc, hide_index=True, width="stretch"); st.caption("A ranking aid with wide uncertainty.")
    with b:
        st.markdown("**Penn State's 2026 transfers: highest production so far**")
        st.dataframe(pd.DataFrame(D["transfers"], columns=["Player", "Pos", "From", "So far"]), hide_index=True, width="stretch")
        st.caption("Five games, ranked within Penn State's own position groups. Eight of the ten are Iowa State transfers; that does not show they are better than other transfers.")

# ---------------------------------------------------------------- market and portal
with tabs[5]:
    st.subheader("Do some programs get more from their recruits than ratings predict?  " + BADGE["tested"])
    st.write("Average gap between actual production and what a recruit's rating, year and position predict, in percentile points. The solid dot is the later classes (2020 to 2022) with its 95% range; the open dot is the earlier classes (2016 to 2019).")
    P = pd.DataFrame(D["programs"], columns=["Program", "Earlier", "Later", "Low", "High"])
    colr = [BLUE if p == "Penn State" else GRAY for p in P["Program"]]
    fig = go.Figure()
    fig.add_scatter(x=P["Later"], y=P["Program"], mode="markers", name="Later classes (95% range)", marker=dict(color=colr, size=10),
                    error_x=dict(type="data", symmetric=False, array=P["High"] - P["Later"], arrayminus=P["Later"] - P["Low"], color=GRAY))
    fig.add_scatter(x=P["Earlier"], y=P["Program"], mode="markers", name="Earlier classes", marker=dict(symbol="circle-open", size=9, color=colr, line=dict(width=2)))
    fig.add_vline(x=0, line_color="#55627D"); fig.update_layout(yaxis=dict(autorange="reversed")); fig.update_xaxes(title="Gap in percentile points")
    st.plotly_chart(style(fig, 560), width="stretch")
    st.write("Programs' earlier and later gaps correlate weakly (**0.38** across 15 programs), so differences are suggestive and not conclusive. Penn State ranks 2nd of 15 in the later classes at +1.9, "
             "but its range (−1.9 to +5.6) includes zero. Size for position passed the test with a tiny effect (a correlation of 0.08), and in-state recruits showed nothing.")
    st.subheader("What predicts how a transfer produces at his new school?  " + BADGE["tested"])
    st.write("709 portal arrivals into Penn State and 14 peers (2021 to 2025); 544 could be matched to a roster. Gap = production percentile minus the average transfer at his position.")
    G = D["portalGroups"]
    fig = go.Figure(go.Bar(y=[f"{r[0]} ({r[1]})" for r in G], x=[r[2] for r in G], orientation="h", marker_color=[BLUE if r[2] >= 0 else BAD for r in G], texttemplate="%{x:+.1f}", textposition="outside", cliponaxis=False))
    fig.update_layout(yaxis=dict(autorange="reversed")); fig.update_xaxes(range=[-18, 6], title="Gap in percentile points")
    st.plotly_chart(style(fig, 260, legend=False), width="stretch")
    st.markdown("- **The portal rating carries information.** Rank correlation with production at the new school was 0.31, then 0.37 in the later classes (range 0.27 to 0.47).\n"
                "- **Step-up transfers produce less, mostly because of one group.** Transfers from outside the top 65 or from non-FBS schools produced 3.1 points less, then 8.6 less (range 2.8 to 14.4). Nearly all of it is the last row above.\n"
                "- **Within FBS the gap is small.** Lower-ranked FBS origins were 3.9 points lower than top-65 ones, which cannot be told apart from zero (range −9.9 to +2.3). After allowing for the rating, the overall gap is about 5 points. Those two checks were exploratory.")

# ---------------------------------------------------------------- decision tool
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

with tabs[6]:
    st.subheader("Recruit or transfer?  " + BADGE["assumption"])
    st.write("The data show how often a roster spot ends up with a **strong producer** (67th percentile or better at the position): 43% of recruit player-seasons and 63% of transfer player-seasons, "
             "so a transfer yields about 1.5 times as much. Whether that is worth it depends on what a transfer costs, and **there is no public cost or NIL data**. Move the slider to try a cost.")
    cost = st.slider("A transfer spot costs this many times a recruit's spot", 1.0, 4.0, 2.0, 0.1)
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
    fig.add_scatter(x=Y["Break-even cost"], y=Y["Position"], mode="markers", name="Break-even (95% range)", marker=dict(color="#12203A", size=10),
                    error_x=dict(type="data", symmetric=False, array=Y["Range high"] - Y["Break-even cost"], arrayminus=Y["Break-even cost"] - Y["Range low"], color=GRAY, thickness=3))
    fig.add_vline(x=cost, line_color=BLUE, line_width=3, annotation_text="Your cost", annotation_position="top")
    fig.update_layout(yaxis=dict(autorange="reversed")); fig.update_xaxes(range=[0.8, 4.2], title="Cost of a transfer spot relative to a recruit spot")
    st.plotly_chart(style(fig, 330, legend=False), width="stretch")
    st.dataframe(Y[["Position", "Recruits strong", "Transfers strong", "Break-even cost", "Better use of a spot"]], hide_index=True, width="stretch",
                 column_config={"Recruits strong": st.column_config.NumberColumn(format="percent"), "Transfers strong": st.column_config.NumberColumn(format="percent"),
                                "Break-even cost": st.column_config.NumberColumn(format="%.2f")})
    st.caption("To the left of the dark dot, a transfer is the better use of a spot; to the right, a recruit. Transfers are counted only if they reached a roster, and they are signed to play right away, "
               "so part of the gap is playing time and not ability.")

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
    fig = go.Figure(go.Bar(y=S["Position"], x=S["Priority score"], orientation="h", marker_color=BLUE, texttemplate="%{x:.1f}", textposition="outside", cliponaxis=False))
    fig.update_layout(yaxis=dict(autorange="reversed")); fig.update_xaxes(title="Priority score (spots times weight)")
    st.plotly_chart(style(fig, 330, legend=False), width="stretch")
    st.caption("Offensive line, special teams and athletes cannot be measured and are left out. Put in better numbers as you get them: spots from a depth chart and eligibility, weights from a coach's view.")

# ---------------------------------------------------------------- status
with tabs[7]:
    st.subheader("The eight modules")
    st.dataframe(pd.DataFrame(D["modules"], columns=["Module", "Where it stands", "What it does and does not do"]), hide_index=True, width="stretch")
    st.subheader("What this data cannot tell us")
    st.markdown("- **Missing data:** snap counts, injuries, depth charts, play-calling, pressure, missed tackles, red-zone results, cost and NIL. Playing time can only be approximated.\n"
                "- **Offensive line:** only 6% of offensive-line player-seasons have any recorded stat, so their production cannot be measured.\n"
                "- **Small samples:** about 12 champions, five games in 2026, and position groups of a few dozen players.\n"
                "- **Association, not cause:** a gap in talent or offense does not show that closing it would produce a title.\n"
                "- **Circular measures:** SP+, per-play efficiency and record are built from the results used to judge Penn State.\n"
                "- **Volume stats:** production mixes ability with opportunity and scheme.")
    st.subheader("How the tests were run")
    st.write("Hypotheses were written before looking at results. Models were fitted on earlier seasons and judged on later ones, so nothing from the future leaked in. A result counted as supported only if the effect pointed "
             "the same way in both groups and the later group's 95% range excluded zero. Several tests came back negative, and those are reported as findings.")
