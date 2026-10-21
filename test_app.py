import unittest
import pandas as pd
from multitarget_data import History
from app import Forecaster, create_app

def forecaster():
    f=object.__new__(Forecaster)
    f.data=pd.DataFrame({'site':['a','a'],'date':pd.to_datetime(['2026-01-01','2026-02-01']),'target':['ph','ph'],'value':[7.,7.2],'waterbody':['X','X'],'replicate_rows':[1,1]})
    f.history=History(f.data);f.models={};f.baseline={};f.names=pd.Series({'a':'X'})
    f.heldout=pd.DataFrame(columns=['site','target','date','actual','predicted','baseline_predicted'])
    f.flags=pd.DataFrame({'site':['a'],'date':pd.to_datetime(['2026-02-01']),'target':['ph'],'value':[7.2],'level':['red'],'reasons':[['Extreme']]})
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
    def test_checks_and_site_flags_are_served(self):
        self.assertEqual(self.client.get('/api/checks').get_json()['rows'][0]['level'],'red')
        flags=self.client.get('/api/site/a?target=ph').get_json()['flags']
        self.assertEqual([f['date'] for f in flags],['2026-02-01'])
    def test_forecast_requires_date(self):
        self.assertEqual(self.client.get('/api/forecast?date=soon').status_code,400)

if __name__=='__main__':unittest.main()
