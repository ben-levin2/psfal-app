"""The canonical PSFAL architecture: 15 child models in five parent families. This list is the single source for the dashboard's
navigation; tests/test_sprint.py fails if a name, number or parent changes.

`status` is IMPLEMENTATION status on this dashboard, not research validation:
    shown            the dashboard shows this model's analysis
    partial          only part of the model is shown (the note says which part)
    link only        the page points to another resource; no analysis for this model is implemented here
    not implemented  no analysis, data or results exist for this model; its page says so and shows nothing else
Whether a result was tested or is descriptive is shown separately, by the evidence labels on each finding.
"""
FAMILIES = ["Recruiting High Schoolers", "Transfer Portal", "Player Development", "Roster Construction", "Competitive Edge Research"]

# (number, name, family, status, note)
MODELS = [
    (1, "Recruiting Intelligence", "Recruiting High Schoolers", "partial",
     "Shows how closely recruiting ratings track production in each year in the program. The recruiting module's class makeup, geography and "
     "retention results are not in this dashboard's data."),
    (2, "Recruit Development Forecast", "Recruiting High Schoolers", "shown",
     "A ranked list for Penn State's 2025 class. Players' current roster status is not part of the forecast; see the status note on the page."),
    (3, "Recruiting Fit & Scheme Projection", "Recruiting High Schoolers", "not implemented", ""),
    (4, "Transfer Portal Analytics", "Transfer Portal", "shown", "Penn State's 2026 transfers and their production so far."),
    (5, "Transfer Production Translation", "Transfer Portal", "shown", "What predicts how a transfer produces at his new school."),
    (6, "Portal Fit & Acquisition Value", "Transfer Portal", "not implemented", ""),
    (7, "Player Development Analytics", "Player Development", "shown", "Production by year in the program, for recruits who stayed."),
    (8, "Development Trajectory & Breakout Forecast", "Player Development", "shown", "Who becomes a strong producer by year 3, and how well calibrated that forecast is."),
    (9, "Opportunity-Adjusted Development", "Player Development", "not implemented", ""),
    (10, "Roster Analytics", "Roster Construction", "shown", "How much of last year's roster and production came back."),
    (11, "Retention & Continuity Forecast", "Roster Construction", "shown", "Expected returners in 2027 by position group (not validated)."),
    (12, "Resource Allocation Optimization", "Roster Construction", "partial",
     "Only the Decision Tool exists: an assumption-based what-if tool, not a validated optimization model. It optimizes nothing; its answers "
     "come from the costs and weights you enter."),
    (13, "Market Inefficiency Model", "Competitive Edge Research", "shown", "Whether some programs get more from their recruits than ratings predict."),
    (14, "Game Analytics", "Competitive Edge Research", "link only",
     "No game-analytics model is implemented on this page. It links to the 2026 Games page, which shows game results and per-play efficiency scores."),
    (15, "Big Ten Competitive Intelligence", "Competitive Edge Research", "shown", "Penn State against Big Ten groups and champions (Child 15 report)."),
]

# Analyses that are kept on the dashboard but are not one of the 15 models (shown unnumbered, after the family's models).
SUPPORTING = {"Competitive Edge Research": ["Championship Gap"]}

STATUS_LABEL = {"shown": "Shown on this dashboard", "partial": "Partly implemented", "link only": "Link only, not an implemented model",
                "not implemented": "Not implemented"}


def label(name):
    """The navigation label of a model ('13 · Market Inefficiency Model') or of a supporting analysis ('Supporting analysis: Championship Gap')."""
    for n, m, *_ in MODELS:
        if m == name:
            return f"{n} · {m}"  # not "13. ...": Streamlit renders button labels as Markdown, where "13." starts a list and hides the number
    if any(name in v for v in SUPPORTING.values()):
        return f"Supporting analysis: {name}"
    raise KeyError(name)


def model(name):
    return next(row for row in MODELS if row[1] == name)


def options(family):
    """The family's navigation labels: its models in number order, then its supporting analyses."""
    return [label(m) for n, m, f, *_ in sorted(MODELS) if f == family] + [label(s) for s in SUPPORTING.get(family, [])]


# RESEARCH status of each model, kept separate from implementation status. Every entry names its evidence; nothing is marked validated
# because code exists. Sources: the PSFAL validation reports (development_validation_report.md, sensitivity_report.md, role_change_report.md)
# and the evidence labels already on this dashboard (its original reports are not in this repository). A status that rests only on such a
# label says so ("Original dashboard label: ...; source report unavailable"), so it is never read as an independently established result.
UNAVAILABLE = "Label and numbers from {}; the report behind them is not in this repository, so they have not been checked against it."
RESEARCH = {
    1: ("Descriptive only", "Rating-vs-production correlations by year in the program; no held-out test shown."),
    2: ("Not validated", "No validation of this list is recorded. Its related year-3 forecast (Model 8) was tested; see there."),
    3: ("No research yet", "Not started."),
    4: ("Descriptive only", "Penn State's 2026 transfers' production so far."),
    5: ("Original dashboard label: Tested; source report unavailable",
        "Portal rating vs production at the new school: rank correlation 0.37 in later classes. " + UNAVAILABLE.format("the dashboard's findings list")),
    6: ("No research yet", "Not started."),
    7: ("Validated, 2026-10-14", "Held-out test: profile-gap persistence supported (0.68); added forecasting value beyond current production not "
                                 "supported (0.10, range includes zero). A pre-registered sensitivity check gave the same verdicts."),
    8: ("Original dashboard label: Tested; source report unavailable",
        "Accuracy (AUC) 0.65 to 0.73 with first-year production; the middle of the range was too high (calibration). "
        + UNAVAILABLE.format("this model's page")),
    9: ("Preliminary research only", "Pre-registered exploratory role-change study (2026-10-14): association only, 'imprecise'. No model built."),
    10: ("Descriptive only", "Share of last year's roster and production that returned."),
    11: ("Original dashboard label: Tested; source report unavailable",
         "2022–2025 backtest: 2.0 players per group missed, the same as a flat rate (1.97), so not better than a flat guess. "
         + UNAVAILABLE.format("the dashboard's findings list")),
    12: ("Original dashboard label: Assumption; source report unavailable; not validated",
         "Break-even of about 1.5x depends on a transfer cost no public data measure. " + UNAVAILABLE.format("the dashboard's findings list")),
    13: ("Original dashboard label: Tested; source report unavailable",
         "No repeatable undervalued recruit type across 15 programs; Penn State's +1.9 has a range that includes zero. "
         + UNAVAILABLE.format("the dashboard's findings list")),
    14: ("Not applicable (link only)", "The 2026 game scores on the 2026 Games page are descriptive."),
    15: ("Descriptive", "Team-level benchmarks from the saved Child 15 report; the page shows the report's own reproduction check."),
}
