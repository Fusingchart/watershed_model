"""Reproduce failure segmentation and source verification without altering trained models."""
from pathlib import Path
import json, hashlib, re
import numpy as np
import pandas as pd
from multitarget_data import TARGETS, transform, History, build_target_dataset

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/failure_audit'


def summarize(g):
    err=g.error.mean();base=g.baseline_error.mean();events=g.actual_tail_event.sum();flags=g.experimental_flag.sum()
    caught=((g.actual_tail_event==1)&g.experimental_flag).sum()
    return {'samples':len(g),'sites':g.site.nunique(),'MAE_transformed':err,'baseline_MAE_transformed':base,'improvement_percent':100*(base-err)/base if base else 0,
            'source_MAE':g.source_error.mean(),'source_bias':(g.predicted-g.actual).mean(),'events':events,'caught':caught,'missed':events-caught,
            'false_flags':flags-caught,'recall':caught/events if events else np.nan,'precision':caught/flags if flags else np.nan}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    base=ROOT/'results/multitarget'
    predictions=pd.read_csv(base/'heldout_predictions.csv',dtype={'site':str},parse_dates=['date','issue_date'])
    clean=pd.read_csv(base/'clean_measurements.csv',dtype={'site':str},parse_dates=['date'])
    assert not predictions.duplicated(['site','date','target']).any()
    check=predictions.merge(clean[['site','date','target','value']],on=['site','date','target'],validate='one_to_one')
    assert len(check)==len(predictions) and np.allclose(check.actual,check.value)
    reports=json.loads((base/'evaluation.json').read_text())['targets']
    p=predictions.copy()
    for target,spec in TARGETS.items():
        mask=p.target.eq(target)
        p.loc[mask,'error']=np.abs(transform(p.loc[mask,'actual'],spec)-transform(p.loc[mask,'predicted'],spec))
        p.loc[mask,'baseline_error']=np.abs(transform(p.loc[mask,'actual'],spec)-transform(p.loc[mask,'baseline_predicted'],spec))
    p['source_error']=abs(p.actual-p.predicted)
    p['season']=p.date.dt.month.map({12:'winter',1:'winter',2:'winter',3:'spring',4:'spring',5:'spring',6:'summer',7:'summer',8:'summer',9:'autumn',10:'autumn',11:'autumn'})
    p['year']=p.date.dt.year
    p['history_age']=pd.cut(p.target_age_days,[0,35,60,120],labels=['10–35 days','36–60 days','61–120 days'])
    p['event_group']=np.where(p.actual_tail_event.eq(1),'historical_tail_event','ordinary_result')
    history=History(clean);seen=set()
    for target in p.target.unique():
        ds=build_target_dataset(clean,history,target)
        fitted=(ds.date<pd.Timestamp('2023-12-22'))|ds.date.between('2024-01-01','2024-12-21')
        seen.update((site,target) for site in ds.loc[fitted,'site'].unique())
    p['site_training_status']=['seen_in_model_fit' if (s,t) in seen else 'unseen_in_model_fit' for s,t in zip(p.site,p.target)]
    p['extreme_group']='within_training_5th_95th_percentiles'
    for target in p.target.unique():
        ds=build_target_dataset(clean,history,target)
        training=ds.loc[ds.date<pd.Timestamp('2023-12-22'),'actual']
        low,high=training.quantile([.05,.95]);mask=p.target.eq(target)
        p.loc[mask & ((p.actual<low)|(p.actual>high)),'extreme_group']='outside_training_5th_95th_percentiles'
    for dimension in ['site','season','year','history_age','event_group','extreme_group','site_training_status']:
        rows=[]
        for (target,segment),g in p.groupby(['target',dimension],observed=True):
            rows.append({'target':target,'segment':str(segment),**summarize(g),'small_sample':len(g)<20})
        pd.DataFrame(rows).to_csv(OUT/f'errors_by_{dimension}.csv',index=False)
    summary=[]
    for target,g in p.groupby('target'):
        r=reports[target]['2025'];m=summarize(g)
        assert np.isclose(m['source_MAE'],r['test']['source_MAE'])
        assert np.isclose(m['recall'],r['risk']['recall'])
        summary.append({'target':target,**m})
    pd.DataFrame(summary).to_csv(OUT/'verified_metrics.csv',index=False)
    p.sort_values('error',ascending=False).groupby('target',sort=False).head(10).to_csv(OUT/'largest_errors.csv',index=False)
    p.loc[p.actual_tail_event.eq(1)&~p.experimental_flag].sort_values('error',ascending=False).to_csv(OUT/'missed_events.csv',index=False)
    raw_tables=[];verification=[];comparisons=[];formula_rows=[];timing=[]
    review_map={'Average_e_coli':None,'water_temperature':'Review_Water_temperature','ph_standard_units':'Review_PH','conductivity':'Review_conductivity','Nitrate':'Review_Nitrate','Phosphate':'Review_Phosphate','Turbidity':'Review_Turbidity','TSS':'Review_TSS'}
    for source,name in [('bacteria','MasterBactSurvey4_13_26.csv'),('chemistry','MasterChemSurvey4_13_26.csv')]:
        path=ROOT/'data/raw'/name;raw=pd.read_csv(path,dtype=str).fillna('')
        raw['source']=source;raw['csv_line']=raw.index+2
        raw['date']=pd.to_datetime(raw.sample_date_time,format='%m/%d/%Y %H:%M:%S.%f',errors='coerce')
        extra=[c for c in raw if c.startswith('Unnamed:')]
        structurally_ok=(~raw[extra].ne('').any(axis=1))&raw.gww_site_code_double.str.fullmatch(r'\d{7,12}')&raw.CreationDate.str.match(r'^\d{1,2}/\d{1,2}/\d{4} ')&raw.date.notna()&(raw.date.dt.normalize()<=pd.Timestamp('2026-04-13'))
        good=raw[structurally_ok].copy();raw_tables.append(good)
        created=pd.to_datetime(good.CreationDate,format='%m/%d/%Y %H:%M:%S.%f',errors='coerce')
        timing.append({'source':source,'rows':len(good),'midnight_sample_timestamps':int(good.date.dt.hour.eq(0).mul(good.date.dt.minute.eq(0)).sum()),'median_creation_lag_days':float((created-good.date).dt.total_seconds().median()/86400),'creation_dates':int(created.dt.date.nunique())})
        for target,spec in TARGETS.items():
            if spec['source']!=source:continue
            values=pd.to_numeric(good[spec['column']],errors='coerce')
            verification.append({'target':target,'structurally_valid_rows':len(good),'numeric_values':int(values.notna().sum()),'missing_or_nonnumeric':int(values.isna().sum()),'minimum':values.min(),'maximum':values.max(),'zero_values':int(values.eq(0).sum()),'most_common_value':values.mode().iloc[0] if values.notna().any() else None,'most_common_count':int(values.value_counts().iloc[0]) if values.notna().any() else 0})
            review=review_map.get(spec['column'])
            if review and review in good:
                rv=pd.to_numeric(good[review],errors='coerce');comparable=values.notna()&rv.notna()
                different=comparable&~np.isclose(values,rv,rtol=1e-4,atol=.01,equal_nan=True)
                for i in good.index[different]:comparisons.append({'source':source,'csv_line':int(good.loc[i,'csv_line']),'target':target,'original':values.loc[i],'reviewed':rv.loc[i]})
        if source=='bacteria':
            volume=pd.to_numeric(good.sample_volume,errors='coerce')
            for kind,field,counts in [('ecoli','Average_e_coli',[f'sample_{i}_e_coli_count' for i in [1,2,3]]),('other_coliform','Average_coliform',[f'sample_{i}_other_coliform_if_test' for i in [1,2,3]])]:
                counts=good[counts].apply(pd.to_numeric,errors='coerce');reported=pd.to_numeric(good[field],errors='coerce')
                expected=counts.mean(axis=1)*100/volume
                complete=counts.notna().all(axis=1)&reported.notna()&volume.gt(0)
                match=np.isclose(reported,expected,rtol=.001,atol=.02)
                for i in good.index[complete]:formula_rows.append({'csv_line':int(good.loc[i,'csv_line']),'target':kind,'reported':reported.loc[i],'candidate_count_volume_formula':expected.loc[i],'matches_candidate_formula':bool(match[good.index.get_loc(i)]),'discrepancy_type':('match' if match[good.index.get_loc(i)] else 'within_half_unit_rounding' if abs(reported.loc[i]-expected.loc[i])<=.5 else 'possible_zero_floor_to_one' if reported.loc[i]==1 and expected.loc[i]==0 else 'requires_protocol_review')})
        else:
            good['turbidity_numeric']=pd.to_numeric(good.Turbidity,errors='coerce')
            good.groupby('turbidity_tube_or_meter').agg(rows=('globalid','size'),numeric_values=('turbidity_numeric','count'),value_equal_8=('turbidity_numeric',lambda s:s.eq(8).sum())).reset_index().to_csv(OUT/'turbidity_methods.csv',index=False)
    allraw=pd.concat(raw_tables,ignore_index=True)
    # Normalize spelling only for candidate detection; never merge identifiers automatically.
    normal=lambda s:re.sub(r'[^a-z0-9]','',str(s).lower())
    allraw['waterbody_key']=allraw.waterbody.map(normal);allraw['location_key']=allraw.Site_Location.map(normal)
    identities=[]
    for site,g in allraw.groupby('gww_site_code_double'):
        identities.append({'site':site,'rows':len(g),'waterbody_variants':g.waterbody_key.nunique(),'location_variants':g.loc[g.location_key.ne(''),'location_key'].nunique(),'first_date':str(g.date.min().date()),'last_date':str(g.date.max().date()),'waterbodies':'; '.join(sorted(g.waterbody.unique()))})
    pd.DataFrame(identities).to_csv(OUT/'site_identity_audit.csv',index=False)
    aliases=[]
    for (waterbody,location),g in allraw[allraw.location_key.ne('')].groupby(['waterbody_key','location_key']):
        codes=sorted(g.gww_site_code_double.unique())
        if len(codes)>1:aliases.append({'waterbody':g.waterbody.iloc[0],'site_codes':';'.join(codes),'site_count':len(codes),'rows':len(g),'note':'Same normalized waterbody and location text; candidate only. Location text omitted for privacy.'})
    pd.DataFrame(aliases,columns=['waterbody','site_codes','site_count','rows','note']).to_csv(OUT/'candidate_site_aliases.csv',index=False)
    pd.DataFrame(verification).to_csv(OUT/'measurement_verification.csv',index=False)
    pd.DataFrame(comparisons,columns=['source','csv_line','target','original','reviewed']).to_csv(OUT/'review_value_disagreements.csv',index=False)
    pd.DataFrame(formula_rows).to_csv(OUT/'bacteria_formula_checks.csv',index=False)
    pd.DataFrame(timing).to_csv(OUT/'timestamp_verification.csv',index=False)
    manifest={'prediction_rows_verified':len(p),'targets_verified':len(summary),'source_checksums':{q.name:hashlib.sha256(q.read_bytes()).hexdigest() for q in (ROOT/'data/raw').glob('*.csv')},'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
