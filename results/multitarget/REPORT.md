# Multi-target water-quality forecasting: results

## Main finding

The system now covers **15 measurements**. Thirteen have enough historical data for the specified retrospective evaluation: eight use learned point predictors and five use simple historical baselines selected on validation data. Phosphate and suspended solids are tracked in the data pipeline but have no trained predictor because their earlier histories are insufficient.

**Water temperature and dissolved oxygen have the clearest repeatable signal.** Their point forecasts improve on the validation-selected baselines across all three historical test periods. The other targets show mixed evidence, baseline-level performance, or inadequate coverage. This system is a research prototype for planning sampling; no operational or health thresholds have been approved.

## Latest held-out evaluation

Models were selected using 2024 data and evaluated on 2025 through April 2026. The comparable baseline is selected on validation data before the test. The strongest-test-baseline column is a stricter descriptive comparison, not another model-selection step.

| Target | Test samples | Selected predictor | MAE, source units | Gain vs validation-selected baseline | Gain vs strongest test baseline | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| E. coli | 459 | forest | 167.176 | +14.7% | +5.5% | positive signal |
| Other coliform | 164 | last_observation | 2030.227 | +0.0% | +0.0% | baseline selected |
| Water temperature | 634 | forest | 1.461 | +35.2% | +31.5% | positive signal |
| Dissolved oxygen | 612 | forest | 0.713 | +22.0% | +21.0% | positive signal |
| Oxygen saturation | 612 | forest | 6.259 | -5.0% | -5.0% | uncertain signal |
| pH | 631 | last_observation | 0.258 | +0.0% | -5.6% | baseline selected |
| Conductivity | 523 | forest | 54.842 | -8.8% | -9.2% | uncertain signal |
| Nitrate | 187 | site_median | 0.449 | +0.0% | +0.0% | baseline selected |
| Turbidity (reported field) | 310 | site_seasonal | 7.256 | +0.0% | -0.3% | baseline selected |
| Turbidity (legacy field) | 412 | site_median | 4.409 | +0.0% | -3.3% | baseline selected |
| Alkalinity | 435 | forest | 31.936 | +7.3% | +7.3% | positive signal |
| Hardness | 428 | forest | 23.017 | +3.6% | +3.6% | uncertain signal |
| Salinity | 33 | ridge | 0.041 | -23.8% | -33.3% | uncertain signal |

“Positive signal” means the site-bootstrap interval for the latest test's error reduction against the validation-selected baseline is above zero. It does not establish operational reliability, causality, or significance adjusted for testing many targets. “Uncertain signal” includes cases where the learned model did worse than the baseline. A baseline being selected is an explicit outcome, not a failed training run.

Temperature, dissolved oxygen, oxygen saturation, and pH use absolute error on their reported scales. Other targets use absolute error on log(1 + value) for model selection; their source-unit errors are also shown. Do not compare MAE values across different measurements. Except for pH's named scale, source units still need confirmation. Back-transformed forecasts are central values on the transformed scale, not unbiased arithmetic means.

For continuity with the earlier E. coli prototype: v2 reduces error **5.5%** against its strongest test baseline, versus **14.7%** against its validation-selected seasonal baseline. These are different comparisons. Its gains do not consistently appear in the earlier folds.

## Earlier-year checks

Each column below is a separate chronological evaluation. The previous year selects the predictor; still-earlier data fits it. Selected predictors may differ between folds. Positive percentages indicate lower error than that fold's validation-selected simple baseline.

| Target | 2023 | 2024 | 2025–Apr 2026 |
| --- | --- | --- | --- |
| E. coli | +0.0% | +0.0% | +14.7% |
| Other coliform | +6.6% | +0.0% | +0.0% |
| Water temperature | +32.6% | +37.0% | +35.2% |
| Dissolved oxygen | +13.1% | +12.8% | +22.0% |
| Oxygen saturation | +0.2% | +3.9% | -5.0% |
| pH | +0.0% | +0.0% | +0.0% |
| Conductivity | +0.0% | +0.0% | -8.8% |
| Nitrate | +27.4% | +0.0% | +0.0% |
| Turbidity (reported field) | +0.0% | +0.0% | +0.0% |
| Turbidity (legacy field) | +0.0% | +0.0% | +0.0% |
| Alkalinity | -1.6% | +0.0% | +7.3% |
| Hardness | +0.0% | +0.0% | +3.6% |
| Salinity | +0.0% | +0.0% | -23.8% |

The 2023 and 2024 tests are historical robustness checks. They also precede the latest test's training/validation period, so the three columns are not three independent prospective trials. Treat all results as exploratory; additional iterations need a new untouched evaluation period or a prospective pilot.

## Experimental flags

Flags mean crossing a historical training-distribution tail, not crossing a legal, ecological, or health action limit. High-direction targets use the training 75th percentile; low-direction targets use the 25th percentile; two-sided targets use the 10th and 90th percentiles. Equality to a threshold does not trigger the event. Directions and thresholds are in `targets.json` and `evaluation.json`.

A random-forest classifier is retained only if it beats constant prevalence on validation probability error. Its probability cutoff is chosen to catch at least 75% of validation tail events. That does not guarantee 75% recall on future data. A constant-prevalence fallback produces a probability estimate but **does not rank sites or issue flags**; absence of a flag is not evidence of safe water.

| Target | Risk estimator | Actual tail events | Caught | False flags | Flag precision |
| --- | --- | --- | --- | --- | --- |
| E. coli | constant_prevalence | 88 | 0 | 0 | 0% |
| Other coliform | forest | 35 | 11 | 6 | 65% |
| Water temperature | forest | 100 | 83 | 39 | 68% |
| Dissolved oxygen | forest | 116 | 74 | 13 | 85% |
| Oxygen saturation | forest | 107 | 85 | 20 | 81% |
| pH | forest | 99 | 85 | 306 | 22% |
| Conductivity | constant_prevalence | 92 | 0 | 0 | 0% |
| Nitrate | forest | 19 | 18 | 161 | 10% |
| Turbidity (reported field) | forest | 57 | 32 | 38 | 46% |
| Turbidity (legacy field) | forest | 115 | 93 | 124 | 43% |
| Alkalinity | forest | 100 | 75 | 108 | 41% |
| Hardness | forest | 89 | 68 | 170 | 29% |
| Salinity | forest | 11 | 7 | 9 | 44% |

The E. coli and conductivity risk classifiers fell back to constant prevalence under this v2 comparison. Their continuous-value forecasts still exist, but v2 does not claim useful site-specific risk probabilities for those targets. Point and risk models are selected independently. Other targets, particularly nitrate and pH, produce many false flags. The probabilities have not had a separate calibration study.

Multiple target flags may be highly correlated—for example, dissolved oxygen and oxygen saturation. The site overview lists the individual flagged targets and unavailable targets. It does **not** add these into a combined danger probability or safety score.

## Targets needing more history

| Target | Valid site-days | Training forecasts | Validation forecasts | Test forecasts |
| --- | --- | --- | --- | --- |
| Phosphate | 284 | 13 | 33 | 178 |
| Suspended solids | 205 | 0 | 0 | 152 |

The fixed support rule requires at least 150 training forecasts, 30 validation forecasts, 30 test forecasts, and 5 test sites. Phosphate and suspended solids fail the earlier-history requirement. Their 2025 observations are not moved into training merely to make a model appear evaluable. They could be considered in a later study with enough independent post-training outcomes. Salinity technically passes but has only 33 test observations, uncertain measurement units, and no eligible April 20 historical-example forecasts; its current evidence is especially weak.

## Data quality and information boundaries

- Chemistry and bacteria observations are now cleaned independently by measurement. A missing E. coli value does not discard a valid other-coliform result, and chemistry forecasts do not require bacteria history.
- Structurally quarantined rows: **39 bacteria and 47 chemistry**. Separate cell-level exclusions are recorded in `excluded_measurements.csv`. These counts differ from v1 because missing targets no longer quarantine the whole row.
- The source's two turbidity fields remain separate. Mixed or missing tube/meter methods, detection limits, and possible capped bacterial counts require review before operational use. Current models treat retained numeric values as reported.
- Site/date/measurement replicates are combined by median. Seven-to-twelve-digit site codes are kept as strings; no mapping between renamed sites is guessed.
- Forecasts assume a planned sampling date known seven days in advance. Only measurements collected at least ten days before that date are used, assuming three days to release results. Each target needs two prior available observations, with the most recent at most 120 days old.
- Availability is based on collection dates plus an assumed delay. Historical publication timestamps, revisions, timezones, and actual laboratory turnaround are unverified. These exports cannot prove what an operator truly knew on each historical issue date.
- Evaluation covers sampled visits, not unobserved days or incidents between monthly visits. There is no validated 24–72-hour incident-detection claim.
- All retained groups and watersheds are included. Confirm the intended service area and site registry. No rainfall, streamflow, land-use, or upstream-network inputs have been added yet.
- Site-resampling uncertainty does not capture all shared storm dependence, sampling-selection bias, or multiple comparisons.

## Saved forecast demonstration

`historical_forecasts_2026-04-20.csv` contains 2,460 site/target statuses across 164 raw site identifiers, including **440 eligible point forecasts** for a planned April 20 visit, issued April 13. Unavailable forecasts have explicit reasons rather than a zero or low-risk score. This is a historical demonstration, not current alerts. A September 21 scoring check correctly produces no eligible forecasts because the April data is stale.

## Recommended next development

1. Review site identities, units, turbidity methods, reporting limits, and the excluded records with the team.
2. Agree which changes warrant action and how many extra sampling visits the team can support. Replace research-tail definitions only after those decisions.
3. Prioritize temperature and dissolved oxygen for a prospective pilot; keep other targets visible with their evidence limitations.
4. Obtain recent observations and station coordinates; test weather and streamflow inputs using only information available before each forecast.
5. Evaluate event detection and sampling workload in a new prospective period before relying on alerts.
