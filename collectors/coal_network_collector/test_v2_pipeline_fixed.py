import sqlite3,unittest
from pathlib import Path
from status_policy_v2 import CANDIDATE_STATUSES,FORMAL_STATUSES
from path_check_v2 import build as path_report
from build_edges_v3 import build as build_edges
from coal_price_import_v2 import import_csv
ROOT=Path(__file__).parent
class V2PipelineTests(unittest.TestCase):
    def test_status_policy_and_real_database(self):
        db=sqlite3.connect(ROOT/'coal_network.db'); self.assertIn('AI_APPROVED',CANDIDATE_STATUSES); self.assertNotIn('AI_APPROVED',FORMAL_STATUSES); report=path_report(db); self.assertGreater(report['candidate_complete_paths'],0); self.assertEqual(report['formal_complete_paths'],0); self.assertEqual(db.execute('pragma foreign_key_check').fetchall(),[]); self.assertEqual(build_edges(db),0); db.close()
    def test_contract_v2_coal_csv_import(self):
        db=sqlite3.connect(':memory:'); db.executescript((ROOT/'complete_schema.sql').read_text(encoding='utf-8')); db.execute("insert into network_registry values('coal_power_v1','x','1','DRAFT','x','2099','now')"); self.assertEqual(import_csv(db,ROOT/'testdata_cctd.csv'),3); self.assertEqual(db.execute('select count(1) from metric_values').fetchone()[0],3); self.assertEqual(db.execute('pragma foreign_key_check').fetchall(),[]); db.close()
if __name__=='__main__': unittest.main()
