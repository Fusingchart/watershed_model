"""Assemble the data-owner verification request from saved failure-audit evidence."""
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent
AUDIT=ROOT/'results/failure_audit'
OUT=ROOT/'results/data_owner_request'
BACT='MasterBactSurvey4_13_26.csv';CHEM='MasterChemSurvey4_13_26.csv'


def site_conflicts(sites):
    s=sites[sites.waterbody_variants>1].copy()
    s['waterbodies']=s.waterbodies.str.split('; ').map(lambda v:'; '.join(x for x in v if x.strip()))
    return s[['site','rows','first_date','last_date','waterbodies']].assign(same_physical_site='',authoritative_name='',notes='')


def bacteria_rows(checks):
    b=checks[checks.discrepancy_type.ne('match')].copy()
    return b.assign(source_file=BACT)[['source_file','csv_line','target','reported','candidate_count_volume_formula','discrepancy_type']].assign(correct_value='',notes='')


def chemistry_rows(checks):
    c=checks[~checks.matches_candidate_formula.astype(bool)].copy()
    return c.assign(source_file=CHEM)[['source_file','csv_line','target','reported','candidate_formula']].assign(correct_value='',notes='')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    sites=site_conflicts(pd.read_csv(AUDIT/'site_identity_audit.csv',dtype={'site':str}))
    bact=bacteria_rows(pd.read_csv(AUDIT/'bacteria_formula_checks.csv'))
    chem=chemistry_rows(pd.read_csv(AUDIT/'chemistry_derived_checks.csv'))
    turb=pd.read_csv(AUDIT/'turbidity_methods.csv').fillna({'turbidity_tube_or_meter':'(no method recorded)'})
    times=pd.read_csv(AUDIT/'timestamp_verification.csv')
    sites.to_csv(OUT/'site_conflicts.csv',index=False)
    bact.to_csv(OUT/'bacteria_rows_to_review.csv',index=False)
    chem.to_csv(OUT/'chemistry_rows_to_review.csv',index=False)
    counts=bact.groupby(['target','discrepancy_type']).size()
    lines=['# Data verification request','',
        f'These questions come from an audit of the April 13, 2026 exports (`{BACT}`, `{CHEM}`). The forecasting models have not been changed; the answers decide which results can be trusted. Line numbers refer to the original export files, counting the header as line 1. Blank columns in each CSV are for your answers.','',
        '## 1. Site identity (`site_conflicts.csv`)','',
        f'{len(sites)} site codes appear with more than one waterbody name. For each code: is it one physical site throughout its history? If so, what is its authoritative name? A site registry with coordinates and any code changes would answer this fully.','',
        '| Site code | Samples | Names used |','| --- | ---: | --- |',
        *[f'| {r.site} | {r.rows} | {r.waterbodies} |' for r in sites.itertuples()],'',
        '## 2. Bacteria calculations (`bacteria_rows_to_review.csv`)','',
        'Most reported averages equal `mean(three replicate counts) × 100 / sample volume`. Please confirm that formula and its units, then check the rows that differ:','',
        *[f'- {t.replace("_"," ")}: {n} rows, {k.replace("_"," ")}' for (t,k),n in counts.items()],'',
        'Also: is there a reporting floor (zero reported as one), a rounding rule, or a cap on countable colonies?','',
        '## 3. Chemistry calculations (`chemistry_rows_to_review.csv`)','',
        f'Dissolved oxygen averages two replicates; alkalinity is drop count × 5; hardness is drop count × 10. {len(chem)} rows do not match. Which value is correct for each?','',
        '## 4. Turbidity','','| Method recorded | Rows | Numeric values | Values equal to 8 |','| --- | ---: | ---: | ---: |',
        *[f'| {r.turbidity_tube_or_meter} | {r.rows} | {r.numeric_values} | {r.value_equal_8} |' for r in turb.itertuples()],'',
        'Does a tube reading of 8 mean "8 or lower" (a reporting limit)? What method was used where none is recorded?','',
        '## 5. Timing','',
        *[f'- {r.source}: {r.midnight_sample_timestamps} of {r.rows} sample times are exactly 00:00; record creation dates fall on {r.creation_dates} calendar date(s).' for r in times.itertuples()],'',
        'Creation dates look like a bulk import, so they cannot show when results became available. Please answer: (a) Are 00:00 times date-only? (b) What timezone are the times in? (c) How many days after collection are bacteria and chemistry results usually available? The models currently assume three days.','',
        '## 6. Newer data','','An export in the same format covering April 2026 to today would allow current forecasts and a fresh test period.','']
    (OUT/'REQUEST.md').write_text('\n'.join(lines))


if __name__=='__main__':main()
