# Sensitivity to unresolved data-quality flags

## Conclusion

**Temperature and dissolved oxygen remain the strongest pilot candidates. E. coli's apparent improvement is sensitive to which sites are included.** Resolving the site registry is a priority before trusting E. coli results.

The analysis holds every model, prediction, baseline, and threshold fixed. It examines subsets of the existing 2025–April 2026 test observations. No source records were corrected or permanently removed.

## Conservative-exclusion comparison

The combined scenario excludes outcomes at the nine site codes with multiple normalized waterbody labels, outcomes with any checked arithmetic discrepancy (including possible rounding), and reported-field turbidity outcomes with a non-meter or missing method label. Any flagged replicate excludes its aggregate site/date/measurement from that scenario.

These are deliberately broad stress-test exclusions. A naming variation or rounding difference is not proof that a record is wrong. Baselines were selected using earlier validation data; the percentages below use that same baseline for each target, not a newly selected baseline for each subset.

| Target | Original test observations | Retained observations | Original error reduction | Subset error reduction |
| --- | ---: | ---: | ---: | ---: |
| Water temperature | 634 | 437 | 35.2% | 37.9% |
| Dissolved oxygen | 612 | 428 | 22.0% | 23.0% |
| E. coli | 459 | 344 | 14.7% | 4.7% |
| Alkalinity | 435 | 250 | 7.3% | 9.4% |
| Hardness | 428 | 249 | 3.6% | 6.0% |
| Conductivity | 523 | 382 | −8.8% | −1.1% |
| Oxygen saturation | 612 | 428 | −5.0% | −8.6% |

Positive values mean lower mean absolute error than baseline. Temperature and oxygen use their reported scales; E. coli and other skewed measurements use log(1 + value). Different target error units are not directly comparable. Complete results, including baseline-selected targets and salinity, are in `scenario_results.csv`.

## E. coli: site coverage drives most of the sensitivity

- Excluding only ambiguous site-label codes leaves 348 observations and reduces the gain to **4.6%**.
- Excluding only any bacterial arithmetic discrepancies leaves 455 observations and yields **14.9%** gain.
- None of the more substantial bacterial formula-review flags intersect the E. coli test outcomes. They can still matter in training histories and must not be dismissed.
- Combined exclusions leave 344 observations and **4.7%** gain. The site-bootstrap interval for absolute log-error gain is **−0.045 to +0.219**, which includes no improvement.

This does not prove the excluded sites are incorrect or that site-label ambiguity causes better scores. It shows the aggregate claim depends on site composition. Some labels may simply be abbreviations for the same location. An authoritative mapping is necessary before deciding what to merge, rename, or exclude.

The existing v2 E. coli risk estimator remains a constant-prevalence fallback and issues no flags. This analysis does not create an E. coli alert capability.

## Temperature and oxygen: point gains survive this check

The conservative-subset site-bootstrap intervals for error improvement remain above zero:

- Temperature: **+0.638 to +1.256** source-unit MAE reduction.
- Dissolved oxygen: **+0.145 to +0.324** source-unit MAE reduction.

This is evidence of robustness to these particular exclusions, not operational validation. The earlier audit's low-oxygen misses, severity bias, seasonal failure cases, and uncertain result-availability times remain unresolved. Bootstrap intervals are exploratory, do not adjust for multiple comparisons, and cannot capture every shared environmental effect.

## Limits of this analysis

1. This is a fixed-prediction subset analysis. Potentially affected training rows and prior predictor measurements are still present in the original model. It is not a retraining experiment with cleaned data.
2. Changes in site and season composition can alter the error distribution. Subset metrics do not estimate what correcting records would accomplish.
3. No available arithmetic check is not the same as a passed arithmetic check; the observation-level file records whether a formula was checked.
4. A recorded “Turbidity meter” label is not independently verified method correctness. The meter-only scenario checks labeling sensitivity, not laboratory validity.
5. Historical research-tail thresholds are unchanged. They are not approved environmental or public-health action limits.
6. The test period has been repeatedly examined. New model development requires a new evaluation period or prospective pilot rather than optimizing to these results.

## Next actions

1. Obtain the authoritative mapping for the nine ambiguous site codes before changing site identities. E. coli is the priority for checking site-dependent performance.
2. Continue preparing temperature and oxygen for a shadow pilot, with actual result-release timestamps and team-approved intervention thresholds.
3. Resolve bacterial conventions and turbidity reporting limits before retraining affected targets.
4. Once those decisions are documented, compare corrected-data training against the frozen baseline on a new period. Until then, retain both the original data and these flags.

## Reproduce

From `/Users/rishabh/watershed_model`, run `.venv/bin/python sensitivity_analysis.py` after `failure_audit.py`. Read:

- `scenario_results.csv`: each target and exclusion scenario, counts, errors, and event rates.
- `observation_flags.csv`: the specific test observations each issue affects.
- `site_bootstrap.csv`: uncertainty for the full and conservative subsets.

This narrative describes the current saved run and should be reviewed after reruns. All model files and source exports are unchanged.
