"""Tests for the dashboard (four-section layout) and the Child 15 integration. Run from the repo root:  python -m pytest tests -q   (or python tests/test_child15_dashboard.py)

They use a synthetic dashboard_data.json fixture (the real one is not in the repo) copied with the app into a temp folder.
"""
import json, re, shutil, subprocess, sys, tempfile, unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from make_fixture import fixture  # noqa: E402
from child15.report_reader import ReportError, load_report, parse_report, METRICS  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402
from streamlit.testing.v1 import element_tree as _et  # noqa: E402
from streamlit.util import calc_md5  # noqa: E402


def make_app(tmp, with_report=True, report_text=None, app_src=None, data=None):
    """Copy the app into a temp folder with the synthetic fixture. `data` (a modified copy of fixture()) is written to the temp folder only."""
    tmp = Path(tmp)
    (tmp / "streamlit_app.py").write_text(app_src if app_src is not None else (ROOT / "streamlit_app.py").read_text())
    shutil.copy(ROOT / "ui.py", tmp / "ui.py")
    (tmp / "dashboard_data.json").write_text(json.dumps(data if data is not None else fixture()))
    shutil.copytree(ROOT / "child15", tmp / "child15", ignore=shutil.ignore_patterns("__pycache__", "*.md"))
    if with_report:
        (tmp / "child15" / "big_ten_benchmark.md").write_text(report_text if report_text is not None else (ROOT / "child15" / "big_ten_benchmark.md").read_text())
    return tmp / "streamlit_app.py"


def run(path):
    import streamlit as st
    st.cache_data.clear()
    for k in [k for k in sys.modules if k == "child15" or k.startswith("child15.")]:
        sys.modules.pop(k)
    sys.path[:] = [str(Path(path).parent)] + [x for x in sys.path if x not in (str(ROOT), str(Path(path).parent))]  # import child15 from the temp copy only
    at = AppTest.from_file(str(path), default_timeout=60)
    at.run()
    return at


def texts(at):
    out = []
    for kind in ("markdown", "caption", "info", "warning", "error", "subheader", "metric"):
        out += [e.value for e in getattr(at, kind)]
    return "\n".join(out)


# Streamlit 1.50's test harness reads a single-choice segmented control's value as a list and iterates the string's characters. Wrap a lone
# value in a list so the harness can drive the sub-section switcher; the app itself is unaffected.
_bg_value = _et.ButtonGroup.value.fget
_et.ButtonGroup.value = property(lambda self: (lambda v: v if isinstance(v, list) else ([] if v is None else [v]))(_bg_value(self)))

# page -> (URL path, sub-section switcher key or None, sub-sections)
PAGES = {
    "Home": ("", None, [None]),
    "Recruiting High Schoolers": ("recruiting", "sub_rec", ["Recruiting Intelligence", "Recruit Development Forecast", "Market Inefficiency Model"]),
    "Transfer Portal": ("transfer-portal", "sub_trn", ["Transfer Production Translation", "Transfer Portal Analytics"]),
    "Player Development": ("player-development", "sub_dev", ["Player Development Analytics", "Development Trajectory & Breakout Forecast"]),
    "Roster Construction": ("roster-construction", "sub_ros", ["Roster Analytics", "Retention & Continuity Forecast", "Decision Tool"]),
    "Competitive Edge Research": ("competitive-edge", "sub_cer", ["Championship Gap", "Big Ten Competitive Intelligence", "Game Analytics"]),
    "2026 Games": ("games-2026", None, [None]),
    "Research & Methods": ("research-methods", "sub_rm", ["All findings", "Module status", "Limitations & methods"]),
}


def goto(at, page):
    """Open a page the way the browser does (by its URL path). AppTest.switch_page only accepts page files and does not follow an in-app
    st.switch_page, so set the page hash Streamlit derives from the URL path."""
    at._page_hash = calc_md5(PAGES[page][0]) if PAGES[page][0] else ""
    return at.run()


def open_view(at, page, sub=None):
    goto(at, page)
    if sub:
        at.button_group(key=PAGES[page][1]).set_value([sub]).run()
    return at


def every_view(path):
    """Yield (name, app) for every page and every sub-section."""
    for page, (_, key, subs) in PAGES.items():
        at = goto(run(path), page)
        for s in subs:
            if s:
                at.button_group(key=key).set_value([s]).run()
            yield f"{page} / {s}" if s else page, at


def _arr(v):
    """A plotted array as a plain list. Plotly 6 writes numeric arrays from pandas/numpy as {'dtype': ..., 'bdata': base64}; decode those."""
    if isinstance(v, dict) and "bdata" in v:
        import base64
        import numpy as np
        return np.frombuffer(base64.b64decode(v["bdata"]), dtype=np.dtype(v["dtype"])).tolist()
    return v if isinstance(v, list) else []


def _decoded(spec):
    for tr in spec["data"]:
        for k in ("x", "y", "customdata"):
            if isinstance(tr.get(k), dict):
                tr[k] = _arr(tr[k])
        for k in ("array", "arrayminus"):
            if isinstance((tr.get("error_x") or {}).get(k), dict):
                tr["error_x"][k] = _arr(tr["error_x"][k])
    return spec


def chart_values(c):
    """All numbers a chart plots (x, y and error-bar lengths), rounded, as a multiset. Colors, labels and layout are left out."""
    out = Counter()
    for tr in _decoded(json.loads(c.proto.spec))["data"]:
        for arr in (tr.get("x"), tr.get("y"), (tr.get("error_x") or {}).get("array"), (tr.get("error_x") or {}).get("arrayminus")):
            for v in _arr(arr):
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    out[round(float(v), 9)] += 1
    return out


def chart(at, trace_name):
    """The parsed spec (arrays decoded) of the first chart on the page that has a trace with this name."""
    for c in at.get("plotly_chart"):
        spec = _decoded(json.loads(c.proto.spec))
        if any(tr.get("name") == trace_name for tr in spec["data"]):
            return spec
    raise AssertionError(f"no chart with a trace named {trace_name!r}")


def table_json(df):
    """Table contents for comparison. The 2025-class Chance column is now a number (77) shown as 77%; the old app stored the text '77%'."""
    df = df.copy()
    if "Chance" in df and df["Chance"].dtype == object:
        df["Chance"] = df["Chance"].str.rstrip("%").astype(int)
    for c in df.columns:
        if str(df[c].dtype) == "Int64":
            df[c] = df[c].astype(object).where(df[c].notna(), None)
    return df.to_json()


def tables(at):
    """Every table on the page, interactive (st.dataframe) or static (st.table, whose first column may be its index), as DataFrames."""
    return [x.value for x in at.dataframe] + [x.value.reset_index() if x.value.index.name else x.value for x in at.table]


TEXT_KINDS = ("markdown", "caption", "info", "warning", "success", "error", "subheader")


def view_texts(at):
    return {e.value for kind in TEXT_KINDS for e in getattr(at, kind)}


class ReaderTests(unittest.TestCase):
    def test_parses_all_groups_windows_metrics(self):
        p, info = load_report()
        for w in ("2014-2025", "2021-2025"):
            for g in ("peers", "fixed18", "national", "champions"):
                self.assertEqual(list(p["windows"][w]["groups"][g]), METRICS)
        self.assertEqual(p["windows"]["2014-2025"]["champion_sample"], (12, 7))
        self.assertEqual(p["windows"]["2021-2025"]["champion_sample"], (5, 4))
        self.assertEqual(info["sha256"], "f0f4a521a28ac221b47aab325662102908a8b6b1b89635b4ef2afdc6060a9f09")
        self.assertEqual(info["bytes"], 10287)

    def test_every_table_cell_matches_report_text(self):
        """Independent check: each parsed gap equals the number printed in the markdown row it came from."""
        text = (ROOT / "child15" / "big_ten_benchmark.md").read_text()
        p, _ = load_report()
        n = 0
        win = grp = None
        names = {"Season-specific Big Ten peers (primary)": "peers", "Fixed 18-team Big Ten set (sensitivity)": "fixed18", "National table average": "national", "National champions": "champions"}
        for line in text.splitlines():
            if line.startswith("## "):
                grp = None
                win = ("2014-2025" if "2014-2025" in line else "2021-2025") if line.startswith("## Window") else None
            if line.startswith("## Window"):
                pass
            elif line.startswith("### "):
                grp = names.get(line[4:].strip())
            elif grp and win and line.startswith("| ") and not line.startswith("| Metric") and not line.startswith("|---"):
                c = [x.strip() for x in line.strip("|").split("|")]
                r = p["windows"][win]["groups"][grp][c[0]]
                self.assertEqual([r["penn_state"], r["group_mean"], r["raw_gap"], r["gap_sd"]], [float(x) for x in c[1:5]])
                self.assertEqual(f"{r['programs']} / {r['team_seasons']}", c[5]); n += 1
        self.assertEqual(n, 2 * 4 * 8)

    def test_headline_value(self):
        p, _ = load_report()
        self.assertEqual(p["windows"]["2014-2025"]["groups"]["champions"]["PPA offense"]["gap_sd"], -1.40)

    def test_missing_report_raises(self):
        with self.assertRaises(ReportError):
            load_report(ROOT / "child15" / "nope.md")

    def test_malformed_report_raises(self):
        text = (ROOT / "child15" / "big_ten_benchmark.md").read_text()
        with self.assertRaises(ReportError):
            parse_report(text.replace("| PPA offense |", "| Mystery metric |", 1))
        with self.assertRaises(ReportError):
            parse_report(text.split("## Window 2021-2025")[0])
        with self.assertRaises(ReportError):
            parse_report(text.replace("Champion sample in this window: 12", "Champion sample missing: 12"))


class AppTests(unittest.TestCase):
    def test_home_renders_snapshot_findings_and_watch_row(self):
        with tempfile.TemporaryDirectory() as d:
            at = run(make_app(d))
            self.assertFalse(at.exception, [str(e.value) for e in at.exception])
            self.assertEqual([s.value for s in at.subheader], ["Team snapshot", "Key Findings", "This season: numbers to watch"])
            # snapshot straight from the fixture: three wins, latest 30-20 win, first remaining game, one game left
            self.assertEqual([(m.label, m.value) for m in at.metric][:4], [("2026 record", "3–0"), ("Latest result", "W 30–20"), ("Next game", "Opp"), ("Games left", "1")])
            self.assertIn("<strong>Data through week 6 of 2026</strong> · snapshot TEST FIXTURE · source: bundled snapshot", texts(at))
            self.assertIn("Penn State Football Analytics Lab", texts(at))
            self.assertFalse(at.dataframe)  # schedule moved to 2026 Games
            self.assertFalse(at.error)

    def test_next_game_tile_separates_notes_without_changing_data(self):
        data = fixture(); data["schedule"] = [["Oct 10", "USC (White Out, 7:30 p.m.)", "Home"], ["Oct 17", "Michigan", "Away"]]
        with tempfile.TemporaryDirectory() as d:
            path = make_app(d, data=data)
            at = run(path)
            tile = [m for m in at.metric if m.label == "Next game"][0]
            self.assertEqual(tile.value, "USC")
            self.assertIn("Oct 10 · Home · White Out, 7:30 p.m.", [c.value for c in at.caption])
            games = goto(run(path), "2026 Games")
            sched = [x.value for x in games.dataframe if "Site" in x.value.columns][0]
            self.assertEqual(sched.values.tolist(), data["schedule"])  # the schedule table still shows the full original text

    def test_navigation_has_home_five_families_and_two_destinations(self):
        with tempfile.TemporaryDirectory() as d:
            at = run(make_app(d))
            got = [(p.proto.label, p.proto.page) for p in at.get("page_link")]
            # page (and so keyboard) order: Home, the five families, then the secondary destinations (shown at the top right on wide screens by CSS only)
            self.assertEqual(got, [("Home", ""), ("Recruiting High Schoolers", "recruiting"), ("Transfer Portal", "transfer-portal"), ("Player Development", "player-development"),
                                   ("Roster Construction", "roster-construction"), ("Competitive Edge Research", "competitive-edge"), ("2026 Games", "games-2026"),
                                   ("Research & Methods", "research-methods")])

    def test_every_view_renders_without_errors(self):
        with tempfile.TemporaryDirectory() as d:
            n = 0
            for name, at in every_view(make_app(d)):
                self.assertFalse(at.exception, (name, [str(e.value) for e in at.exception]))
                self.assertFalse(at.error, name)
                self.assertNotIn("deprecated", texts(at), name)  # the Plotly keyword warning no longer appears on the page
                n += 1
            self.assertEqual(n, 18)

    def test_no_copy_table_sections_anywhere(self):
        with tempfile.TemporaryDirectory() as d:
            for name, at in every_view(make_app(d)):
                self.assertFalse([e for e in at.expander if "Copy this table" in e.label], name)
                self.assertFalse(at.code, name)

    def test_redesign_keeps_every_original_table_chart_and_text(self):
        """Render the app as it was before the redesign (add7469) and the new app on the same fixture. Every table must appear with the same contents,
        every chart's plotted numbers must appear in one chart, and every piece of explanatory text must appear somewhere, apart from the listed exceptions."""
        orig = subprocess.run(["git", "show", "add7469:streamlit_app.py"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        removed = {
            "What the data say",  # heading renamed to Key Findings (Home) and All findings (Research & Methods)
            "The keyword arguments have been deprecated and will be removed in a future release. Use `config` instead to specify Plotly configuration options.",
        }
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            a = run(make_app(d1, app_src=orig))
            self.assertFalse(a.exception)
            self.assertEqual(len(a.dataframe), 10); self.assertEqual(len(a.get("plotly_chart")), 11)
            # the old page-top result cards (Week n, opponent, score, Win/Loss): the same results are in the 2026 Games "What stood out" table
            cards = {f"Week {g['wk']}" for g in fixture()["games"]} | {f"**{g['opp']}**" for g in fixture()["games"]} | {f"### {g['pf']}–{g['pa']}" for g in fixture()["games"]} | {":green[**Win**]", ":red[**Loss**]"}
            old_text = {t for t in view_texts(a) if not t.startswith("What public data say about Penn State football")} - removed - cards
            new_dfs, new_charts, new_text = set(), [], set()
            for _, b in every_view(make_app(d2)):
                new_dfs |= {table_json(x) for x in tables(b)}
                new_charts += [chart_values(c) for c in b.get("plotly_chart")]
                new_text |= view_texts(b)
            self.assertEqual({table_json(x.value) for x in a.dataframe} - new_dfs, set())
            for c in a.get("plotly_chart"):
                old = chart_values(c)
                self.assertTrue(old, "an original chart produced no comparable numbers")
                self.assertTrue(any(not (old - new) for new in new_charts), f"values of an original chart are missing: {sorted(old)[:8]}")
            self.assertEqual(old_text - new_text, set())

    def test_key_findings_cards_keep_wording_badges_and_links(self):
        with tempfile.TemporaryDirectory() as d:
            path = make_app(d)
            research = view_texts(open_view(run(path), "Research & Methods", "All findings"))
            at = run(path)
            md = [m.value for m in at.markdown]
            for text, badge in (("Penn State beats nearly everyone below the elite tier.", ":gray-background[Descriptive]"), ("The biggest gap to national champions", ":gray-background[Descriptive]"),
                                ("Across 15 programs, no repeatable type", ":blue-background[Tested]"), ("A transfer is the better use of a roster spot", ":orange-background[Assumption]")):
                card = [m for m in md if m.startswith(text)]
                self.assertEqual(len(card), 1, text); self.assertIn(card[0], research)  # word for word from the full list
                self.assertTrue(any(m.startswith(badge) for m in md), badge)
            self.assertEqual([b.label for b in at.button][:5], ["Open the championship gap analysis", "Open the championship gap analysis", "Open recruiting and portal results",
                                                                "Open the decision tool", "All eight findings, with how each was tested"])
            for fi, page, sub, heading in ((0, "Competitive Edge Research", "Championship Gap", "How Penn State loses"), (1, "Competitive Edge Research", "Championship Gap", "How Penn State loses"),
                                           (4, "Recruiting High Schoolers", "Market Inefficiency Model", "Do some programs get more from their recruits than ratings predict?  :blue-background[Tested]"),
                                           (7, "Roster Construction", "Decision Tool", "Recruit or transfer?  :orange-background[Assumption]")):
                at = run(path)
                at.button(key=f"go_finding_{fi}").click().run()
                self.assertIn(heading, [s.value for s in at.subheader])  # the click runs the target analysis
                goto(at, page)
                self.assertEqual(at.button_group(key=PAGES[page][1]).value, [sub])
                self.assertIn(heading, [s.value for s in at.subheader])

    def test_schedule_and_results_on_2026_games(self):
        with tempfile.TemporaryDirectory() as d:
            at = goto(run(make_app(d)), "2026 Games")
            dfs = {tuple(x.value.columns): x.value for x in at.dataframe}
            self.assertEqual(dfs[("Date", "Opponent", "Site")].values.tolist(), fixture()["schedule"])
            self.assertEqual(dfs[("Week", "Opponent", "Result", "What stands out")]["Result"].tolist(), [f"{g['res']} {g['pf']}–{g['pa']}" for g in fixture()["games"]])
            self.assertIn("Three numbers to watch", [s.value for s in at.subheader])

    def test_charts_plot_the_source_values(self):
        data = fixture()
        data["gap"] = [["Roster talent", 1.38, 1.5, 1.82], ["SP+ offense", 0.72, 1.58, 1.76], ["Win percentage", 0.79, 1.66, 2.05]]
        data["games"] = [dict(g, wk=w, o=o, d=dd) for g, w, o, dd in zip(fixture()["games"], (1, 2, 4), (90, 65, 6), (94, 32, 54))]  # no game in week 3
        with tempfile.TemporaryDirectory() as d:
            path = make_app(d, data=data)
            gap = chart(open_view(run(path), "Competitive Edge Research", "Championship Gap"), "Penn State")
            pts = {(tr["name"], y, x) for tr in gap["data"] if tr.get("name") in ("Penn State", "Playoff teams", "Champions") for x, y in zip(tr["x"], tr["y"])}
            self.assertEqual(pts, {(n, r[0], r[k]) for r in data["gap"] for n, k in (("Penn State", 1), ("Playoff teams", 2), ("Champions", 3))})
            titles = [a["text"] for a in gap["layout"]["annotations"]]
            self.assertIn("Cleaner comparison: talent and recruiting", titles); self.assertIn("Partly circular: record, SP+ and per-play", titles)
            g26 = chart(goto(run(path), "2026 Games"), "Offense")
            off = [tr for tr in g26["data"] if tr["name"] == "Offense"][0]
            self.assertEqual(off["x"], [1, 2, 3, 4]); self.assertEqual(off["y"], [90, 65, None, 6]); self.assertFalse(off["connectgaps"])  # the missing week breaks the line
            fc = chart(open_view(run(path), "Roster Construction", "Retention & Continuity Forecast"), "Expected back in 2027 (line: the forecast's 80% range)")
            tr = [t for t in fc["data"] if t["name"].startswith("Expected back")][0]
            for (grp, n, exp, lo, hi), x, up, down in zip(data["forecast"], tr["x"], tr["error_x"]["array"], tr["error_x"]["arrayminus"]):
                self.assertAlmostEqual(x, exp); self.assertAlmostEqual(x + up, hi); self.assertAlmostEqual(x - down, lo)

    def test_forecast_and_research_caveats_stay_visible(self):
        with tempfile.TemporaryDirectory() as d:
            path = make_app(d)
            fc = texts(open_view(run(path), "Roster Construction", "Retention & Continuity Forecast"))
            self.assertIn("**Expected returners in 2027 by position group (not validated)**", fc)
            self.assertIn("Do not lean on the position-by-position numbers.", fc)
            gap = texts(open_view(run(path), "Competitive Edge Research", "Championship Gap"))
            self.assertIn("Record, SP+ and per-play rows are partly circular because champions are chosen for winning.", gap)
            b10 = texts(open_view(run(path), "Competitive Edge Research", "Big Ten Competitive Intelligence"))
            self.assertIn("The champion groups are very small, and the champion row is partly circular", b10)
            self.assertIn("† Named in the warning above as partly circular for the champion comparison.", b10)

    def test_missing_rank_and_numeric_chance(self):
        data = fixture()
        data["seasons"] = [[2014, "7–6", 36, None, 24], [2025, "10–3", 5, 12, 15]]
        data["watchClass"] = [["A", "QB", 0.9, "1", 0.05], ["B", "QB", 0.91, "1", 0.5], ["C", "QB", 0.95, "1", 0.77]]
        with tempfile.TemporaryDirectory() as d:
            path = make_app(d, data=data)
            gap = open_view(run(path), "Competitive Edge Research", "Championship Gap")
            seasons = [x for x in tables(gap) if "Talent rank" in x.columns][0]
            self.assertTrue(pd_isna(seasons["Talent rank"].iloc[0])); self.assertEqual(int(seasons["Talent rank"].iloc[1]), 12)  # missing stays missing, not 0 or a guess
            self.assertEqual(len(seasons), 2)  # static table: every season shown, no scroll box
            self.assertIn("— means the rank is missing from the data for that season.", texts(gap))
            wc = [x for x in open_view(run(path), "Recruiting High Schoolers", "Recruit Development Forecast").dataframe if "Chance" in x.value.columns][0].value
            self.assertEqual(wc["Chance"].tolist(), [5, 50, 77])
            self.assertEqual(wc.sort_values("Chance")["Player"].tolist(), ["A", "B", "C"])  # as text, "5%" would sort after "50%" and "77%"

    def test_decision_chart_follows_slider_and_rule(self):
        with tempfile.TemporaryDirectory() as d:
            at = open_view(run(make_app(d)), "Roster Construction", "Decision Tool")
            for cost, verdict in ((1.2, "Transfer"), (1.5, "Recruit"), (4.0, "Recruit")):  # fixture break-even is 1.5 at every position; equal counts as Recruit
                at.slider(key="cost").set_value(cost).run()
                spec = chart(at, "Break-even (95% range)")
                self.assertEqual(spec["layout"]["yaxis"]["ticktext"], [f"{p} · {verdict}" for p in ["QB", "RB", "WR", "TE", "DL", "LB", "DB"]])
                self.assertEqual([s["x0"] for s in spec["layout"]["shapes"] if s.get("type") == "rect"], [cost])
                table = [x.value for x in at.dataframe if "Better use of a spot" in x.value.columns][0]
                self.assertEqual(set(table["Better use of a spot"]), {verdict})

    def test_choices_kept_when_moving_between_sub_sections(self):
        with tempfile.TemporaryDirectory() as d:
            path = make_app(d)
            at = open_view(run(path), "Roster Construction", "Decision Tool")
            at.slider(key="cost").set_value(3.0).run()
            at.number_input(key="s_QB").set_value(5.0).run()
            for sub in ("Roster Analytics", "Decision Tool"):
                at.button_group(key="sub_ros").set_value([sub]).run()
            self.assertEqual(at.slider(key="cost").value, 3.0)
            self.assertEqual(at.number_input(key="s_QB").value, 5.0)
            at = open_view(run(path), "Competitive Edge Research", "Big Ten Competitive Intelligence")
            at.radio(key="c15_window").set_value("2021-2025").run()
            for sub in ("Championship Gap", "Big Ten Competitive Intelligence"):
                at.button_group(key="sub_cer").set_value([sub]).run()
            self.assertEqual(at.radio(key="c15_window").value, "2021-2025")

    def test_big_ten_view_renders(self):
        with tempfile.TemporaryDirectory() as d:
            at = open_view(run(make_app(d)), "Competitive Edge Research", "Big Ten Competitive Intelligence")
            self.assertFalse(at.exception, [str(e.value) for e in at.exception])
            t = texts(at)
            for needle in ("1.40 standard deviations below", "12 champion team-seasons", "5 champion team-seasons", "across 7 distinct programs", "across 4 distinct programs",
                           "Not a causal explanation", "Not proof of market inefficiency", "not a predictive model", "Not yet built", "f0f4a521a28a"):
                self.assertIn(needle, t, needle)
            self.assertFalse(at.error)

    def test_window_switch(self):
        with tempfile.TemporaryDirectory() as d:
            at = open_view(run(make_app(d)), "Competitive Edge Research", "Big Ten Competitive Intelligence")
            at.radio(key="c15_window").set_value("2021-2025").run()
            self.assertFalse(at.exception)
            self.assertIn("1.40 standard deviations below", texts(at))  # headline stays the 2014-2025 finding

    def test_displayed_table_matches_report(self):
        with tempfile.TemporaryDirectory() as d:
            at = open_view(run(make_app(d)), "Competitive Edge Research", "Big Ten Competitive Intelligence")
            p, _ = load_report()
            for w in ("2014-2025", "2021-2025"):
                at.radio(key="c15_window").set_value(w).run()
                at.checkbox(key="c15_fixed").set_value(True).run()
                df = [x for x in at.dataframe if "Gap in SD (+ = PSU better)" in x.value.columns][0].value
                self.assertEqual(len(df), 32)
                self.assertEqual(list(df.columns), ["Metric", "Comparison group", "Gap in SD (+ = PSU better)", "Penn State", "Group mean", "Raw gap (PSU minus group)",
                                                    "Direction", "Unit", "Period", "Programs", "Team-seasons"])
                names = {"Season-specific Big Ten peers": "peers", "National average": "national", "National champions": "champions", "Fixed 18-team Big Ten set (sensitivity)": "fixed18"}
                for _, r in df.iterrows():
                    src = p["windows"][w]["groups"][names[r["Comparison group"]]][r["Metric"]]
                    self.assertEqual((r["Gap in SD (+ = PSU better)"], r["Penn State"], r["Group mean"], r["Raw gap (PSU minus group)"], r["Programs"], r["Team-seasons"]),
                                     (src["gap_sd"], src["penn_state"], src["group_mean"], src["raw_gap"], src["programs"], src["team_seasons"]))
                    self.assertEqual(r["Period"], w)

    def test_chart_values_match_report(self):
        with tempfile.TemporaryDirectory() as d:
            at = open_view(run(make_app(d)), "Competitive Edge Research", "Big Ten Competitive Intelligence")
            p, _ = load_report()
            fig = chart(at, "National champions")
            got = {tr["name"]: list(tr["x"]) for tr in fig["data"]}
            for name, g in (("Season-specific Big Ten peers", "peers"), ("National average", "national"), ("National champions", "champions")):
                self.assertEqual(got[name], [p["windows"]["2014-2025"]["groups"][g][m]["gap_sd"] for m in METRICS])
            labels = {tr["name"]: tr["text"] for tr in fig["data"]}["National champions"]
            self.assertEqual(labels, [format(p["windows"]["2014-2025"]["groups"]["champions"][m]["gap_sd"], "+.2f") for m in METRICS])  # signed, two decimals

    def test_missing_report_gives_clear_error_no_numbers(self):
        with tempfile.TemporaryDirectory() as d:
            at = open_view(run(make_app(d, with_report=False)), "Competitive Edge Research", "Big Ten Competitive Intelligence")
            self.assertFalse(at.exception)
            self.assertTrue(any("could not be shown" in e.value for e in at.error))
            self.assertNotIn("1.40 standard deviations", texts(at))

    def test_corrupt_report_gives_clear_error(self):
        with tempfile.TemporaryDirectory() as d:
            at = open_view(run(make_app(d, report_text="not a report")), "Competitive Edge Research", "Big Ten Competitive Intelligence")
            self.assertFalse(at.exception)
            self.assertTrue(any("could not be shown" in e.value for e in at.error))

    def test_missing_module_does_not_break_other_views(self):
        with tempfile.TemporaryDirectory() as d:
            path = make_app(d)
            shutil.rmtree(Path(d) / "child15")
            for name, at in every_view(path):
                self.assertFalse(at.exception, name)
                if name.endswith("Big Ten Competitive Intelligence"):
                    self.assertTrue(any("could not be loaded" in e.value for e in at.error))
                else:
                    self.assertFalse(at.error, name)

    def test_no_network_or_recalc_in_child15(self):
        src = (ROOT / "child15" / "page.py").read_text() + (ROOT / "child15" / "report_reader.py").read_text()
        for bad in ("urllib", "requests", "read_csv", "mean(", "std(", "zscore"):
            self.assertNotIn(bad, src, bad)


def pd_isna(v):
    import pandas as pd
    return bool(pd.isna(v))


if __name__ == "__main__":
    unittest.main(verbosity=2)
