"""Retrospective E. coli forecasting prototype. See README.md for assumptions."""
from pathlib import Path
import argparse, json, hashlib, platform
import numpy as np
import pandas as pd
import sklearn, joblib
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.metrics import mean_absolute_error, mean_squared_error, roc_auc_score, average_precision_score, brier_score_loss, precision_score, recall_score

ROOT=Path(__file__).resolve().parent
SNAPSHOT=pd.Timestamp('2026-04-13')
# Issue forecast 7 days before planned sample. Allow 3 days for prior results.
LEAD=7
LAG=3
CHEM={'water_temperature':(0,40),'ph_standard_units':(0,14),'Average_dissolved_oxygen_dis':(0,30),'conductivity':(0,10000),'Nitrate':(0,100),'Phosphate':(0,100)}

def read_clean(path,kind,snapshot=SNAPSHOT):
    raw=pd.read_csv(path,dtype=str).fillna('')
    d=raw.copy(); reasons=pd.Series('',index=d.index)
    def reject(mask,reason):
        reasons.loc[mask]+=reason+';'
    extra=[c for c in d if c.startswith('Unnamed:')]
    reject(d[extra].ne('').any(axis=1),'nonempty_extra_columns')
    reject(~d.gww_site_code_double.str.fullmatch(r'\d{7,12}'),'invalid_site_identifier')
    reject(~d.CreationDate.str.match(r'^\d{1,2}/\d{1,2}/\d{4} '),'shifted_or_invalid_metadata')
    d['date']=pd.to_datetime(d.sample_date_time,format='%m/%d/%Y %H:%M:%S.%f',errors='coerce').dt.normalize()
    reject(d.date.isna(),'invalid_date');reject(d.date>snapshot,'sample_after_export_date')
    d['site']=d.gww_site_code_double
    if kind=='bacteria':
        d['ecoli']=pd.to_numeric(d.Average_e_coli,errors='coerce')
        reject(d.ecoli.isna() | (d.ecoli<0),'missing_or_negative_target')
        fields={'air_temperature':(-20,50),'water_temperature':(0,40)}
    else:fields=CHEM
    for c,(lo,hi) in fields.items():
        d[c]=pd.to_numeric(d[c],errors='coerce');d.loc[~d[c].between(lo,hi),c]=np.nan
    excluded=pd.DataFrame({'file':Path(path).name,'csv_line':d.index+2,'globalid':d.globalid,'reason':reasons})
    good=d.loc[reasons.eq('')].copy()
    # Aggregate replicate visits per site/day; prevent duplicated outcomes across splits.
    numeric=['ecoli','air_temperature','water_temperature'] if kind=='bacteria' else list(CHEM)
    agg={c:'median' for c in numeric};agg.update({'watershed':'first','waterbody':'first'})
    grouped=good.groupby(['site','date'],as_index=False).agg(agg)
    audit={'input_rows':len(raw),'excluded_rows':int(reasons.ne('').sum()),'retained_rows':len(good),'site_days':len(grouped),'duplicate_site_days_collapsed':len(good)-len(grouped),'sites':grouped.site.nunique(),'date_min':str(grouped.date.min().date()),'date_max':str(grouped.date.max().date())}
    return grouped,excluded.loc[reasons.ne('')],audit

def feature_row(site,date,b,c):
    issue=date-pd.Timedelta(days=LEAD);cutoff=issue-pd.Timedelta(days=LAG)
    bh=b[(b.site==site)&(b.date<=cutoff)].sort_values('date')
    ch=c[(c.site==site)&(c.date<=cutoff)].sort_values('date')
    if len(bh)<2:return None
    last=bh.iloc[-1];age=(date-last.date).days
    if age>120:return None
    r={'site':str(site),'month_sin':np.sin(2*np.pi*date.month/12),'month_cos':np.cos(2*np.pi*date.month/12),'history_count':len(bh),'bacteria_age_days':age,
       'last_log_ecoli':np.log1p(last.ecoli),'mean_last3_log_ecoli':np.log1p(bh.ecoli.tail(3)).mean(),'median_history_log_ecoli':np.log1p(bh.ecoli).median(),
       'last_air_temp':last.air_temperature,'last_water_temp':last.water_temperature,'trend_log_ecoli':np.log1p(bh.ecoli.iloc[-1])-np.log1p(bh.ecoli.iloc[-2])}
    for name in CHEM:r['chem_'+name]=np.nan
    r['chem_age_days']=np.nan
    if len(ch) and (date-ch.iloc[-1].date).days<=120:
        r['chem_age_days']=(date-ch.iloc[-1].date).days
        for name in CHEM:r['chem_'+name]=ch.iloc[-1][name]
    assert bh.date.max()<=cutoff
    return r

def make_dataset(b,c):
    rows=[]
    for x in b.itertuples():
        f=feature_row(x.site,x.date,b,c)
        if f is not None:rows.append({**f,'date':x.date,'issue_date':x.date-pd.Timedelta(days=LEAD),'actual_ecoli':x.ecoli,'waterbody':x.waterbody})
    return pd.DataFrame(rows)

def pipeline(X,estimator):
    nums=[c for c in X if c!='site']
    pre=ColumnTransformer([('site',OneHotEncoder(handle_unknown='ignore',sparse_output=False),['site']),('numeric',make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),StandardScaler()),nums)])
    return make_pipeline(pre,estimator)

def reg_metrics(y,p):
    return {'log_MAE':float(mean_absolute_error(np.log1p(y),p)),'log_RMSE':float(mean_squared_error(np.log1p(y),p)**.5),'raw_MAE':float(mean_absolute_error(y,np.maximum(0,np.expm1(p))))}

def cls_metrics(y,p,t=.5):
    pred=p>=t
    return {'ROC_AUC':float(roc_auc_score(y,p)) if len(set(y))>1 else None,'average_precision':float(average_precision_score(y,p)),'Brier':float(brier_score_loss(y,p)),'precision':float(precision_score(y,pred,zero_division=0)),'recall':float(recall_score(y,pred,zero_division=0)),'alerts':int(pred.sum()),'missed_elevated':int(((y==1)&~pred).sum()),'false_alerts':int(((y==0)&pred).sum())}

def train(args):
    b,be,ba=read_clean(args.bacteria,'bacteria',pd.Timestamp(args.snapshot_date));c,ce,ca=read_clean(args.chemistry,'chemistry',pd.Timestamp(args.snapshot_date))
    b.to_csv(ROOT/'clean_bacteria.csv',index=False);c.to_csv(ROOT/'clean_chemistry.csv',index=False)
    pd.concat([be,ce]).to_csv(ROOT/'excluded_records.csv',index=False)
    d=make_dataset(b,c)
    # Boundary embargo: all training outcomes precede first validation/test issue dates by the assumed result lag.
    tr=d.date<pd.Timestamp('2023-12-22');va=d.date.between('2024-01-01','2024-12-21');te=d.date>=pd.Timestamp('2025-01-01')
    cols=[x for x in d if x not in ['date','issue_date','actual_ecoli','waterbody']]
    X=d[cols];y=np.log1p(d.actual_ecoli)
    threshold=float(d.loc[tr,'actual_ecoli'].quantile(.75));z=(d.actual_ecoli>threshold).astype(int)
    regressors={'ridge':Ridge(alpha=30),'forest':RandomForestRegressor(n_estimators=250,min_samples_leaf=12,max_features=.8,random_state=42,n_jobs=2)}
    classifiers={'logistic':LogisticRegression(C=.1,max_iter=2000),'forest':RandomForestClassifier(n_estimators=250,min_samples_leaf=15,max_features=.8,random_state=42,n_jobs=2)}
    validation={'regression':{},'classification':{}};rm={};cm={}
    for name,est in regressors.items():
        m=pipeline(X,est).fit(X[tr],y[tr]);rm[name]=m
        validation['regression'][name]=reg_metrics(d.loc[va,'actual_ecoli'],m.predict(X[va]))
    for name,est in classifiers.items():
        m=pipeline(X,est).fit(X[tr],z[tr]);cm[name]=m
        validation['classification'][name]=cls_metrics(z[va],m.predict_proba(X[va])[:,1])
    best_r=min(rm,key=lambda n:validation['regression'][n]['log_MAE'])
    best_c=min(cm,key=lambda n:validation['classification'][n]['Brier'])
    # Compare chemistry ablation on validation only.
    no_chem=[k for k in cols if not k.startswith('chem_')]
    m=pipeline(X[no_chem],Ridge(alpha=30)).fit(X.loc[tr,no_chem],y[tr])
    validation['regression']['ridge_without_chemistry']=reg_metrics(d.loc[va,'actual_ecoli'],m.predict(X.loc[va,no_chem]))
    if validation['regression']['ridge_without_chemistry']['log_MAE']<validation['regression'][best_r]['log_MAE']:
        best_r='ridge_without_chemistry';rcols=no_chem;reg=m
    else:rcols=cols;reg=rm[best_r]
    # Select the highest cutoff reaching 75% validation recall; never tune on test outcomes.
    vp=cm[best_c].predict_proba(X[va])[:,1]
    candidates=np.unique(np.r_[0.,vp])
    alert_cutoff=float(max(t for t in candidates if recall_score(z[va],vp>=t)>=.75))
    validation['chosen_alert_cutoff']=alert_cutoff
    validation['chosen_alert_metrics']=cls_metrics(z[va],vp,alert_cutoff)
    fitmask=tr|va
    reg.fit(X.loc[fitmask,rcols],y[fitmask]);clf=cm[best_c].fit(X[fitmask],z[fitmask])
    rp=reg.predict(X.loc[te,rcols]);cp=clf.predict_proba(X[te])[:,1]
    baseline_global=np.full(te.sum(),y[fitmask].median())
    baseline_prob=np.full(te.sum(),z[fitmask].mean())
    test={'model_regression':reg_metrics(d.loc[te,'actual_ecoli'],rp),'last_observation':reg_metrics(d.loc[te,'actual_ecoli'],X.loc[te,'last_log_ecoli']),'site_history_median':reg_metrics(d.loc[te,'actual_ecoli'],X.loc[te,'median_history_log_ecoli']),'global_median':reg_metrics(d.loc[te,'actual_ecoli'],baseline_global),'model_classifier':cls_metrics(z[te],cp),'sensitive_alert_policy':cls_metrics(z[te],cp,alert_cutoff),'constant_prevalence':cls_metrics(z[te],baseline_prob)}
    out=d.loc[te,['site','waterbody','date','issue_date','actual_ecoli','bacteria_age_days']].copy();out['predicted_ecoli']=np.maximum(0,np.expm1(rp));out['elevated_probability']=cp;out['actual_elevated']=z[te];out['experimental_alert']=cp>=alert_cutoff
    out.to_csv(ROOT/'heldout_predictions.csv',index=False)
    # Paired bootstrap over sites, to preserve within-site dependence.
    rng=np.random.default_rng(42);err=np.abs(y[te].to_numpy()-rp);base=np.abs(y[te].to_numpy()-X.loc[te,'median_history_log_ecoli'].to_numpy());sites=out.site.to_numpy();unique=np.unique(sites)
    diffs=[]
    for _ in range(1000):
        idx=np.concatenate([np.flatnonzero(sites==s) for s in rng.choice(unique,len(unique),replace=True)])
        diffs.append(float((base[idx]-err[idx]).mean()))
    improvement={'mean_log_MAE_gain_over_site_median':float((base-err).mean()),'site_bootstrap_95_percent_interval':np.quantile(diffs,[.025,.975]).tolist()}
    global_gain=np.abs(y[te].to_numpy()-baseline_global)-err
    rng=np.random.default_rng(12);global_boot=[]
    for _ in range(1000):
        idx=np.concatenate([np.flatnonzero(sites==s) for s in rng.choice(unique,len(unique),replace=True)])
        global_boot.append(float(global_gain[idx].mean()))
    improvement['gain_over_global_median']=float(global_gain.mean())
    improvement['global_median_gain_site_bootstrap_95_percent_interval']=np.quantile(global_boot,[.025,.975]).tolist()
    metrics={'audit':{'bacteria':ba,'chemistry':ca},'eligible_forecasts':len(d),'split_counts':{'train':int(tr.sum()),'validation':int(va.sum()),'test':int(te.sum()),'boundary_embargo':int((~(tr|va|te)).sum())},'elevated_threshold_strictly_greater_than':threshold,'alert_probability_cutoff':alert_cutoff,'selected_regressor':best_r,'selected_classifier':best_c,'validation':validation,'test':test,'uncertainty':improvement,'test_elevated_prevalence':float(z[te].mean()),'test_sites':int(out.site.nunique()),'test_chemistry_available_fraction':float(X.loc[te,'chem_age_days'].notna().mean()),'assumed_lead_days':LEAD,'assumed_results_lag_days':LAG}
    (ROOT/'metrics.json').write_text(json.dumps(metrics,indent=2))
    joblib.dump({'regressor':reg,'classifier':clf,'regression_features':rcols,'features':cols,'threshold':threshold,'alert_cutoff':alert_cutoff,'training_end':str(d.loc[fitmask,'date'].max().date())},ROOT/'model.joblib')
    manifest={'inputs':{str(Path(p).name):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in [args.bacteria,args.chemistry]},'python':platform.python_version(),'sklearn':sklearn.__version__,'numpy':np.__version__,'pandas':pd.__version__,'joblib':joblib.__version__}
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    d.to_csv(ROOT/'model_dataset.csv',index=False)
    print(json.dumps(metrics,indent=2))

def predict(args):
    bundle=joblib.load(ROOT/'model.joblib')
    b,_,_=read_clean(args.bacteria,'bacteria',pd.Timestamp(args.snapshot_date));c,_,_=read_clean(args.chemistry,'chemistry',pd.Timestamp(args.snapshot_date))
    date=pd.Timestamp(args.date).normalize()
    if date<=pd.Timestamp(bundle['training_end'])+pd.Timedelta(days=LEAD+LAG):
        raise ValueError('Prediction date must follow model training end plus lead and result lag.')
    rows=[]
    for site in sorted(b.site.unique()):
        r=feature_row(site,date,b,c)
        if r is not None:rows.append(r)
    if not rows:raise ValueError('No eligible sites: need two prior samples and latest sample within 120 days. Refresh the data.')
    X=pd.DataFrame(rows);p=bundle['classifier'].predict_proba(X[bundle['features']])[:,1]
    out=X[['site','history_count','bacteria_age_days']].copy();out['planned_sample_date']=date;out['issue_date']=date-pd.Timedelta(days=LEAD);out['predicted_ecoli']=np.maximum(0,np.expm1(bundle['regressor'].predict(X[bundle['regression_features']])));out['experimental_elevated_probability']=p;out['experimental_alert']=p>=bundle['alert_cutoff']
    out.sort_values('experimental_elevated_probability',ascending=False).to_csv(args.output,index=False)
    print(f'Saved {len(out)} forecasts to {args.output}')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['train','predict']);ap.add_argument('--bacteria',required=True);ap.add_argument('--chemistry',required=True);ap.add_argument('--date');ap.add_argument('--snapshot-date',default='2026-04-13',help='Export date; update when supplying refreshed CSVs');ap.add_argument('--output',default=str(ROOT/'forecasts.csv'));args=ap.parse_args()
    if args.command=='train':train(args)
    else:
        if not args.date:ap.error('--date is required for predict')
        predict(args)
