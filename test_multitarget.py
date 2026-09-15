"""Tests that protect temporal validity and independent target availability."""
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from multitarget_data import TARGETS, History, load_data, inverse, transform
from multitarget_model import risk_labels, forecast, evaluate_fold


class MultiTargetTests(unittest.TestCase):
    def fixture(self):
        return pd.DataFrame([
            {'site':'5303305','date':pd.Timestamp(date),'target':target,'value':value,'waterbody':'Test creek','replicate_rows':1}
            for target in ['ecoli','water_temperature','dissolved_oxygen']
            for date,value in [('2024-01-01',5),('2024-02-01',10),('2024-03-05',20),('2024-04-01',30)]
        ])

    def test_no_target_or_cross_target_future_leakage(self):
        data=self.fixture();planned=pd.Timestamp('2024-03-10')
        before,_=History(data).features('5303305','ecoli',planned)
        data.loc[data.date>pd.Timestamp('2024-02-29'),'value']=99999
        after,_=History(data).features('5303305','ecoli',planned)
        pd.testing.assert_series_equal(pd.Series(before),pd.Series(after))
        self.assertAlmostEqual(before['last_value'],np.log1p(10))
        self.assertEqual(before['prior_water_temperature'],10)

    def test_target_history_not_bacteria_history_controls_eligibility(self):
        data=self.fixture();data=data[data.target!='ecoli']
        history=History(data)
        self.assertIsNotNone(history.features('5303305','water_temperature','2024-03-10')[0])
        self.assertIsNone(history.features('5303305','ecoli','2024-03-10')[0])
        self.assertIsNone(history.features('5303305','water_temperature','2025-01-01')[0])

    def test_cutoff_includes_only_results_available_at_issue(self):
        data=self.fixture();history=History(data)
        before,_=history.features('5303305','ecoli','2024-03-14')
        after,_=history.features('5303305','ecoli','2024-03-15')
        self.assertEqual(before['history_count'],2)
        self.assertEqual(after['history_count'],3)

    def test_directional_tail_definitions(self):
        np.testing.assert_array_equal(risk_labels([1,5,10],{'lower':3,'upper':np.inf}),[1,0,0])
        np.testing.assert_array_equal(risk_labels([1,5,10],{'lower':-np.inf,'upper':7}),[0,0,1])
        np.testing.assert_array_equal(risk_labels([1,5,10],{'lower':3,'upper':7}),[1,0,1])

    def test_missing_ecoli_does_not_remove_valid_coliform(self):
        common={'globalid':'a','gww_site_code_double':'5303305','CreationDate':'4/13/2026 20:00:00.000',
                'sample_date_time':'1/1/2024 0:00:00.000','waterbody':'Test creek','Unnamed: 99':''}
        bacteria=pd.DataFrame([{**common,'Average_e_coli':'','Average_coliform':'12'},
                               {**common,'globalid':'b','Average_e_coli':'4','Average_coliform':'16'}])
        chemistry=pd.DataFrame([{**common,**{s['column']:'7' for s in TARGETS.values() if s['source']=='chemistry'}}])
        chemistry.loc[0,'ph_standard_units']='24'
        with tempfile.TemporaryDirectory() as folder:
            b=Path(folder)/'b.csv';c=Path(folder)/'c.csv'
            bacteria.to_csv(b,index=False);chemistry.to_csv(c,index=False)
            data,excluded,cells,audit=load_data(b,c,'2026-04-13')
        coliform=data[data.target=='other_coliform'].iloc[0]
        self.assertEqual(coliform.value,14);self.assertEqual(coliform.replicate_rows,2)
        self.assertEqual(data[data.target=='ecoli'].value.iloc[0],4)
        self.assertTrue(data[data.target=='ph'].empty)
        self.assertIn('ph',cells.target.to_list());self.assertTrue(excluded.empty)

    def test_sparse_target_cannot_train(self):
        d=pd.DataFrame({'date':pd.to_datetime(['2023-01-01','2024-01-01','2025-01-01']),'site':['x']*3})
        result,bundle,pred=evaluate_fold(d,'ph',2025,final=True)
        self.assertEqual(result['status'],'insufficient_history');self.assertIsNone(bundle)

    def test_transform_roundtrip_and_baseline(self):
        for spec in TARGETS.values():
            np.testing.assert_allclose(inverse(transform([1,3,7],spec),spec),[1,3,7])
        X=pd.DataFrame({'last_value':[1,2],'site':['a','b']})
        np.testing.assert_array_equal(forecast({'selected':'last_observation'},X),[1,2])
        np.testing.assert_array_equal(forecast({'selected':'global_median','median':3},X),[3,3])

if __name__=='__main__':unittest.main()
