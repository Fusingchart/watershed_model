import unittest
import pandas as pd
from prospective_evaluation import verdict, revisions, MIN_OBSERVATIONS, MIN_SITES

class ProspectiveTests(unittest.TestCase):
    def test_small_samples_are_never_judged(self):
        u={'mean_gain':1.,'site_bootstrap_95_interval':[.5,1.]}
        self.assertEqual(verdict(MIN_OBSERVATIONS-1,MIN_SITES,u),'insufficient_data')
        self.assertEqual(verdict(MIN_OBSERVATIONS,MIN_SITES-1,u),'insufficient_data')
    def test_confirmation_requires_interval_above_zero(self):
        n,s=MIN_OBSERVATIONS,MIN_SITES
        self.assertEqual(verdict(n,s,{'mean_gain':.2,'site_bootstrap_95_interval':[.01,.4]}),'confirmed')
        self.assertEqual(verdict(n,s,{'mean_gain':.2,'site_bootstrap_95_interval':[-.01,.4]}),'inconclusive')
        self.assertEqual(verdict(n,s,{'mean_gain':-.1,'site_bootstrap_95_interval':[-.3,.1]}),'not_confirmed')
    def test_revisions_ignore_new_samples_after_snapshot(self):
        d=lambda x:pd.to_datetime(x)
        old=pd.DataFrame({'site':['a','a','b'],'date':d(['2026-01-01','2026-02-01','2026-03-01']),'target':['ph']*3,'value':[7.,7.5,8.]})
        new=pd.DataFrame({'site':['a','a','c','a'],'date':d(['2026-01-01','2026-02-01','2026-03-01','2026-06-01']),'target':['ph']*4,'value':[7.,7.6,6.,7.]})
        self.assertEqual(revisions(old,new,'2026-04-13'),{'unchanged':1,'changed':1,'removed':1,'added':1})

if __name__=='__main__':unittest.main()
