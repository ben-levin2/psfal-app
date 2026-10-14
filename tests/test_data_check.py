"""Tests for the data checks, coverage notes, dynamic game counts and data-link retries. Synthetic data only (copies of the test fixture,
changed in memory). Run from the repo root:  python -m unittest discover tests
"""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
import data_check  # noqa: E402
from make_fixture import fixture  # noqa: E402
from test_child15_dashboard import goto, make_app, open_view, run, texts  # noqa: E402  (also fixes PSFAL_TODAY for the app tests)

SEP1, OCT14 = dt.date(2026, 9, 1), dt.date(2026, 10, 14)


def game(wk, opp="Opp", res="W"):
    return {"wk": wk, "opp": opp, "pf": 30, "pa": 20, "res": res, "o": 50, "d": 60, "note": "x"}


def data(**changes):
    d = fixture()
    d.update(changes)
    return d


class CheckRules(unittest.TestCase):
    def test_clean_fixture_has_no_messages(self):
        self.assertEqual(data_check.check_data(fixture(), SEP1, 2026), [])

    def test_header_week_behind_the_results(self):
        d = data(games=[game(1), game(2), game(7)]); d["meta"]["through_week"] = 6
        self.assertIn("The header says data through week 6, but the results include week 7. Update meta.through_week.", data_check.check_data(d, SEP1, 2026))

    def test_header_week_ahead_of_the_results_is_allowed(self):
        # a bye week: data through week 6, last game in week 5
        d = data(games=[game(4), game(5)]); d["meta"]["through_week"] = 6
        self.assertEqual(data_check.check_data(d, SEP1, 2026), [])

    def test_through_week_not_a_number(self):
        d = fixture(); d["meta"]["through_week"] = "6"
        self.assertIn("meta.through_week should be a whole week number; it is '6'.", data_check.check_data(d, SEP1, 2026))

    def test_duplicate_week(self):
        msgs = data_check.check_data(data(games=[game(1), game(2, "A"), game(2, "B")]), SEP1, 2026)
        self.assertIn("Week 2 appears 2 times in the results. Remove the duplicate, or correct the week number.", msgs)
        self.assertIn("The latest game cannot be identified: 2 games are listed for week 2.", msgs)

    def test_out_of_order(self):
        msgs = data_check.check_data(data(games=[game(3), game(1), game(2)]), SEP1, 2026)
        self.assertIn("The results are not in week order. The dashboard uses the highest week as the latest game, but the file should be sorted.", msgs)

    def test_game_in_results_and_schedule(self):
        d = data(games=[game(1), game(6, "USC")], schedule=[["Oct 10", "USC (White Out, 7:30 p.m.)", "Home"], ["Oct 17", "Michigan", "Away"]])
        msgs = data_check.check_data(d, OCT14, 2026)
        self.assertEqual([m for m in msgs if "both the results and the remaining schedule" in m],
                         ["USC (White Out, 7:30 p.m.) (Oct 10) is in both the results and the remaining schedule. Remove it from the schedule; "
                          "if it was a second game against the same team, add that game's result."])
        # 'at Northwestern' in the results matches 'Northwestern' on the schedule
        d = data(games=[game(5, "at Northwestern")], schedule=[["Oct 3", "Northwestern", "Away"]])
        self.assertTrue(any("Northwestern (Oct 3) is in both" in m for m in data_check.check_data(d, OCT14, 2026)))

    def test_future_rematch_is_not_flagged(self):
        d = data(games=[game(9, "Ohio State")], schedule=[["Dec 5", "Ohio State (Big Ten Championship)", "Neutral"]]); d["meta"]["through_week"] = 9
        self.assertEqual(data_check.check_data(d, OCT14, 2026), [])

    def test_missing_fields(self):
        d = fixture(); del d["programs"]; del d["meta"]["snapshot"]
        g = game(4); del g["pa"]; d["games"].append(g)
        d["watch"][0].pop("refLabel")
        msgs = data_check.check_data(d, SEP1, 2026)
        self.assertIn("Missing from the data file: programs. Pages that use them cannot be shown until they are added.", msgs)
        self.assertIn("The data's meta section is missing snapshot.", msgs)
        self.assertIn("Result row 4 (Opp) is missing pa.", msgs)
        self.assertIn("Number to watch 1 is missing refLabel.", msgs)

    def test_week_that_is_not_a_number(self):
        msgs = data_check.check_data(data(games=[game(1), game("bye week", "X")]), SEP1, 2026)
        self.assertIn("Result row 2 (X) has no whole-number week ('bye week'); it is left out of the week-by-week chart and cannot be the latest game.", msgs)

    def test_malformed_rows_do_not_crash_the_check(self):
        msgs = data_check.check_data(data(games=[game(1), "oops"], schedule=[[], ["Oct 1"]], watch=["x"]), OCT14, 2026)
        self.assertIn("Result row 2 is not a game record.", msgs)

    def test_coverage_rules(self):
        d = data(games=[game(1), game(2), game(3)]); d["meta"]["through_week"] = 3
        d["meta"]["coverage"] = {"watch": 2, "transfers": 3}
        self.assertEqual(data_check.check_data(d, SEP1, 2026),
                         ["Numbers to watch are through week 2, but the results include week 3. Update them, then meta.coverage.watch."])
        d["meta"]["coverage"] = {"watch": 4, "transfers": "3", "kicking": 3}
        msgs = data_check.check_data(d, SEP1, 2026)
        self.assertIn("Numbers to watch say week 4, later than the header's week 3. Check meta.through_week and meta.coverage.watch.", msgs)
        self.assertIn("meta.coverage.transfers should be a whole week number; it is '3'.", msgs)
        self.assertIn("meta.coverage has an unknown section 'kicking'; known sections are watch, transfers.", msgs)
        d["meta"]["coverage"] = [3]
        self.assertIn('meta.coverage should map sections to weeks, for example {"watch": 6, "transfers": 6}.', data_check.check_data(d, SEP1, 2026))


class LatestAndCounts(unittest.TestCase):
    def test_latest_game_by_week_not_row_order(self):
        g, why = data_check.latest_game([game(3, "C"), game(1, "A"), game(2, "B")])
        self.assertEqual((g["opp"], why), ("C", None))

    def test_latest_game_unclear_cases(self):
        self.assertEqual(data_check.latest_game([game(2, "A"), game(2, "B")]), (None, "2 games are listed for week 2"))
        self.assertEqual(data_check.latest_game([game(None)]), (None, "no game in the results has a week number"))
        self.assertEqual(data_check.latest_game([]), (None, None))
        g, _ = data_check.latest_game([game(1, "A"), game("7", "B")])  # a week written as text is not trusted as the latest
        self.assertEqual(g["opp"], "A")

    def test_count_words(self):
        self.assertEqual([data_check.count_words(n) for n in (0, 1, 5, 6, 15, 16)],
                         ["no games", "one game", "five games", "six games", "fifteen games", "16 games"])

    def test_coverage_notes(self):
        d = data(games=[game(1), game(2)])
        self.assertEqual(data_check.coverage_note(d, "watch"),
                         "Numbers to watch: the data do not say which week these are through, so they may not include the latest game.")
        d["meta"]["coverage"] = {"watch": 1, "transfers": 2}
        self.assertEqual(data_check.coverage_note(d, "watch"),
                         "Numbers to watch: through week 1. The results include week 2, so these do not include the latest game yet.")
        self.assertEqual(data_check.coverage_note(d, "transfers"), "Transfer statistics: through week 2.")
        self.assertEqual(data_check.games_through(data(games=[game(1), game(2), game(4)]), 3), 2)  # weeks, not rows: a bye in week 3


class FetchRetry(unittest.TestCase):
    def test_failure_is_retried_after_the_wait_and_not_on_every_load(self):
        calls, failures = [], {}
        replies = [OSError("down"), {"meta": {}}]

        def fetch(url):
            calls.append(url)
            r = replies.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        d, note = data_check.fetch_with_retry("u", fetch, failures, now=100.0, wait=20)
        self.assertEqual((d, note), (None, "data_url was set but could not be read (OSError)"))
        d, note = data_check.fetch_with_retry("u", fetch, failures, now=110.0, wait=20)  # ten seconds later: not tried again yet
        self.assertIsNone(d); self.assertEqual(len(calls), 1)
        self.assertIn("it will be tried again in about 10 seconds", note)
        d, note = data_check.fetch_with_retry("u", fetch, failures, now=121.0, wait=20)  # after the wait: tried, and it works
        self.assertEqual((d, note, len(calls), failures), ({"meta": {}}, None, 2, {}))

    def test_streamlit_does_not_cache_a_failed_read(self):
        """The app's _fetch_ok raises on failure and relies on Streamlit not caching a call that raises (a returned None would be cached
        for the full 10 minutes, which was the old bug). If a Streamlit upgrade changes that, this fails."""
        import streamlit as st
        calls = []

        @st.cache_data(ttl=600, show_spinner=False)
        def read(url):
            calls.append(url)
            if len(calls) == 1:
                raise OSError("down")
            return {"ok": True}

        with self.assertRaises(OSError):
            read("u")
        self.assertEqual(read("u"), {"ok": True}); self.assertEqual(read("u"), {"ok": True})
        self.assertEqual(len(calls), 2)  # retried after the failure, then the success is cached
        read.clear()

    def test_empty_object_counts_as_a_failure(self):
        """Regression: an empty JSON object {} decodes successfully but holds no dashboard data. It must count as a failed read, so the
        app falls back to the app secrets and the bundled snapshot, and the link is retried after the usual wait."""
        failures = {}
        d, note = data_check.fetch_with_retry("u", lambda u: {}, failures, now=5.0)
        self.assertEqual((d, note, failures), (None, "data_url was set but could not be read (ValueError)", {"u": 5.0}))
        d, _ = data_check.fetch_with_retry("u", lambda u: {"meta": {}}, failures, now=26.0)  # after the wait, a real object is accepted
        self.assertEqual((d, failures), ({"meta": {}}, {}))

    def test_non_object_reply_counts_as_a_failure(self):
        failures = {}
        d, note = data_check.fetch_with_retry("u", lambda u: [1, 2], failures, now=5.0)
        self.assertEqual((d, note, failures), (None, "data_url was set but could not be read (ValueError)", {"u": 5.0}))

    def test_note_never_contains_the_link(self):
        _, note = data_check.fetch_with_retry("https://example.invalid/secret-token-123", lambda u: 1 / 0, {}, now=1.0)
        self.assertNotIn("secret-token-123", note)


class AppBehaviour(unittest.TestCase):
    def test_older_file_without_coverage(self):
        """A file in the old format (no meta.coverage) works and says the coverage is unknown instead of implying it is current."""
        with tempfile.TemporaryDirectory() as d:
            path = make_app(d)
            at = run(path)
            self.assertFalse(at.exception)
            self.assertFalse([w for w in at.warning if "Data check" in w.value])
            self.assertIn("Coverage not specified", [c.value for c in at.caption])  # on the watch card, not inferred from the snapshot
            trn = open_view(run(path), "Transfer Portal", "Transfer Portal Analytics")
            self.assertIn("The number of games covered is not stated in the data, ranked within Penn State's own position groups. Eight of the ten are "
                          "Iowa State transfers; that does not show they are better than other transfers.", [c.value for c in trn.caption])
            self.assertIn("three games in 2026", texts(open_view(run(path), "Research & Methods", "Limitations & methods")))

    def test_counts_follow_the_data(self):
        d6 = data(games=[game(w) for w in range(1, 7)]); d6["meta"]["coverage"] = {"watch": 6, "transfers": 5}
        with tempfile.TemporaryDirectory() as d:
            path = make_app(d, data=d6)
            self.assertIn("six games in 2026", texts(open_view(run(path), "Research & Methods", "Limitations & methods")))
            trn = open_view(run(path), "Transfer Portal", "Transfer Portal Analytics")
            caps = [c.value for c in trn.caption]
            self.assertIn("Five games, ranked within Penn State's own position groups. Eight of the ten are Iowa State transfers; that does not show "
                          "they are better than other transfers.", caps)
            self.assertIn("Transfer statistics: through week 5. The results include week 6, so these do not include the latest game yet.", caps)
            home = run(path)
            self.assertIn("Coverage: through week 6", [c.value for c in home.caption])  # one week stated for every card
            self.assertIn("Transfer statistics are through week 5, but the results include week 6.", texts(home))

    def test_latest_result_by_week_and_unclear(self):
        with tempfile.TemporaryDirectory() as d:
            at = run(make_app(d, data=data(games=[game(3, "Third", "L"), game(1, "First"), game(2, "Second")])))
            tiles = {m.label: m.value for m in at.metric}
            self.assertEqual(tiles["Latest result"], "L 30–20")
            self.assertIn("Week 3 · Third", [c.value for c in at.caption])
            self.assertIn("The results are not in week order.", texts(at))
        with tempfile.TemporaryDirectory() as d:
            at = run(make_app(d, data=data(games=[game(1), game(2, "A"), game(2, "B")])))
            self.assertFalse(at.exception)
            self.assertEqual({m.label: m.value for m in at.metric}["Latest result"], "Unclear")
            self.assertIn("Check the data: 2 games are listed for week 2", [c.value for c in at.caption])

    def test_game_in_results_and_schedule_is_not_called_missing(self):
        d1 = data(games=[game(1), game(6, "USC")], schedule=[["Oct 10", "USC (White Out, 7:30 p.m.)", "Home"], ["Oct 17", "Michigan", "Away"]])
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"PSFAL_TODAY": "2026-10-14"}):
            path = make_app(d, data=d1)
            at = run(path)
            self.assertIn("USC (White Out, 7:30 p.m.) (Oct 10) is in both the results and the remaining schedule.", texts(at))
            self.assertNotIn("Already played, result not in this data yet", texts(at))
            self.assertEqual({m.label: m.value for m in at.metric}["Next game"], "Michigan")
            games = goto(run(path), "2026 Games")
            self.assertNotIn("Played, result not in the data yet", [s.value for s in games.subheader])

    def test_check_is_shown_on_every_page_and_hides_nothing(self):
        d1 = data(games=[game(1), game(2), game(9)]); d1["meta"]["through_week"] = 6; del d1["modules"]
        with tempfile.TemporaryDirectory() as d:
            path = make_app(d, data=d1)
            for page in ("Home", "Competitive Edge Research", "2026 Games"):
                at = goto(run(path), page)
                self.assertIn("The header says data through week 6, but the results include week 9. Update meta.through_week.", texts(at), page)
                self.assertIn("Missing from the data file: modules.", texts(at), page)
            g26 = goto(run(path), "2026 Games")
            self.assertEqual([x for x in g26.table if "Week" in x.value.columns][0].value["Week"].tolist(), [1, 2, 9])  # every result still shown

    def test_empty_object_link_falls_back(self):
        """Regression: a data link that returns {} must not be used as the dashboard data (the header would fail on the missing meta);
        the next source is used and the reader is told."""
        import streamlit as st
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as live:
            path = make_app(d)
            f = Path(live) / "live.json"
            f.write_text("{}")
            with mock.patch.dict(os.environ, {"PSFAL_DATA_URL": f.as_uri()}):
                st.cache_resource.clear()
                at = run(path)
                self.assertFalse(at.exception)
                self.assertIn("snapshot TEST FIXTURE · source: bundled snapshot", texts(at))
                self.assertTrue(any(w.value.startswith("Data note: data_url was set but could not be read (ValueError)") for w in at.warning))
            st.cache_resource.clear()

    def test_empty_object_is_not_cached_as_data(self):
        """Regression: the app's cached reader must not keep {} as a successful read for 10 minutes. Run the app twice WITHOUT clearing
        Streamlit's data cache (the run() helper clears it): once the link holds real data and the retry wait has passed, it is used at once."""
        import streamlit as st
        from streamlit.testing.v1 import AppTest
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as live:
            path = make_app(d)
            f = Path(live) / "live.json"
            f.write_text("{}")
            with mock.patch.dict(os.environ, {"PSFAL_DATA_URL": f.as_uri()}):
                st.cache_data.clear(); st.cache_resource.clear()
                at = run(path)  # clears the data cache once, before the first read
                self.assertIn("source: bundled snapshot", texts(at))
                live_data = fixture(); live_data["meta"]["snapshot"] = "LIVE AFTER EMPTY"
                f.write_text(json.dumps(live_data))
                st.cache_resource.clear()  # stands in for the 20-second retry wait passing; the data cache is left alone
                at = AppTest.from_file(str(path), default_timeout=60); at.run()
                self.assertFalse(at.exception)
                self.assertIn("snapshot LIVE AFTER EMPTY · source: live data link", texts(at))  # {} was not cached as a success
            st.cache_data.clear(); st.cache_resource.clear()

    def test_failed_link_falls_back_then_recovers(self):
        import streamlit as st
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as live:
            path = make_app(d)
            f = Path(live) / "live.json"
            with mock.patch.dict(os.environ, {"PSFAL_DATA_URL": f.as_uri()}):
                st.cache_resource.clear()
                at = run(path)  # the link does not work yet: the bundled file is used and the reader is told
                self.assertIn("source: bundled snapshot", texts(at))
                self.assertTrue(any(w.value.startswith("Data note: data_url was set but could not be read") for w in at.warning))
                self.assertNotIn(f.as_uri(), texts(at))  # the link itself is never shown
                live_data = fixture(); live_data["meta"]["snapshot"] = "LIVE TEST"
                f.write_text(json.dumps(live_data))
                at = run(path)  # fixed a moment later: not retried on every load
                self.assertIn("source: bundled snapshot", texts(at))
                self.assertTrue(any("it will be tried again in about" in w.value for w in at.warning))
                st.cache_resource.clear()  # stands in for the retry wait passing
                at = run(path)
                self.assertIn("snapshot LIVE TEST · source: live data link", texts(at))
                self.assertFalse([w for w in at.warning if w.value.startswith("Data note")])
            st.cache_resource.clear()


WATCH3 = [{"label": "Sacks per game", "now": 1.2, "ref": 3.2, "refLabel": "3.2 in 2022 to 2024", "better": "high"},
          {"label": "Opponent run success rate", "now": 40, "ref": 44, "refLabel": "44% in 2025", "better": "low"},
          {"label": "Offense success rate", "now": 41.6, "ref": 46.6, "refLabel": "46.6% in 2022 to 2024", "better": "high"}]


def six_games(cov=None):
    d = data(games=[game(w) for w in range(1, 7)], watch=[dict(x) for x in WATCH3])
    d["meta"]["through_week"] = 6
    if cov is not None:
        d["meta"]["coverage"] = cov
    return d


class WatchCoverage(unittest.TestCase):
    """Per-card coverage of the numbers to watch (meta.coverage.watch as a map from card label to {through_week, games})."""

    def test_valid_per_card_coverage(self):
        d = six_games({"watch": {"Offense success rate": {"through_week": 6, "games": 6}, "Sacks per game": {"through_week": 6},
                                 "Opponent run success rate": {"games": 6}}})
        self.assertEqual(data_check.check_data(d, SEP1, 2026), [])
        self.assertEqual(data_check.watch_coverage_line(d, "Offense success rate"), "Coverage: six completed games through week 6")
        self.assertEqual(data_check.watch_coverage_line(d, "Sacks per game"), "Coverage: through week 6")
        self.assertEqual(data_check.watch_coverage_line(d, "Opponent run success rate"), "Coverage: six completed games")

    def test_cards_need_not_share_coverage(self):
        d = six_games({"watch": {"Offense success rate": {"through_week": 6, "games": 6}}})
        self.assertEqual(data_check.watch_coverage_line(d, "Offense success rate"), "Coverage: six completed games through week 6")
        self.assertEqual(data_check.watch_coverage_line(d, "Sacks per game"), "Coverage not specified")  # not borrowed from another card
        self.assertEqual(data_check.watch_coverage_line(d, "Opponent run success rate"), "Coverage not specified")
        self.assertEqual(data_check.check_data(d, SEP1, 2026), [])  # unspecified coverage is shown on the card, not warned about

    def test_missing_coverage_never_comes_from_the_snapshot(self):
        d = six_games()  # no meta.coverage at all: an older file
        d["meta"]["snapshot"] = "October 11, 2026"
        self.assertEqual(data_check.check_data(d, SEP1, 2026), [])  # older files load cleanly
        self.assertEqual({data_check.watch_coverage_line(d, x["label"]) for x in WATCH3}, {"Coverage not specified"})
        self.assertIsNone(data_check.watch_coverage(d, "Offense success rate"))

    def test_malformed_coverage(self):
        d = six_games({"watch": {"Offense success rate": {"through_week": "6", "games": -1, "plays": 400}, "Sacks per game": 6,
                                 "Opponent run success rate": {}}})
        msgs = data_check.check_data(d, SEP1, 2026)
        for m in ("meta.coverage.watch['Offense success rate'] has unknown keys plays; use through_week and games.",
                  "meta.coverage.watch['Offense success rate'].through_week should be a whole week number of 1 or more; it is '6'.",
                  "meta.coverage.watch['Offense success rate'].games should be a whole number of games; it is -1.",
                  'meta.coverage.watch[\'Sacks per game\'] should look like {"through_week": 6, "games": 6}; it is 6.',
                  'meta.coverage.watch[\'Opponent run success rate\'] should look like {"through_week": 6, "games": 6}; it is {}.'):
            self.assertIn(m, msgs)
        # a malformed entry never shows as coverage
        self.assertEqual({data_check.watch_coverage_line(d, x["label"]) for x in WATCH3}, {"Coverage not specified"})
        d["meta"]["coverage"] = {"watch": "week 6"}
        self.assertIn("meta.coverage.watch should be one week number or a map from a card's label to its coverage; it is 'week 6'.",
                      data_check.check_data(d, SEP1, 2026))
        self.assertEqual(data_check.watch_coverage_line(d, "Offense success rate"), "Coverage not specified")

    def test_conflicting_coverage(self):
        d = six_games({"watch": {"Offense success rate": {"through_week": 5, "games": 6}, "Sacks per game": {"through_week": 7, "games": 7},
                                 "Opponent run success rate": {"through_week": 4}, "Rushing success": {"through_week": 6}}})
        msgs = data_check.check_data(d, SEP1, 2026)
        for m in ("meta.coverage.watch['Offense success rate'] says 6 games through week 5, but Penn State plays at most one game a week.",
                  "meta.coverage.watch['Offense success rate'] says 6 games through week 5, but the results list only 5 completed games by week 5.",
                  "Sacks per game says week 7, later than the header's week 6. Check meta.through_week and meta.coverage.watch['Sacks per game'].",
                  "meta.coverage.watch['Sacks per game'] says 7 games through week 7, but the results list only 6 completed games by week 7.",
                  "Opponent run success rate is through week 4, but the results include week 6. Update it, then meta.coverage.watch['Opponent run success rate'].",
                  "meta.coverage.watch['Rushing success'] does not match any number to watch (labels: Sacks per game, Opponent run success rate, "
                  "Offense success rate). Check the spelling."):
            self.assertIn(m, msgs)
        self.assertEqual(data_check.watch_coverage_line(d, "Opponent run success rate"), "Coverage: through week 4 (the results include week 6)")

    def test_duplicate_labels(self):
        d = six_games({"watch": {"Sacks per game": {"through_week": 6}}})
        d["watch"][1]["label"] = "Sacks per game"
        self.assertIn("Two numbers to watch share the label 'Sacks per game', so their coverage cannot be told apart. Give each a distinct label.",
                      data_check.check_data(d, SEP1, 2026))

    def test_cards_show_coverage_and_keep_their_values(self):
        """On both pages each card shows its own coverage line; values, status and benchmark text are unchanged, and bad coverage only warns."""
        good = six_games({"watch": {"Offense success rate": {"through_week": 6, "games": 6}}})
        bad = six_games({"watch": {"Offense success rate": {"through_week": 5, "games": 9}}})
        for d1, line in ((good, "Coverage: six completed games through week 6"), (bad, "Coverage: nine completed games through week 5 (the results include week 6)")):
            with tempfile.TemporaryDirectory() as d:
                path = make_app(d, data=d1)
                home = run(path)
                self.assertFalse(home.exception)
                md = [m.value for m in home.markdown]
                self.assertIn("Offense success rate: **41.6%**  \n:red[Below the benchmark] :gray[· benchmark 46.6% in 2022 to 2024]", md)
                self.assertIn("Sacks per game: **1.2**  \n:red[Below the benchmark] :gray[· benchmark 3.2 in 2022 to 2024]", md)
                caps = [c.value for c in home.caption]
                self.assertIn(line, caps)
                self.assertEqual(caps.count("Coverage not specified"), 2)
                g26 = goto(run(path), "2026 Games")
                self.assertEqual([(m.label, m.value) for m in g26.metric], [("Sacks per game", "1.2"), ("Opponent run success rate", "40.0%"),
                                                                           ("Offense success rate", "41.6%")])
                self.assertIn(line, [c.value for c in g26.caption])
        self.assertIn("says 9 games through week 5", texts(home))  # the contradiction is reported, the dashboard still loads


if __name__ == "__main__":
    unittest.main(verbosity=2)
