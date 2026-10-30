from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

from contract_v1 import COMPANIES, METRICS, NETWORK_ID, TEMPLATES
from initialize import initialize
from ingest_v1 import IngestRejected, ingest_record
from quality_gate_v1 import run_quality_gate
from scenario_engine_v1 import run_scenario


class NetworkV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = Path(__file__).resolve().parent / ".test_new_energy_vehicle.db"
        self.db.unlink(missing_ok=True)
        initialize(self.db)

    def tearDown(self) -> None:
        self.db.unlink(missing_ok=True)

    def test_blueprint_exists_before_collection(self) -> None:
        conn = sqlite3.connect(self.db)
        node_count = conn.execute(
            "SELECT count(*) FROM network_nodes WHERE network_id=?", (NETWORK_ID,)
        ).fetchone()[0]
        edge_count = conn.execute(
            "SELECT count(*) FROM network_edges WHERE network_id=?", (NETWORK_ID,)
        ).fetchone()[0]
        self.assertEqual(node_count, 8 + 23 * len(COMPANIES))
        self.assertEqual(edge_count, sum(1 if t[3] == "INDUSTRY" else len(COMPANIES) for t in TEMPLATES))
        missing = conn.execute(
            "SELECT count(*) FROM network_nodes WHERE network_id=? AND value_status='DATA_MISSING'",
            (NETWORK_ID,),
        ).fetchone()[0]
        self.assertEqual(missing, node_count)
        conn.close()

    def test_company_node_sets_are_identical(self) -> None:
        conn = sqlite3.connect(self.db)
        sets = []
        for entity in COMPANIES:
            rows = conn.execute(
                "SELECT metric_code FROM network_nodes WHERE network_id=? AND entity_code=?",
                (NETWORK_ID, entity),
            )
            sets.append({row[0] for row in rows})
        self.assertTrue(all(item == sets[0] for item in sets[1:]))
        self.assertEqual(sets[0], {code for code, spec in METRICS.items() if spec[4] == "COMPANY"})
        conn.close()

    def test_upstream_change_reaches_valuation_for_every_company(self) -> None:
        inputs = {
            "NEV_INDUSTRY_SALES": 1_000_000,
            "LITHIUM_CARBONATE_PRICE": 100_000,
            "BATTERY_KWH_PER_VEHICLE": 60,
            "ASP_PROXY": 200_000,
        }
        params = {
            "market_share": 0.10,
            "material_coefficient": 0.0005,
            "profit_conversion_ratio": 0.60,
            "valuation_multiple": 12,
        }
        changed = dict(inputs)
        changed["NEV_INDUSTRY_SALES"] = 1_100_000
        for entity in COMPANIES:
            before = run_scenario(self.db, entity, inputs, params, persist=False)
            after = run_scenario(self.db, entity, changed, params, persist=False)
            for metric in (
                "COMPANY_NEV_SALES", "VEHICLE_REVENUE_PROXY",
                "GROSS_PROFIT_PROXY", "NET_PROFIT", "CURRENT_MARKET_CAP",
            ):
                self.assertNotEqual(
                    before["values"][metric], after["values"][metric],
                    f"{entity}:{metric}",
                )

    def test_missing_inputs_block_instead_of_zero_fill(self) -> None:
        result = run_scenario(
            self.db, "002594.SZ", {"NEV_INDUSTRY_SALES": 1_000_000},
            {"market_share": 0.10}, persist=False,
        )
        self.assertIsNone(result["values"]["CURRENT_MARKET_CAP"])
        self.assertEqual(result["statuses"]["CURRENT_MARKET_CAP"], "BLOCKED_DATA_MISSING")

    def test_gate_and_causal_boundary(self) -> None:
        report = run_quality_gate(self.db)
        self.assertEqual(report["status"], "PASS", report)
        conn = sqlite3.connect(self.db)
        conclusions = {
            row[0] for row in conn.execute(
                "SELECT DISTINCT causal_conclusion FROM formulas WHERE network_id=?", (NETWORK_ID,)
            )
        }
        self.assertEqual(conclusions, {"ABSTAIN"})
        self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
        conn.close()

    def test_ingestion_updates_existing_node(self) -> None:
        payload = {
            "evidence": {
                "source_type": "SOURCE_FACT",
                "source_name": "测试法定公告",
                "publisher": "比亚迪股份有限公司",
                "published_at": "2026-09-01T08:00:00+08:00",
                "retrieved_at": "2026-09-02T08:00:00+08:00",
                "original_quote": "新能源汽车销量为100000辆。",
                "locator": "第1页，产销快报表格",
                "source_url": "https://example.invalid/legal-disclosure.pdf",
                "anchor_at": "2026-09-02T23:59:59+08:00",
                "source_tier": "T2",
            },
            "metric": {
                "metric_code": "COMPANY_NEV_SALES",
                "entity_code": "002594.SZ",
                "value": 100000,
                "unit": "辆",
                "report_period": "2026-08",
                "source_row_key": "test-byd-2026-08-sales",
            },
        }
        accepted = ingest_record(self.db, payload)
        self.assertEqual(accepted["status"], "ACCEPTED")
        conn = sqlite3.connect(self.db)
        node = conn.execute(
            "SELECT baseline_value,value_status,evidence_id FROM network_nodes WHERE network_id=? AND node_id=?",
            (NETWORK_ID, "company::002594.SZ::COMPANY_NEV_SALES"),
        ).fetchone()
        self.assertEqual(float(node[0]), 100000)
        self.assertEqual(node[1], "SOURCE_FACT")
        self.assertTrue(node[2])
        conn.close()

    def test_t3_cannot_be_promoted_to_source_fact(self) -> None:
        payload = {
            "evidence": {
                "source_type": "SOURCE_FACT",
                "source_name": "行情接口",
                "publisher": "第三方行情平台",
                "published_at": "2026-09-01T08:00:00+08:00",
                "retrieved_at": "2026-09-01T08:01:00+08:00",
                "original_quote": "收盘价为100元。",
                "locator": "响应字段 close",
                "source_url": "https://example.invalid/quote",
                "anchor_at": "2026-09-01T23:59:59+08:00",
                "source_tier": "T3",
            },
            "metric": {
                "metric_code": "CLOSE_PRICE",
                "entity_code": "002594.SZ",
                "value": 100,
                "unit": "元/股",
                "as_of_date": "2026-09-01",
                "source_row_key": "test-quote",
            },
        }
        with self.assertRaisesRegex(IngestRejected, "SOURCE_TIER_NOT_ELIGIBLE"):
            ingest_record(self.db, payload)
        conn = sqlite3.connect(self.db)
        reason = conn.execute(
            "SELECT reason_code FROM quarantine ORDER BY quarantine_id DESC LIMIT 1"
        ).fetchone()[0]
        self.assertEqual(reason, "SOURCE_TIER_NOT_ELIGIBLE")
        conn.close()


if __name__ == "__main__":
    unittest.main()
