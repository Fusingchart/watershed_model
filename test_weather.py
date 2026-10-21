import unittest
import numpy as np
import pandas as pd
from weather import features_at, add_weather, oracle_rain

def table(days=60, rain=0., flow=10.):
    idx=pd.date_range('2024-01-01',periods=days)
    return pd.DataFrame({'rain':np.full(days,rain),'flow':np.full(days,flow)},index=idx)

class WeatherTests(unittest.TestCase):
    def test_issue_time_features_ignore_later_days(self):
        t=table();before=features_at(t,pd.Timestamp('2024-02-10'))
        t.loc['2024-02-11':,'rain']=100.;t.loc['2024-02-11':,'flow']=1000.
        self.assertEqual(features_at(t,pd.Timestamp('2024-02-10')),before)
    def test_cutoff_is_day_before_issue(self):
        t=table();t.loc['2024-02-10','rain']=20.
        d=pd.DataFrame({'issue_date':pd.to_datetime(['2024-02-10','2024-02-11']),'date':pd.to_datetime(['2024-02-17','2024-02-18'])})
        self.assertEqual(add_weather(d,t).rain_1.tolist(),[0.,20.])
    def test_missing_rain_is_not_treated_as_dry(self):
        t=table();t.loc['2024-02-05','rain']=np.nan
        self.assertTrue(np.isnan(features_at(t,pd.Timestamp('2024-02-10'))['rain_30']))
        d=pd.DataFrame({'date':pd.to_datetime(['2024-02-06'])})
        self.assertTrue(np.isnan(oracle_rain(d,t)[0]))

if __name__=='__main__':unittest.main()
