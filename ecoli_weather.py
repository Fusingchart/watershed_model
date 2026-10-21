"""Develop and freeze an E. coli model with issue-time rainfall and streamflow.

Decision rule, fixed before any result was computed:
- Development uses samples dated before 2025 only. 2025-01-01 onward is never loaded into scoring.
- Two development years, each scored after training on data ending ten days before it:
  2023 (training before 2022-12-22) and 2024 (training before 2023-12-22).
- The weather model becomes the v3 candidate only if its mean absolute log error is lower than the
  unchanged v2 feature set in BOTH years. Otherwise v2 stays and the result is reported as negative.
- The oracle variant (rain on the sample day and the three days before) is never a candidate.
- A v3 candidate is refit on exactly the rows v2 used (before 2023-12-22, plus 2024-01-01 to 2024-12-21)
  and saved with its SHA-256 for the prospective protocol.
"""
from pathlib import Path
import hashlib
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from multitarget_data import ROOT, TARGETS, History, load_data, build_target_dataset, transform
from multitarget_model import pipeline, cluster_gain, save_json
from weather import WEATHER_FEATURES, daily, add_weather, oracle_rain

OUT = ROOT/'results/ecoli_weather'
DEVELOPMENT_END = pd.Timestamp('2025-01-01')
YEARS = [2023, 2024]


def forest():
    return RandomForestRegressor(n_estimators=150, min_samples_leaf=12, max_features=.8, random_state=42, n_jobs=2)


def development_rows(data, table):
    d = build_target_dataset(data, History(data), 'ecoli')
    d = d.loc[d.date < DEVELOPMENT_END].reset_index(drop=True)
    assert d.date.max() < DEVELOPMENT_END
    d = add_weather(d, table)
    d['oracle_rain_0_3'] = oracle_rain(d, table)
    return d


def compare(d, year, base_cols):
    train = d.date < pd.Timestamp(f'{year-1}-12-22')
    test = d.date.between(f'{year}-01-01', f'{year}-12-31')
    y = transform(d.actual, TARGETS['ecoli'])
    variants = {'v2':base_cols, 'weather':base_cols+WEATHER_FEATURES, 'oracle_diagnostic':base_cols+WEATHER_FEATURES+['oracle_rain_0_3']}
    errors, result = {}, {'train':int(train.sum()), 'test':int(test.sum()), 'test_sites':int(d.loc[test,'site'].nunique())}
    for name, cols in variants.items():
        p = pipeline(d[cols], forest()).fit(d.loc[train,cols], y[train]).predict(d.loc[test,cols])
        errors[name] = p
        result[name] = {'log_MAE':float(np.mean(np.abs(y[test]-p)))}
    sites = d.loc[test,'site'].to_numpy()
    for name in ['weather','oracle_diagnostic']:
        result[name]['gain_vs_v2'] = cluster_gain(y[test].to_numpy(), errors[name], errors['v2'], sites)
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data,_,_,_ = load_data(ROOT/'data/raw/MasterBactSurvey4_13_26.csv', ROOT/'data/raw/MasterChemSurvey4_13_26.csv', '2026-04-13')
    table = daily()
    d = development_rows(data, table)
    frozen = joblib.load(ROOT/'results/multitarget/models.joblib')['ecoli']
    base_cols = frozen['features']
    years = {str(year):compare(d, year, base_cols) for year in YEARS}
    adopt = all(years[str(y)]['weather']['log_MAE'] < years[str(y)]['v2']['log_MAE'] for y in YEARS)
    summary = {'decision':'weather_model_is_v3_candidate' if adopt else 'keep_v2', 'development_end':str(DEVELOPMENT_END.date()),
               'weather_missing_rate':float(d[WEATHER_FEATURES].isna().any(axis=1).mean()), 'years':years}
    if adopt:
        fitted = (d.date < pd.Timestamp('2023-12-22')) | d.date.between('2024-01-01','2024-12-21')
        cols = base_cols+WEATHER_FEATURES
        model = pipeline(d[cols], forest()).fit(d.loc[fitted,cols], transform(d.loc[fitted,'actual'], TARGETS['ecoli']))
        joblib.dump({'target':'ecoli','features':cols,'regressor':model,'training_end':str(d.loc[fitted,'date'].max().date())}, OUT/'model_v3.joblib')
        summary['model_v3_sha256'] = hashlib.sha256((OUT/'model_v3.joblib').read_bytes()).hexdigest()
        summary['fitted_rows'] = int(fitted.sum())
    save_json(OUT/'development.json', summary)
    print(summary['decision'])
    for year, r in years.items():
        print(year, {k:(round(v['log_MAE'],4) if isinstance(v,dict) else v) for k,v in r.items()})


if __name__ == '__main__':main()
