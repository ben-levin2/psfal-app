# Recruit Development Forecast (Model 2): provenance, reproducibility and rebuild plan

**Status:** decision record and proposal, 2026-10-17. Nothing here changes a forecast, a frozen research output or the 15-model registry.
Forecast values from the private dashboard data file are deliberately not reproduced in this public repository.

## 1. Decision

The existing forecast **cannot be expanded**: its model is not recorded anywhere accessible and could not be reproduced, so it cannot
score any additional player defensibly. **Additional defensible forecasts today: 0.** The five active forecasts and the one historical
forecast stay exactly as generated. Expanding the list needs either the original model (section 6, option A) or a rebuilt and validated
model (section 5).

## 2. Where the six original chances came from

| Evidence | What it shows |
|---|---|
| Dashboard data file, `watchClass` section | Six rows: player, position, recruiting rating, 2025 production (as text), chance. No model name, version, training data, date or selection rule. Its freshness note says only "not week-dependent: 2025 output and chance estimates; unchanged". |
| Earliest app version (commit `2c62f6b`, 2026-10-04) | The list was shown inside "Who becomes a strong producer by year 3?" (today's Model 8, Development Trajectory & Breakout Forecast), next to that model's accuracy and calibration. So the chances are most likely that model applied to the 2025 class. |
| Model 8 as described on the dashboard | Outcome: becoming a strong producer by year 3 (elsewhere on the dashboard a strong producer is the 67th percentile or better at the position). Features: recruiting rating and position, plus first-year production. Fitted on earlier classes and judged on later ones: AUC 0.65 → 0.73 with first-year production (gain +0.07, range +0.05 to +0.11). Calibration: the order held, but the middle was too high (predicted 58%, actual 36%). Evidence label "Tested"; its report is not in this repository. |
| This repository's full git history (27 commits, all branches) | App code only. No model code, notebook, training data or forecast file; the data file was never committed. |
| PSFAL v0.7 pipeline and the read-only v0.6 copy | No breakout or year-3 forecast code, and nothing that writes `watchClass`. The pipeline writes its reports to Google Drive (`/content/drive/MyDrive/PSFAL/reports`), which is not accessible here. |
| Local disk search (code, notebooks, documents) | No other source names these players, apart from copies of the app and of the data file. One more copy of the data file exists locally (a week-5 version); it was not opened, because reading it was not approved. |

**Not recorded anywhere accessible:** model type, training classes and programs, exact outcome window (the year-3 season, or any season
up to year 3), how players who left before year 3 were counted, how zero or missing first-year production was treated, the rule that chose
six players, and when the chances were generated.

## 3. Reproduction check (scratch only, 2026-10-17)

Penn State's player-season table (`player_seasons.parquet`, SHA-256 `cd67a64b…`) and the pipeline's production measure gave **107 training
recruits** (classes 2016–2023, measurable positions, with a first-year season). Penalized logistic regressions on rating, position and
first-year production percentile, for both outcome windows, put the six players in a broadly similar order (rank correlation 0.66–0.83)
but missed the original chances by **0.10 on average and up to 0.16–0.23**. The original model therefore cannot be regenerated from the
data available here; its reported interval is also narrower than 107 players would allow, which suggests a larger, probably multi-program,
training sample.

Consequences: chances from any new model are **not comparable** with the original six, and must be stored and shown separately.

## 4. The ten current players without a forecast

All are 2025-class high-school recruits on the 2026 roster (CFBD roster data, as of 2026-10-14; official roster checked 2026-10-17).

| Player | Pos | Group | Rating | 2025 production on record | Blocking issue |
|---|---|---|---|---|---|
| Owen Aliciene | OL | OL | 0.8956 | none (no measure) | Offensive line has no individual production measure in public data |
| Malachi Goodman | OL | OL | 0.9702 | none (no measure) | Same |
| Matthew Parker | PK | ST | 0.7900 | kicking only | Not covered by the production measure |
| Joshua Johnson | CB | DB | 0.8733 | 1 tackle | Has every input; model unavailable |
| LaVar Arrington II | DE | DL | 0.9028 | no stat row | Inputs present only if no stat row counts as zero production; model unavailable |
| Dayshaun Burnett | DE | DL | 0.9000 | no stat row | Same |
| Cam Smith | LB | LB | 0.8983 | no stat row | Same |
| Lyrick Samuel | WR | WR | 0.8948 | no stat row | Same |
| Brian Kortovich | TE | TE | 0.8868 | no stat row | Same |
| Xxavier Thomas | CB | DB | 0.8814 | no stat row | Same |

**Could be scored by a recovered or rebuilt model: 7** (one with recorded production, six whose first-year production is zero by the
pipeline's convention; whether a redshirt or injury year should count as zero must be decided before scoring). **Ineligible under any
production-based model: 3** (two offensive linemen, one kicker).

## 5. Rebuild and validation plan (if the original model cannot be recovered)

Written to be pre-registered, as the Model 7 validation was, before any outcome is computed.

1. **Outcome (fixed in advance).** Strong producer in the player's **year-3 season**: production percentile ≥ 66.7 among players at his
   position group in that season. Primary rule: a player who left before year 3 counts as not strong (that is the question a roster
   planner faces); a sensitivity analysis keeps only players still on the roster in year 3.
2. **Population.** High-school recruits at measurable positions (QB, RB, WR, TE, DL, LB, DB). Penn State alone gives about 107 training
   players; the primary analysis should add the 14 peer programs already used in PSFAL's portal and market studies, with percentiles
   computed within each team, season and position group. This needs CFBD player-season pulls for the peers (request quota; approval).
3. **Features (all known at the end of year 1).** Recruiting rating, star rating, position group, first-year production percentile, and an
   indicator for no first-year stat row (redshirt, injury or no playing time), so zero production is not silently treated as measured.
   Nothing from year 2 or later, and no roster status after year 1.
4. **Leakage prevention.** Percentiles computed within each season from that season's players only; time-based splits by recruiting class;
   every scored player's inputs stored with the data snapshot hash and scoring date.
5. **Baselines.** (a) Base rate by position group; (b) rating and position; (c) rating, position and first-year production. The model is
   reported only as an improvement over (b).
6. **Model.** Penalized logistic regression (few features, rare and noisy outcome); no tuning on the test classes.
7. **Out-of-sample evaluation.** Fit on classes 2016–2019; test on 2020–2022 (year-3 seasons 2022–2024); confirm on the 2023 class (year 3 =
   2025). Report AUC and Brier score with bootstrap intervals that resample players, and calibration in five groups. Decision rule fixed in
   advance: the model is used only if its gain over baseline (b) has an interval above zero on the test classes and points the same way on
   the confirmation class, and its calibration slope is within an agreed range.
8. **Scoring and display.** If it passes: score the 2025 class (and later classes) once, store the predictions in a versioned file with
   the model version, scoring date, training classes and input snapshot hash, and show them in a separate, labelled table. The original six
   chances stay as generated, never overwritten or re-ranked by the new model.

## 6. Positions outside the production measure

- **Offensive line.** Public data record almost no individual line statistics (about 6% of line player-seasons have any stat). A separate
  model would need snap counts, starts or licensed grades; without them, line recruits are reported as "not forecastable with public data",
  not given a chance.
- **Specialists (K, P, LS).** One starter per team and kicking statistics that do not translate into a "strong producer" percentile. Not
  worth a separate forecast; report as not forecastable.
- **Quarterbacks.** Measurable, but groups of three to five players make percentiles coarse; flag their forecasts as low-information.

## 7. Next steps and approvals

- **A. Recover the original (preferred).** The owner looks in the Google Drive PSFAL folder (`reports/`, notebooks) for the Model 8 /
  year-3 forecast code or report and its training data. If found: reproduce the six chances exactly, then score the seven eligible players
  with the same model, stored separately with version and date.
- **B. Rebuild.** Approve the pre-registration in section 5 and CFBD pulls for the 14 peer programs.
- **Optional.** Approve reading the forecast section of the local week-5 data file copy, to see whether the chances changed between
  snapshots (evidence on when they were generated).
