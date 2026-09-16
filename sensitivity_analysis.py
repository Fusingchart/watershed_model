"""Descriptive sensitivity of frozen test predictions to unresolved source flags.

No records are corrected and no models or thresholds are retuned. Excluding a
flagged outcome does not remove possibly affected training data or predictors.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from multitarget_data import TARGETS, transform
from failure_audit import summarize

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/sensitivity'


def source_keys(source):
    name='MasterBactSurvey4_13_26.csv' if source=='bacteria' else 'MasterChemSurvey4_13_26.csv'
    raw=pd.read_csv(ROOT/'data/raw'/name,dtype=str).fillna('')
    raw['csv_line']=raw.index+2
    raw['site']=raw.gww_site_code_double
    raw['date']=pd.to_datetime(raw.sample_date_time,format='%m/%d/%Y %H:%M:%S.%f',errors='coerce').dt.normalize()
    return raw


def flagged_keys(checks, raw):
    """Any flagged replicate marks its aggregate site/date/target for sensitivity."""
    joined=checks.merge(raw[['csv_line','site','date']],on='csv_line',validate='many_to_one')
    return set(zip(joined.site,joined.date,joined.target))


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    audit=ROOT/'results/failure_audit'
    p=pd.read_csv(ROOT/'results/multitarget/heldout_predictions.csv',dtype={'site':str},parse_dates=['date','issue_date'])
    for target,spec in TARGETS.items():
        mask=p.target.eq(target)
        p.loc[mask,'error']=abs(transform(p.loc[mask,'actual'],spec)-transform(p.loc[mask,'predicted'],spec))
        p.loc[mask,'baseline_error']=abs(transform(p.loc[mask,'actual'],spec)-transform(p.loc[mask,'baseline_predicted'],spec))
    p['source_error']=abs(p.actual-p.predicted)
    identities=pd.read_csv(audit/'site_identity_audit.csv',dtype={'site':str})
    ambiguous=set(identities.loc[identities.waterbody_variants>1,'site'])
    p['ambiguous_site_label']=p.site.isin(ambiguous)
    b=source_keys('bacteria');c=source_keys('chemistry')
    bc=pd.read_csv(audit/'bacteria_formula_checks.csv')
    chemistry=pd.read_csv(audit/'chemistry_derived_checks.csv')
    major=flagged_keys(bc[bc.discrepancy_type.eq('requires_protocol_review')],b)|flagged_keys(chemistry[~chemistry.matches_candidate_formula],c)
    nonmatching=flagged_keys(bc[~bc.matches_candidate_formula],b)|flagged_keys(chemistry[~chemistry.matches_candidate_formula],c)
    keys=list(zip(p.site,p.date,p.target))
    p['formula_protocol_review']=[k in major for k in keys]
    p['any_formula_difference']=[k in nonmatching for k in keys]
    unknown_turbidity=set(zip(c.loc[c.turbidity_tube_or_meter.ne('Turbidity meter'),'site'],c.loc[c.turbidity_tube_or_meter.ne('Turbidity meter'),'date']))
    p['reported_turbidity_nonmeter_or_missing_method']=[t=='turbidity_reported' and (s,d) in unknown_turbidity for s,d,t in keys]
    # Missing formula checks are not confirmation that an outcome is correct.
    checked=flagged_keys(bc,b)|flagged_keys(chemistry,c)
    p['formula_checked']=[k in checked for k in keys]
    scenarios={
        'all_test_observations':pd.Series(True,index=p.index),
        'exclude_ambiguous_site_labels':~p.ambiguous_site_label,
        'exclude_protocol_formula_flags':~p.formula_protocol_review,
        'exclude_any_formula_difference':~p.any_formula_difference,
        'reported_turbidity_meter_only':~p.reported_turbidity_nonmeter_or_missing_method,
        'combined_conservative_subset':~(p.ambiguous_site_label|p.any_formula_difference|p.reported_turbidity_nonmeter_or_missing_method)
    }
    rows=[]
    for target,g in p.groupby('target'):
        for scenario,mask in scenarios.items():
            selected=g[mask.loc[g.index]]
            result=summarize(selected) if len(selected) else {'samples':0}
            rows.append({'target':target,'scenario':scenario,'original_samples':len(g),'excluded_samples':len(g)-len(selected),**result})
    result=pd.DataFrame(rows)
    result.to_csv(OUT/'scenario_results.csv',index=False)
    columns=['site','date','target','ambiguous_site_label','formula_protocol_review','any_formula_difference','reported_turbidity_nonmeter_or_missing_method','formula_checked']
    p[columns].to_csv(OUT/'observation_flags.csv',index=False)
    # Block-bootstrap comparisons remain exploratory and use fixed predictions.
    gains=[]
    for target,g in p.groupby('target'):
        for scenario in ['all_test_observations','combined_conservative_subset']:
            selected=g[scenarios[scenario].loc[g.index]]
            if not len(selected):continue
            grouped=selected.assign(gain=selected.baseline_error-selected.error).groupby('site').gain.agg(['sum','count'])
            rng=np.random.default_rng(42);idx=rng.integers(len(grouped),size=(1000,len(grouped)))
            estimates=grouped['sum'].to_numpy()[idx].sum(axis=1)/grouped['count'].to_numpy()[idx].sum(axis=1)
            gains.append({'target':target,'scenario':scenario,'sites':len(grouped),'mean_error_gain':float((selected.baseline_error-selected.error).mean()),'lower_95':float(np.quantile(estimates,.025)),'upper_95':float(np.quantile(estimates,.975))})
    pd.DataFrame(gains).to_csv(OUT/'site_bootstrap.csv',index=False)
    print(result[result.scenario.eq('combined_conservative_subset')][['target','samples','excluded_samples','improvement_percent','recall']].to_string(index=False))

if __name__=='__main__':run()
