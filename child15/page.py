"""Streamlit page for PSFAL Child 15 (Big Ten competitive intelligence). Display only: every number comes from the validated saved report."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .report_reader import GROUPS, METRICS, ReportError, load_report

GROUP_LABEL = {"peers": "Season-specific Big Ten peers", "national": "National average", "champions": "National champions",
               "fixed18": "Fixed 18-team Big Ten set (sensitivity)"}
# metric -> (direction as measured, unit of the raw columns)
META = {
    "SP+ overall": ("Higher is better", "SP+ rating points"),
    "SP+ offense": ("Higher is better", "SP+ points"),
    "SP+ defense": ("Lower is better (points allowed)", "SP+ points"),
    "PPA offense": ("Higher is better", "predicted points added per play"),
    "PPA defense": ("Lower is better (points allowed per play)", "predicted points added per play"),
    "Win percentage": ("Higher is better", "share of games won (0 to 1)"),
    "Recruiting points (4-yr)": ("Higher is better", "4-year recruiting points"),
    "Talent composite": ("Higher is better", "talent composite points"),
}


@st.cache_data(show_spinner=False)
def _load():
    return load_report()


def _table(rows):
    return pd.DataFrame(rows)


def render(blue, gray, gold, style, grouped_hbar):
    st.subheader("Big Ten competitive intelligence (Child 15)  :gray-background[Descriptive]")
    try:
        parsed, info = _load()
    except ReportError as ex:
        st.error(f"Child 15 could not be shown. {ex} No benchmark values are displayed in place of the saved report. "
                 "Check that child15/big_ten_benchmark.md is present in the app files.")
        return
    W = parsed["windows"]

    st.write("How far Penn State sits above or below three comparison groups on eight team measures, in standard deviations. "
             "**Positive means Penn State is better**, for every measure. Defense measures are flipped so that fewer points allowed counts as better.")
    win = st.radio("Time period", ["2014-2025", "2021-2025"], horizontal=True, key="c15_window",
                   format_func=lambda w: {"2014-2025": "2014 to 2025 (12 seasons, 2020 kept)", "2021-2025": "2021 to 2025 (5 seasons)"}[w])
    G = W[win]["groups"]

    # ---- headline
    h = W["2014-2025"]["groups"]["champions"]["PPA offense"]
    st.info(f"**Headline (2014 to 2025):** Penn State's offensive PPA is **{abs(h['gap_sd']):.2f} standard deviations below** the national-champion comparison group "
            f"({h['penn_state']:.3f} against {h['group_mean']:.3f} predicted points added per play).")

    # ---- champion sample sizes
    st.markdown("**Champion sample sizes**")
    a, b = st.columns(2)
    for col, w, lab in ((a, "2014-2025", "2014 to 2025"), (b, "2021-2025", "2021 to 2025")):
        n, p = W[w]["champion_sample"]
        with col:
            with st.container(border=True):
                st.metric(lab, f"{n} champion team-seasons")
                st.caption(f"across {p} distinct programs")
    st.warning("The champion groups are very small, and the champion row is partly circular with SP+ and win percentage because champions are chosen for winning. "
               "Read it as a profile of a handful of teams, not as a target or a prediction.")

    # ---- chart
    st.markdown(f"**Penn State's gap in standard deviations, {win.replace('-', ' to ')}**")
    series = [(GROUP_LABEL[g], [G[g][m]["gap_sd"] for m in METRICS]) for g in ("peers", "national", "champions")]
    # † marks the measures the warning above calls partly circular for the champion row (SP+ and win percentage)
    labels = [f"{m} †" if m.startswith("SP+") or m == "Win percentage" else m for m in METRICS]
    fig = grouped_hbar(labels, series, [blue, gray, gold], xrange=[-1.8, 2.1], fmt="%{x:+.2f}", height=640)
    fig.add_vline(x=0, line_color="#55627D")
    fig.update_xaxes(title="Standard deviations (positive = Penn State better; negative = Penn State behind)")
    st.plotly_chart(fig)
    st.caption("Each team-season is standardized against all teams in the same season. Penn State is excluded from every comparison average. "
               "Bars to the right of zero mean Penn State is ahead of that group; to the left, behind.")
    st.caption("† Named in the warning above as partly circular for the champion comparison. The lab's general limitations also list per-play "
               "efficiency (PPA here) as a circular measure.")

    # ---- table
    st.markdown("**Full numbers**")
    rows = []
    for m in METRICS:
        for g in ("peers", "national", "champions", "fixed18"):
            r = G[g][m]
            rows.append({"Metric": m, "Direction": META[m][0], "Unit": META[m][1], "Comparison group": GROUP_LABEL[g], "Period": win,
                         "Penn State": r["penn_state"], "Group mean": r["group_mean"], "Raw gap (PSU minus group)": r["raw_gap"],
                         "Gap in SD (+ = PSU better)": r["gap_sd"], "Programs": r["programs"], "Team-seasons": r["team_seasons"]})
    df = _table(rows)[["Metric", "Comparison group", "Gap in SD (+ = PSU better)", "Penn State", "Group mean", "Raw gap (PSU minus group)",
                       "Direction", "Unit", "Period", "Programs", "Team-seasons"]]
    show_fixed = st.checkbox("Include the fixed 18-team Big Ten set (sensitivity check)", value=False, key="c15_fixed")
    if not show_fixed:
        df = df[df["Comparison group"] != GROUP_LABEL["fixed18"]]
    st.caption("Metric stays in view; scroll the table sideways to see every column, including the sample sizes (Programs, Team-seasons).")
    st.dataframe(df, hide_index=True, width="stretch", height=38 + 35 * len(df),  # every row shown, no scroll box inside the page
                 column_config={"Metric": st.column_config.TextColumn(pinned=True, width=150), "Comparison group": st.column_config.TextColumn(width=205),
                                "Gap in SD (+ = PSU better)": st.column_config.NumberColumn(format="%+.2f", width=110),
                                "Penn State": st.column_config.NumberColumn(format="%.3f", width=85), "Group mean": st.column_config.NumberColumn(format="%.3f", width=95),
                                "Raw gap (PSU minus group)": st.column_config.NumberColumn(format="%+.3f", width=115),
                                "Direction": st.column_config.TextColumn(width=205), "Unit": st.column_config.TextColumn(width=215),
                                "Period": st.column_config.TextColumn(width=80), "Programs": st.column_config.NumberColumn(width=75),
                                "Team-seasons": st.column_config.NumberColumn(width=95)})
    st.caption("Raw gaps are in the metric's own unit and keep its direction, so a negative raw gap on a defense measure is good for Penn State. The standardized gap is already flipped. "
               "Recruiting points and talent have fewer team-seasons because they are missing for 2014 and for a few teams; zero talent values are treated as missing.")

    # ---- methodology and limits
    with st.container(border=True):
        st.markdown("**How to read this**")
        st.markdown("- **Descriptive and team-level.** It shows where Penn State sits, not why.\n"
                    "- **Not a causal explanation** of Penn State's results, and not evidence that any roster or coaching decision caused a gap.\n"
                    "- **Not proof of market inefficiency**, and **not a predictive model**.\n"
                    "- **Based on the saved 2014 to 2025 team-season dataset.** 2020 is kept in the 2014 to 2025 period (a shortened season) and is outside 2021 to 2025.\n"
                    f"- **Membership:** {parsed['reproduction'].get('membership', 'see the saved report')}")
    rp = parsed["reproduction"].get("match")
    if rp:
        st.caption(f"Reproduction check recorded in the saved report: {rp[0]} of {rp[1]} published gaps match the earlier competitive-intelligence figures within rounding.")
    st.caption(f"Source: validated Child 15 report (reports/big_ten_benchmark.md), shown as saved, not recalculated here. File sha256 {info['sha256'][:12]}…, {info['bytes']:,} bytes.")
    st.caption("Not yet built: exact 2025 Big Ten team rankings and 2014 to 2025 average team rankings. They are a separate future extension and are not shown.")
