"""Tests for the improvement sprint: standard header wording (group A) and stated data freshness (group B). Synthetic data only.
Run from the repo root:  python -m unittest discover tests
"""
import sys
import tempfile
from datetime import date
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
import data_check  # noqa: E402
from make_fixture import fixture  # noqa: E402
from test_child15_dashboard import chart, make_app, open_view, run, texts  # noqa: E402  (also fixes PSFAL_TODAY for the app tests)

TAGLINE = "What public data says about Penn State football from 2014 to 2026, with uncertainty shown."


def game(wk):
    return {"wk": wk, "opp": f"Opp{wk}", "pf": 30, "pa": 20, "res": "W", "o": 50, "d": 60, "note": "x"}


def data(games=6, **meta):
    d = fixture()
    d["games"] = [game(w) for w in range(1, games + 1)]
    d["meta"].update(meta)
    return d


class Wording(unittest.TestCase):
    def test_header_uses_the_standard_sentence_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            shown = texts(run(make_app(tmp)))
        self.assertEqual(shown.count(TAGLINE), 1)
        self.assertNotIn("What public data say about", shown)
        self.assertNotIn("with the uncertainty shown", shown)

    def test_old_wording_is_gone_from_the_app_source(self):
        src = (ROOT / "streamlit_app.py").read_text()
        self.assertIn(TAGLINE, src)
        self.assertNotIn("What public data say about", src)


class SectionFreshness(unittest.TestCase):
    def test_nothing_stated_is_reported_as_not_stated(self):
        f = data_check.section_freshness(data(), "transfers")
        self.assertEqual((f["status"], f["cutoff_week"], f["stated"], f["last_refresh"]), ("not stated", None, None, None))
        self.assertEqual(f["reasons"], [])

    def test_coverage_behind_the_latest_result_is_stale(self):
        f = data_check.section_freshness(data(coverage={"transfers": 5}), "transfers")
        self.assertEqual(f["status"], "stale")
        self.assertEqual(f["reasons"], ["it covers through week 5, but the results include week 6"])

    def test_coverage_at_the_latest_result_is_up_to_date_with_the_file_only(self):
        f = data_check.section_freshness(data(coverage={"transfers": 6}), "transfers")
        self.assertEqual((f["status"], f["reasons"]), ("up to date", []))

    def test_builder_note_saying_not_refreshed_is_stale(self):
        note = "NOT refreshed: through week 5 (the report lists only the top 5 per stat)"
        f = data_check.section_freshness(data(freshness={"transfers": note}), "transfers")
        self.assertEqual((f["status"], f["stated"]), ("stale", note))
        self.assertEqual(f["reasons"], ["the data file says this section was not refreshed"])

    def test_other_builder_notes_do_not_claim_freshness(self):
        f = data_check.section_freshness(data(freshness={"transfers": "through week 6"}), "transfers")
        self.assertEqual(f["status"], "not stated")  # a free-text note is shown, never read as proof the section is current

    def test_last_successful_refresh_only_when_valid(self):
        for value, want in (("2026-10-11T21:30:00-04:00", "2026-10-11T21:30:00-04:00"), ("2026-10-11", "2026-10-11"),
                            ("last Tuesday", None), ("", None), (20261011, None), (None, None)):
            with self.subTest(value=value):
                self.assertEqual(data_check.section_freshness(data(last_successful_refresh=value), "transfers")["last_refresh"], want)

    def test_snapshot_date_is_never_used_as_freshness(self):
        f = data_check.section_freshness(data(snapshot="October 11, 2026"), "transfers")
        self.assertEqual((f["snapshot"], f["status"], f["last_refresh"]), ("October 11, 2026", "not stated", None))


class TransferPortalAnalyticsView(unittest.TestCase):
    def view(self, d):
        with tempfile.TemporaryDirectory() as tmp:
            at = open_view(run(make_app(tmp, data=d)), "Transfer Portal", "Transfer Portal Analytics")
            self.assertFalse(at.exception)
            return at

    def test_unstated_freshness_says_so(self):
        at = self.view(data())
        caps = "\n".join(c.value for c in at.caption)
        self.assertIn("**Data cutoff:** not stated in the data", caps)
        self.assertIn("**Freshness:** not stated in the data", caps)
        self.assertIn("**Latest successful refresh:** not recorded in the data", caps)
        self.assertFalse([w for w in at.warning if "Stale" in w.value])

    def test_stale_section_is_marked_stale(self):
        note = "NOT refreshed: through week 5"
        at = self.view(data(freshness={"transfers": note}))
        self.assertTrue([w for w in at.warning if w.value.startswith("**Stale: these transfer statistics are not current.**")])
        self.assertIn(f"**Data cutoff:** as stated in the data file: “{note}”", "\n".join(c.value for c in at.caption))

    def test_recorded_values_are_shown_as_recorded(self):
        at = self.view(data(coverage={"transfers": 6}, last_successful_refresh="2026-10-11", snapshot="October 11, 2026"))
        caps = "\n".join(c.value for c in at.caption)
        for line in ("**Data cutoff:** through week 6 of 2026", "**Freshness:** up to date with the latest result in this data file",
                     "**Data snapshot:** October 11, 2026", "**Latest successful refresh:** 2026-10-11"):
            self.assertIn(line, caps)
        self.assertFalse([w for w in at.warning if "Stale" in w.value])


CANONICAL = [
    (1, "Recruiting Intelligence", "Recruiting High Schoolers"), (2, "Recruit Development Forecast", "Recruiting High Schoolers"),
    (3, "Recruiting Fit & Scheme Projection", "Recruiting High Schoolers"),
    (4, "Transfer Portal Analytics", "Transfer Portal"), (5, "Transfer Production Translation", "Transfer Portal"), (6, "Portal Fit & Acquisition Value", "Transfer Portal"),
    (7, "Player Development Analytics", "Player Development"), (8, "Development Trajectory & Breakout Forecast", "Player Development"),
    (9, "Opportunity-Adjusted Development", "Player Development"),
    (10, "Roster Analytics", "Roster Construction"), (11, "Retention & Continuity Forecast", "Roster Construction"),
    (12, "Resource Allocation Optimization", "Roster Construction"),
    (13, "Market Inefficiency Model", "Competitive Edge Research"), (14, "Game Analytics", "Competitive Edge Research"),
    (15, "Big Ten Competitive Intelligence", "Competitive Edge Research"),
]
NAV = {"Recruiting High Schoolers": ("Recruiting High Schoolers", "sub_rec"), "Transfer Portal": ("Transfer Portal", "sub_trn"),
       "Player Development": ("Player Development", "sub_dev"), "Roster Construction": ("Roster Construction", "sub_ros"),
       "Competitive Edge Research": ("Competitive Edge Research", "sub_cer")}


class Architecture(unittest.TestCase):
    def test_exactly_the_canonical_fifteen(self):
        import models
        self.assertEqual([(n, m, f) for n, m, f, *_ in models.MODELS], CANONICAL)
        self.assertEqual(models.FAMILIES, list(NAV))

    def test_market_inefficiency_is_competitive_edge_research(self):
        import models
        self.assertEqual(models.model("Market Inefficiency Model")[2], "Competitive Edge Research")

    def test_supporting_analysis_is_outside_the_count(self):
        import models
        self.assertEqual(models.SUPPORTING, {"Competitive Edge Research": ["Championship Gap"]})
        self.assertNotIn("Championship Gap", [m for _, m, *_ in models.MODELS])
        self.assertNotIn("Decision Tool", [m for _, m, *_ in models.MODELS])
        self.assertEqual(models.label("Championship Gap"), "Supporting analysis: Championship Gap")

    def test_status_is_never_overstated(self):
        import models
        status = {m: s for _, m, _, s, _ in models.MODELS}
        self.assertEqual({m for m, s in status.items() if s == "not implemented"},
                         {"Recruiting Fit & Scheme Projection", "Portal Fit & Acquisition Value", "Opportunity-Adjusted Development"})
        self.assertEqual(status["Resource Allocation Optimization"], "partial")
        self.assertEqual(status["Game Analytics"], "link only")
        self.assertEqual(status["Recruiting Intelligence"], "partial")

    def test_navigation_shows_the_numbered_models_per_family(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_app(tmp)
            for family, (page, key) in NAV.items():
                at = open_view(run(path), page)
                want = [f"{n} · {m}" for n, m, f in CANONICAL if f == family] + (["Supporting analysis: Championship Gap"] if family == "Competitive Edge Research" else [])
                self.assertEqual([getattr(o, "content", o) for o in at.button_group(key=key).options], want, family)

    def test_unimplemented_models_show_nothing_but_the_notice(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_app(tmp)
            for name, page in (("Recruiting Fit & Scheme Projection", "Recruiting High Schoolers"), ("Portal Fit & Acquisition Value", "Transfer Portal"),
                               ("Opportunity-Adjusted Development", "Player Development")):
                at = open_view(run(path), page, name)
                self.assertFalse(at.exception)
                self.assertTrue(at.info[0].value.startswith("**Not implemented.** No analysis, data or results exist for this model yet"), name)
                self.assertEqual((len(at.get("plotly_chart")), len(at.dataframe), len(at.table), len(at.metric)), (0, 0, 0, 0), name)

    def test_partial_and_link_only_models_say_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_app(tmp)
            dec = open_view(run(path), "Roster Construction", "Resource Allocation Optimization")
            self.assertTrue([w for w in dec.warning if w.value.startswith("**Decision Tool: an assumption-based what-if tool, not a validated optimization model.**")])
            self.assertIn("**Model 12 of 15** · Roster Construction · **Partly implemented**", texts(dec))
            game = open_view(run(path), "Competitive Edge Research", "Game Analytics")
            self.assertTrue(game.info[0].value.startswith("**Link only.** No game-analytics model is implemented on this page."))
            self.assertIn("**Link only, not an implemented model**", texts(game))
            gap = open_view(run(path), "Competitive Edge Research", "Championship Gap")
            self.assertIn("**Supporting analysis**, not one of the 15 PSFAL models.", texts(gap))
            self.assertIn("How Penn State loses", [s.value for s in gap.subheader])  # existing content kept


CH = "Chance of becoming a strong producer by 2027"


def forecast_data(status=None):
    d = fixture()
    d["watchClass"] = [["Stayer", "DL", 0.9, "5.0 TFL", 0.77], ["Leaver", "DL", 0.91, "3.0 TFL", 0.72], ["Unsure", "DB", 0.95, "24 tackles", 0.71]]
    if status is not None:
        d["watchClassStatus"] = status
    return d


def tables_by_columns(at):
    from test_child15_dashboard import tables
    return {tuple(x.columns): x for x in tables(at)}


def snapshot(names, as_of="2026-10-14", season=2026, **extra):
    """A synthetic roster snapshot: (name, recruit_class) pairs or plain names."""
    players = [{"id": str(i), "name": n if isinstance(n, str) else n[0], "recruit_class": None if isinstance(n, str) else n[1],
                "recruit_type": "HighSchool"} for i, n in enumerate(names)]
    return {"season": season, "as_of": as_of, "players": players, "provenance": {"source": "test roster"}, **extra}


TODAY = date(2026, 10, 17)
NOW = ("roster_snapshot.json",)  # leave the repository's real snapshot out of tests about other sources
BASE = ("Position", "Recruiting rating", "First-season production (2025)", CH)


class ForecastStatus(unittest.TestCase):
    def test_no_status_data_means_not_verified_for_everyone(self):
        st, problems = data_check.player_status(forecast_data())
        self.assertEqual({p: s["status"] for p, s in st.items()}, {"Stayer": "not verified", "Leaver": "not verified", "Unsure": "not verified"})
        self.assertEqual(problems, [])

    def test_a_status_needs_a_valid_date(self):
        st, problems = data_check.player_status(forecast_data({"Stayer": {"status": "current"}, "Leaver": {"status": "gone", "verified": "2026-10-15"},
                                                               "Nobody": {"status": "current", "verified": "2026-10-15"}}))
        self.assertEqual(st["Stayer"]["status"], "not verified")   # a status nobody dated is not treated as checked
        self.assertEqual(st["Leaver"]["status"], "not verified")   # unknown status word
        self.assertEqual(len(problems), 3)
        self.assertIn("watchClassStatus names 'Nobody', who is not in the forecast list; ignored.", problems)

    def view(self, d, today="2026-09-01", without=NOW):
        from unittest import mock
        import os
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"PSFAL_TODAY": today}):
            at = open_view(run(make_app(tmp, data=d, without=without)), "Recruiting High Schoolers", "Recruit Development Forecast")
            self.assertFalse(at.exception)
            return at

    def test_unverified_players_are_never_current_candidates(self):
        at = self.view(forecast_data())
        self.assertTrue(at.info[0].value.startswith("No player in this list has a verified current Penn State roster status"))
        t = tables_by_columns(at)
        self.assertEqual(list(t), [("Player", "Original rank") + BASE])  # one table: not verified
        self.assertEqual(list(t.values())[0]["Player"].tolist(), ["Stayer", "Leaver", "Unsure"])
        caps = texts(at)
        self.assertIn("**Roster status checked:** not recorded in the data", caps)
        self.assertIn("no player is confirmed in this data", caps)

    def test_departed_player_moves_to_historical_predictions(self):
        at = self.view(forecast_data({"Stayer": {"status": "current", "verified": "2026-10-15", "source": "roster page"},
                                      "Leaver": {"status": "transferred", "verified": "2026-10-15"},
                                      "Unsure": {"status": "unknown", "verified": "2026-10-15"}}))
        from test_child15_dashboard import tables
        self.assertEqual(len(tables(at)), 3)  # current, transferred or departed, unknown
        cur, _, unknown = tables(at)
        self.assertEqual(unknown["Player"].tolist(), ["Unsure"])
        t = tables_by_columns(at)
        md = [m.value for m in at.markdown]
        self.assertLess(md.index("**Current Penn State candidates**"), md.index("**Transferred or departed: historical predictions**"))
        gone = t[("Player", "Original rank") + BASE + ("Roster status", "Status verified on", "Status source")]
        self.assertEqual(gone["Player"].tolist(), ["Leaver"])
        self.assertEqual(gone["Roster status"].tolist(), ["transferred"])
        self.assertIn("**Roster status checked:** 2026-10-15", texts(at))
        self.assertFalse(at.info)  # someone is confirmed, so the "nobody confirmed" notice is not shown
        self.assertIn("Stayer", [s for s in cur["Player"]])
        self.assertNotIn("Leaver", [s for s in cur["Player"]])

    def test_recorded_status_merges_with_the_data_file_and_the_later_check_wins(self):
        rec = {"Leaver": {"status": "transferred", "verified": "2026-10-17", "source": "news report"},
               "Somebody else": {"status": "departed", "verified": "2026-10-17"}}  # not in this list: skipped without a warning
        st, problems = data_check.player_status(forecast_data(), rec)
        self.assertEqual(st["Leaver"], {"status": "transferred", "verified": "2026-10-17", "source": "news report"})
        self.assertEqual(st["Stayer"]["status"], "not verified")
        self.assertEqual(problems, [])
        newer = forecast_data({"Leaver": {"status": "current", "verified": "2026-10-20", "source": "roster page"}})
        self.assertEqual(data_check.player_status(newer, rec)[0]["Leaver"]["status"], "current")  # the data file's later check wins
        older = forecast_data({"Leaver": {"status": "current", "verified": "2026-09-01"}})
        self.assertEqual(data_check.player_status(older, rec)[0]["Leaver"]["status"], "transferred")
        tie = forecast_data({"Leaver": {"status": "departed", "verified": "2026-10-17"}})
        self.assertEqual(data_check.player_status(tie, rec)[0]["Leaver"]["status"], "departed")  # a tie keeps the data file
        bad = {"Leaver": {"status": "gone", "verified": "2026-10-17"}, "Stayer": {"status": "current", "verified": "soon"}}
        st, problems = data_check.player_status(forecast_data(), bad)
        self.assertEqual({st["Leaver"]["status"], st["Stayer"]["status"]}, {"not verified"})
        self.assertEqual(len(problems), 2)
        self.assertTrue(all(p.startswith("roster_status.json[") for p in problems))

    def test_names_match_despite_case_punctuation_and_suffixes_but_never_across_people(self):
        k = data_check.name_key
        self.assertEqual(k("LaVar Arrington II"), k("Lavar Arrington"))
        self.assertEqual(k("Jeff Exinor Jr."), k("jeff exinor"))
        self.assertEqual(k("Brady O'Hara"), k("Brady OHara"))
        self.assertNotEqual(k("Chaz Coleman"), k("Jabree Coleman"))
        self.assertNotEqual(k("Joshua Johnson"), k("Josh Johnson"))
        st, problems = data_check.player_status(forecast_data(), {"leaver": {"status": "departed", "verified": "2026-10-17"}})
        self.assertEqual(st["Leaver"]["status"], "departed")  # a record spelled differently still reaches its player

    def test_the_roster_decides_current_and_departed_and_flags_what_it_cannot_resolve(self):
        d = forecast_data()
        d["watchClass"].append(["Joshua Near", "DB", 0.88, "1 tackle", 0.4])
        roster, problem = data_check.roster_snapshot(snapshot(["Stayer", "Unsure", "Unsure", "Josh Near"]), 2026, TODAY)
        self.assertIsNone(problem)
        st, _ = data_check.player_status(d, None, roster)
        self.assertEqual((st["Stayer"]["status"], st["Stayer"]["verified"]), ("current", "2026-10-14"))
        self.assertEqual(st["Leaver"]["status"], "departed")  # not on the roster
        self.assertEqual(st["Unsure"]["status"], "unknown")   # two roster players share the name: never guessed
        self.assertEqual(st["Joshua Near"]["status"], "unknown")  # 'Josh Near' may be him: never called a departure
        self.assertIn("possible match: Josh Near", st["Joshua Near"]["source"])

    def test_a_dated_record_and_the_roster_snapshot_the_later_one_wins(self):
        roster, _ = data_check.roster_snapshot(snapshot(["Stayer", "Leaver"]), 2026, TODAY)
        rec = {"Leaver": {"status": "transferred", "verified": "2026-10-17", "source": "news"}}
        self.assertEqual(data_check.player_status(forecast_data(), rec, roster)[0]["Leaver"]["status"], "transferred")
        old = {"Leaver": {"status": "transferred", "verified": "2026-09-01", "source": "old news"}}
        self.assertEqual(data_check.player_status(forecast_data(), old, roster)[0]["Leaver"]["status"], "current")  # the later roster wins

    def test_stale_or_malformed_roster_snapshots_are_not_used(self):
        for obj, words in ((snapshot(["A"], season=2025), "is for 2025, not 2026"), (snapshot(["A"], as_of="2026-12-01"), "after today"),
                           (snapshot(["A"], as_of="soon"), "no valid as_of"), ({"season": 2026, "players": []}, "malformed"),
                           ({**snapshot(["A", "B"]), "players": [{"id": "1", "name": "A"}, {"id": "1", "name": "B"}]}, "repeated athlete ids")):
            got, problem = data_check.roster_snapshot(obj, 2026, TODAY)
            self.assertIsNone(got)
            self.assertIn(words, problem)
        self.assertEqual(data_check.roster_snapshot(None, 2026, TODAY), (None, None))

    def test_duplicate_forecast_entries_are_flagged_not_merged(self):
        d = forecast_data()
        d["watchClass"].append(["stayer", "DL", 0.9, "5.0 TFL", 0.5])
        roster, _ = data_check.roster_snapshot(snapshot(["Stayer"]), 2026, TODAY)
        st, problems = data_check.player_status(d, None, roster)
        self.assertEqual({st["Stayer"]["status"], st["stayer"]["status"]}, {"unknown"})
        self.assertTrue(any("2 entries for one player" in p for p in problems))

    def test_unscored_class_members_are_listed_without_a_chance(self):
        roster, _ = data_check.roster_snapshot(snapshot([("Stayer", 2025), ("New Guy", 2025), ("Old Hand", 2023), "Walk On"]), 2026, TODAY)
        self.assertEqual([r["name"] for r in data_check.unscored_class_members(forecast_data(), roster, 2025)], ["New Guy"])
        self.assertEqual(data_check.unscored_class_members(forecast_data(), None, 2025), [])

    def test_the_repository_records_chaz_coleman_as_transferred_with_date_and_source(self):
        import json
        rec = json.loads((ROOT / "roster_status.json").read_text())["watchClassStatus"]
        e = rec["Chaz Coleman"]
        self.assertEqual((e["status"], e["verified"]), ("transferred", "2026-10-17"))
        for part in ("2026 roster", "transfer portal", "Tennessee"):
            self.assertIn(part, e["source"])

    def test_the_repository_roster_snapshot_is_valid_and_sourced(self):
        import json
        raw = json.loads((ROOT / "roster_snapshot.json").read_text())
        snap, problem = data_check.roster_snapshot(raw, 2026, TODAY)
        self.assertIsNone(problem)
        self.assertEqual((snap["season"], snap["as_of"]), (2026, "2026-10-14"))
        self.assertTrue(snap["provenance"]["checks"] and "gopsusports.com" in snap["provenance"]["checks"][0])
        names = {data_check.name_key(p["name"]) for p in snap["players"]}
        self.assertNotIn(data_check.name_key("Chaz Coleman"), names)
        for n in ("Yvan Kemajou", "Daryus Dixson", "Alex Tatsch", "Jahmir Joseph", "Koby Howard"):
            self.assertIn(data_check.name_key(n), names)

    def leaderboard(self):
        """The Recruit Development Forecast's six names with SYNTHETIC chances (the real ones live in the data file), against the
        repository's real roster snapshot and status records, viewed on 2026-10-17."""
        d = fixture()
        chances = (0.80, 0.75, 0.70, 0.65, 0.60, 0.55)
        names = ("Yvan Kemajou", "Chaz Coleman", "Daryus Dixson", "Alex Tatsch", "Jahmir Joseph", "Koby Howard")
        d["watchClass"] = [[n, "DL", 0.9, "x", c] for n, c in zip(names, chances)]
        return d, self.view(d, today="2026-10-17", without=())

    def test_active_leaderboard_reranks_current_players_without_changing_any_chance(self):
        d, at = self.leaderboard()
        t = tables_by_columns(at)
        cur = t[("Player", "Rank", "Original rank") + BASE + ("Status verified on",)]
        self.assertEqual(cur["Player"].tolist(), ["Yvan Kemajou", "Daryus Dixson", "Alex Tatsch", "Jahmir Joseph", "Koby Howard"])
        self.assertEqual(cur["Rank"].tolist(), [1, 2, 3, 4, 5])
        self.assertEqual(cur["Original rank"].tolist(), [1, 3, 4, 5, 6])
        self.assertEqual(cur[CH].tolist(), [80, 70, 65, 60, 55])  # the original chances, unchanged
        self.assertEqual(set(cur["Status verified on"]), {"2026-10-14"})
        gone = t[("Player", "Original rank") + BASE + ("Roster status", "Status verified on", "Status source")]
        row = gone.iloc[0]
        self.assertEqual((row["Player"], row["Original rank"], row[CH], row["Roster status"], row["Status verified on"]),
                         ("Chaz Coleman", 2, 75, "transferred", "2026-10-17"))  # kept as a historical prediction, chance as generated
        self.assertIn("Tennessee", row["Status source"])
        self.assertEqual(sorted(cur[CH].tolist() + [row[CH]]), sorted(round(r[4] * 100) for r in d["watchClass"]))  # nothing changed or lost

    def test_current_class_members_missing_from_the_forecast_are_shown_unranked(self):
        _, at = self.leaderboard()
        t = tables_by_columns(at)
        missing = t[("Player", "Position")]["Player"].tolist()
        self.assertEqual(len(missing), 10)
        self.assertIn("LaVar Arrington II", missing)
        self.assertNotIn("Chaz Coleman", missing)
        self.assertIn("no chance is computed for them here", texts(at))
        self.assertIn("**Roster snapshot:** 2026 roster as of 2026-10-14", texts(at))

    def test_a_missing_chance_gets_no_rank_and_moves_nobody(self):
        d = forecast_data({p: {"status": "current", "verified": "2026-08-01"} for p in ("Stayer", "Leaver", "Unsure")})
        d["watchClass"][1][4] = None
        at = self.view(d)
        cur = tables_by_columns(at)[("Player", "Rank", "Original rank") + BASE + ("Status verified on",)]
        self.assertEqual(cur["Player"].tolist(), ["Stayer", "Unsure", "Leaver"])
        self.assertEqual(cur["Rank"].tolist()[:2], [1, 2])
        self.assertTrue(cur["Rank"].isna().tolist()[2])
        self.assertIn("Data note: Leaver: no valid forecast chance in the data file; shown without a chance or rank.", texts(at))

    def test_a_data_file_snapshot_takes_precedence_and_a_stale_one_falls_back(self):
        d = forecast_data()
        d["rosterSnapshot"] = snapshot(["Leaver"], as_of="2026-10-16")
        at = self.view(d, today="2026-10-17", without=())
        self.assertEqual(tables_by_columns(at)[("Player", "Rank", "Original rank") + BASE + ("Status verified on",)]["Player"].tolist(), ["Leaver"])
        d["rosterSnapshot"] = snapshot(["Leaver"], season=2025)
        at = self.view(d, today="2026-10-17", without=())
        self.assertIn("Data note: The roster snapshot is for 2025, not 2026; roster status was not taken from it.", texts(at))
        self.assertIn("**Roster snapshot:** 2026 roster as of 2026-10-14", texts(at))  # the repository's snapshot is used instead

    def test_chaz_coleman_forecast_is_kept_as_a_historical_prediction(self):
        """The original forecast row (72%) is unchanged; only its group changes, with the verification date and source shown."""
        d = fixture()
        d["watchClass"] = [["Chaz Coleman", "DL", 0.9065, "3.0 TFL", 0.72], ["Stayer", "DL", 0.9, "5.0 TFL", 0.77]]
        at = self.view(d)
        t = tables_by_columns(at)
        gone = t[("Player", "Original rank") + BASE + ("Roster status", "Status verified on", "Status source")]
        row = gone[gone["Player"] == "Chaz Coleman"].iloc[0]
        self.assertEqual((row[CH], row["Roster status"], row["Status verified on"]), (72, "transferred", "2026-10-17"))
        self.assertIn("Tennessee", row["Status source"])
        self.assertEqual(t[("Player", "Original rank") + BASE]["Player"].tolist(), ["Stayer"])
        self.assertIn("**Roster status checked:** 2026-10-17", texts(at))

    def test_list_generation_note_comes_only_from_the_data(self):
        d = forecast_data(); d["meta"]["freshness"] = {"watchClass": "not week-dependent: 2025 output and chance estimates; unchanged"}
        self.assertIn("**List generated:** as stated in the data file: “not week-dependent: 2025 output and chance estimates; unchanged”", texts(self.view(d)))
        self.assertIn("**List generated:** date not recorded in the data", texts(self.view(forecast_data())))


class RecruitingIntelligenceView(unittest.TestCase):
    def test_readable_labels_values_and_guide(self):
        d = fixture(); d["ratingCorr"] = [[1, 0.42, 61], [2, 0.31, 55], [3, 0.2, 38]]
        with tempfile.TemporaryDirectory() as tmp:
            at = open_view(run(make_app(tmp, data=d)), "Recruiting High Schoolers", "Recruiting Intelligence")
        self.assertFalse(at.exception)
        t = tables_by_columns(at)[("Year in the program", "Rating vs production (rank correlation)", "Players measured")]
        self.assertEqual(t.values.tolist(), [[1, 0.42, 61], [2, 0.31, 55], [3, 0.2, 38]])  # values unchanged; only the labels are readable
        shown = texts(at)
        self.assertIn("In year 1, players' recruiting ratings and their production line up at **0.42** (61 players). By year 3 it is **0.20** (38 players).", shown)
        self.assertIn("The smallest year has 38 players", shown)  # from the data, not a fixed claim
        self.assertIn("How much does a recruiting rating tell us about how a player will produce?", [s.value for s in at.subheader])
        self.assertIn("**A rating matters most early**  :gray-background[Descriptive]", [m.value for m in at.markdown])
        self.assertEqual([e.label for e in at.expander], ["Technical details"])


class Explainers(unittest.TestCase):
    def test_sp_plus_explainer_before_the_first_sp_chart(self):
        with tempfile.TemporaryDirectory() as tmp:
            gap = open_view(run(make_app(tmp)), "Competitive Edge Research", "Championship Gap")
        self.assertFalse(gap.exception)
        ex = [e for e in gap.expander if e.label == "What is SP+?"]
        self.assertEqual(len(ex), 1)
        body = "\n".join(m.value for m in ex[0].markdown) + "\n".join(c.value for c in ex[0].caption)
        for needle in ("**What it measures:**", "**Why PSFAL uses it:**", "**How it helps here:**", "**What it cannot tell us:**",
                       "It does not by itself explain wins and losses.", "The date the ratings were downloaded, and whether they are final end-of-season values, are not recorded"):
            self.assertIn(needle, body)

    def test_decision_chart_notes_are_kept_in_an_expander(self):
        with tempfile.TemporaryDirectory() as tmp:
            at = open_view(run(make_app(tmp)), "Roster Construction", "Resource Allocation Optimization")
        notes = [e for e in at.expander if e.label == "How to read this chart"][0]
        self.assertEqual(len(notes.caption), 2)
        self.assertIn("so part of the gap is playing time and not ability.", "\n".join(c.value for c in at.caption))  # the limitation stays visible


class BigTenSummary(unittest.TestCase):
    def test_summary_is_the_report_numbers_reshaped(self):
        from test_child15_dashboard import METRICS, load_report  # bound to the repo copy of the report reader at import time
        p, _ = load_report()
        with tempfile.TemporaryDirectory() as tmp:
            at = open_view(run(make_app(tmp)), "Competitive Edge Research", "Big Ten Competitive Intelligence")
            for w in ("2014-2025", "2021-2025"):
                at.radio(key="c15_window").set_value(w).run()
                self.assertFalse(at.exception)
                G = p["windows"][w]["groups"]
                s = tables_by_columns(at)[("Measure", "As measured", "vs Big Ten peers", "vs national average", "vs national champions")]
                self.assertEqual(len(s), len(METRICS))
                for (_, r), m in zip(s.iterrows(), METRICS):
                    self.assertTrue(r["Measure"].startswith(m))
                    self.assertEqual((r["vs Big Ten peers"], r["vs national average"], r["vs national champions"]),
                                     (G["peers"][m]["gap_sd"], G["national"][m]["gap_sd"], G["champions"][m]["gap_sd"]))
                ahead = sum(G["peers"][m]["gap_sd"] > 0 for m in METRICS)
                self.assertIn(f"ahead of season-specific Big Ten peers on **{ahead} of {len(METRICS)}** measures", texts(at))
                full = [e for e in at.expander if e.label.startswith("Full numbers")]
                self.assertEqual(len(full), 1)  # the full table is kept, one click away (contents checked by test_displayed_table_matches_report)

    def test_sp_plus_finality_and_date_are_stated_as_unverified(self):
        with tempfile.TemporaryDirectory() as tmp:
            at = open_view(run(make_app(tmp)), "Competitive Edge Research", "Big Ten Competitive Intelligence")
        self.assertIn("When they were downloaded, and whether they are final end-of-season ratings, are not recorded on this page and have not "
                      "been verified.", texts(at))
        self.assertEqual(len([e for e in at.expander if e.label == "What is SP+?"]), 1)


class ModuleStatus(unittest.TestCase):
    def test_every_model_has_both_statuses_and_validation_is_not_implied(self):
        import models
        self.assertEqual(sorted(models.RESEARCH), list(range(1, 16)))
        validated = {n for n, (status, _) in models.RESEARCH.items() if status.startswith("Validated")}
        self.assertEqual(validated, {7})  # only the model with a held-out validation report
        for n, name, _, status, _ in models.MODELS:
            if status == "not implemented":
                self.assertFalse(models.RESEARCH[n][0].startswith(("Validated", "Tested")), name)

    def test_table_shows_fifteen_rows_and_keeps_the_history(self):
        import models
        from test_child15_dashboard import tables
        with tempfile.TemporaryDirectory() as tmp:
            at = open_view(run(make_app(tmp)), "Research & Methods", "Module status")
        self.assertFalse(at.exception)
        # one table per family (no Family column), in family order, together all 15 models in number order
        cur = [x for x in tables(at) if tuple(x.columns) == ("Model", "Status", "Evidence")]
        self.assertEqual(len(cur), len(models.FAMILIES))
        for t, family in zip(cur, models.FAMILIES):
            self.assertEqual(list(t["Model"]), [models.label(m) for n, m, f, *_ in models.MODELS if f == family])
        rows = [r for t in cur for _, r in t.iterrows()]
        self.assertEqual([int(r["Model"].split(" · ")[0]) for r in rows], list(range(1, 16)))  # numbered like the navigation
        for r, (n, name, _, status, _) in zip(rows, models.MODELS):  # both statuses unchanged, each labelled
            self.assertEqual(r["Status"], f"On this dashboard: {models.STATUS_LABEL[status]}. Research: {models.RESEARCH[n][0]}.")
            self.assertEqual(r["Evidence"], models.RESEARCH[n][1])
        self.assertIn("On this dashboard: Partly implemented.", rows[11]["Status"])  # 12 · Resource Allocation Optimization
        self.assertIn(("Module", "Where it stands", "What it does and does not do"), tables_by_columns(at))  # original status history kept

    def test_statuses_resting_on_an_unavailable_report_say_so(self):
        """Models 5, 8, 11, 12 and 13 rest only on the dashboard's own evidence labels; their reports are not in this repository."""
        import models
        values = {5: ["0.37"], 8: ["0.65", "0.73"], 11: ["2.0", "1.97"], 12: ["1.5x"], 13: ["15 programs", "+1.9"]}  # research values kept
        for n, keep in values.items():
            status, evidence = models.RESEARCH[n]
            self.assertTrue(status.startswith("Original dashboard label: "), n)
            self.assertIn("source report unavailable", status)
            self.assertIn("not in this repository", evidence)
            for v in keep:
                self.assertIn(v, evidence, n)
        self.assertIn("Tested", models.RESEARCH[5][0]); self.assertIn("Assumption", models.RESEARCH[12][0])
        others = {n for n, (s, _) in models.RESEARCH.items() if "source report unavailable" in s}
        self.assertEqual(others, set(values))
        self.assertEqual(len(models.MODELS), 15)


class ImportantFindings(unittest.TestCase):
    def test_every_finding_is_complete_and_sourced(self):
        import findings, models
        for f in findings.FINDINGS:
            with self.subTest(f["key"]):
                self.assertEqual(set(findings.REQUIRED) - set(f), set())
                self.assertIn(f["status"], findings.STATUS)
                self.assertTrue(all(isinstance(f[k], str) and f[k].strip() for k in ("headline", "plain", "matters", "result", "sample", "cutoff", "source")))
                self.assertTrue(f["limits"])
                self.assertTrue(f["source"] in findings.REPORTS or f["source"] == findings.DASHBOARD_LIST)
                self.assertTrue((isinstance(f["model"], int) and 1 <= f["model"] <= 15) or f["model"] in ("Supporting analysis: Championship Gap",))
        self.assertEqual(len({f["key"] for f in findings.FINDINGS}), len(findings.FINDINGS))

    def test_dashboard_findings_keep_their_wording_and_labels(self):
        import findings
        src = (ROOT / "streamlit_app.py").read_text()
        dash = [f for f in findings.FINDINGS if f["source"] == findings.DASHBOARD_LIST]
        self.assertEqual(len(dash), 8)
        import re
        pairs = re.findall(r'\(\"(.+?)\", \"(descriptive|tested|assumption)\"\)', src)
        self.assertEqual(len(pairs), 8)
        self.assertEqual([f["headline"] for f in dash], [t for t, _ in pairs])  # headlines unchanged, in the original order
        self.assertEqual([f["label"] for f in dash], [k for _, k in pairs])  # the original evidence label is kept with each finding
        # their own group: never filed as validated, preliminary or hypothesis
        self.assertEqual({f["status"] for f in dash}, {"dashboard"})
        self.assertEqual([f for f in findings.FINDINGS if f["status"] == "dashboard"], dash)

    def test_dashboard_findings_show_their_original_badge_and_added_note(self):
        import findings
        with tempfile.TemporaryDirectory() as tmp:
            path = make_app(tmp)
            at = open_view(run(path), "Important Findings", "Dashboard findings")
            md = [m.value for m in at.markdown]
            for badge, n in ((":blue-background[Tested]", 3), (":gray-background[Descriptive]", 4), (":orange-background[Assumption]", 1)):
                self.assertEqual(md.count(badge + "  :gray[original dashboard evidence label]"), n, badge)
            self.assertIn("### Dashboard findings — original reports unavailable", md)
            self.assertEqual([c.value for c in at.caption].count(findings.ADDED_NOTE), 8)  # the added explanations are marked on every card
            for flt in ("Validated", "Preliminary", "Hypotheses"):
                shown = open_view(run(path), "Important Findings", flt)
                self.assertFalse([m for m in shown.markdown if "original dashboard evidence label" in m.value], flt)
                self.assertNotIn(findings.ADDED_NOTE, [c.value for c in shown.caption], flt)

    def test_page_renders_each_filter(self):
        import findings
        with tempfile.TemporaryDirectory() as tmp:
            path = make_app(tmp)
            header = [m.value for m in open_view(run(path), "Important Findings", "All").markdown]
            for badge, n in (("Validated", 3), ("Preliminary", 2), ("Hypothesis", 1), ("Original reports unavailable", 8)):
                self.assertTrue([m for m in header if f"[{badge}] **{n} {'finding' if n == 1 else 'findings'}**" in m], badge)  # the counts
            for flt, want in (("All", 14), ("Validated", 3), ("Preliminary", 2), ("Hypotheses", 1), ("Dashboard findings", 8)):
                at = open_view(run(path), "Important Findings", flt)
                self.assertFalse(at.exception, flt)
                caps = [c.value for c in at.caption if c.value.startswith("**Result:**")]
                self.assertEqual(len(caps), want, flt)
                for c in caps:
                    for part in ("**Model:**", "**Sample:**", "**Data cutoff:**"):
                        self.assertIn(part, c)
                self.assertEqual(len([e for e in at.expander if e.label == "Limitations and source"]), want)
            self.assertIn("Model 9: Opportunity-Adjusted Development (not implemented on this dashboard yet)", texts(open_view(run(path), "Important Findings", "Preliminary")))


class SplitStarDevelopmentChart(unittest.TestCase):
    """Four- and five-star lines come only from separately measured series, all lines from one source; the combined line is the fallback."""
    COMBINED = "4 and 5 stars (combined; source split unavailable)"

    def view(self, d, without=()):
        with tempfile.TemporaryDirectory() as tmp:
            at = open_view(run(make_app(tmp, data=d, without=without)), "Player Development", "Player Development Analytics")
            self.assertFalse(at.exception)
            return at

    def lines(self, at, name):
        return {t["name"]: t for t in chart(at, name)["data"] if t.get("name")}

    def repo_file(self):
        import json
        return json.loads((ROOT / "development_by_star.json").read_text())

    def test_a_split_in_the_data_file_is_used_as_given(self):
        d = fixture()
        d["traj"].update(star5=[68, 79], star4=[44, 56])
        at = self.view(d)
        got = self.lines(at, "4 stars")
        self.assertEqual({k: list(v["y"]) for k, v in got.items()},
                         {"4 stars": [44, 56], "5 stars": [68, 79], "3 stars": [40, 50], "2 stars or fewer": [30, 40]})
        self.assertIn("Source: the dashboard data file.", texts(at))

    def test_without_a_split_in_the_data_file_the_repository_series_are_used_whole(self):
        f = self.repo_file()
        at = self.view(fixture())  # the fixture has only the combined series
        got = self.lines(at, "5 stars")
        self.assertNotIn(self.COMBINED, got)
        for name, key in (("5 stars", "star5"), ("4 stars", "star4"), ("3 stars", "star3"), ("2 stars or fewer", "star2")):
            self.assertEqual(list(got[name]["y"]), f[key], name)  # every line from the file: never mixed with the data file's 3-star line
            self.assertEqual(list(got[name]["customdata"]), f["players"][key], name)
            self.assertIn("players)", got[name]["hovertemplate"])
        self.assertEqual(list(got["5 stars"]["x"]), f["years"])
        cap = texts(at)
        self.assertIn(f"Source: {f['provenance']['label']}", cap)
        self.assertIn("5 stars: " + ", ".join(map(str, f["players"]["star5"])), cap)  # small groups are named with their sizes

    def test_a_malformed_split_is_not_used(self):
        d = fixture()
        d["traj"].update(star5=[68], star4=[44, 56])  # one value missing: the data file's split is ignored, nothing is filled in
        got = self.lines(self.view(d), "5 stars")
        self.assertEqual(list(got["5 stars"]["y"]), self.repo_file()["star5"])

    def test_combined_source_is_disclosed_instead_of_fabricating_a_split(self):
        at = self.view(fixture(), without=("development_by_star.json",))
        got = self.lines(at, self.COMBINED)
        self.assertEqual(set(got), {self.COMBINED, "3 stars", "2 stars or fewer"})
        self.assertEqual(list(got[self.COMBINED]["y"]), [50, 60])
        self.assertIn("The current data source combines four- and five-star recruits.", texts(at))

    def test_repository_series_are_internally_consistent(self):
        """The combined series in the file must equal the season-weighted mean of its four- and five-star series, so the split series are the
        same measurement as the combined one, not separate estimates."""
        f = self.repo_file()
        self.assertEqual(f["players"]["star45"], [a + b for a, b in zip(f["players"]["star4"], f["players"]["star5"])])
        n = f["seasons"]
        self.assertEqual(n["star45"], [a + b for a, b in zip(n["star4"], n["star5"])])
        for i in range(len(f["years"])):
            w = (f["star4"][i] * n["star4"][i] + f["star5"][i] * n["star5"][i]) / n["star45"][i]
            self.assertAlmostEqual(w, f["star45"][i], delta=0.1)  # the file rounds each mean to 0.1
        self.assertEqual(f["provenance"]["seasons"], [2016, 2025])  # complete seasons only; 2026 is in progress
        self.assertIn("cd67a64b438c13f0", f["provenance"]["data"])


if __name__ == "__main__":
    unittest.main()
