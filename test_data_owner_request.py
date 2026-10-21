import unittest
import pandas as pd
from data_owner_request import site_conflicts, bacteria_rows, chemistry_rows

class DataOwnerRequestTests(unittest.TestCase):
    def test_only_multi_name_sites_listed_without_blank_names(self):
        sites=pd.DataFrame({'site':['1','2'],'rows':[5,6],'waterbody_variants':[1,3],'first_date':['a','a'],'last_date':['b','b'],'waterbodies':['X','; Pipers; Trib M']})
        out=site_conflicts(sites)
        self.assertEqual(out.site.tolist(),['2'])
        self.assertEqual(out.waterbodies.iloc[0],'Pipers; Trib M')
    def test_matching_rows_excluded(self):
        b=pd.DataFrame({'csv_line':[2,3],'target':['ecoli']*2,'reported':[1,2],'candidate_count_volume_formula':[1,3],'discrepancy_type':['match','requires_protocol_review']})
        self.assertEqual(bacteria_rows(b).csv_line.tolist(),[3])
        c=pd.DataFrame({'csv_line':[2,3],'target':['hardness']*2,'reported':[1,2],'candidate_formula':[1,3],'matches_candidate_formula':[True,False]})
        self.assertEqual(chemistry_rows(c).csv_line.tolist(),[3])
    def test_no_location_or_submitter_columns(self):
        sites=pd.DataFrame({'site':['2'],'rows':[6],'waterbody_variants':[2],'first_date':['a'],'last_date':['b'],'waterbodies':['A; B'],'location':['secret']})
        self.assertNotIn('location',site_conflicts(sites).columns)

if __name__=='__main__':unittest.main()
