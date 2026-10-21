"""Local web interface for the frozen multi-target forecasts. Binds to localhost only: source data contains personal details."""
from pathlib import Path
import argparse
import json
import joblib
import numpy as np
import pandas as pd
from flask import Flask, jsonify, request, send_from_directory
from multitarget_data import ROOT, TARGETS, MAX_AGE_DAYS, LEAD_DAYS, History, load_data, inverse
from multitarget_model import BASELINES, forecast, risk_probability

FROZEN = ROOT/'results/multitarget'
UI = ROOT/'ui'
# Units are only given where the configured range makes them unambiguous; bacteria units await data-owner confirmation.
UNITS = {'water_temperature':'°C','dissolved_oxygen':'mg/L','oxygen_saturation':'%','ph':'','ecoli':'per 100 mL','other_coliform':'per 100 mL'}
STATUS_TEXT = {'eligible':'Forecast available',
               'fewer_than_two_available_target_samples':'Fewer than two earlier samples were available at issue time',
               'target_history_older_than_120_days':f'Latest usable sample is more than {MAX_AGE_DAYS} days before the visit',
               'insufficient_training_history':'Not enough history to train a forecast for this measurement',
               'date_overlaps_training_information':'Visit date overlaps the data the model was trained on'}
NOTES = {'water_temperature':'Strongest evidence; gains survive data-quality exclusions.',
         'dissolved_oxygen':'Strong evidence; low-oxygen events are harder.',
         'ecoli':'Gain depends on which sites are included; site names need confirmation. No risk flags.',
         'turbidity_reported':'Tube readings cluster at 8; reporting convention unconfirmed.',
         'salinity':'Units and large values need verification.'}


class Forecaster:
    def __init__(self, bacteria, chemistry, snapshot):
        self.models = joblib.load(FROZEN/'models.joblib')
        evaluation = json.loads((FROZEN/'evaluation.json').read_text())['targets']
        self.baseline = {t:v['2025'].get('selected_baseline') for t,v in evaluation.items()}
        self.evaluation = evaluation
        self.data,_,_,_ = load_data(bacteria, chemistry, snapshot)
        self.history = History(self.data)
        self.snapshot = snapshot
        self.names = self.data.groupby('site').waterbody.agg(lambda s:s.str.strip().mode().iloc[0] if s.str.strip().ne('').any() else '')
        self.heldout = pd.read_csv(FROZEN/'heldout_predictions.csv', dtype={'site':str}, parse_dates=['date'])

    def rows(self, date, history=None, sites=None):
        history = history or self.history; date = pd.Timestamp(date).normalize()
        out, pending = [], {}
        for site in sites or history.sites:
            for target, spec in TARGETS.items():
                row = {'site':site, 'target':target}
                bundle = self.models.get(target)
                if bundle is None:
                    row['status'] = 'insufficient_training_history'
                elif date <= pd.Timestamp(bundle['training_end'])+pd.Timedelta(days=10):
                    row['status'] = 'date_overlaps_training_information'
                else:
                    f, row['status'] = history.features(site, target, date)
                    if f is not None: pending.setdefault(target, []).append((row, f))
                out.append(row)
        # One model call per measurement; per-row calls made the full table take ~10 s.
        for target, items in pending.items():
            spec, bundle = TARGETS[target], self.models[target]
            X = pd.DataFrame([f for _, f in items]); p = risk_probability(bundle, X)
            predicted = inverse(forecast(bundle, X), spec)
            base = inverse(forecast({'selected':self.baseline[target], 'median':bundle['median']}, X), spec)
            last = inverse(X.last_value.to_numpy(), spec)
            for i, (row, f) in enumerate(items):
                row.update(predicted=float(predicted[i]), baseline=float(base[i]), last_value=float(last[i]), age_days=int(f['target_age_days']),
                           flag=bool(p[i] >= bundle['alert_cutoff']), uses_baseline=bundle['selected'] in BASELINES)
        for row in out: row['reason'] = STATUS_TEXT.get(row['status'], row['status'])
        return out


def create_app(f):
    app = Flask(__name__, static_folder=None)

    @app.get('/')
    def index():
        return send_from_directory(UI, 'index.html')

    @app.get('/ui/<path:name>')
    def assets(name):
        return send_from_directory(UI, name)

    @app.get('/api/meta')
    def meta():
        counts = f.data.groupby('site').size()
        last = f.data.date.max()
        targets = []
        for t, spec in TARGETS.items():
            r = f.evaluation[t]['2025']; bundle = f.models.get(t)
            targets.append({'id':t, 'label':spec['label'], 'unit':UNITS.get(t), 'log':spec['transform']=='log1p', 'status':r['status'], 'model':r.get('selected'),
                            'baseline':r.get('selected_baseline'), 'improvement':r.get('improvement_percent'),
                            'interval':r.get('uncertainty',{}).get('site_bootstrap_95_interval'), 'test':r['counts'].get('test'),
                            'source_MAE':r.get('test',{}).get('source_MAE'), 'flags':bool(bundle and bundle.get('classifier') is not None),
                            'note':NOTES.get(t,''), 'caution':spec.get('caution','')})
        return jsonify(snapshot=f.snapshot, last_sample=str(last.date()), lead_days=LEAD_DAYS,
                       latest_useful_date=str((last+pd.Timedelta(days=MAX_AGE_DAYS)).date()),
                       sites=[{'id':s, 'name':f.names.get(s,''), 'samples':int(counts[s])} for s in f.history.sites], targets=targets)

    @app.get('/api/forecast')
    def forecast_all():
        try: date = pd.Timestamp(request.args['date'])
        except (KeyError, ValueError): return jsonify(error='Give a date as YYYY-MM-DD'), 400
        return jsonify(date=str(date.date()), issue_date=str((date-pd.Timedelta(days=LEAD_DAYS)).date()), rows=f.rows(date))

    @app.get('/api/site/<site>')
    def site(site):
        target = request.args.get('target', 'water_temperature')
        if site not in f.history.sites: return jsonify(error='Unknown site'), 404
        obs = f.data[(f.data.site==site)&(f.data.target==target)]
        held = f.heldout[(f.heldout.site==site)&(f.heldout.target==target)]
        return jsonify(site=site, name=f.names.get(site,''), target=target,
                       observations=[{'date':str(d.date()), 'value':float(v)} for d, v in zip(obs.date, obs.value)],
                       tested=[{'date':str(r.date.date()), 'actual':r.actual, 'predicted':r.predicted, 'baseline':r.baseline_predicted} for r in held.itertuples()])

    @app.post('/api/whatif')
    def whatif():
        body = request.get_json(force=True, silent=True) or {}
        site = str(body.get('site','')); added = []
        try:
            date = pd.Timestamp(body['date']).normalize()
            for m in body.get('measurements', []):
                t, v, d = m['target'], float(m['value']), pd.Timestamp(m['sample_date']).normalize()
                spec = TARGETS[t]
                if not np.isfinite(v) or v < spec.get('min',-np.inf) or v > spec.get('max',np.inf): raise ValueError(f'{spec["label"]} value is outside the allowed range')
                added.append({'site':site, 'date':d, 'target':t, 'value':v, 'waterbody':'', 'replicate_rows':1})
        except (KeyError, ValueError, TypeError) as e:
            return jsonify(error=str(e) or 'Invalid input'), 400
        own = f.data[f.data.site==site]
        if own.empty: return jsonify(error='Unknown site'), 404
        # Hypothetical samples replace any real sample for the same site/date/measurement.
        extra = pd.DataFrame(added)
        if len(extra): own = own.merge(extra[['date','target']], how='left', indicator=True).query('_merge=="left_only"').drop(columns='_merge')
        scenario = History(pd.concat([own, extra], ignore_index=True)) if len(extra) else History(own)
        return jsonify(date=str(date.date()), before=f.rows(date, sites=[site]), after=f.rows(date, history=scenario, sites=[site]))

    return app


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bacteria', default=str(ROOT/'data/raw/MasterBactSurvey4_13_26.csv'))
    ap.add_argument('--chemistry', default=str(ROOT/'data/raw/MasterChemSurvey4_13_26.csv'))
    ap.add_argument('--snapshot-date', default='2026-04-13')
    ap.add_argument('--port', type=int, default=5057)
    args = ap.parse_args()
    print('Loading data and frozen models...', flush=True)
    app = create_app(Forecaster(args.bacteria, args.chemistry, args.snapshot_date))
    print(f'Open http://127.0.0.1:{args.port}', flush=True)
    app.run(host='127.0.0.1', port=args.port)


if __name__ == '__main__':main()
