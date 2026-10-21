import unittest
import pandas as pd
from multitarget_data import History
from multitarget_data import TARGETS
from app import Forecaster, create_app, limit_check

def forecaster():
    f=object.__new__(Forecaster)
    f.data=pd.DataFrame({'site':['a','a'],'date':pd.to_datetime(['2026-01-01','2026-02-01']),'target':['ph','ph'],'value':[7.,7.2],'waterbody':['X','X'],'replicate_rows':[1,1]})
    f.history=History(f.data);f.models={};f.baseline={};f.names=pd.Series({'a':'X'})
    f.heldout=pd.DataFrame(columns=['site','target','date','actual','predicted','baseline_predicted'])
    f.limits={};f.margin={};f.limits_source=''
    return f

class AppTests(unittest.TestCase):
    def setUp(self):
        self.client=create_app(forecaster()).test_client()
    def post(self,**body):
        return self.client.post('/api/whatif',json={'site':'a','date':'2026-04-20',**body})
    def test_out_of_range_value_rejected(self):
        r=self.post(measurements=[{'target':'ph','sample_date':'2026-03-01','value':20}])
        self.assertEqual(r.status_code,400);self.assertIn('outside',r.get_json()['error'])
    def test_unknown_measurement_and_site(self):
        self.assertEqual(self.post(measurements=[{'target':'lead','sample_date':'2026-03-01','value':1}]).status_code,400)
        self.assertEqual(self.client.post('/api/whatif',json={'site':'zz','date':'2026-04-20'}).status_code,404)
        self.assertEqual(self.client.get('/api/site/zz').status_code,404)
    def test_whatif_returns_before_and_after_for_every_target(self):
        d=self.post(measurements=[{'target':'ph','sample_date':'2026-02-01','value':8}]).get_json()
        self.assertEqual(len(d['before']),len(d['after']))
        self.assertTrue(all(r['status']=='insufficient_training_history' for r in d['after']))
    def test_limit_levels(self):
        temp,oxy,ecoli=TARGETS['water_temperature'],TARGETS['dissolved_oxygen'],TARGETS['ecoli']
        self.assertEqual(limit_check(16.1,{'max':16},temp,1.5)[0],'red')
        self.assertEqual(limit_check(14.6,{'max':16},temp,1.5)[0],'yellow')
        self.assertIsNone(limit_check(14.4,{'max':16},temp,1.5)[0])
        self.assertEqual(limit_check(9.4,{'min':9.5},oxy,.7)[0],'red')
        self.assertEqual(limit_check(10.1,{'min':9.5},oxy,.7)[0],'yellow')
    def test_skewed_limits_use_log_margin(self):
        e=TARGETS['ecoli']
        self.assertEqual(limit_check(100,{'max':320},e,1.6)[0],'yellow')
        self.assertIsNone(limit_check(50,{'max':320},e,1.6)[0])
    def test_both_sided_limit(self):
        self.assertEqual(limit_check(8.6,{'min':6.5,'max':8.5},TARGETS['ph'],.26)[0],'red')
        self.assertEqual(limit_check(6.4,{'min':6.5,'max':8.5},TARGETS['ph'],.26)[0],'red')
        self.assertIsNone(limit_check(7.5,{'min':6.5,'max':8.5},TARGETS['ph'],.26)[0])
    def test_forecast_requires_date(self):
        self.assertEqual(self.client.get('/api/forecast?date=soon').status_code,400)

if __name__=='__main__':unittest.main()
