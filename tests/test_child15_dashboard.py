"""Tests for the Child 15 dashboard integration. Run from the repo root:  python -m pytest tests -q   (or python tests/test_child15_dashboard.py)

They use a synthetic dashboard_data.json fixture (the real one is not in the repo) copied with the app into a temp folder.
"""
import io, json, re, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from make_fixture import fixture  # noqa: E402
from child15.report_reader import ReportError, load_report, parse_report, METRICS  # noqa: E402
from table_copy import to_tsv  # noqa: E402
import pandas as pd  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402


def make_app(tmp, with_report=True, report_text=None, app_src=None):
    tmp = Path(tmp)
    (tmp / "streamlit_app.py").write_text(app_src if app_src is not None else (ROOT / "streamlit_app.py").read_text())
    shutil.copy(ROOT / "table_copy.py", tmp / "table_copy.py")
    (tmp / "dashboard_data.json").write_text(json.dumps(fixture()))
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
    def test_app_starts_and_new_tab_renders(self):
        with tempfile.TemporaryDirectory() as d:
            at = run(make_app(d))
            self.assertFalse(at.exception, [str(e.value) for e in at.exception])
            self.assertEqual([t.label for t in at.tabs][:9], ["Overview", "2026 season", "Gap to champions", "Roster", "Players", "Market and portal", "Decision tool", "Status and limits", "Big Ten benchmark"])
            t = texts(at)
            for needle in ("1.40 standard deviations below", "12 champion team-seasons", "5 champion team-seasons", "across 7 distinct programs", "across 4 distinct programs",
                           "Not a causal explanation", "Not proof of market inefficiency", "not a predictive model", "Not yet built", "f0f4a521a28a"):
                self.assertIn(needle, t, needle)
            self.assertFalse(at.error)

    def test_window_switch(self):
        with tempfile.TemporaryDirectory() as d:
            at = run(make_app(d))
            at.radio(key="c15_window").set_value("2021-2025").run()
            self.assertFalse(at.exception)
            self.assertIn("1.40 standard deviations below", texts(at))  # headline stays the 2014-2025 finding

    def test_displayed_table_matches_report(self):
        with tempfile.TemporaryDirectory() as d:
            at = run(make_app(d))
            p, _ = load_report()
            for w in ("2014-2025", "2021-2025"):
                at.radio(key="c15_window").set_value(w).run()
                at.checkbox(key="c15_fixed").set_value(True).run()
                df = [x for x in at.dataframe if "Gap in SD (+ = PSU better)" in x.value.columns][0].value
                self.assertEqual(len(df), 32)
                names = {"Season-specific Big Ten peers": "peers", "National average": "national", "National champions": "champions", "Fixed 18-team Big Ten set (sensitivity)": "fixed18"}
                for _, r in df.iterrows():
                    src = p["windows"][w]["groups"][names[r["Comparison group"]]][r["Metric"]]
                    self.assertEqual((r["Gap in SD (+ = PSU better)"], r["Penn State"], r["Group mean"], r["Raw gap (PSU minus group)"], r["Programs"], r["Team-seasons"]),
                                     (src["gap_sd"], src["penn_state"], src["group_mean"], src["raw_gap"], src["programs"], src["team_seasons"]))
                    self.assertEqual(r["Period"], w)

    def test_chart_values_match_report(self):
        with tempfile.TemporaryDirectory() as d:
            at = run(make_app(d))
            p, _ = load_report()
            figs = at.get("plotly_chart")
            self.assertTrue(figs)
            fig = json.loads(figs[-1].proto.spec)
            got = {tr["name"]: list(tr["x"]) for tr in fig["data"]}
            for name, g in (("Season-specific Big Ten peers", "peers"), ("National average", "national"), ("National champions", "champions")):
                self.assertEqual(got[name], [p["windows"]["2014-2025"]["groups"][g][m]["gap_sd"] for m in METRICS])

    def test_missing_report_gives_clear_error_no_numbers(self):
        with tempfile.TemporaryDirectory() as d:
            at = run(make_app(d, with_report=False))
            self.assertFalse(at.exception)
            self.assertTrue(any("could not be shown" in e.value for e in at.error))
            self.assertNotIn("1.40 standard deviations", texts(at))

    def test_corrupt_report_gives_clear_error(self):
        with tempfile.TemporaryDirectory() as d:
            at = run(make_app(d, report_text="not a report"))
            self.assertFalse(at.exception)
            self.assertTrue(any("could not be shown" in e.value for e in at.error))

    def test_missing_module_does_not_break_other_tabs(self):
        with tempfile.TemporaryDirectory() as d:
            path = make_app(d)
            shutil.rmtree(Path(d) / "child15")
            at = run(path)
            self.assertFalse(at.exception)
            self.assertTrue(any("could not be loaded" in e.value for e in at.error))
            self.assertEqual(len(at.tabs), 9)

    def test_existing_tabs_unchanged_vs_original(self):
        """Render the ORIGINAL app (base commit 85eb850) and the new app on the same fixture; elements inside the 8 original tabs must be identical."""
        orig = subprocess.run(["git", "show", "85eb850:streamlit_app.py"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        def snap(at):
            out = []
            for t in list(at.tabs)[:8]:
                for kind in ("markdown", "caption", "subheader", "info", "warning", "success"):
                    out.append((t.label, kind, [e.value for e in getattr(t, kind)]))
                out.append((t.label, "df", [e.value.to_json() for e in t.dataframe]))
                out.append((t.label, "charts", [c.proto.spec for c in t.get("plotly_chart")]))
            return out
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            a = run(make_app(d1, app_src=orig)); b = run(make_app(d2))
            self.assertFalse(a.exception); self.assertFalse(b.exception)
            self.assertEqual(snap(a), snap(b))
            self.assertEqual(len(a.tabs), 8); self.assertEqual(len(b.tabs), 9)

    def test_every_table_has_collapsed_copy_section_matching_it(self):
        """Each table is followed by a collapsed copy section whose text is that table: headers first, same rows, same order."""
        with tempfile.TemporaryDirectory() as d:
            at = run(make_app(d))
            self.assertFalse(at.exception)
            self.assertEqual(len(at.dataframe), 10)
            for t in at.tabs:
                dfs, codes, exps = list(t.dataframe), list(t.code), list(t.expander)
                self.assertEqual((len(codes), len(exps)), (len(dfs), len(dfs)), t.label)
                for df, code, exp in zip(dfs, codes, exps):
                    self.assertFalse(exp.proto.expanded, t.label)
                    self.assertEqual(code.value, to_tsv(df.value), t.label)
                    self.assertEqual(code.value.split("\n")[0].split("\t"), [str(c) for c in df.value.columns], t.label)

    def test_copy_text_follows_widgets(self):
        """The Child 15 copy text tracks the period and the fixed-18 checkbox, and the decision-tool copy text tracks the cost slider."""
        with tempfile.TemporaryDirectory() as d:
            at = run(make_app(d))
            c15 = lambda: [c.value for c in at.tabs[8].code][0]
            self.assertEqual(len(c15().splitlines()), 1 + 24)
            at.radio(key="c15_window").set_value("2021-2025").run()
            at.checkbox(key="c15_fixed").set_value(True).run()
            rows = c15().splitlines()
            self.assertEqual(len(rows), 1 + 32)
            self.assertTrue(all(r.split("\t")[8] == "2021-2025" for r in rows[1:]))
            choice = lambda: {r.split("\t")[-1] for r in at.tabs[6].code[0].value.splitlines()[1:]}
            at.slider[0].set_value(1.2).run()
            self.assertEqual(choice(), {"Transfer"})
            at.slider[0].set_value(4.0).run()
            self.assertEqual(choice(), {"Recruit"})

    def test_no_network_or_recalc_in_child15(self):
        src = (ROOT / "child15" / "page.py").read_text() + (ROOT / "child15" / "report_reader.py").read_text()
        for bad in ("urllib", "requests", "read_csv", "mean(", "std(", "zscore"):
            self.assertNotIn(bad, src, bad)


class TableCopyTests(unittest.TestCase):
    def test_headers_rows_and_order(self):
        df = pd.DataFrame({"Player": ["A", "B"], "Rating": [90.5, 88], "Pos": ["QB", "WR"]})
        self.assertEqual(to_tsv(df), "Player\tRating\tPos\nA\t90.5\tQB\nB\t88.0\tWR")

    def test_index_left_out(self):
        df = pd.DataFrame({"x": [1, 2]}, index=[7, 9])
        self.assertEqual(to_tsv(df), "x\n1\n2")

    def test_cells_cannot_break_columns_or_rows(self):
        df = pd.DataFrame({"Note": ["one\ttab", "two\nlines\r\nhere", None], "n": [1.0, float("nan"), 3.0]})
        self.assertEqual(to_tsv(df), "Note\tn\none tab\t1.0\ntwo lines here\t\n\t3.0")

    def test_round_trips_like_a_spreadsheet_paste(self):
        """Read the text back the way a spreadsheet splits a paste (tabs = columns, lines = rows): headers and every value survive."""
        df = pd.DataFrame({"Metric": ["SP+ offense", "PPA defense"], "Gap in SD (+ = PSU better)": [-1.4, 0.25], "Programs": [7, 4], "Note": ["W 30–20", "−1.9 to +5.6"]})
        back = pd.read_csv(io.StringIO(to_tsv(df)), sep="\t")
        pd.testing.assert_frame_equal(back, df)

    def test_does_not_modify_the_table(self):
        df = pd.DataFrame({"a": ["x\ty"], "b": [None]})
        before = df.copy()
        to_tsv(df)
        pd.testing.assert_frame_equal(df, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
