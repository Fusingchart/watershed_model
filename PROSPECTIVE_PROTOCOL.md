# Prospective evaluation protocol

This protocol was written and committed before any sample taken after April 13, 2026 was available. The commit time is the evidence that the rules below were fixed before the outcomes were known. Changing them after seeing new data invalidates the evaluation.

## Why

The January 2025–April 2026 test period has been examined in detail (failure audit and sensitivity analysis). Any further claim about forecast quality must come from samples the models and analyses have never seen.

## What is frozen

- `results/multitarget/models.joblib`, SHA-256 `dbf87e6be9c2925446d1fdaa3106306f1393f38763f3584926a471638e3bb45b`. `prospective_evaluation.py` refuses to run if the file differs.
- The comparison baseline for each target, as selected on validation data in `results/multitarget/evaluation.json` (`2025` fold, `selected_baseline`).
- Features, the 7-day lead, the assumed 3-day result delay, and the 120-day history limit in `multitarget_data.py`.

No retraining, re-tuning, threshold change, or site merge happens before scoring. If the data owner's answers require changes to data or code, those changes produce a new model version that needs its own untouched period.

## Scored samples

Every site/date measurement in a newer export with a sample date on or after **April 14, 2026** that meets the usual eligibility rules (two prior samples available at issue time, the latest within 120 days). Features may use any earlier measurement, including pre-snapshot data.

## Primary questions

Separately for **water temperature** and **dissolved oxygen**: does the frozen model have lower mean absolute error than its frozen baseline (site-seasonal average for both)?

| Verdict | Rule |
| --- | --- |
| `insufficient_data` | Fewer than 100 scored observations or fewer than 10 sites. No conclusion is drawn. |
| `confirmed` | The lower end of the site-bootstrap 95% interval for the error gain is above zero. |
| `not_confirmed` | Mean gain is zero or negative, or the whole interval is at or below zero. |
| `inconclusive` | Positive mean gain, but the interval includes zero. |

The result for all sites is primary. The result excluding the nine site codes listed in `results/data_owner_request/site_conflicts.csv` is reported alongside it as a check.

## Secondary results

All other targets are scored the same way and reported, but they do not support any claim on their own. Targets whose frozen model is a baseline are marked `frozen_model_is_baseline`. E. coli results are secondary until the site-identity questions are resolved.

## Data-integrity check

Before reading any scores, review `source_revisions_before_frozen_snapshot` in the output. Pre-snapshot values that were changed, removed or added in the newer export mean the source was revised. Report this together with the results; a large number of revisions should be explained by the data owner first.

## Running

```sh
.venv/bin/python prospective_evaluation.py \
  --bacteria data/raw/<new bacteria export>.csv \
  --chemistry data/raw/<new chemistry export>.csv \
  --snapshot-date <export date>
```

Results go to `results/prospective/`. Running with `--start 2025-01-01` on the April exports reproduces the saved 2025–April 2026 test results exactly; that run is only a check of the scorer, not new evidence.
