"""Shared look and building blocks for the Penn State Football Analytics Lab. Colors live here and in .streamlit/config.toml; pages call these helpers
instead of repeating layout code."""
import html
import re

import streamlit as st

APP_NAME = "Penn State Football Analytics Lab"
MISSION = "Competitive Edge Discovery"

# Interface colors (official Penn State)
NAVY, PUGH, WHITE = "#001E44", "#96BEE6", "#FFFFFF"
NAV_IDLE = "#14386B"  # lighter navy for inactive navigation; white text on it is above 9:1 contrast
# Chart series, in fixed order: Penn State, comparison group, champions/accent. Checked for color-vision separation against a white surface;
# the light blue is below 3:1 contrast, so charts using it keep direct value labels and a legend.
PSU, LIGHT, ACCENT = "#1F4E9A", "#6FA8E0", "#A97C2C"
NEUTRAL, INK = "#8C96A6", "#12203A"
GOOD, BAD = "#2A7A58", "#AE4337"
SHADE = "rgba(150, 190, 230, 0.22)"  # Pugh Blue wash for highlighted chart regions

# Evidence status: badge, short name, what it means (the definitions are the lab's own, unchanged)
EVIDENCE = {
    "tested": (":blue-background[Tested]", "Tested", "the question was written down before running it and checked on later seasons."),
    "descriptive": (":gray-background[Descriptive]", "Descriptive", "what happened, with no cause claimed."),
    "assumption": (":orange-background[Assumption]", "Assumption", "the answer depends on a number nobody has measured."),
}
BADGE = {k: v[0] for k, v in EVIDENCE.items()}

# Some rules below use Streamlit's own element names (data-testid values and the stMainBlockContainer class) because Streamlit offers no other
# hook for page padding. They are checked against Streamlit 1.50. If a later version renames them, the rule stops matching and Streamlit's
# default spacing returns; nothing is hidden or broken.
_CSS = f"""
<style>
/* Top spacing: Streamlit's top bar is 60px; its default 8rem (128px) padding left about 70px of empty space above the header. */
.stMainBlockContainer {{padding-top: 4.75rem;}}
@media (min-width: 1100px) {{ .stMainBlockContainer {{padding-left: 3rem; padding-right: 3rem;}} }}
/* This style block is the first element on every page and takes no space itself; drop its 16px row gap. Matches only that element. */
[data-testid="stElementContainer"]:has(style#psfal-css) {{display: none;}}

.st-key-psfal_brand {{background: {NAVY}; border-radius: 10px; padding: 0.9rem 1.2rem 0.85rem; gap: 0.55rem; margin-bottom: 0.3rem;}}
.psfal-header {{color: {PUGH}; padding-bottom: 0.95rem;}}  /* clears the negative bottom margin Streamlit gives markdown */
.psfal-header .psfal-mission {{color: {PUGH}; font-size: 0.78rem; letter-spacing: 0.08em; text-transform: uppercase; margin: 0 0 0.15rem;}}
.psfal-header .psfal-name {{color: {WHITE}; font-size: 1.7rem; font-weight: 700; line-height: 1.2; margin: 0 0 0.3rem;}}
.psfal-header .psfal-line {{margin: 0; line-height: 1.5;}}
.psfal-header strong {{color: {WHITE};}}

/* Navigation: compact rectangular links inside the navy header block */
[class*="st-key-nav_"] {{flex-wrap: wrap; gap: 6px !important; row-gap: 6px !important;}}
/* each link keeps its natural width (Streamlit would otherwise give every item an equal, shrinkable slot and cut long names off) */
[class*="st-key-nav_"] > [data-testid="stLayoutWrapper"], [class*="st-key-navo"] {{flex: 0 0 auto !important; width: auto !important; min-width: 0;}}
/* Streamlit gives page links -6px top and bottom margins sized for its 32px links; with 44px links that made wrapped rows overlap */
[class*="st-key-navo"] [data-testid="stElementContainer"] {{margin-top: 0 !important; margin-bottom: 0 !important;}}
[class*="st-key-nav_"] a[data-testid="stPageLink-NavLink"] {{background: {NAV_IDLE}; border-radius: 3px; min-height: 44px; padding: 0 0.8rem;
  margin: 0; display: flex; align-items: center;}}
[class*="st-key-nav_"] a[data-testid="stPageLink-NavLink"] p, [class*="st-key-nav_"] a[data-testid="stPageLink-NavLink"] span {{color: {WHITE}; font-weight: 600; font-size: 0.92rem;}}
[class*="st-key-nav_"] a[data-testid="stPageLink-NavLink"]:hover {{background: #22508F;}}
[class*="st-key-nav_"] a[data-testid="stPageLink-NavLink"]:focus-visible {{outline: 3px solid {PUGH}; outline-offset: 2px;}}
[class*="st-key-navon_"] a[data-testid="stPageLink-NavLink"] {{background: {PUGH} !important;}}
[class*="st-key-navon_"] a[data-testid="stPageLink-NavLink"] p, [class*="st-key-navon_"] a[data-testid="stPageLink-NavLink"] span {{color: {NAVY} !important;}}
.st-key-nav_secondary a[data-testid="stPageLink-NavLink"] {{background: transparent; border: 1px solid #3A5F92; min-height: 38px;}}
/* Wide screens: show the secondary pair at the top right of the header. Only the position changes; they stay last in keyboard order. */
@media (min-width: 900px) {{
  .st-key-psfal_brand {{position: relative;}}
  .st-key-psfal_brand [data-testid="stLayoutWrapper"]:has(> .st-key-nav_secondary) {{position: absolute; top: 0.9rem; right: 1.2rem; width: auto;}}
  .psfal-header {{padding-right: 22rem;}}
}}
/* Cards and tiles: tighter spacing between their parts */
[class*="st-key-card_"], [class*="st-key-tile_"] {{gap: 0.45rem;}}

[class*="st-key-card_"] {{border-top: 3px solid {PUGH} !important; background: {WHITE};}}
[class*="st-key-tile_"] {{background: #F3F7FC;}}
[class*="st-key-tile_"] [data-testid="stMetricValue"] {{color: {NAVY}; font-size: 1.5rem;}}
[class*="st-key-card_"] [data-testid="stMetricValue"] {{color: {NAVY}; font-size: 1.6rem;}}
.stMainBlockContainer h2, .stMainBlockContainer h3 {{color: {NAVY};}}
@media (max-width: 640px) {{
  .psfal-header .psfal-name {{font-size: 1.35rem;}}
  [class*="st-key-tile_"] [data-testid="stMetricValue"] {{font-size: 1.25rem;}}
  [class*="st-key-navo"] {{flex: 1 1 auto !important;}}  /* on phones the wrapped links fill each row evenly */
}}
</style>
"""


def inject_css():
    st.markdown(_CSS.replace("<style>", '<style id="psfal-css">', 1), unsafe_allow_html=True)


def esc(text):
    return html.escape(str(text))


def brand_header(tagline, freshness, home, families, secondary, current):
    """One navy block: mission, app name, description and data freshness, then the Home control and the five family links, then the secondary
    destinations. That is also the keyboard order; on wide screens CSS shows the secondary pair at the top right. Callers escape any data
    values inside `freshness`."""
    def link(page, label=None):
        on = page.url_path == current.url_path
        with st.container(key=f"navon_{page.url_path or 'home'}" if on else f"navoff_{page.url_path or 'home'}"):
            st.page_link(page, label=label or page.title, icon=page.icon, width="content")

    with st.container(key="psfal_brand"):
        st.markdown(f'<div class="psfal-header"><p class="psfal-mission">{esc(MISSION)}</p>'
                    f'<div class="psfal-name" role="heading" aria-level="1">{esc(APP_NAME)}</div>'
                    f'<p class="psfal-line">{esc(tagline)}</p><p class="psfal-line">{freshness}</p></div>', unsafe_allow_html=True)
        with st.container(horizontal=True, key="nav_primary"):
            link(home, "Home")
            for p in families:
                link(p)
        with st.container(horizontal=True, key="nav_secondary"):
            for p in secondary:
                link(p)


LEGEND = ("Tested: the question was written down before running it and checked on later seasons. Descriptive: what happened, with no cause claimed. "
          "Assumption: the answer depends on a number nobody has measured.")


def evidence_legend():
    st.caption(LEGEND)


def keep_state(keys):
    """Streamlit drops a widget's value when the widget is not drawn on a run. Re-saving the keys keeps choices (sliders, inputs, sub-sections)
    when the reader moves between sections."""
    for k in keys:
        if k in st.session_state:
            st.session_state[k] = st.session_state[k]


def _hold(key):
    # Clicking the selected option of a segmented control clears it; put the last choice back so a sub-section is always shown.
    if st.session_state.get(key) is None:
        st.session_state[key] = st.session_state.get(f"{key}__last")
    st.session_state[f"{key}__last"] = st.session_state[key]


def subnav(key, options):
    """Sub-section switcher shown at the top of a section. Returns the chosen option."""
    st.session_state.setdefault(key, options[0])
    st.session_state.setdefault(f"{key}__last", st.session_state[key])
    st.segmented_control("Show", options, key=key, on_change=_hold, args=(key,), label_visibility="collapsed")
    return st.session_state[key] or options[0]


def open_analysis(label, page, sub_key=None, sub_value=None, key=None):
    """Button that opens another section, optionally at a given sub-section."""
    if st.button(label, key=key, type="tertiary", icon=":material/arrow_forward:"):
        if sub_key:
            st.session_state[sub_key] = sub_value
            st.session_state[f"{sub_key}__last"] = sub_value
        st.switch_page(page)


def stat_tile(key, label, value, note=None):
    with st.container(border=True, key=f"tile_{key}"):
        st.metric(label, value)
        if note:
            st.caption(note)


def split_note(name):
    """'USC (White Out, 7:30 p.m.)' -> ('USC', 'White Out, 7:30 p.m.'). Display only: the schedule data are not changed."""
    m = re.fullmatch(r"\s*(.+?)\s*\((.+)\)\s*", str(name))
    return (m.group(1), m.group(2)) if m else (str(name), "")


def module_status(modules, names):
    """The lab's own status lines (from the data's module table) for the named modules, so each family shows how far its research has got."""
    want = {n.lower() for n in names}
    for row in modules:
        if str(row[0]).lower() in want:
            st.caption(f"**Module status, {row[0]}:** {row[1]}. {row[2]}")


def fmt_spec(fmt):
    """Python format spec from a Plotly-style label format such as '%{x:+.2f}'. The plotly.js bundled with Streamlit 1.50 ignores a '+' in
    texttemplate formats and falls back to the raw number, so labels are formatted in Python instead. For these specs (sign, precision, 'f')
    Python and d3 formatting agree."""
    m = re.fullmatch(r"%\{[xy]:([^}]*)\}", fmt)
    return m.group(1) if m else ".2f"


def labels(values, fmt):
    spec = fmt_spec(fmt)
    return ["" if v is None else format(v, spec) for v in values]
