"""Train, retrospectively evaluate, and score separate water-quality forecasts."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, roc_auc_score, average_precision_score, brier_score_loss, precision_score, recall_score
from multitarget_data import ROOT, TARGETS, History, load_data, build_target_dataset, transform, inverse

MIN_TRAIN, MIN_VALIDATION, MIN_TEST = 150, 30, 30
BASELINES = ['global_median', 'last_observation', 'site_median', 'site_seasonal']


def pipeline(X, estimator):
    numeric = [k for k in X if k != 'site']
    return make_pipeline(ColumnTransformer([
        ('site', OneHotEncoder(handle_unknown='ignore', sparse_output=False), ['site']),
        ('numeric', make_pipeline(SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True), StandardScaler()), numeric)
    ]), estimator)


def forecast(bundle, X):
    name = bundle['selected']
    if name == 'global_median':
        return np.full(len(X), bundle['median'])
    if name in BASELINES:
        return X[{'last_observation':'last_value', 'site_median':'history_median', 'site_seasonal':'seasonal_site'}[name]].to_numpy()
    return bundle['regressor'].predict(X[bundle['features']])


def risk_labels(values, thresholds):
    values = np.asarray(values)
    return ((values < thresholds['lower']) | (values > thresholds['upper'])).astype(int)


def risk_probability(bundle, X):
    if bundle.get('classifier') is None:
        return np.full(len(X), bundle['prevalence'])
    return bundle['classifier'].predict_proba(X[bundle['features']])[:, 1]


def regression_metrics(y, p, spec):
    return {'transformed_MAE':float(mean_absolute_error(transform(y, spec), p)),
            'source_MAE':float(mean_absolute_error(y, inverse(p, spec)))}


def classification_metrics(y, p, cutoff):
    alerts = p >= cutoff
    n_positive = int(y.sum())
    return {'AUC':float(roc_auc_score(y,p)) if 0 < n_positive < len(y) else None,
            'average_precision':float(average_precision_score(y,p)) if n_positive else None,
            'Brier':float(brier_score_loss(y,p)), 'prevalence':float(np.mean(y)),
            'precision':float(precision_score(y,alerts,zero_division=0)),
            'recall':float(recall_score(y,alerts,zero_division=0)),
            'events':n_positive, 'caught':int(((y==1)&alerts).sum()),
            'missed':int(((y==1)&~alerts).sum()), 'false_alerts':int(((y==0)&alerts).sum()),
            'alerts':int(alerts.sum()), 'alert_cutoff':float(cutoff)}


def cluster_gain(y, p, baseline, sites):
    delta = np.abs(y-baseline)-np.abs(y-p)
    group = pd.DataFrame({'site':sites,'gain':delta}).groupby('site').gain.agg(['sum','count'])
    rng = np.random.default_rng(42)
    selected = rng.integers(0, len(group), size=(1000,len(group)))
    boot = group['sum'].to_numpy()[selected].sum(axis=1)/group['count'].to_numpy()[selected].sum(axis=1)
    return {'mean_gain':float(delta.mean()), 'site_bootstrap_95_interval':np.quantile(boot,[.025,.975]).tolist()}


def evaluate_fold(d, target, test_year, final=False):
    """Tune on previous year only; embargo 10 days at year boundaries."""
    spec = TARGETS[target]
    train = d.date < pd.Timestamp(f'{test_year-2}-12-22')
    validation = d.date.between(f'{test_year-1}-01-01',f'{test_year-1}-12-21')
    test = d.date >= pd.Timestamp(f'{test_year}-01-01')
    if not final:
        test &= d.date <= pd.Timestamp(f'{test_year}-12-31')
    counts = {'train':int(train.sum()), 'validation':int(validation.sum()), 'test':int(test.sum())}
    if counts['train']<MIN_TRAIN or counts['validation']<MIN_VALIDATION or counts['test']<MIN_TEST or d.loc[test,'site'].nunique()<5:
        return {'status':'insufficient_history', 'counts':counts}, None, None
    cols = [k for k in d if k not in ['date','issue_date','actual']]
    X = d[cols]; y = transform(d.actual,spec)
    candidates = {name:{'selected':name,'median':float(np.median(y[train]))} for name in BASELINES}
    for name, estimator in [('ridge',Ridge(alpha=30)),('forest',RandomForestRegressor(n_estimators=150,min_samples_leaf=12,max_features=.8,random_state=42,n_jobs=2))]:
        candidates[name] = {'selected':name,'features':cols,'regressor':pipeline(X,estimator).fit(X[train],y[train])}
    validation_scores = {name:regression_metrics(d.loc[validation,'actual'],forecast(m,X[validation]),spec) for name,m in candidates.items()}
    selected = min(candidates, key=lambda n:validation_scores[n]['transformed_MAE'])
    selected_baseline = min(BASELINES, key=lambda n:validation_scores[n]['transformed_MAE'])
    # Experimental flags describe historical tails, never legal/health thresholds.
    values = d.loc[train,'actual']
    direction = spec['direction']
    lower = float(values.quantile(.1 if direction=='both' else .25)) if direction in ['both','low'] else -np.inf
    upper = float(values.quantile(.9 if direction=='both' else .75)) if direction in ['both','high'] else np.inf
    thresholds = {'lower':lower, 'upper':upper}
    labels = risk_labels(d.actual,thresholds)
    prevalence = float(labels[train].mean())
    validation_probability = np.full(validation.sum(),prevalence)
    classifier = None
    risk_selection = 'constant_prevalence'
    train_counts = np.bincount(labels[train],minlength=2)
    validation_counts = np.bincount(labels[validation],minlength=2)
    if min(train_counts)>=20 and min(validation_counts)>=5:
        trial = pipeline(X,RandomForestClassifier(n_estimators=150,min_samples_leaf=15,max_features=.8,random_state=42,n_jobs=2)).fit(X[train],labels[train])
        trial_p = trial.predict_proba(X[validation])[:,1]
        if brier_score_loss(labels[validation],trial_p) < brier_score_loss(labels[validation],validation_probability):
            classifier = trial; validation_probability = trial_p; risk_selection = 'forest'
    # Constant prevalence cannot rank sites and must not trigger blanket warnings.
    cutoff = 1.1
    if classifier is not None:
        possible = np.unique(np.r_[0.,validation_probability])
        cutoff = float(max(t for t in possible if recall_score(labels[validation],validation_probability>=t)>=.75))
    fitted = train|validation
    bundle = candidates[selected]
    if selected not in BASELINES:
        bundle['regressor'].fit(X[fitted],y[fitted])
    bundle.update({'median':float(np.median(y[fitted])), 'features':cols,'thresholds':thresholds,
                   'classifier':classifier,'prevalence':float(labels[fitted].mean()),'risk_selection':risk_selection,
                   'alert_cutoff':cutoff,'training_end':str(d.loc[fitted,'date'].max().date()),'target':target})
    if classifier is not None:
        classifier.fit(X[fitted],labels[fitted])
    prediction = forecast(bundle,X[test]);p = risk_probability(bundle,X[test])
    baselines = {name:forecast({'selected':name,'median':bundle['median']},X[test]) for name in BASELINES}
    metrics = regression_metrics(d.loc[test,'actual'],prediction,spec)
    baseline_metrics = {name:regression_metrics(d.loc[test,'actual'],pred,spec) for name,pred in baselines.items()}
    reference = baseline_metrics[selected_baseline]['transformed_MAE']
    uncertainty = cluster_gain(y[test],prediction,baselines[selected_baseline],d.loc[test,'site'].to_numpy())
    status = 'baseline_selected' if selected in BASELINES else ('positive_signal' if uncertainty['site_bootstrap_95_interval'][0]>0 else 'uncertain_signal')
    report = {'status':status,'counts':counts,'test_sites':int(d.loc[test,'site'].nunique()),'selected':selected,
              'selected_baseline':selected_baseline,'validation':validation_scores,'test':metrics,'baselines':baseline_metrics,
              'improvement_percent':float(100*(reference-metrics['transformed_MAE'])/reference) if reference else 0.,
              'uncertainty':uncertainty,'risk_selection':risk_selection,
              'thresholds':{k:float(v) if np.isfinite(v) else None for k,v in thresholds.items()},
              'risk':classification_metrics(labels[test],p,cutoff)}
    predictions = d.loc[test,['site','date','issue_date','actual','target_age_days']].copy()
    predictions['target']=target;predictions['predicted']=inverse(prediction,spec)
    predictions['baseline_predicted']=inverse(baselines[selected_baseline],spec)
    predictions['experimental_tail_probability']=p
    predictions['actual_tail_event']=labels[test]
    predictions['experimental_flag']=p>=cutoff
    return report,bundle,predictions


def save_json(path, value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False))


def train(args):
    out = Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    data, excluded, cells, audit = load_data(args.bacteria,args.chemistry,args.snapshot_date)
    data.to_csv(out/'clean_measurements.csv',index=False)
    excluded.to_csv(out/'excluded_rows.csv',index=False)
    cells.to_csv(out/'excluded_measurements.csv',index=False)
    history = History(data)
    reports, coverage, summaries, bundles, predictions = {},[],[],{},[]
    for target,spec in TARGETS.items():
        observed = data.loc[data.target.eq(target)]
        d = build_target_dataset(data,history,target)
        item = {'target':target,'label':spec['label'],'valid_site_days':len(observed),'sites':int(observed.site.nunique()),
                'first_date':str(observed.date.min().date()) if len(observed) else None,
                'last_date':str(observed.date.max().date()) if len(observed) else None,
                'eligible_forecasts':len(d),'source_column':spec['column'],'caution':spec.get('caution','')}
        coverage.append(item)
        folds = {}
        for year in [2023,2024,2025]:
            if d.empty:
                result,bundle,pred = {'status':'insufficient_history','counts':{'train':0,'validation':0,'test':0}},None,None
            else:
                result,bundle,pred = evaluate_fold(d,target,year,final=year==2025)
            folds[str(year)] = result
            if year==2025 and bundle is not None:
                bundles[target]=bundle;predictions.append(pred)
        reports[target] = folds
        final = folds['2025']
        summaries.append({'target':target,'label':spec['label'],'status':final['status'],**final['counts'],
                          'selected_model':final.get('selected'), 'baseline':final.get('selected_baseline'),
                          'improvement_percent':final.get('improvement_percent'),
                          'source_MAE':final.get('test',{}).get('source_MAE'),
                          'risk_model':final.get('risk_selection'),
                          'risk_recall':final.get('risk',{}).get('recall'),
                          'risk_precision':final.get('risk',{}).get('precision')})
        print(target,final['status'],final['counts'],flush=True)
    pd.DataFrame(coverage).to_csv(out/'target_coverage.csv',index=False)
    pd.DataFrame(summaries).to_csv(out/'target_summary.csv',index=False)
    if predictions:pd.concat(predictions,ignore_index=True).to_csv(out/'heldout_predictions.csv',index=False)
    save_json(out/'evaluation.json',{'protocol':{'lead_days':7,'assumed_results_delay_days':3,'max_history_age_days':120,
               'minimum_train':MIN_TRAIN,'minimum_validation':MIN_VALIDATION,'minimum_test':MIN_TEST,
               'final_test_period':'2025-01-01 through snapshot','snapshot_date':args.snapshot_date},'audit':audit,'targets':reports})
    joblib.dump(bundles,out/'models.joblib')
    save_json(out/'manifest.json',{'inputs':{Path(p).name:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in [args.bacteria,args.chemistry]},
              'config_sha256':hashlib.sha256((ROOT/'targets.json').read_bytes()).hexdigest(),
              'python':platform.python_version(),'sklearn':sklearn.__version__,'pandas':pd.__version__,'numpy':np.__version__,
              'code_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['multitarget_data.py','multitarget_model.py']}})


def predict(args):
    out = Path(args.output_dir)
    models = joblib.load(out/'models.joblib')
    data,_,_,_ = load_data(args.bacteria,args.chemistry,args.snapshot_date)
    history = History(data);date=pd.Timestamp(args.date).normalize()
    rows = []
    for site in history.sites:
        for target,spec in TARGETS.items():
            row={'site':site,'target':target,'planned_sample_date':str(date.date()),'issue_date':str((date-pd.Timedelta(days=7)).date())}
            bundle=models.get(target)
            if bundle is None:
                row['status']='insufficient_training_history'
            elif date <= pd.Timestamp(bundle['training_end'])+pd.Timedelta(days=10):
                row['status']='date_overlaps_training_information'
            else:
                f,reason=history.features(site,target,date)
                row['status']=reason
                if f is not None:
                    X=pd.DataFrame([f]);p=float(risk_probability(bundle,X)[0])
                    row.update(predicted=float(inverse(forecast(bundle,X),spec)[0]),experimental_tail_probability=p,
                               experimental_flag=bool(p>=bundle['alert_cutoff']),target_age_days=f['target_age_days'],
                               selected_model=bundle['selected'],risk_model=bundle['risk_selection'])
            rows.append(row)
    result=pd.DataFrame(rows)
    result.to_csv(args.output,index=False)
    overview=[]
    for site,g in result.groupby('site'):
        eligible=g[g.status.eq('eligible')]
        flagged=eligible.loc[eligible.get('experimental_flag',pd.Series(False,index=eligible.index)).eq(True),'target']
        overview.append({'site':site,'eligible_targets':len(eligible),'unavailable_targets':len(g)-len(eligible),
                         'flagged_targets':';'.join(flagged),'note':'Correlated target flags; no combined safety score.'})
    pd.DataFrame(overview).to_csv(Path(args.output).with_name(Path(args.output).stem+'_site_overview.csv'),index=False)
    print(f'Saved {len(result)} site/target statuses; {(result.status=="eligible").sum()} eligible forecasts.')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('command',choices=['train','predict'])
    ap.add_argument('--bacteria',default=str(ROOT/'data/raw/MasterBactSurvey4_13_26.csv'))
    ap.add_argument('--chemistry',default=str(ROOT/'data/raw/MasterChemSurvey4_13_26.csv'))
    ap.add_argument('--snapshot-date',default='2026-04-13')
    ap.add_argument('--output-dir',default=str(ROOT/'results/multitarget'))
    ap.add_argument('--date');ap.add_argument('--output',default=str(ROOT/'results/multitarget/forecasts.csv'))
    args=ap.parse_args()
    if args.command=='train':train(args)
    else:
        if not args.date:ap.error('--date is required')
        predict(args)

if __name__=='__main__':main()
