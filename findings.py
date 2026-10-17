"""Important Findings: each entry is tied to its source, sample, validation status, model and data cutoff. Display text only; nothing here is
calculated. Numbers from the PSFAL validation reports were checked against their saved result files (validation_results.json,
sensitivity_results.json, role_change_results.json) when this file was written; the SHA-256 of each source report is recorded so a changed
report can be noticed. The eight dashboard findings (FINDINGS in streamlit_app.py) keep their original wording; their original reports are not
in this repository, so their source is the dashboard's own findings list, and only details already stated on the dashboard are repeated.

STATUS (what kind of evidence it is; never a claim of cause):
    validated    the question and method were fixed in advance and the result was checked on later, held-out seasons. A validated result can be
                 negative: "not supported" is a validated finding too.
    preliminary  descriptive or exploratory: what happened, or an association, without a held-out test.
    hypothesis   an idea or assumption the data have not tested.
    dashboard    one of the dashboard's eight original findings. Its report is not in this repository, so it is NOT classed as validated,
                 preliminary or hypothesis; it keeps its original evidence label (`label`: tested, descriptive or assumption) as stated.
"""
STATUS = {
    "validated": ("Validated", "Fixed in advance and checked on later, held-out seasons. The result may be positive or negative."),
    "preliminary": ("Preliminary", "Descriptive or exploratory: what happened, or an association, without a held-out test. Not proof of cause."),
    "hypothesis": ("Hypothesis", "An idea or assumption the data have not tested."),
    "dashboard": ("Dashboard findings — original reports unavailable",
                  "The dashboard's original findings. Their reports are not in this repository, so each keeps its original evidence label "
                  "(Tested, Descriptive or Assumption) and is not counted as validated, preliminary or a hypothesis."),
}
# The explanation lines of a dashboard finding (plain, matters, result) were written for this page from details already on the dashboard;
# they are not text from the unavailable original reports, and the page says so.
ADDED_NOTE = ("Added explanation: the lines below the headline (explanation, why it matters, result) were written for this page from "
              "details shown elsewhere on the dashboard. They are not text from the unavailable original report.")

VALIDATION_DATA = ("Penn State player-seasons 2014–2026 (player_seasons.parquet, SHA-256 cd67a64b…5957525); tested seasons 2016–2025, "
                   "2026 excluded as in progress")
REPORTS = {
    "development_validation_report.md": "d8ae3d876d9480a607c1696d80b14cc32603b861e4a208dc7f3b7edc7c2ee248",
    "sensitivity_report.md": "863ddc6be38c443381bfea138202223685418aaca2507f19c55d68ba25d19449",
    "role_change_report.md": "3988bf374d2b436e164ec9650b501f38a06343526dbe31b491a250aa84d59c86",
}
DASHBOARD_LIST = "Dashboard findings list (Research & Methods); the original PSFAL report is not in this repository"

# Each finding: key, headline, plain-English explanation, why it matters for Penn State, status, result, model (canonical number or a
# supporting analysis), sample, data cutoff, source, limitations (list).
FINDINGS = [
    dict(key="m7_persistence",
         headline="Players who out- or under-produce their recruiting profile tend to keep doing so the next season.",
         plain="A recruit's production was compared with what his rating, year in the program and position predict. On held-out seasons, "
               "the gap one season went with the gap the next: rank correlation 0.68 (95% range 0.50 to 0.80).",
         matters="A recruit who is outperforming his profile now is likely to stay ahead of it next season. But see the next finding: the "
                 "gap does not add anything beyond current production.",
         status="validated", result="Supported (the same direction in both periods; the held-out range excludes zero)",
         model=7, sample="109 held-out pairs of consecutive seasons from 65 players, 2022–2025 (DB, DL, LB, RB, WR); 147 earlier pairs, 85 players",
         cutoff=VALIDATION_DATA + "; run 2026-10-14", source="development_validation_report.md",
         limits=["Production is a volume count, so the gap mixes ability with playing time, role and scheme.",
                 "Only players who stayed at the same position in consecutive seasons form pairs (survivorship).",
                 "QB, TE, offensive line, specialists, transfers and unmatched players were not tested.",
                 "One program; wide ranges."]),
    dict(key="m7_incremental",
         headline="That gap does not help forecast next season once current production is known.",
         plain="After allowing for this season's production, the gap's link to next season was 0.10 (95% range −0.11 to 0.31), and it was "
               "negative in the earlier period. Raw production was at least as persistent as the gap.",
         matters="For development forecasts, a player's current production is the stronger signal. A 'beats his rating' score should not be "
                 "used as a forecast of improvement.",
         status="validated", result="Not supported (opposite directions in the two periods; the held-out range includes zero)",
         model=7, sample="Same pairs: 109 held-out (65 players), 147 earlier (85 players)",
         cutoff=VALIDATION_DATA + "; run 2026-10-14", source="development_validation_report.md",
         limits=["A null result in a small sample cannot rule out a small effect.", "Same playing-time and survivorship limits as above."]),
    dict(key="m7_sensitivity",
         headline="Both results hold when players with no production are left out.",
         plain="Dropping pairs with zero production in either season (a pre-specified check) left persistence at 0.59 (0.38 to 0.74) and the "
               "added forecasting value at 0.07 (−0.14 to 0.25).",
         matters="The two results above are not just players who did not play staying that way. Most of the persistence remains.",
         status="validated", result="Sensitivity check passed: the same verdicts as the primary test",
         model=7, sample="71 held-out pairs from 44 players; 103 earlier pairs from 63 players",
         cutoff=VALIDATION_DATA + "; run 2026-10-14", source="sensitivity_report.md",
         limits=["It removes whether a player recorded the stat at all, not differences in snaps, role or scheme.", "Fewer pairs, so wider ranges."]),
    dict(key="role_usage",
         headline="A skill player's share of team production moves with CFBD's usage measure from one season to the next.",
         plain="For rushers and receivers in the same role in consecutive seasons, the change in production share and the change in CFBD's "
               "'usage' figure had a rank correlation of 0.47 (95% range 0.23 to 0.69). Under the pre-set wording rule this is 'imprecise'.",
         matters="Changes in production partly travel with changes in involvement, which supports adjusting development measures for "
                 "opportunity (Model 9, not yet built). It does not show that more usage causes more production.",
         status="preliminary", result="Exploratory, pre-registered; association only; 'imprecise'",
         model=9, sample="43 pairs from 27 players (rushers and receivers), 2016–2025",
         cutoff="Penn State player-seasons 2016–2025 (same data file as above); run 2026-10-14", source="role_change_report.md",
         limits=["CFBD's usage figure is an unverified proxy: its formula and comparability across seasons are not documented, and 2025's "
                 "team total is an outlier.", "Not playing time, not causation, not a prediction.",
                 "Only role-stable players with at least 10 touches in both seasons (survivorship)."]),
    dict(key="role_touches",
         headline="Season-to-season swings in touches vary far more than swings in yards per touch.",
         plain="Changes in touches (carries or receptions) varied about 4.6 times as much as changes in yards per touch (95% range 1.8 to "
               "12.9). This compares variability only.",
         matters="Year-to-year changes in a skill player's yards are worth reading alongside his opportunity, not only as a change in "
                 "ability. Which component drives changes in yards is not established here.",
         status="preliminary", result="Exploratory, pre-registered; a comparison of variability, not of causes",
         model=9, sample="43 pairs from 27 players, 2016–2025",
         cutoff="Penn State player-seasons 2016–2025; run 2026-10-14", source="role_change_report.md",
         limits=["Receptions stand in for opportunity because targets are not in the data.", "Small sample; one program."]),
    dict(key="m7_roles_hypothesis",
         headline="Persistent over-production may reflect stable roles and playing time rather than ability.",
         plain="The validation report names this as a plausible explanation for the persistence above. No data here can test it, because "
               "snap counts and depth charts are not available.",
         matters="Until it is tested, persistence should not be read as evidence of development or of a player's ceiling.",
         status="hypothesis", result="Untested", model=9, sample="Not applicable",
         cutoff="Not applicable", source="development_validation_report.md",
         limits=["Testing it needs snap counts, participation or depth-chart data, which PSFAL does not have."]),
    # The dashboard's eight findings: original headline and evidence label; plain, matters and result are added explanations (ADDED_NOTE)
    dict(key="d_elite", label="descriptive", headline="Penn State beats nearly everyone below the elite tier. It is 66–9 against teams outside the top 50 by SP+ and 5–22 against the top 10.",
         plain="A record against opponents grouped by their SP+ rank that season.", matters="The gap is against elite opponents, not the rest of the schedule.",
         status="dashboard", result="Descriptive", model="Supporting analysis: Championship Gap", sample="75 games outside the top 50; 27 against the top 10",
         cutoff="Seasons in the dashboard's loss profile; the end season is not recorded in the data file", source=DASHBOARD_LIST,
         limits=["SP+ is built from the same results, so this is partly circular.", "No cause is claimed."]),
    dict(key="d_offense", label="descriptive", headline="The biggest gap to national champions is offense, and passing most of all. Defense is close to playoff level.",
         plain="Average standard deviations above the FBS average, Penn State against playoff teams and champions.",
         matters="Points to where Penn State differs most from champions, not to what would close the gap.",
         status="dashboard", result="Descriptive", model="Supporting analysis: Championship Gap", sample="About 12 champions; seasons 2014–2025",
         cutoff="2014–2025 averages; passing gap 2021–2025", source=DASHBOARD_LIST,
         limits=["About 12 champions describe a profile and cannot predict a winner.", "Association, not cause."]),
    dict(key="d_turnover", label="descriptive", headline="This year's roster turnover is the largest in the data. Only 27% of last year's producers returned, against a previous low of 57%.",
         plain="The share of last year's producers who were back on the 2026 roster.", matters="Context for 2026 results and for how much experience returns in 2027.",
         status="dashboard", result="Descriptive", model=10, sample="2026 roster against 2015–2025", cutoff="2026 roster in the dashboard data",
         source=DASHBOARD_LIST, limits=["Leaving for any reason counts."]),
    dict(key="d_losses", label="descriptive", headline="The Northwestern loss was mostly one game of run defense (427 yards). The Wisconsin loss was an offense that could not move.",
         plain="What stood out in two 2026 losses.", matters="Single games: useful context, not a trend.",
         status="dashboard", result="Descriptive", model=14, sample="Two games", cutoff="2026 results in the dashboard data",
         source=DASHBOARD_LIST, limits=["One game proves little."]),
    dict(key="d_undervalued", label="tested", headline="Across 15 programs, no repeatable type of undervalued recruit showed up. Recruiting ratings explain only about a quarter of production.",
         plain="Programs' gaps between actual production and what ratings predict, earlier classes (2016–2019) against later (2020–2022).",
         matters="No recruit type was found that Penn State could reliably target as undervalued. Penn State ranked 2nd of 15 in the later classes "
                 "(+1.9), but its range (−1.9 to +5.6) includes zero.",
         status="dashboard", result="Tested; no repeatable undervalued type found (earlier and later gaps correlate 0.38)", model=13,
         sample="15 programs; classes 2016–2022", cutoff="Recruiting classes through 2022", source=DASHBOARD_LIST,
         limits=["Differences between programs are suggestive, not conclusive.", "Production is a volume measure."]),
    dict(key="d_portal", label="tested", headline="A transfer's portal rating predicts how he produces, and transfers from non-FBS schools produce less.",
         plain="Rank correlation of portal rating with production at the new school: 0.31, then 0.37 in the later classes (range 0.27 to 0.47).",
         matters="Portal ratings carry information for Penn State's transfer decisions; a step-up from outside FBS is the main risk group.",
         status="dashboard", result="Tested; supported", model=5, sample="709 portal arrivals into Penn State and 14 peers, 2021–2025; 544 matched to a roster",
         cutoff="Portal classes 2021–2025", source=DASHBOARD_LIST,
         limits=["Two of the checks were exploratory.", "Transfers are counted only if they reached a roster."]),
    dict(key="d_retention", label="tested", headline="The roster forecast did not beat a flat guess for any single position. Plan on about 64% of the roster returning.",
         plain="In a backtest on 2022 to 2025, the models missed by 2.0 players per position group, the same as a flat overall rate (1.97).",
         matters="Use the overall return rate for planning, not the position-by-position numbers.", status="dashboard",
         result="Tested; the position forecasts were not better than a flat guess", model=11, sample="Backtest 2022–2025; 2026 roster of 112 players",
         cutoff="2026 roster; backtest seasons 2022–2025", source=DASHBOARD_LIST,
         limits=["A coaching change and rebuild cannot be predicted from history.", "Early NFL departures and portal exits cannot be predicted."]),
    dict(key="d_cost", label="assumption", headline="A transfer is the better use of a roster spot only if he costs less than about 1.5 times a recruit's spot. Nobody has the real cost.",
         plain="43% of recruit player-seasons and 63% of transfer player-seasons reached strong production, so a transfer yields about 1.5 times as much.",
         matters="Whether a transfer is worth it depends on a cost no public data measure.", status="dashboard",
         result="Assumption-based: depends on an unmeasured cost", model=12, sample="Recruit and transfer player-seasons in the portal study",
         cutoff="Portal classes 2021–2025", source=DASHBOARD_LIST,
         limits=["No public cost or NIL data.", "Part of the gap is playing time, because transfers are signed to play right away."]),
]

# Dashboard findings keep their ORIGINAL evidence label (Tested / Descriptive / Assumption) and are listed in their own group. Their labels are
# not mapped onto validated / preliminary / hypothesis: that would claim evidence the missing reports cannot show.
REQUIRED = ("key", "headline", "plain", "matters", "status", "result", "model", "sample", "cutoff", "source", "limits")
