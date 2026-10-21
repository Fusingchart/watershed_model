"""Regional rainfall and streamflow features known at forecast issue time."""
from pathlib import Path
import sys
import urllib.request
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
EXTERNAL = ROOT/'data/external'
# Sea-Tac, Paine Field, Sand Point, Boeing Field: sites have no coordinates, so rain is a regional mean.
STATIONS = ['USW00024233', 'USW00024222', 'USW00094290', 'USW00024234']
# Issaquah Creek is the nearest active USGS gauge with a complete 2015-2026 daily record.
GAUGE = '12121600'
RAIN_FILE, FLOW_FILE = EXTERNAL/'noaa_prcp.csv', EXTERNAL/f'usgs_{GAUGE}_q.rdb'
WEATHER_FEATURES = ['rain_1','rain_3','rain_7','rain_14','rain_30','days_since_rain5','flow_log','flow_7_log','flow_ratio_30']


def fetch(start='2015-01-01', end=None):
    end = end or str(pd.Timestamp.today().date())
    EXTERNAL.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve('https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries'
        f'&stations={",".join(STATIONS)}&dataTypes=PRCP&startDate={start}&endDate={end}&format=csv&units=metric', RAIN_FILE)
    urllib.request.urlretrieve('https://waterservices.usgs.gov/nwis/dv/?format=rdb'
        f'&sites={GAUGE}&parameterCd=00060&statCd=00003&startDT={start}&endDT={end}', FLOW_FILE)


def daily():
    rain = pd.read_csv(RAIN_FILE, parse_dates=['DATE']).groupby('DATE').PRCP.mean()
    flow = pd.read_csv(FLOW_FILE, sep='\t', comment='#').iloc[1:]
    flow = pd.Series(pd.to_numeric(flow.iloc[:,3], errors='coerce').to_numpy(), index=pd.to_datetime(flow.datetime))
    days = pd.date_range(min(rain.index.min(), flow.index.min()), max(rain.index.max(), flow.index.max()))
    return pd.DataFrame({'rain':rain.reindex(days), 'flow':flow.reindex(days)})


def features_at(table, cutoff):
    """Use only days on or before cutoff; missing days stay missing rather than becoming zero rain."""
    w = table.loc[:cutoff]
    if w.empty or cutoff not in w.index or w.rain.iloc[-30:].isna().any():
        return {k:np.nan for k in WEATHER_FEATURES}
    r, q = w.rain, w.flow
    wet = r[r >= 5].index
    f = {f'rain_{n}':float(r.iloc[-n:].sum()) for n in [1,3,7,14,30]}
    f['days_since_rain5'] = float(min((cutoff-wet[-1]).days, 60)) if len(wet) else 60.
    f['flow_log'] = float(np.log1p(q.iloc[-1]))
    f['flow_7_log'] = float(np.log1p(q.iloc[-7:].mean()))
    f['flow_ratio_30'] = float(q.iloc[-1]/q.iloc[-30:].median()) if q.iloc[-30:].median() > 0 else np.nan
    return f


def add_weather(d, table):
    """Issue-time features: data through the day before the forecast is issued."""
    cutoffs = (pd.to_datetime(d.issue_date) - pd.Timedelta(days=1)).dt.normalize()
    cache = {c:features_at(table, c) for c in cutoffs.unique()}
    return pd.concat([d.reset_index(drop=True), pd.DataFrame([cache[c] for c in cutoffs])], axis=1)


def oracle_rain(d, table):
    """Rain over the sample day and three days before. Unknown at issue time; diagnostic only."""
    return np.array([table.rain.loc[s-pd.Timedelta(days=3):s].sum(min_count=4) for s in pd.to_datetime(d.date)])


if __name__ == '__main__' and sys.argv[1:] == ['fetch']:
    fetch()
