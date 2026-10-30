import csv,sqlite3,tempfile,unittest
from pathlib import Path
from coal_price_import import import_csv
class CoalPriceImportTests(unittest.TestCase):
    def test_import(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'x.csv'; path.write_text('date,price_5500,price_5000,price_4500,source_url\n2026-09-05,738,650,560,https://example.test/cctd\n',encoding='utf-8')
            db=sqlite3.connect(':memory:'); db.executescript(Path(__file__).with_name('schema.sql').read_text(encoding='utf-8')); db.execute("insert into network_registry values('coal_power_v1','x','1','DRAFT','x','2099','now')")
            self.assertEqual(import_csv(db,path),3); self.assertEqual(db.execute("select count(*) from metric_values").fetchone()[0],3)
if __name__=='__main__': unittest.main()
