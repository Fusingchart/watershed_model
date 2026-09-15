"""Checks forecasting information boundaries and malformed input handling."""
import unittest,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from model import feature_row,read_clean,CHEM

class ForecastTests(unittest.TestCase):
    def setUp(self):
        self.b=pd.DataFrame({'site':['5303305']*4,'date':pd.to_datetime(['2024-01-01','2024-02-01','2024-03-05','2024-03-20']),'ecoli':[10,20,9000,9999],'air_temperature':[5]*4,'water_temperature':[6]*4})
        self.c=pd.DataFrame({'site':['5303305']*2,'date':pd.to_datetime(['2024-02-01','2024-03-05']),**{k:[7,999] for k in CHEM}})
    def test_future_and_not_yet_available_results_cannot_change_features(self):
        date=pd.Timestamp('2024-03-10')
        a=feature_row('5303305',date,self.b,self.c)
        b=self.b.copy();b.loc[b.date>pd.Timestamp('2024-02-29'),'ecoli']=123456
        c=self.c.copy();c.loc[c.date>pd.Timestamp('2024-02-29'),list(CHEM)]=123456
        other=feature_row('5303305',date,b,c)
        pd.testing.assert_series_equal(pd.Series(a),pd.Series(other))
        self.assertAlmostEqual(a['last_log_ecoli'],np.log1p(20))
        self.assertEqual(a['chem_water_temperature'],7)
    def test_sparse_and_stale_histories_are_rejected(self):
        self.assertIsNone(feature_row('unknown',pd.Timestamp('2024-03-10'),self.b,self.c))
        self.assertIsNone(feature_row('5303305',pd.Timestamp('2025-01-01'),self.b,self.c))
        self.assertIsNone(feature_row('5303305',pd.Timestamp('2024-01-20'),self.b,self.c))
    def test_shifted_rows_are_quarantined(self):
        rows=pd.DataFrame({'gww_site_code_double':['5303305','SnoKingGISaccount'],'CreationDate':['4/13/2026 22:00:00.000']*2,'sample_date_time':['1/1/2024 0:00:00.000']*2,'globalid':['a','b'],'Average_e_coli':['10','20'],'air_temperature':['5']*2,'water_temperature':['6']*2,'watershed':['test']*2,'waterbody':['test']*2,'Unnamed: 48':['','5303305']})
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.csv';rows.to_csv(p,index=False)
            good,excluded,audit=read_clean(p,'bacteria')
        self.assertEqual(len(good),1);self.assertEqual(len(excluded),1)
        self.assertIn('nonempty_extra_columns',excluded.reason.iloc[0])

if __name__=='__main__':unittest.main()
