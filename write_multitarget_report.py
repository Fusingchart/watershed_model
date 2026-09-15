"""Render a readable report directly from the saved multi-target evaluation."""
from pathlib import Path
import json
import pandas as pd

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/multitarget'

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows])

def main():
    e=json.loads((OUT/'evaluation.json').read_text())
    specs=json.loads((ROOT/'targets.json').read_text())
    coverage=pd.read_csv(OUT/'target_coverage.csv').set_index('target')
    point_rows=[];risk_rows=[];rolling=[];unsupported=[]
    for target,folds in e['targets'].items():
        r=folds['2025'];label=specs[target]['label']
        if r['status']=='insufficient_history':
            unsupported.append([label,coverage.loc[target,'valid_site_days'],r['counts']['train'],r['counts']['validation'],r['counts']['test']])
            continue
        strongest=min(r['baselines'],key=lambda n:r['baselines'][n]['transformed_MAE'])
        best_gain=100*(1-r['test']['transformed_MAE']/r['baselines'][strongest]['transformed_MAE'])
        point_rows.append([label,r['counts']['test'],r['selected'],f"{r['test']['source_MAE']:.3f}",f"{r['improvement_percent']:+.1f}%",f"{best_gain:+.1f}%",r['status'].replace('_',' ')])
        risk=r['risk']
        risk_rows.append([label,r['risk_selection'],risk['events'],risk['caught'],risk['false_alerts'],f"{risk['precision']:.0%}"])
        rolling.append([label]+[('not enough history' if folds[str(y)]['status']=='insufficient_history' else f"{folds[str(y)]['improvement_percent']:+.1f}%") for y in [2023,2024,2025]])
    point=table(['Target','Test samples','Selected predictor','MAE, source units','Gain vs validation-selected baseline','Gain vs strongest test baseline','Evidence'],point_rows)
    risks=table(['Target','Risk estimator','Actual tail events','Caught','False flags','Flag precision'],risk_rows)
    roll=table(['Target','2023','2024','2025–Apr 2026'],rolling)
    sparse=table(['Target','Valid site-days','Training forecasts','Validation forecasts','Test forecasts'],unsupported)
    text=f'''# Multi-target water-quality forecasting: results

## Main finding

The system now covers **15 measurements**. Thirteen have enough historical data for the specified retrospective evaluation: eight use learned point predictors and five use simple historical baselines selected on validation data. Phosphate and suspended solids are tracked in the data pipeline but have no trained predictor because their earlier histories are insufficient.

**Water temperature and dissolved oxygen have the clearest repeatable signal.** Their point forecasts improve on the validation-selected baselines across all three historical test periods. The other targets show mixed evidence, baseline-level performance, or inadequate coverage. This system is a research prototype for planning sampling; no operational or health thresholds have been approved.

## Latest held-out evaluation

Models were selected using 2024 data and evaluated on 2025 through April 2026. The comparable baseline is selected on validation data before the test. The strongest-test-baseline column is a stricter descriptive comparison, not another model-selection step.

{point}

“Positive signal” means the site-bootstrap interval for the latest test's error reduction against the validation-selected baseline is above zero. It does not establish operational reliability, causality, or significance adjusted for testing many targets. “Uncertain signal” includes cases where the learned model did worse than the baseline. A baseline being selected is an explicit outcome, not a failed training run.

Temperature, dissolved oxygen, oxygen saturation, and pH use absolute error on their reported scales. Other targets use absolute error on log(1 + value) for model selection; their source-unit errors are also shown. Do not compare MAE values across different measurements. Except for pH's named scale, source units still need confirmation. Back-transformed forecasts are central values on the transformed scale, not unbiased arithmetic means.

For continuity with the earlier E. coli prototype: v2 reduces error **5.5%** against its strongest test baseline, versus **14.7%** against its validation-selected seasonal baseline. These are different comparisons. Its gains do not consistently appear in the earlier folds.

## Earlier-year checks

Each column below is a separate chronological evaluation. The previous year selects the predictor; still-earlier data fits it. Selected predictors may differ between folds. Positive percentages indicate lower error than that fold's validation-selected simple baseline.

{roll}

The 2023 and 2024 tests are historical robustness checks. They also precede the latest test's training/validation period, so the three columns are not three independent prospective trials. Treat all results as exploratory; additional iterations need a new untouched evaluation period or a prospective pilot.

## Experimental flags

Flags mean crossing a historical training-distribution tail, not crossing a legal, ecological, or health action limit. High-direction targets use the training 75th percentile; low-direction targets use the 25th percentile; two-sided targets use the 10th and 90th percentiles. Equality to a threshold does not trigger the event. Directions and thresholds are in `targets.json` and `evaluation.json`.

A random-forest classifier is retained only if it beats constant prevalence on validation probability error. Its probability cutoff is chosen to catch at least 75% of validation tail events. That does not guarantee 75% recall on future data. A constant-prevalence fallback produces a probability estimate but **does not rank sites or issue flags**; absence of a flag is not evidence of safe water.

{risks}

The E. coli and conductivity risk classifiers fell back to constant prevalence under this v2 comparison. Their continuous-value forecasts still exist, but v2 does not claim useful site-specific risk probabilities for those targets. Point and risk models are selected independently. Other targets, particularly nitrate and pH, produce many false flags. The probabilities have not had a separate calibration study.

Multiple target flags may be highly correlated—for example, dissolved oxygen and oxygen saturation. The site overview lists the individual flagged targets and unavailable targets. It does **not** add these into a combined danger probability or safety score.

## Targets needing more history

{sparse}

The fixed support rule requires at least 150 training forecasts, 30 validation forecasts, 30 test forecasts, and 5 test sites. Phosphate and suspended solids fail the earlier-history requirement. Their 2025 observations are not moved into training merely to make a model appear evaluable. They could be considered in a later study with enough independent post-training outcomes. Salinity technically passes but has only 33 test observations, uncertain measurement units, and no eligible April 20 historical-example forecasts; its current evidence is especially weak.

## Data quality and information boundaries

- Chemistry and bacteria observations are now cleaned independently by measurement. A missing E. coli value does not discard a valid other-coliform result, and chemistry forecasts do not require bacteria history.
- Structurally quarantined rows: **{e['audit']['bacteria']['structurally_excluded_rows']} bacteria and {e['audit']['chemistry']['structurally_excluded_rows']} chemistry**. Separate cell-level exclusions are recorded in `excluded_measurements.csv`. These counts differ from v1 because missing targets no longer quarantine the whole row.
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
'''
    (OUT/'REPORT.md').write_text(text)

if __name__=='__main__':main()
