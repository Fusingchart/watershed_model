# Failure analysis and data verification

## Assessment

**Share the retrospective results with caveats. Do not treat this system as operationally validated.** Temperature and dissolved oxygen remain the best pilot candidates, but their average performance conceals difficult cases. E. coli is not ready for proactive alerts. Reporting conventions, site identity, and true result-availability times require confirmation.

This audit uses the April 13, 2026 exports and the saved January 2025–April 2026 test predictions. It does not retrain models, tune thresholds against these test outcomes, or alter source measurements. The evaluation period has now been examined in detail; further model revisions need a new untouched period or prospective evaluation.

## What was verified

- All **5,440 saved test predictions across 13 targets** join one-to-one to the cleaned site/date/measurement outcomes. No duplicated prediction keys or mismatched actual values were found.
- Source-unit mean absolute errors and event recall reproduce the saved evaluation. Undefined subgroup rates are left blank rather than presented as zero or perfect performance.
- Errors are broken down by site, season, year, history age, historical-tail status, extreme observations, and whether the site had eligible rows in the actual model-fitting data.
- The source checks examine retained rows, candidate arithmetic formulas, original/reviewed numeric values, site naming, timestamps, and turbidity method coverage. Matching arithmetic does not independently establish correct units or laboratory procedures.

## Failure findings

### 1. Temperature performs well overall, but the tails are harder

- Latest overall source-unit MAE: **1.46**.
- Observations outside the original training 5th–95th percentiles: **3.61 MAE across 42 samples**, versus 1.31 for other observations. This extreme group includes both hot and cold observations.
- The high-temperature research flag caught **83 of 100** tail events, missed **17**, and produced **39 false flags**.
- It caught **72 of 77 summer events**, but **none of 5 spring events**. Five events are too few to estimate stable spring recall.
- Among 31 sites with at least 10 test observations, **6 had worse point error than the validation-selected baseline**. These small site slices are diagnostic, not a basis for declaring individual sites reliable or unreliable.

**Implication:** a temperature pilot should examine seasonal transitions and extremes, and should not infer reliable spring warning from strong summer performance.

### 2. Low dissolved oxygen is harder than ordinary oxygen readings

- Overall source-unit MAE: **0.71**.
- Low-oxygen research-tail MAE: **1.38**, versus **0.56** for ordinary results.
- On low-oxygen events, predictions averaged **0.84 source units too high**. That direction of error can understate the problem.
- The flag caught **74 of 116** low-oxygen events, missed **42**, and produced **13 false flags**. Twenty of the misses occurred in summer.
- Among 30 sites with at least 10 test observations, **6 had worse point error than the chosen baseline**.
- MAE rises from **0.64** with 10–35-day-old measurements to **0.92** with 61–120-day-old measurements. These groups differ in composition; this does not prove that age caused the error.

**Implication:** evaluate low-oxygen misses and underprediction of severity explicitly when setting sampling priorities. Average error alone is insufficient.

### 3. E. coli gains do not translate into reliable event prediction

- On the 88 elevated research-tail samples, source-unit MAE was **669**, versus **48** on ordinary samples. Predictions averaged **662 source units below** the elevated outcomes.
- For 13 observations outside the training 5th–95th percentiles, log-scale error was **28% worse** than the validation-selected baseline. This is a small sample, but it directly challenges the use case of anticipating spikes.
- At sites absent from the model-fitting rows, log-scale error was **4.7% worse** than baseline across 166 observations. At fitting sites, it was 24.3% better. Site-code changes may contribute to this split.
- The current v2 classifier deliberately fell back to constant prevalence because its learned classifier did not improve validation probability error. It issues **no E. coli flags**, so all 88 elevated results appear in the missed-event audit. This is a documented fallback, not a functioning E. coli alert system.

**Implication:** do not deploy E. coli alerts from v2. Investigate site continuity and bacterial reporting conventions, then evaluate event-focused models with pre-forecast environmental inputs.

### 4. Improvement is not uniform across targets or locations

The CSVs retain all 13 targets, including targets whose selected point predictor is a simple baseline. Some subgroups are small and some seasons include portions of two calendar years. All subgroup gains compare against the same target-specific baseline selected before the latest test. They are descriptive diagnostics, not independent significance tests or causal explanations.

## Data verification findings

### Candidate bacterial calculations

The candidate formula is `mean(all three replicate counts) × 100 / sample_volume`. Only rows with all three counts, a positive volume, and a numeric reported average were checked. The factor 100 is an arithmetic hypothesis supported by many rows; it is not verification of units or protocol.

| Target | Complete comparisons | Match within tolerance | Within half-unit rounding | Possible zero-to-one floor | Needs other protocol review |
| --- | ---: | ---: | ---: | ---: | ---: |
| E. coli | 2,288 | 2,232 | 37 | 12 | 7 |
| Other coliform | 1,893 | 1,814 | 0 | 0 | 79 |

Tolerance is relative 0.1% or absolute 0.02. Rounding and floor categories are possible explanations, not confirmed corrections. The row-level evidence is in `bacteria_formula_checks.csv`. Incomplete replicates and quarantined rows are outside these denominators.

### Candidate chemistry calculations

| Target | Candidate formula | Complete comparisons | Matches |
| --- | --- | ---: | ---: |
| Dissolved oxygen | Mean of both recorded replicates | 2,714 | 2,713 |
| Alkalinity | Drop count × 5 | 2,401 | 2,400 |
| Hardness | Drop count × 10 | 2,406 | 2,403 |

These checks use relative 0.1% or absolute 0.05 tolerance. Five comparisons do not match; see `chemistry_derived_checks.csv`. They warrant source review, not automatic replacement.

No disagreements were found among comparable numeric original/reviewed pairs for the selected fields (water temperature, pH, conductivity, nitrate, phosphate, reported turbidity, and suspended solids). Reviewed fields are incomplete and may simply duplicate originals; agreement is not independent certification.

### Turbidity reporting is a material modeling concern

Of structurally valid chemistry rows:

- 247 have a numeric reported turbidity value and a tube method; **229 of these are exactly 8**.
- 190 have a numeric value and a meter method; only **1 is exactly 8**.
- **462 numeric reported turbidity values have no recorded method.**

The clustering at 8 is consistent with a method/reporting convention or possible reporting limit, but the CSV cannot establish which. The current reported-field model treats these numbers as exact observations. Confirm how to interpret them before relying on this target, and keep legacy turbidity separate.

### Site identity remains unresolved

There are **164 structurally valid raw site identifiers** across the two files. Nine identifiers have more than one normalized waterbody label. Many look like abbreviations or spelling differences; some are ambiguous. For example, code **5303394** appears with “North Creek,” “Piper's Creek North Creek,” and “Venema.”

An exact normalized waterbody-plus-location check found no matching-location groups spanning multiple codes. This narrow result does not rule out renamed sites, changed location descriptions, or identity problems. No site codes were merged. Use `site_identity_audit.csv` with the authoritative site registry. Precise location text and submitter information are omitted from published audit outputs.

### Creation dates do not establish result availability

Among structurally valid rows, bacteria creation timestamps fall on one calendar date and chemistry creation timestamps on two. Median creation-minus-sampling lag is roughly **1,508 days for bacteria and 1,364 days for chemistry**, consistent with bulk import metadata.

Additionally, 1,818 bacteria and 2,352 chemistry sampling timestamps fall at hour/minute 00:00. Some may have only date-level precision. The timestamp timezone is not established.

The assumed three-day result delay and seven-day forecast lead remain **unverified operational assumptions**. Collection date plus an invented delay cannot establish what the team actually knew at a historical issue time.

## Action queue

| Priority | Work | Evidence or input required |
| --- | --- | --- |
| 1 | Verify the nine site-label conflicts and continuity of newer codes | Authoritative site ID, coordinates, name history, service-area roster |
| 1 | Resolve bacterial discrepancies and reporting limits | Review rows in the formula-check CSVs; confirm units, volume interpretation, rounding, zero floors, and capped counts |
| 1 | Clarify turbidity methods and value 8 | Measurement protocol and detection/reporting limits; explain missing method labels |
| 1 | Establish true forecast-time availability | Sample collection, result release, revision timestamps, and timezone |
| 2 | Design a temperature/oxygen shadow pilot | Approved action thresholds, required warning, acceptable missed events and extra visits |
| 2 | Improve E. coli event modeling | Resolve data issues first; add rainfall/streamflow available at issue time; evaluate on a new period |

The first four require the data owner's records or explanations. None have been guessed into the model. Existing models and thresholds remain unchanged.

## Reproduce and inspect

Run `.venv/bin/python failure_audit.py` from `/Users/rishabh/watershed_model`. The script recreates the CSV evidence and manifest; this narrative report is an interpretation of the current snapshot and should be reviewed after reruns.

- `verified_metrics.csv`: independently recalculated overall metrics.
- `errors_by_*.csv`: complete target-specific subgroup results. Blank precision/recall means an undefined denominator.
- `largest_errors.csv`: ten largest transformed errors per target.
- `missed_events.csv`: every unflagged research-tail outcome, including deliberately inactive risk fallbacks.
- `measurement_verification.csv`: completeness, ranges, zeros, and repeated values.
- `*_checks.csv`, `site_identity_audit.csv`, `timestamp_verification.csv`, `turbidity_methods.csv`: source verification evidence.
- `manifest.json`: source and audit-script checksums.

The two new audit tests check event denominators and undefined rates. Existing temporal and data-cleaning tests remain applicable. These checks verify computation; they do not validate the field measurements themselves.
