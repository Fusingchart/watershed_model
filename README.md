# Sno-King watershed: E. coli forecasting prototype

## Result

A trained model and reproducible pipeline now predict E. coli at a planned sampling visit and assign an experimental elevated-result probability. This is a retrospective research prototype for prioritizing sampling. Its measured performance does not support autonomous public advisories or safety decisions.

**Held-out evaluation: 459 samples at 52 sites, January 2025–April 2026.**

| Prediction approach | Mean absolute error on log(1 + E. coli), lower is better | Mean absolute error in source units |
|---|---:|---:|
| Random forest model | 1.588 | 168.0 |
| Global historical median | 1.700 | 177.9 |
| Last available site result | 1.942 | 238.0 |
| Site's historical median | 1.951 | 181.2 |

The model reduced log-scale error by **6.6% against the strongest simple baseline**, and 18.2% against the last observation. Large absolute errors remain. A bootstrap that resamples whole sites gives a 95% interval of **−0.007 to +0.248** for the log-error gain against the global median: that interval includes no improvement. This is promising but not conclusive evidence of better forecasting. The bootstrap does not capture all shared weather-event dependence or model-selection uncertainty.

## What the alerts mean

“Elevated” means **Average_e_coli > 233.3333333**, the 75th percentile of eligible training outcomes. This is a statistical research definition, not a regulatory or health threshold. Source measurement units have not been independently verified. The model predicts the exported `Average_e_coli` field without reconstructing it from plate counts, volumes, or review fields.

The sensitive policy uses a probability cutoff of **0.2200**, selected on the 2024 validation data to achieve at least 75% recall there. It was not optimized against test outcomes. On the held-out data:

- 88 samples were elevated; the policy identified **60 (68%)** and missed **28**.
- It flagged **208 of 459** samples: **60 true alerts and 148 false alerts**.
- Alert precision was **29%**, compared with a 19% elevated rate overall.
- Risk-ranking ROC AUC was **0.716**; average precision was **0.381**.
- Brier score, a probability error metric, was 0.142 versus 0.157 for constant historical prevalence.

The default 50% probability cutoff is too insensitive: it identified only 9 of 88 elevated samples. The lower cutoff trades substantially more sampling workload for fewer misses. Probabilities have not undergone a separate calibration study. The classifier and continuous-value model are separate models; their outputs need not agree at a specific concentration cutoff.

## Forecast definition and information boundaries

A forecast is issued **7 days before a planned sampling date**. Only samples collected at least **10 days before that date** can contribute features, allowing an assumed 3-day result turnaround. Features include site identity, seasonal month, previous E. coli results, historical summaries, previous temperature measurements, and historical chemistry. Chemistry older than 120 days is treated as missing.

A site needs at least two available prior bacteria samples, with its latest no more than 120 days before the planned date. Sites without sufficient history are omitted, not labeled low risk. Identifiers are kept as strings; new 12-digit identifiers are retained as separate sites rather than guessed to match older codes.

The historical evaluation treats each observed visit date as if it had been scheduled in advance. It therefore evaluates **seven-day-ahead predictions at sampled visits**, not all-day event detection, unscheduled incidents, or the timing of the next visit. Monthly sampling cannot reveal contamination events occurring between visits.

The 3-day result delay is an assumption: actual publication timestamps are not available. These are retrospective exports, so later corrections and historical availability cannot be reconstructed. Date timezone is also unconfirmed. A live pilot needs actual availability timestamps and a fixed sampling schedule.

## Data preparation

| Dataset | Input rows | Quarantined rows | Clean site-days | Sites |
|---|---:|---:|---:|---:|
| Bacteria | 2,526 | 72 | 2,401 | 109 |
| Chemistry | 3,268 | 47 | 3,147 | 162 |

Quarantine criteria include nonempty extra CSV columns, shifted or invalid metadata, invalid/scientific-notation site identifiers, missing or negative bacteria targets, and invalid dates. One chemistry sample dated after the assumed April 13, 2026 export date was excluded. Original CSVs were not changed.

Duplicate site/date rows were collapsed using medians: 53 bacteria rows and 74 chemistry rows were absorbed. This may combine distinct within-day samples and needs review. Broad plausibility ranges turn invalid numeric predictors into missing values. Measurement protocols, reviewed-versus-original values, detection limits, site-code continuity, units, and cross-site comparability still require the data owner's confirmation. No capped counts were reinterpreted or corrected.

Both CSVs contain multiple groups and watersheds. This prototype uses all retained records, not only records labeled “Sno-King Water Watchers.” Confirm the intended service area before deployment. Cleaned files omit submitter names, access codes, comments, and precise location descriptions.

## Training and evaluation

- Training: 1,437 eligible forecasts before December 22, 2023.
- Validation: 207 forecasts from January 1–December 21, 2024.
- Test: 459 forecasts from January 1, 2025 onward; 365 in 2025 and 94 in 2026.
- Nine boundary observations were excluded to preserve the assumed lead time and result lag.
- Validation compared ridge regression, random forest regression, logistic classification, and random forest classification. A ridge model without chemistry was also evaluated. This limited comparison does not establish the independent value of chemistry.
- Random forests were selected for both tasks. They were refitted on training and validation observations before test scoring.
- Saved model weights remain fitted through December 21, 2024, matching the evaluation. Earlier test-period observations may enter later forecasts as history after the assumed delay; model weights are not updated during testing.
- Continuous predictions are fitted in log(1 + E. coli) space and back-transformed. They estimate a central value in transformed space, not an unbiased arithmetic mean.
- Three automated tests verify future-result exclusion, rejection of sparse/stale histories, and quarantine of shifted rows. Training and prediction commands were exercised successfully.

## Files

- `model.py`: cleaning, feature construction, training, evaluation, and scoring CLI.
- `model.joblib`: fitted model bundle, feature lists, and thresholds.
- `metrics.json`: validation and held-out scores, audit counts, and uncertainty estimates.
- `heldout_predictions.csv`: actual versus predicted results and alerts for every test observation.
- `historical_example_forecasts.csv`: 44 eligible site forecasts for April 20, 2026, issued April 13. **Historical demonstration, not current alerts.**
- `clean_bacteria.csv`, `clean_chemistry.csv`: cleaned observations.
- `model_dataset.csv`: eligible feature/outcome rows for reproducibility. Use the documented chronological splits; do not randomly split this table.
- `excluded_records.csv`: source row references and quarantine reasons.
- `manifest.json`: source CSV hashes and environment versions.
- `test_model.py`, `requirements.txt`: automated checks and dependencies.

## Run it

Use Python 3.12. From this folder:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest test_model.py -v

.venv/bin/python model.py train \
  --bacteria /Users/rishabh/Downloads/MasterBactSurvey4_13_26.csv \
  --chemistry /Users/rishabh/Downloads/MasterChemSurvey4_13_26.csv

.venv/bin/python model.py predict \
  --bacteria /Users/rishabh/Downloads/MasterBactSurvey4_13_26.csv \
  --chemistry /Users/rishabh/Downloads/MasterChemSurvey4_13_26.csv \
  --date 2026-04-20 \
  --output historical_example_forecasts.csv
```

For refreshed CSVs, also supply `--snapshot-date YYYY-MM-DD` with their export date. The schema must match these files. `--date` is the planned sampling date, seven days after issue. This April data is too old for current September forecasts under the 120-day freshness rule. The scoring command raises an error if no sites qualify. Retraining overwrites the model and evaluation artifacts; the evaluation dates are fixed in the script and must be deliberately advanced for a new study.

## Next step toward an operational pilot

Agree on the intervention, approved measurement definition, site roster, alert threshold, and acceptable extra-sampling workload. Confirm laboratory turnaround and field definitions with the team. Then evaluate rainfall, streamflow, and upstream information available at forecast time, and run the system in a prospective shadow pilot. Measure missed events and unnecessary visits before allowing it to drive operational decisions.
