"""Score the frozen multi-target models on samples taken after the April 13, 2026 snapshot."""
from pathlib import Path
import argparse
import hashlib
import json
import joblib
import numpy as np
import pandas as pd
from multitarget_data import ROOT, TARGETS, History, load_data, build_target_dataset, transform, inverse
from multitarget_model import BASELINES, forecast, regression_metrics, cluster_gain, save_json

FROZEN = ROOT/'results/multitarget'
FROZEN_MODELS_SHA256 = 'dbf87e6be9c2925446d1fdaa3106306f1393f38763f3584926a471638e3bb45b'
FROZEN_SNAPSHOT = '2026-04-13'
PRIMARY = ['water_temperature', 'dissolved_oxygen']
MIN_OBSERVATIONS, MIN_SITES = 100, 10
CONFLICT_SITES = {'5303387','5303391','5303392','5303393','5303394','5303395','5303396','5303397','5303398'}


def verdict(n, sites, uncertainty):
    if n < MIN_OBSERVATIONS or sites < MIN_SITES:
        return 'insufficient_data'
    low, high = uncertainty['site_bootstrap_95_interval']
    return 'confirmed' if low > 0 else ('not_confirmed' if high <= 0 or uncertainty['mean_gain'] <= 0 else 'inconclusive')


def score(d, bundle, baseline, target):
    spec = TARGETS[target]
    if d.empty:
        return {'observations':0,'sites':0,'verdict':'insufficient_data'}, None
    X = d[bundle['features']]; y = transform(d.actual, spec)
    prediction = forecast(bundle, X)
    reference = forecast({'selected':baseline,'median':bundle['median']}, X)
    model, base = regression_metrics(d.actual, prediction, spec), regression_metrics(d.actual, reference, spec)
    n, sites = len(d), int(d.site.nunique())
    uncertainty = cluster_gain(y, prediction, reference, d.site.to_numpy()) if sites > 1 else {'mean_gain':float(np.mean(np.abs(y-reference)-np.abs(y-prediction))),'site_bootstrap_95_interval':[np.nan,np.nan]}
    result = {'observations':n,'sites':sites,'model':model,'baseline':base,
              'improvement_percent':float(100*(base['transformed_MAE']-model['transformed_MAE'])/base['transformed_MAE']) if base['transformed_MAE'] else 0.,
              'uncertainty':uncertainty,'verdict':verdict(n, sites, uncertainty)}
    rows = d[['site','date','issue_date','actual','target_age_days']].assign(target=target, predicted=inverse(prediction, spec), baseline_predicted=inverse(reference, spec))
    return result, rows


def revisions(old, new, snapshot):
    """Compare pre-snapshot aggregates so silent source revisions are visible before scoring."""
    keys = ['site','date','target']
    new = new.loc[new.date <= pd.Timestamp(snapshot), keys+['value']]
    m = old[keys+['value']].merge(new, on=keys, how='outer', suffixes=('_old','_new'), indicator=True)
    both = m._merge.eq('both')
    return {'unchanged':int((both & np.isclose(m.value_old, m.value_new)).sum()),'changed':int((both & ~np.isclose(m.value_old, m.value_new)).sum()),
            'removed':int(m._merge.eq('left_only').sum()),'added':int(m._merge.eq('right_only').sum())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bacteria', required=True); ap.add_argument('--chemistry', required=True)
    ap.add_argument('--snapshot-date', required=True)
    ap.add_argument('--start', default='2026-04-14', help='First sample date scored; earlier dates are a reproduction check only')
    ap.add_argument('--output-dir', default=str(ROOT/'results/prospective'))
    args = ap.parse_args()
    digest = hashlib.sha256((FROZEN/'models.joblib').read_bytes()).hexdigest()
    if digest != FROZEN_MODELS_SHA256:
        raise SystemExit(f'models.joblib changed ({digest}); prospective scoring requires the frozen September 14, 2026 models')
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    models = joblib.load(FROZEN/'models.joblib')
    selected = {t:v['2025'].get('selected_baseline') for t,v in json.loads((FROZEN/'evaluation.json').read_text())['targets'].items()}
    data,_,_,audit = load_data(args.bacteria, args.chemistry, args.snapshot_date)
    old = pd.read_csv(FROZEN/'clean_measurements.csv', dtype={'site':str}, parse_dates=['date'])
    history = History(data); start = pd.Timestamp(args.start)
    results, predictions = {}, []
    for target, bundle in models.items():
        d = build_target_dataset(data, history, target)
        d = d.loc[d.date >= start] if not d.empty else d
        all_sites, rows = score(d, bundle, selected[target], target)
        kept = d.loc[~d.site.isin(CONFLICT_SITES)] if not d.empty else d
        conflict_free = score(kept, bundle, selected[target], target)[0]
        if bundle['selected'] in BASELINES:
            # The frozen forecast is the baseline itself; there is no gain to confirm.
            all_sites['verdict'] = conflict_free['verdict'] = 'frozen_model_is_baseline'
        results[target] = {'primary':target in PRIMARY,'frozen_model':bundle['selected'],'frozen_baseline':selected[target],
                           'all_sites':all_sites,'excluding_site_conflicts':conflict_free}
        if rows is not None: predictions.append(rows)
        print(target, all_sites['verdict'], all_sites['observations'], flush=True)
    save_json(out/'evaluation.json', {'protocol':'PROSPECTIVE_PROTOCOL.md','models_sha256':digest,'start':str(start.date()),
              'snapshot_date':args.snapshot_date,'reproduction_check_only':bool(start <= pd.Timestamp(FROZEN_SNAPSHOT)),
              'source_revisions_before_frozen_snapshot':revisions(old, data, FROZEN_SNAPSHOT),'audit':audit,'targets':results})
    if predictions: pd.concat(predictions, ignore_index=True).to_csv(out/'predictions.csv', index=False)


if __name__ == '__main__':main()
