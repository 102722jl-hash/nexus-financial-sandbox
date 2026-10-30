import sqlite3,unittest
from pathlib import Path
from status_policy_v2 import CANDIDATE_STATUSES,FORMAL_STATUSES
from path_check_v2 import build as path_report
from build_edges_v3 import build as build_edges

ROOT=Path(__file__).parent
class AiCandidatePolicyTests(unittest.TestCase):
    def setUp(self): self.db=sqlite3.connect(ROOT/'coal_network.db')
    def tearDown(self): self.db.close()
    def test_ai_approved_is_candidate_not_formal(self):
        self.assertIn('AI_APPROVED',CANDIDATE_STATUSES)
        self.assertNotIn('AI_APPROVED',FORMAL_STATUSES)
    def test_candidate_paths_exist(self):
        report=path_report(self.db)
        self.assertGreater(report['candidate_complete_paths'],0)
        self.assertEqual(report['formal_complete_paths'],0)
    def test_cutoff_is_real(self):
        cutoff=self.db.execute("select data_cutoff from network_registry where network_id='coal_power_v1'").fetchone()[0]
        self.assertEqual(cutoff,'2026-09-05')
    def test_foreign_keys(self): self.assertEqual(self.db.execute('pragma foreign_key_check').fetchall(),[])
    def test_edge_build_is_idempotent(self): self.assertEqual(build_edges(self.db),0)
if __name__=='__main__': unittest.main()
