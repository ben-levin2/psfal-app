"""Shared look and building blocks for the Penn State Football Analytics Lab. Colors live here and in .streamlit/config.toml; pages call these helpers
instead of repeating layout code."""
import html
import re
from datetime import datetime

import streamlit as st

APP_NAME = "Penn State Football Analytics Lab"
MISSION = "Competitive Edge Discovery"

# Interface colors (official Penn State)
NAVY, PUGH, WHITE = "#001E44", "#96BEE6", "#FFFFFF"
NAV_IDLE = "#14386B"  # lighter navy for inactive navigation; white text on it is above 9:1 contrast
# Chart series, in fixed order: Penn State, the nearer comparison group, the other comparison group. Penn State is always Nittany Navy;
# comparisons are Pugh Blue and a restrained slate. Checked with the dataviz palette validator against a white surface: every pair separates
# under color-vision deficiency (worst pair 26, target 8) and for normal vision. Pugh Blue is below 3:1 contrast on white, so every Pugh Blue
# mark gets a navy outline or a value label, and every chart keeps a legend or direct labels.
PSU, LIGHT, ACCENT = NAVY, PUGH, "#5E6B7E"
NEUTRAL, INK = "#8C96A6", "#12203A"
AXIS_INK, GRID = "#3D4A63", "#E6ECF3"  # axis text (about 9:1 on white) and recessive gridlines
GOOD, BAD = "#2A7A58", "#AE4337"
SHADE = "rgba(150, 190, 230, 0.22)"  # Pugh Blue wash for highlighted chart regions

# Evidence status: badge, short name, what it means (the definitions are the lab's own, unchanged)
EVIDENCE = {
    "tested": (":blue-background[Tested]", "Tested", "the question was written down before running it and checked on later seasons."),
    "descriptive": (":gray-background[Descriptive]", "Descriptive", "what happened, with no cause claimed."),
    "assumption": (":orange-background[Assumption]", "Assumption", "the answer depends on a number nobody has measured."),
}
BADGE = {k: v[0] for k, v in EVIDENCE.items()}

EDGE = "rgba(150, 190, 230, 0.45)"  # Pugh Blue at reduced strength, for card borders
SOFT = "#C9D6E8"  # light neutral for secondary text on navy
NAVY_CARD = '[class*="st-key-card_"], [class*="st-key-tile_"], [class*="st-key-panel_"]'
NAVY_ALERT = ('[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]), '
              '[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"])')
NAVY_ALL = ":is(" + NAVY_CARD + ", " + NAVY_ALERT + ")"

# Some rules below use Streamlit's own element names (data-testid values and the stMainBlockContainer class) because Streamlit offers no other
# hook for page padding. They are checked against Streamlit 1.50. If a later version renames them, the rule stops matching and Streamlit's
# default spacing returns; nothing is hidden or broken.
_CSS = f"""
<style>
/* Top spacing: Streamlit's top bar is 60px; its default 8rem (128px) padding left about 70px of empty space above the header. */
.stMainBlockContainer {{padding-top: 4.75rem; padding-bottom: 3rem;}}  /* Streamlit's default 10rem bottom padding is empty space */
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
/* ---- Navy cards: one style for every information card. A container joins it through its key: card_ (Key Findings), tile_ (metric tiles),
   panel_ (text panels). Streamlit's info and success boxes (highlighted results and the decision tool's verdict) use it too; warnings and
   errors keep their own colors because they mean "caution". Measured contrast on navy: white 16.5:1, Pugh Blue 8.5:1, SOFT 11:1. */
{NAVY_CARD} {{background: {NAVY} !important; border: 1px solid {EDGE} !important; border-radius: 10px; gap: 0.45rem;}}
[class*="st-key-card_"] {{border-top: 3px solid {PUGH} !important;}}  /* the Key Findings lead the page: a slightly stronger top edge */
{NAVY_ALERT} {{background: {NAVY} !important; border: 1px solid {EDGE}; border-left: 4px solid {PUGH};}}
{NAVY_ALL} :is(p, li, strong, em, h1, h2, h3, h4) {{color: {WHITE} !important;}}
{NAVY_ALL} [data-testid="stMetricValue"] {{color: {WHITE} !important; font-weight: 700;}}
[class*="st-key-tile_"] [data-testid="stMetricValue"] {{font-size: 1.55rem;}}
[class*="st-key-card_"] [data-testid="stMetricValue"] {{font-size: 1.7rem;}}
/* secondary text: metric labels in Pugh Blue, notes and captions in a soft light neutral */
{NAVY_ALL} [data-testid="stMetricLabel"] p {{color: {PUGH} !important; font-weight: 600; letter-spacing: 0.01em;}}
{NAVY_ALL} [data-testid="stCaptionContainer"], {NAVY_ALL} [data-testid="stCaptionContainer"] p {{color: {SOFT} !important;}}
/* status words inside cards (:green / :red / :gray text): lighter tints of the same meanings, readable on navy */
{NAVY_ALL} .stMarkdownColoredText[style*="21, 130, 55"] {{color: #8EDCB2 !important; font-weight: 600;}}
{NAVY_ALL} .stMarkdownColoredText[style*="189, 64, 67"] {{color: #FFA79D !important; font-weight: 600;}}
{NAVY_ALL} .stMarkdownColoredText[style*="49, 51, 63"] {{color: {SOFT} !important;}}
/* evidence labels: light chips with navy text; each kind keeps its own tint (Descriptive grey, Tested blue, Assumption amber) */
{NAVY_ALL} .stMarkdownColoredBackground {{color: {NAVY} !important; font-weight: 600; padding: 0.1em 0.45em; border-radius: 4px;}}
{NAVY_ALL} .stMarkdownColoredBackground[style*="49, 51, 63"] {{background-color: #E4E9F0 !important;}}
{NAVY_ALL} :is(.stMarkdownColoredBackground[style*="28, 131, 225"], .stMarkdownColoredBackground[style*="28, 131, 255"]) {{background-color: {PUGH} !important;}}  /* Streamlit 1.50 emits 28, 131, 255 for blue */
{NAVY_ALL} .stMarkdownColoredBackground[style*="255, 164, 33"] {{background-color: #F6D7A4 !important;}}
/* links inside cards: Pugh Blue, white and underlined on hover, a visible outline on keyboard focus */
{NAVY_ALL} button[kind="tertiary"], {NAVY_ALL} button[kind="tertiary"] p, {NAVY_ALL} button[kind="tertiary"] [data-testid="stIconMaterial"] {{color: {PUGH} !important; font-weight: 600;}}
{NAVY_ALL} button[kind="tertiary"]:hover p, {NAVY_ALL} button[kind="tertiary"]:hover [data-testid="stIconMaterial"] {{color: {WHITE} !important; text-decoration: underline;}}
{NAVY_ALL} button[kind="tertiary"]:focus-visible {{outline: 3px solid {PUGH}; outline-offset: 2px; border-radius: 3px;}}
/* cards side by side in a row share one height, so a longer note in one card does not leave the others short */
[data-testid="stColumn"]:has([class*="st-key-card_"], [class*="st-key-tile_"]) > [data-testid="stVerticalBlock"] {{height: 100%;}}
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]:has(> [class*="st-key-card_"], > [class*="st-key-tile_"]) {{flex: 1 1 auto;}}
[data-testid="stColumn"] [data-testid="stLayoutWrapper"] > :is([class*="st-key-card_"], [class*="st-key-tile_"]) {{height: 100%;}}
{NAVY_ALL} a {{color: {PUGH} !important;}}
{NAVY_ALL} a:hover {{color: {WHITE} !important;}}

/* Charts sit on white panels with a light edge, so each plot reads as one unit between its heading and its notes */
[data-testid="stPlotlyChart"] {{background: {WHITE}; border: 1px solid #DCE4EF; border-radius: 10px; padding: 0.6rem 0.75rem 0.3rem; box-shadow: 0 1px 2px rgba(0, 30, 68, 0.05);}}
.stMainBlockContainer h2, .stMainBlockContainer h3 {{color: {NAVY};}}
/* Tables drawn by table() below: hide the 0, 1, 2 row numbers Streamlit adds (it ignores a hidden index); keep the text selectable */
[class*="st-key-tbl"] th.row_heading, [class*="st-key-tbl"] th.blank {{display: none;}}
[data-testid="stTable"] table {{user-select: text; -webkit-user-select: text;}}
/* Streamlit wraps each cell's text in a paragraph; shown inline, a copied selection keeps one tab between cells and one line per row,
   so it pastes into a spreadsheet as rows and columns. */
[data-testid="stTable"] :is(td, th) [data-testid="stMarkdownContainer"], [data-testid="stTable"] :is(td, th) p {{display: inline;}}
/* Streamlit's word-break: break-word lets a narrow column split words at any letter ("Recruitin g"); the module-status tables and the
   forecast's wide tables wrap between words instead (those scroll sideways, first column pinned) */
:is([class*="st-key-tbl_model_status"], [class*="st-key-tblpin_watch_class"]) [data-testid="stTable"] :is(td, th) p {{word-break: normal; overflow-wrap: normal;}}
:is([class*="st-key-tblpin_watch_class_transferred"], [class*="st-key-tblpin_watch_class_unknown"]) td:last-child {{min-width: 22rem;}}  /* the status source */
/* a wide table keeps its first column in view while it scrolls sideways */
[class*="st-key-tblpin_"] td.col0, [class*="st-key-tblpin_"] th.col_heading.col0 {{position: sticky; left: 0; z-index: 1; background: {WHITE};
  box-shadow: 1px 0 0 #D6E0EE;}}
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


def game_date(text, season):
    """'Oct 10' -> date(season, 10, 10). January to July dates (bowls, playoffs) belong to the next calendar year. None if the text is not a date."""
    try:
        d = datetime.strptime(f"{str(text).strip()} {season}", "%b %d %Y").date()
    except ValueError:
        return None
    return d.replace(year=season + 1) if d.month < 8 else d


def split_schedule(rows, today, season):
    """Split the data's remaining-schedule rows ([date, opponent, site]) into games already played and games still to come. The data are
    hand-updated snapshots, so a game can be over before a new snapshot records its result. A game dated today still counts as to come;
    a row whose date cannot be read is kept as to come."""
    played, upcoming = [], []
    for r in rows:
        d = game_date(r[0], season)
        (played if d is not None and d < today else upcoming).append(r)
    return played, upcoming


def module_status(modules, names):
    """The lab's own status lines (from the data's module table) for the named modules, so each family shows how far its research has got."""
    want = {n.lower() for n in names}
    for row in modules:
        if str(row[0]).lower() in want:
            st.caption(f"**Module status, {row[0]}:** {row[1]}. {row[2]}")


# Charts are for reading, not exploring: Plotly's default drag mode (zoom) let any click-drag zoom into a box and a double-click rescale the axes,
# and its toolbar offered pan, box and lasso tools. These settings turn all of that off and keep hover tooltips.
CHART_CONFIG = {"displayModeBar": False, "scrollZoom": False, "doubleClick": False, "showAxisDragHandles": False, "showAxisRangeEntryBoxes": False}


def plot(fig):
    """Draw a Plotly chart that holds still under the mouse: no drag-to-zoom, pan, box or lasso selection, scroll zoom or double-click
    rescaling. Hover tooltips still work. Every chart in the app goes through here."""
    fig.update_layout(dragmode=False)
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)  # applies to every axis, including both panels of two-panel charts
    chart_type(fig)
    st.plotly_chart(fig, config=CHART_CONFIG)


def chart_type(fig):
    """Shared chart typography: darker axis text than Plotly's default grey, light gridlines, and hover boxes in white with a navy edge
    and the app's ink color, large enough to read. Data colors and values are not touched."""
    fig.update_layout(font=dict(color=INK), legend=dict(font=dict(size=13, color=INK)),
                      hoverlabel=dict(bgcolor=WHITE, bordercolor=NAVY, font=dict(size=13, color=INK), align="left"))
    for upd in (fig.update_xaxes, fig.update_yaxes):
        upd(tickfont=dict(size=12, color=AXIS_INK), title_font=dict(size=13, color=AXIS_INK), gridcolor=GRID, zerolinecolor="#C9D3E0")
    if fig.layout.hovermode in ("x unified", "y unified"):  # one hover box per row: its dashed guide line would cross the value labels
        fig.update_xaxes(showspikes=False); fig.update_yaxes(showspikes=False)


def table(df, key, formats=None, pin_first=False):
    """A plain HTML table. Its text can be dragged over, highlighted and copied like the rest of the page; st.dataframe draws its cells on a
    canvas, so it could not be. Every row is shown. `formats` maps a column to a function that turns a value into its displayed text (the
    stored values are unchanged); a missing value shows as a dash. With `pin_first`, the first column stays in view when the table scrolls."""
    fm = {c: _plain for c in df.columns if df[c].dtype.kind == "f"}  # unformatted decimals as the interactive tables showed them, not 0.500000
    fm.update(formats or {})
    with st.container(key=f"{'tblpin' if pin_first else 'tbl'}_{key}"):
        st.table(df.style.format(fm, na_rep="—"))


def _plain(v):
    return f"{v:.4f}".rstrip("0").rstrip(".")


def pct(v):
    """0.4 -> '40%', 0.4567 -> '45.67%': the same as the interactive tables' "percent" format (0 to 2 decimals)."""
    return f"{v * 100:.2f}".rstrip("0").rstrip(".") + "%"


def fmt_spec(fmt):
    """Python format spec from a Plotly-style label format such as '%{x:+.2f}'. The plotly.js bundled with Streamlit 1.50 ignores a '+' in
    texttemplate formats and falls back to the raw number, so labels are formatted in Python instead. For these specs (sign, precision, 'f')
    Python and d3 formatting agree."""
    m = re.fullmatch(r"%\{[xy]:([^}]*)\}", fmt)
    return m.group(1) if m else ".2f"


def labels(values, fmt):
    spec = fmt_spec(fmt)
    return ["" if v is None else format(v, spec) for v in values]
