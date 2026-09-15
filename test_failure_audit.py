import unittest
import numpy as np
import pandas as pd
from failure_audit import summarize

class FailureAuditTests(unittest.TestCase):
    def test_error_and_event_denominators(self):
        d=pd.DataFrame({'site':['a','a','b','b'],'error':[1.,3.,2.,2.],'baseline_error':[4.]*4,'source_error':[1.,3.,2.,2.],
                        'actual':[3.,5.,2.,2.],'predicted':[2.,2.,4.,4.],'actual_tail_event':[1,1,0,0],
                        'experimental_flag':[True,False,True,False]})
        result=summarize(d)
        self.assertEqual(result['improvement_percent'],50)
        self.assertEqual(result['caught'],1);self.assertEqual(result['missed'],1)
        self.assertEqual(result['false_flags'],1);self.assertEqual(result['recall'],.5)
        self.assertEqual(result['precision'],.5)
    def test_no_events_or_flags_is_undefined_not_perfect_performance(self):
        d=pd.DataFrame({'site':['a'],'error':[1.],'baseline_error':[0.],'source_error':[1.],
                        'actual':[1.],'predicted':[2.],'actual_tail_event':[0],'experimental_flag':[False]})
        result=summarize(d)
        self.assertTrue(np.isnan(result['improvement_percent']));self.assertTrue(np.isnan(result['recall']));self.assertTrue(np.isnan(result['precision']))

if __name__=='__main__':unittest.main()
