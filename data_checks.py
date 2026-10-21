"""Flag individual measurements that look wrong (red) or unusual enough to check (yellow).

Flags are for review only; no value is changed or removed from modelling.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from multitarget_data import ROOT, TARGETS, transform, inverse

AUDIT = ROOT/'results/failure_audit'
CONFLICT_SITES = {'5303387','5303391','5303392','5303393','5303394','5303395','5303396','5303397','5303398'}
MIN_SITE_HISTORY = 8
RED_Z, YELLOW_Z = 6., 4.


def oxygen_capacity(temp_c):
    """Dissolved oxygen (mg/L) that fresh water holds at sea level (Benson-Krause polynomial fit)."""
    t = np.asarray(temp_c, dtype=float)
    return 14.652 - 0.41022*t + 0.007991*t**2 - 0.000077774*t**3


def robust_outliers(data):
    """Score each value against its own site's history and against all values for that measurement."""
    rows = []
    for target, g in data.groupby('target'):
        v = transform(g.value, TARGETS[target]); g = g.assign(v=v)
        gmed = np.median(v); gscale = 1.4826*np.median(np.abs(v-gmed)) or float(np.std(v)) or 1.
        low, high = np.quantile(v, [.001, .999])
        for _, s in g.groupby('site'):
            if len(s) < MIN_SITE_HISTORY: continue
            med = np.median(s.v); mad = 1.4826*np.median(np.abs(s.v-med))
            # Coarse readings (e.g. turbidity tubes stuck on one value) have zero MAD; fall back to the spread itself.
            scale = max(mad if mad > 0 else np.std(s.v), .25*gscale)
            z = (s.v-med)/scale
            usual = f'{float(inverse(np.array([med]), TARGETS[target])[0]):.3g}'
            for (i, r), zi in zip(s.iterrows(), z):
                if abs(zi) >= RED_Z and (r.v < low or r.v > high):
                    rows.append((r.site, r.date, target, 'red', f'Extremely {"high" if zi > 0 else "low"}: far from this site’s usual {usual} and outside 99.8% of all recorded values'))
                elif abs(zi) >= YELLOW_Z:
                    rows.append((r.site, r.date, target, 'yellow', f'Unusually {"high" if zi > 0 else "low"} for this site (usual {usual})'))
    return rows


def oxygen_checks(data):
    wide = data.pivot_table(index=['site','date'], columns='target', values='value')
    rows = []
    if not {'water_temperature','dissolved_oxygen'} <= set(wide): return rows
    w = wide.dropna(subset=['water_temperature','dissolved_oxygen'])
    w = w[w.water_temperature.between(0, 35)]
    ratio = w.dissolved_oxygen/oxygen_capacity(w.water_temperature)
    for (site, date), r in ratio.items():
        if r > 1.5: rows.append((site, date, 'dissolved_oxygen', 'red', f'Oxygen is {r:.0%} of what water at this temperature can hold'))
        elif r > 1.2: rows.append((site, date, 'dissolved_oxygen', 'yellow', f'Oxygen is {r:.0%} of what water at this temperature can hold'))
    if 'oxygen_saturation' in w:
        s = w.dropna(subset=['oxygen_saturation'])
        gap = s.oxygen_saturation - 100*s.dissolved_oxygen/oxygen_capacity(s.water_temperature)
        for (site, date), d in gap.items():
            if abs(d) > 20: rows.append((site, date, 'oxygen_saturation', 'yellow', f'Reported saturation differs by {abs(d):.0f} points from oxygen and temperature'))
    return rows


def source_rows(raw_bacteria, raw_chemistry):
    """Map saved audit findings (by export line) to site/date/measurement."""
    def keyed(path):
        raw = pd.read_csv(path, dtype=str).fillna('')
        return raw.assign(csv_line=raw.index+2, site=raw.gww_site_code_double,
                          date=pd.to_datetime(raw.sample_date_time, format='%m/%d/%Y %H:%M:%S.%f', errors='coerce').dt.normalize())
    bact, chem = keyed(raw_bacteria), keyed(raw_chemistry)
    rows = []
    reason = {'requires_protocol_review':('red','Reported average does not match replicate counts × 100 / volume'),
              'within_half_unit_rounding':('yellow','Reported average differs from replicate counts by rounding'),
              'possible_zero_floor_to_one':('yellow','Zero count may have been recorded as one')}
    b = pd.read_csv(AUDIT/'bacteria_formula_checks.csv')
    b = b[b.discrepancy_type.isin(reason)].merge(bact[['csv_line','site','date']], on='csv_line')
    rows += [(r.site, r.date, r.target, *reason[r.discrepancy_type]) for r in b.itertuples()]
    c = pd.read_csv(AUDIT/'chemistry_derived_checks.csv')
    c = c[~c.matches_candidate_formula.astype(bool)].merge(chem[['csv_line','site','date']], on='csv_line')
    rows += [(r.site, r.date, r.target, 'red', f'Reported {r.reported:g} does not match its replicates or drop count ({r.candidate_formula:g})') for r in c.itertuples()]
    tube = chem[chem.turbidity_tube_or_meter.str.strip().eq('Turbidity tube') & (pd.to_numeric(chem.Turbidity, errors='coerce') == 8)]
    rows += [(s, d, 'turbidity_reported', 'yellow', 'Tube reading of exactly 8 may be a reporting limit, not a measurement') for s, d in zip(tube.site, tube.date)]
    return rows


def flag_measurements(data, raw_bacteria=None, raw_chemistry=None):
    rows = robust_outliers(data) + oxygen_checks(data)
    if raw_bacteria and raw_chemistry: rows += source_rows(raw_bacteria, raw_chemistry)
    # Site-name conflicts are a property of the site, shown beside its name rather than on every row.
    flags = pd.DataFrame(rows, columns=['site','date','target','level','reason'])
    # Keep only flags that point at a measurement in the cleaned data.
    flags = flags.merge(data[['site','date','target','value']], on=['site','date','target'])
    order = flags.level.map({'red':0,'yellow':1})
    flags = flags.assign(order=order).sort_values(['order','date'], ascending=[True,False])
    return (flags.groupby(['site','date','target'], sort=False)
                 .agg(level=('level','first'), value=('value','first'), reasons=('reason', lambda r:list(dict.fromkeys(r))))
                 .reset_index())
