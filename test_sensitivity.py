import unittest
import pandas as pd
from sensitivity_analysis import flagged_keys

class SensitivityTests(unittest.TestCase):
    def test_any_flagged_replicate_marks_one_aggregate(self):
        raw=pd.DataFrame({'csv_line':[2,3,4],'site':['a','a','b'],'date':pd.to_datetime(['2025-01-01']*3)})
        checks=pd.DataFrame({'csv_line':[2,3],'target':['ecoli','ecoli']})
        self.assertEqual(flagged_keys(checks,raw),{('a',pd.Timestamp('2025-01-01'),'ecoli')})
    def test_target_specific_flags_do_not_cross_measurements(self):
        raw=pd.DataFrame({'csv_line':[2],'site':['a'],'date':pd.to_datetime(['2025-01-01'])})
        keys=flagged_keys(pd.DataFrame({'csv_line':[2],'target':['ecoli']}),raw)
        self.assertNotIn(('a',pd.Timestamp('2025-01-01'),'water_temperature'),keys)
    def test_non_unique_source_rows_fail_join(self):
        raw=pd.DataFrame({'csv_line':[2,2],'site':['a','b'],'date':pd.to_datetime(['2025-01-01']*2)})
        with self.assertRaises(pd.errors.MergeError):
            flagged_keys(pd.DataFrame({'csv_line':[2],'target':['ecoli']}),raw)

if __name__=='__main__':unittest.main()
