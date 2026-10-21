import unittest
import numpy as np
import pandas as pd
from data_checks import oxygen_capacity, robust_outliers, oxygen_checks, flag_measurements

def series(target, values, site='a'):
    return pd.DataFrame({'site':site,'date':pd.date_range('2024-01-01',periods=len(values),freq='14D'),'target':target,'value':values})

class DataCheckTests(unittest.TestCase):
    def test_oxygen_capacity_matches_published_values(self):
        self.assertAlmostEqual(float(oxygen_capacity(0)),14.65,places=1)
        self.assertAlmostEqual(float(oxygen_capacity(20)),9.09,delta=.1)
    def test_steady_site_is_not_flagged_and_spike_is(self):
        rng=np.random.default_rng(0);v=list(10+rng.normal(0,.5,30))
        self.assertEqual(robust_outliers(series('water_temperature',v)),[])
        flags=robust_outliers(series('water_temperature',v[:-1]+[20.]))
        self.assertEqual(len(flags),1);self.assertIn('high',flags[0][4])
    def test_flat_coarse_readings_do_not_flag_every_change(self):
        v=[2.]*25+[5.,5.,10.]
        self.assertEqual([f for f in robust_outliers(series('turbidity_legacy',v)) if f[3]=='red'],[])
        self.assertLessEqual(len(robust_outliers(series('turbidity_legacy',v))),3)
    def test_supersaturated_oxygen_is_red(self):
        d=pd.concat([series('water_temperature',[20.]),series('dissolved_oxygen',[15.])])
        self.assertEqual([f[3] for f in oxygen_checks(d)],['red'])
    def test_one_row_per_measurement_with_worst_level(self):
        d=pd.concat([series('water_temperature',[20.]),series('dissolved_oxygen',[15.]),series('oxygen_saturation',[200.])])
        f=flag_measurements(d)
        self.assertFalse(f.duplicated(['site','date','target']).any())
        self.assertEqual(f.set_index('target').level.to_dict(),{'dissolved_oxygen':'red','oxygen_saturation':'yellow'})

if __name__=='__main__':unittest.main()
