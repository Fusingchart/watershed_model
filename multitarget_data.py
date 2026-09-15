"""Auditable multi-measurement ingestion and strictly historical feature generation."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
TARGETS = json.loads((ROOT / 'targets.json').read_text())
LEAD_DAYS = 7
RESULT_DELAY_DAYS = 3
MAX_AGE_DAYS = 120


def transform(values, spec):
    a = np.asarray(values, dtype=float)
    return np.log1p(a) if spec['transform'] == 'log1p' else a


def inverse(values, spec):
    a = np.asarray(values, dtype=float)
    result = np.expm1(a) if spec['transform'] == 'log1p' else a
    return np.clip(result, spec.get('min', -np.inf), spec.get('max', np.inf))


def load_data(bacteria_path, chemistry_path, snapshot_date):
    """Keep valid measurements even when other targets on the same row are missing."""
    tables, excluded, cell_issues, audit = [], [], [], {}
    for source, path in [('bacteria', bacteria_path), ('chemistry', chemistry_path)]:
        raw = pd.read_csv(path, dtype=str).fillna('')
        reasons = pd.Series('', index=raw.index)
        def reject(mask, reason):
            reasons.loc[mask] += reason + ';'
        extra = [c for c in raw if c.startswith('Unnamed:')]
        reject(raw[extra].ne('').any(axis=1), 'nonempty_extra_columns')
        reject(~raw.gww_site_code_double.str.fullmatch(r'\d{7,12}'), 'invalid_site_identifier')
        reject(~raw.CreationDate.str.match(r'^\d{1,2}/\d{1,2}/\d{4} '), 'invalid_or_shifted_metadata')
        date = pd.to_datetime(raw.sample_date_time, format='%m/%d/%Y %H:%M:%S.%f', errors='coerce').dt.normalize()
        reject(date.isna(), 'invalid_date')
        reject(date > pd.Timestamp(snapshot_date), 'sample_after_snapshot')
        good = reasons.eq('')
        excluded.append(pd.DataFrame({'source': source, 'csv_line': raw.index + 2, 'globalid': raw.globalid, 'reason': reasons}).loc[~good])
        audit[source] = {'input_rows': len(raw), 'structurally_excluded_rows': int((~good).sum()), 'retained_rows': int(good.sum())}
        for target, spec in TARGETS.items():
            if spec['source'] != source:
                continue
            text = raw[spec['column']].str.strip()
            numeric = pd.to_numeric(text, errors='coerce')
            bad = (text.ne('') & (~np.isfinite(numeric) | (numeric < spec.get('min', -np.inf)) | (numeric > spec.get('max', np.inf)))) & good
            cell_issues.append(pd.DataFrame({'source': source, 'csv_line': raw.index + 2, 'target': target, 'value': text, 'reason': 'non_numeric_or_outside_configured_range'}).loc[bad])
            ok = good & np.isfinite(numeric) & ~bad
            t = pd.DataFrame({'site': raw.gww_site_code_double, 'date': date, 'target': target, 'value': numeric, 'waterbody': raw.waterbody}).loc[ok]
            # Site/date/target is the prediction unit. Do not inflate counts with replicates.
            t = t.groupby(['site', 'date', 'target'], as_index=False).agg(value=('value', 'median'), waterbody=('waterbody', 'first'), replicate_rows=('value', 'size'))
            tables.append(t)
    data = pd.concat(tables, ignore_index=True).sort_values(['site', 'target', 'date']).reset_index(drop=True)
    return data, pd.concat(excluded, ignore_index=True), pd.concat(cell_issues, ignore_index=True), audit


class History:
    """Index each series once; search availability cutoff without seeing future rows."""
    def __init__(self, data):
        self.series = {}
        self.sites = sorted(data.site.unique())
        for (site, target), g in data.groupby(['site', 'target']):
            g = g.sort_values('date')
            self.series[(site, target)] = (g.date.to_numpy(dtype='datetime64[ns]'), g.value.to_numpy(dtype=float))

    def available(self, site, target, cutoff):
        dates, values = self.series.get((site, target), (np.array([], dtype='datetime64[ns]'), np.array([], dtype=float)))
        end = np.searchsorted(dates, np.datetime64(cutoff), side='right')
        return dates[:end], values[:end]

    def features(self, site, target, date):
        date = pd.Timestamp(date)
        cutoff = date - pd.Timedelta(days=LEAD_DAYS + RESULT_DELAY_DAYS)
        dates, values = self.available(site, target, cutoff)
        if len(values) < 2:
            return None, 'fewer_than_two_available_target_samples'
        age = (date - pd.Timestamp(dates[-1])).days
        if age > MAX_AGE_DAYS:
            return None, 'target_history_older_than_120_days'
        spec = TARGETS[target]
        v = transform(values, spec)
        # Month is known for a scheduled visit, not the future weather or measurements.
        same_month = pd.DatetimeIndex(dates).month == date.month
        same = v[same_month]
        seasonal = (same.sum() + 3 * np.median(v)) / (len(same) + 3)
        f = {'site': str(site), 'month_sin': np.sin(2*np.pi*date.month/12), 'month_cos': np.cos(2*np.pi*date.month/12),
             'target_age_days': age, 'history_count': len(v), 'last_value': v[-1], 'last3_mean': v[-3:].mean(),
             'history_median': np.median(v), 'seasonal_site': seasonal, 'last_change': v[-1]-v[-2]}
        for other, other_spec in TARGETS.items():
            ds, vs = self.available(site, other, cutoff)
            other_age = (date-pd.Timestamp(ds[-1])).days if len(ds) else np.nan
            usable = len(ds) and other_age <= MAX_AGE_DAYS
            f['prior_'+other] = float(transform(vs[-1], other_spec)) if usable else np.nan
            f['age_'+other] = other_age if usable else np.nan
        return f, 'eligible'


def build_target_dataset(data, history, target):
    rows = []
    for row in data.loc[data.target.eq(target)].itertuples():
        features, _ = history.features(row.site, target, row.date)
        if features is not None:
            rows.append({**features, 'date': row.date, 'issue_date': row.date-pd.Timedelta(days=LEAD_DAYS), 'actual': row.value})
    return pd.DataFrame(rows)
