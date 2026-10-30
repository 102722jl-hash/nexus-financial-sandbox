import sqlite3
import unittest
from pathlib import Path

from ai_judge_v3 import run as ai_review
from build_edges_v4 import build as build_edges
from build_nodes_v3 import build as build_nodes
from calculated_metrics_v3 import run as calculate
from deep_report_metrics_v3 import is_full_periodic_report, report_metadata, run as extract

ROOT = Path(__file__).parent
SOURCE = ROOT / "coal_network.db"
REQUIRED = {
    "600011.SH": {
        "CONTROLLABLE_CAPACITY": 158779.0,
        "OPERATING_CASH_FLOW": 25242626732.0,
        "CAPEX": 20390405467.0,
    },
    "600027.SH": {
        "CONTROLLABLE_CAPACITY": 7864.5598,
        "GRID_SALES_POWER": 1010.38,
        "FUEL_COST": 33212000000.0,
    },
    "600795.SH": {
        "THERMAL_POWER_GENERATION": 1741.44,
        "OPERATING_CASH_FLOW": 20516819187.46,
        "CAPEX": 16273059216.17,
    },
}


class V4MultiPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = sqlite3.connect(SOURCE)
        cls.db = sqlite3.connect(":memory:")
        source.backup(cls.db)
        source.close()
        cls.db.execute("PRAGMA foreign_keys=ON")
        cls.db.executescript((ROOT / "complete_schema.sql").read_text(encoding="utf-8"))
        cls.db.execute(
            "DELETE FROM document_processors WHERE processor='deep_report_metrics' AND processor_version IN ('3','4')"
        )
        cls.db.commit()
        cls.extraction = extract(cls.db)
        cls.calculation = calculate(cls.db)
        build_nodes(cls.db)
        build_edges(cls.db)
        ai_review(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_full_reports_and_page_facts(self):
        self.assertEqual(self.extraction["reports_parsed"], 3)
        self.assertEqual(self.extraction["errors"], [])
        for entity, expected in REQUIRED.items():
            for code, value in expected.items():
                row = self.db.execute(
                    """SELECT value,evidence_id FROM metric_values
                    WHERE entity_code=? AND metric_code=? AND source_table='deep_financial_report_v3'
                    AND value_status='SOURCE_FACT'""",
                    (entity, code),
                ).fetchone()
                self.assertIsNotNone(row, f"{entity}:{code}")
                self.assertAlmostEqual(row[0], value, places=2)
                locator = self.db.execute(
                    "SELECT page_or_locator FROM evidence WHERE evidence_id=?", (row[1],)
                ).fetchone()[0]
                self.assertTrue(locator.startswith("page:"))

    def test_calculated_lineage_and_no_missing_fill(self):
        self.assertEqual(self.calculation["skipped"], [])
        for code in (
            "DISCLOSED_DEBT_COMPONENTS", "NET_DEBT_PROXY",
            "FREE_CASH_FLOW_PROXY", "CURRENT_MARKET_CAP",
        ):
                self.assertGreaterEqual(
                    self.db.execute(
                    "SELECT count(*) FROM metric_values WHERE metric_code=? AND value_status='CALCULATED'",
                    (code,),
                ).fetchone()[0],
                3,
            )
        self.assertGreater(
            self.db.execute("SELECT count(*) FROM calculated_metric_lineage").fetchone()[0],
            30,
        )
        self.assertEqual(
            self.db.execute(
                """SELECT count(*) FROM metric_values
                WHERE source_table='calculated_metrics_v3' AND value IS NULL"""
            ).fetchone()[0],
            0,
        )

    def test_multi_path_formula_policy(self):
        self.assertGreater(
            self.db.execute(
                """SELECT count(*) FROM formulas
                WHERE formula_version='4.0' AND parameter_status='CALCULATED_LINEAGE'"""
            ).fetchone()[0],
            10,
        )
        self.assertGreater(
            self.db.execute(
                """SELECT count(*) FROM formulas
                WHERE formula_version='4.0' AND parameter_status='AI_ASSUMPTION'
                AND parameters_json LIKE '%ABSTAIN%'"""
            ).fetchone()[0],
            10,
        )
        self.assertEqual(self.db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_future_reports_are_not_silently_mislabeled(self):
        quarterly = ["某公司2026年第三季度报告", "合并资产负债表"]
        annual = ["某公司2026年年度报告", "合并资产负债表"]
        self.assertFalse(is_full_periodic_report(quarterly))
        self.assertFalse(is_full_periodic_report(annual))
        self.assertIsNone(report_metadata(quarterly, "https://x/2026-10-30/a.pdf"))
        self.assertIsNone(report_metadata(annual, "https://x/2027-03-30/a.pdf"))


if __name__ == "__main__":
    unittest.main()
