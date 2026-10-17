"""Regression tests for _remove_result_annotated_schedule_rows (upstream commit b46e743): a schedule row is dropped only when it carries an
explicit ', played: W/L a–b' note that matches a game already in the results. Synthetic data only. The tests skip until the function is in
streamlit_app.py (that is, until b46e743 is merged into this branch).
Run from the repo root:  python -m unittest discover tests
"""
import ast
import copy
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from make_fixture import fixture  # noqa: E402
from test_child15_dashboard import goto, make_app, run, tables  # noqa: E402

NAME = "_remove_result_annotated_schedule_rows"
_fn = next((n for n in ast.parse((ROOT / "streamlit_app.py").read_text()).body if isinstance(n, ast.FunctionDef) and n.name == NAME), None)
needs_filter = unittest.skipIf(_fn is None, f"{NAME} is not in streamlit_app.py yet (it arrives with upstream b46e743)")
if _fn is not None:  # the function exactly as written in the app, without running the rest of the app
    _ns = {"re": re}
    exec(compile(ast.Module([_fn], []), "streamlit_app.py", "exec"), _ns)
    remove_rows = _ns[NAME]


def g(opp, res, pf, pa, wk=1):
    return {"wk": wk, "opp": opp, "res": res, "pf": pf, "pa": pa, "o": 50, "d": 50, "note": "x"}


def apply(schedule, games):
    d = {"schedule": copy.deepcopy(schedule), "games": games}
    remove_rows(d)
    return d["schedule"]


@needs_filter
class Filter(unittest.TestCase):
    def test_note_matching_a_recorded_game_removes_the_row(self):
        s = [["Oct 10", "USC (White Out, 7:30 p.m.), played: L 23–31", "Home"], ["Oct 17", "Michigan", "Away"]]
        self.assertEqual(apply(s, [g("USC", "L", 23, 31)]), [s[1]])

    def test_note_without_a_recorded_game_keeps_the_row(self):
        s = [["Oct 10", "USC, played: L 23–31", "Home"]]
        self.assertEqual(apply(s, []), s)
        self.assertEqual(apply(s, [g("Iowa", "L", 23, 31)]), s)

    def test_note_disagreeing_with_the_recorded_result_keeps_the_row(self):
        s = [["Oct 10", "USC, played: L 23–31", "Home"]]
        for game in (g("USC", "W", 23, 31), g("USC", "L", 24, 31), g("USC", "L", 31, 23)):
            self.assertEqual(apply(s, [game]), s, game)

    def test_row_without_a_note_is_kept_even_if_the_opponent_was_played(self):
        s = [["Oct 10", "USC (White Out, 7:30 p.m.)", "Home"], ["Oct 17", "Michigan", "Away"]]
        self.assertEqual(apply(s, [g("USC", "L", 23, 31)]), s)

    def test_valid_upcoming_games_are_kept(self):
        games = [g("Ohio State", "L", 14, 28), g("at Northwestern", "W", 30, 20), g("USC", "L", 23, 31)]
        s = [["Dec 5", "Ohio State (Big Ten Championship)", "Neutral"],       # rematch, no note
             ["Nov 1", "Northwestern", "Home"],
             ["Nov 8", "Purdue; Homecoming", "Home"],
             ["Nov 15", "Maryland, noon kickoff", "Away"],                    # a note that is not a result
             ["Nov 22", "Rutgers (played: W 30–20 last year)", "Home"]]       # 'played' inside parentheses
        self.assertEqual(apply(s, games), s)

    def test_hyphen_or_en_dash_and_any_case(self):
        for text in ("USC, played: L 23–31", "USC, played: L 23-31", "usc, PLAYED: l 23–31"):
            self.assertEqual(apply([["Oct 10", text, "Home"]], [g("USC", "L", 23, 31)]), [], text)

    def test_other_rows_keep_their_order_and_the_results_are_untouched(self):
        s = [["Oct 3", "A", "Home"], ["Oct 10", "USC, played: L 23–31", "Home"], ["Oct 17", "B", "Away"]]
        games = [g("USC", "L", 23, 31)]
        before = copy.deepcopy(games)
        self.assertEqual(apply(s, games), [s[0], s[2]])
        self.assertEqual(games, before)

    def test_malformed_data_is_left_alone(self):
        for d in ({}, {"schedule": None, "games": []}, {"schedule": [], "games": None}, [], None):
            before = copy.deepcopy(d)
            remove_rows(d)
            self.assertEqual(d, before)
        s = [[], ["Oct 1"], "oops", ["Oct 2", None, "Home"], ["Oct 3", 5, "Home"]]
        self.assertEqual(apply(s, [g("USC", "L", 23, 31), "bad"]), s)


@needs_filter
class InTheApp(unittest.TestCase):
    def setUp(self):
        self.data = fixture()
        self.data["games"] = self.data["games"] + [g("USC", "L", 23, 31, wk=6)]
        self.data["schedule"] = [["Oct 10", "USC (White Out, 7:30 p.m.), played: L 23–31", "Home"], ["Oct 17", "Michigan", "Away"],
                                 ["Oct 31", "Purdue", "Home"]]

    def test_played_row_is_not_upcoming_and_results_are_unchanged(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"PSFAL_TODAY": "2026-10-14"}):
            path = make_app(d, data=self.data)
            at = run(path)
            self.assertFalse(at.exception)
            tiles = {m.label: m.value for m in at.metric}
            self.assertEqual((tiles["Next game"], tiles["Games left"], tiles["2026 record"]), ("Michigan", "2", "3–1"))
            self.assertFalse([w for w in at.warning if "USC" in w.value])
            games = goto(run(path), "2026 Games")
            dfs = {tuple(x.columns): x for x in tables(games)}
            self.assertEqual(dfs[("Date", "Opponent", "Site")].values.tolist(), self.data["schedule"][1:])
            self.assertIn(["USC", "L 23–31"], dfs[("Week", "Opponent", "Result", "What stands out")][["Opponent", "Result"]].values.tolist())

    def test_note_without_a_result_still_reports_the_missing_result(self):
        self.data["games"] = self.data["games"][:-1]
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"PSFAL_TODAY": "2026-10-14"}):
            at = run(make_app(d, data=self.data))
            tiles = {m.label: m.value for m in at.metric}
            self.assertEqual((tiles["Next game"], tiles["2026 record"]), ("Michigan", "3–0"))
            self.assertTrue([w for w in at.warning if "USC" in w.value])


if __name__ == "__main__":
    unittest.main()
