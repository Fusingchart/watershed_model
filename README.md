# Sno-King water-quality forecasting

Working folder: `/Users/rishabh/watershed_model`.

## Interface

```sh
.venv/bin/python app.py      # then open http://127.0.0.1:5057
```

A local web app over the frozen models. **Forecast** shows every site's predictions for a planned visit date, with the reason when a forecast is unavailable. Rows turn red when a forecast is outside the acceptable range in `limits.json` and yellow when it is within the model's typical test error of a limit. The default limits are Washington State freshwater criteria (temperature ≤ 16 °C for core summer salmonid habitat; dissolved oxygen ≥ 8.0 mg/L for salmonid spawning, rearing and migration, provisional because 9.5 applies to core summer habitat; pH 6.5–8.5, E. coli ≤ 320 per 100 mL); they are reference values, not approved action levels, so confirm them with the data owner. **Site history** plots a site's measurements against the 2025–April 2026 test forecasts and has a scenario panel: add hypothetical measurements and see the forecast change. **Model results** summarizes each measurement's test result and caveats. It reads `data/raw/` and binds to localhost only, because the exports contain personal details. Forecasts for visits after August 9, 2026 are unavailable until newer exports are loaded (`--bacteria`, `--chemistry`, `--snapshot-date`).

## E. coli weather features: negative

`results/ecoli_weather/REPORT.md`: regional rainfall and Issaquah Creek streamflow, known at issue time, made E. coli forecasts worse in both 2023 and 2024 development years. Even rain on the sample day did not help. Under the rule committed in advance, v2 stays and no new model was frozen. Public weather data lives in `data/external/` (`weather.py fetch` refreshes it).

## Next evaluation: prospective

`PROSPECTIVE_PROTOCOL.md` fixes, before any new data is seen, how the frozen models will be judged on samples taken after April 13, 2026. Temperature and dissolved oxygen are the primary questions. When a newer export arrives, run `.venv/bin/python prospective_evaluation.py --bacteria ... --chemistry ... --snapshot-date ...`; it checks the model file hash, reports source revisions, and writes `results/prospective/`.

## Data-owner request

`results/data_owner_request/REQUEST.md` collects the open questions for the data owner: site identity, bacteria and chemistry rows to check, turbidity reporting, result timing, and newer exports. The CSVs beside it list the exact source lines, with blank columns for answers. Regenerate with `.venv/bin/python data_owner_request.py` after rerunning the failure audit.

## Latest sensitivity check

Read `results/sensitivity/REPORT.md` for the fixed-model comparison after conservative data-quality exclusions. Temperature and oxygen gains persist; E. coli improvement is sensitive to site selection. Reproduce with `.venv/bin/python sensitivity_analysis.py`.

## Latest audit

Read `results/failure_audit/REPORT.md` for failure analysis by site, season, extreme observations, and history age, plus source arithmetic, site identity, turbidity, and timestamp checks. Reproduce the evidence with `.venv/bin/python failure_audit.py`. Models remain unchanged; operational use still needs the data-owner verifications listed in the report.

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

Commit and push each small completed change to https://github.com/Fusingchart/watershed_model. The environment, original exports, and scratch logs are excluded from Git.
