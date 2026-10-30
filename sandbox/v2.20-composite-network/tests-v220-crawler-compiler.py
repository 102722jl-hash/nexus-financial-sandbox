from __future__ import annotations

import copy
import json
from pathlib import Path

from crawler_network_compiler import compile_crawler_network
from v218_pipeline import simulate


root = Path(__file__).resolve().parent
payload = json.loads((root / "v220_crawler_payload.example.json").read_text(encoding="utf-8"))
plan = compile_crawler_network(payload)

assert plan["networkName"] == payload["network"]["network_name"]
assert plan["sourceNetworkId"] == payload["network"]["network_id"]
assert plan["networkId"] == plan["networkPlanId"]
assert plan["status"] == "ACTIVE"
assert plan["mode"] == "CREATE_NEW_NETWORK"
assert plan["crawlerContractVersion"] == "nexus-crawler-batch-1.0.0"
assert len(plan["nodes"]) == 3
assert len(plan["edges"]) == 2
assert all(item["layer"] in {"EXTERNAL_INPUT", "OPERATIONS", "FINANCIAL_RESULT"} for item in plan["nodes"])
assert all(item["candidateSimulation"] for item in plan["edges"])
assert plan["readiness"]["dataStatus"] == "DATA_READY"
assert plan["readiness"]["graphStatus"] == "GRAPH_READY"
assert plan["readiness"]["scenarioStatus"] == "SCENARIO_READY"
assert plan["qualityReport"]["counts"]["reachableTerminalNodes"] == 1

again = compile_crawler_network(copy.deepcopy(payload))
assert [item["nodeId"] for item in plan["nodes"]] == [item["nodeId"] for item in again["nodes"]]
assert [item["edgeId"] for item in plan["edges"]] == [item["edgeId"] for item in again["edges"]]
assert plan["networkPlanId"] == again["networkPlanId"]

missing = copy.deepcopy(payload)
missing["observations"] = missing["observations"][:1]
compiled_missing = compile_crawler_network(missing)
assert len(compiled_missing["nodes"]) == 3
assert sum(item["status"] == "DATA_MISSING" for item in compiled_missing["nodes"]) == 2

scenario = simulate(
    "SCENARIO-CRAWLER-CONTRACT",
    [{"metricCode": "INPUT_PRICE_INDEX", "changePercent": 20}],
    plan,
    plan["metricValues"],
    plan["dataCutoff"],
)
assert scenario["status"] == "CALCULATED"
assert len(scenario["calculationLedger"]) == 2
profit_node = next(item["nodeId"] for item in plan["nodes"] if "PROFIT_MARGIN" in item["metricCodes"])
assert next(item["changePercent"] for item in scenario["affectedNodes"] if item["nodeId"] == profit_node) < 0

company_payload = copy.deepcopy(payload)
company_payload["entities"][0]["entity_code"] = "000001.SZ"
company_payload["entities"][0]["entity_name"] = "示例公司"
company_payload["entities"][0]["entity_type"] = "COMPANY"
for metric in company_payload["metric_definitions"]:
    metric["entity_scope"] = "COMPANY"
for observation in company_payload["observations"]:
    observation["entity_code"] = "000001.SZ"
company_plan = compile_crawler_network(company_payload)
company_nodes = [item for item in company_plan["nodes"] if item["nodeType"] == "ENTITY"]
assert len(company_nodes) == 1
assert company_nodes[0]["entityCode"] == "000001.SZ"
assert set(company_nodes[0]["metricCodes"]) == {"INPUT_PRICE_INDEX", "OPERATING_COST_INDEX", "PROFIT_MARGIN"}
assert len(company_nodes[0]["baseline"]) == 3
assert any(
    item["relationType"] == "ENTITY_METRIC" and item["targetNodeId"] == company_nodes[0]["nodeId"]
    for item in company_plan["edges"]
)
assert company_plan["entities"][0]["entity_name"] == "示例公司"

print("V2.20 crawler network compiler: 28/28 passed")
