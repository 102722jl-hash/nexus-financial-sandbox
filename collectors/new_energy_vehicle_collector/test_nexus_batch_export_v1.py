from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from contract_v1 import COMPANIES, TEMPLATES
from export_nexus_batch_v1 import DEFAULT_OUTPUT_DIR, SANDBOX, export_batch
from initialize import DEFAULT_DB


sys.path.insert(0, str(SANDBOX))
from crawler_contract import validate_crawler_payload
from crawler_network_compiler import compile_crawler_network


class NexusBatchExportTests(unittest.TestCase):
    def test_existing_nev_database_exports_and_compiles(self):
        result = export_batch(DEFAULT_DB, output_dir=DEFAULT_OUTPUT_DIR, compile_network=False)
        payload = json.loads(Path(result["output"]).read_text(encoding="utf-8"))
        report = validate_crawler_payload(payload)
        self.assertNotEqual(report["status"], "REJECTED")
        self.assertTrue(report["ingestionAllowed"])
        self.assertEqual(
            {item["data_cutoff"] for item in payload["observations"]},
            {payload["batch"]["data_cutoff"]},
        )
        quarantined_ids = {
            item.get("objectId") for item in report.get("quarantine", [])
            if item.get("objectType") == "observation"
        }
        monthly = [
            item for item in payload["observations"]
            if item["metric_code"] in {"COMPANY_NEV_SALES", "COMPANY_NEV_PRODUCTION"}
        ]
        self.assertTrue(monthly)
        self.assertFalse(quarantined_ids.intersection(item["observation_id"] for item in monthly))
        plan = compile_crawler_network(payload)
        self.assertEqual(plan["networkName"], "新能源汽车多链路传导网络")
        metric_nodes = 8 + 23 * len(COMPANIES)
        causal_edges = sum(1 if item[3] == "INDUSTRY" else len(COMPANIES) for item in TEMPLATES)
        self.assertEqual(len(plan["nodes"]), metric_nodes + len(COMPANIES))
        self.assertEqual(len(plan["edges"]), causal_edges + len(COMPANIES))
        sales_nodes = [item for item in plan["nodes"] if item.get("metricCodes") == ["COMPANY_NEV_SALES"]]
        self.assertEqual(len(sales_nodes), len(COMPANIES))
        self.assertTrue(all(item.get("baseline") for item in sales_nodes))
        propagating = [item for item in plan["edges"] if item["relationType"] != "ENTITY_METRIC"]
        self.assertTrue(all(edge["candidateWeight"] > 0 for edge in propagating))


if __name__ == "__main__":
    unittest.main()
