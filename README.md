# Sno-King water-quality forecasting

Working folder: `/Users/rishabh/watershed_model`.

## Current version: multi-target prototype

The project now audits 15 water-quality measurements. Thirteen have sufficient history for the configured evaluation: eight use learned point predictors and five use historical baselines. Phosphate and suspended solids remain explicitly unsupported for forecasting under the current history requirements.

**Start with `results/multitarget/REPORT.md`.** It contains per-target results, historical checks, alert tradeoffs, and limitations. Temperature and dissolved oxygen show the clearest repeatable gains. Other measurements have mixed evidence; no target is approved for autonomous operational decisions.

### Main files

| File | Purpose |
| --- | --- |
| `targets.json` | Measurement fields, transformations, directions, and quality bounds |
| `multitarget_data.py` | Auditable cleaning and time-appropriate historical features |
| `multitarget_model.py` | Model selection, rolling tests, and forecast CLI |
| `write_multitarget_report.py` | Generate the readable results report |
| `test_multitarget.py` | Temporal and independent-target tests |
| `results/multitarget/models.joblib` | Saved predictor bundles for 13 targets |
| `results/multitarget/target_summary.csv` | Current target-by-target model comparison |
| `results/multitarget/target_coverage.csv` | Data history and coverage |
| `results/multitarget/evaluation.json` | Full results for 2023, 2024, and 2025–April 2026 |
| `results/multitarget/heldout_predictions.csv` | Latest test predictions against actual measurements |
| `results/multitarget/historical_forecasts_2026-04-20.csv` | Historical scenario with explicit unavailable statuses |
| `results/multitarget/historical_forecasts_2026-04-20_site_overview.csv` | Per-site coverage and individual experimental flags |
| `results/multitarget/excluded_rows.csv` | Structurally quarantined records |
| `results/multitarget/excluded_measurements.csv` | Invalid numeric cells |
| `data/raw/` | Local copies of the two original CSVs; intentionally not in Git |

## Reproduce locally

Python 3.12 and the project environment are configured locally. From this folder:

```sh
# On a fresh checkout only:
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Tests:
.venv/bin/python -m unittest test_model.py test_multitarget.py -v

# Rebuild all multi-target results (overwrites results/multitarget):
.venv/bin/python multitarget_model.py train
.venv/bin/python write_multitarget_report.py

# Historical demonstration, not current alerts:
.venv/bin/python multitarget_model.py predict \
  --date 2026-04-20 \
  --output results/multitarget/historical_forecasts_2026-04-20.csv
```

The default inputs are `data/raw/MasterBactSurvey4_13_26.csv` and `data/raw/MasterChemSurvey4_13_26.csv`. Supply `--bacteria`, `--chemistry`, and `--snapshot-date` for updated exports with the same schema. A fresh Git checkout needs these original exports supplied separately. The original files contain personal details and access codes, so they are excluded from commits.

The prediction date is a planned visit date, seven days after forecast issue. Prior measurements must be at least ten days older than that date, accounting for an assumed three-day result delay. A target needs two available prior samples and a latest sample within 120 days. Missing or stale targets receive an unavailable status, not a safe score. Constant-prevalence risk estimates cannot rank sites and do not issue flags.

The April exports are too old for current September forecasts. No live feed, notification service, or dashboard is running. Flag thresholds are historical statistical definitions, not approved action thresholds. The training/evaluation calendar is fixed in code; a new evaluation period requires a deliberate protocol update.

## Version history

The original E. coli-only prototype is preserved in `model.py`, `model.joblib`, the original root-level CSV/JSON files, `README_ecoli_v1.md`, and `watershed_model.zip`. That ZIP is the **old E. coli package**, not the new multi-target system. Use the `multitarget_*` code and `results/multitarget` for current work.

Changes are committed locally after each small completed change. No remote repository has been supplied, so nothing has been pushed. The environment, original exports, and scratch logs are excluded from Git.
