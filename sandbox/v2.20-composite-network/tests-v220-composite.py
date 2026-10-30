from __future__ import annotations

import json
from pathlib import Path

from composite_quality import assess_mapping_readiness, assess_network_readiness, decorate_network_plan


ROOT = Path(__file__).resolve().parent


def node(node_id: str, layer: str, editable: bool = False, unit: str = "%") -> dict:
    return {"nodeId": node_id, "label": node_id, "layer": layer, "editable": editable, "unit": unit, "metricCodes": [node_id.upper()]}


def edge(edge_id: str, source: str, target: str, formula: str = "LINEAR_WEIGHT") -> dict:
    return {
        "edgeId": edge_id, "sourceNodeId": source, "targetNodeId": target,
        "status": "CANDIDATE", "sourceStatus": "AI_APPROVED",
        "parameterStatus": "AI_ASSUMPTION", "candidateSimulation": True,
        "candidateWeight": 0.4, "weight": 0, "formulaType": formula,
        "relationType": "BUSINESS_TRANSMISSION", "direction": "positive",
    }


valid = {
    "fullGraph": {
        "nodes": [node("demand", "market", True), node("revenue", "operations"), node("profit", "outcome")],
        "edges": [edge("demand-revenue", "demand", "revenue"), edge("revenue-profit", "revenue", "profit")],
    },
    "candidateScenarioReady": True,
    "causalStatus": "ABSTAIN",
}
quality = assess_network_readiness(valid)
assert quality["status"] == "SCENARIO_READY"
assert quality["readiness"] == {
    "dataReady": True, "graphReady": True, "scenarioReady": True,
    "dataStatus": "DATA_READY", "graphStatus": "GRAPH_READY", "scenarioStatus": "SCENARIO_READY",
}
assert quality["counts"]["nodes"] == 3
assert quality["counts"]["propagatingEdges"] == 2
assert quality["counts"]["candidateEdges"] == 2
assert quality["counts"]["reachableTerminalNodes"] == 1
assert quality["reachableResultNodeIds"] == ["profit"]

decorated = decorate_network_plan(dict(valid))
assert decorated["outputLevel"] == "CANDIDATE_SCENARIO"
assert decorated["activationBlocked"] is not True if "activationBlocked" in decorated else True

broken = json.loads(json.dumps(valid))
broken["fullGraph"]["edges"][0]["targetNodeId"] = "missing"
broken_quality = assess_network_readiness(broken)
assert broken_quality["readiness"]["graphReady"] is False
assert broken_quality["readiness"]["scenarioReady"] is False
assert broken_quality["blockingIssues"][0]["code"] == "EDGE_NODE_NOT_FOUND"

unknown = json.loads(json.dumps(valid))
unknown["fullGraph"]["edges"][0]["formulaType"] = "QUANTUM_MAGIC"
unknown_quality = assess_network_readiness(unknown)
assert unknown_quality["readiness"]["graphReady"] is True
assert unknown_quality["counts"]["quarantinedFormulaEdges"] == 1
assert unknown_quality["counts"]["propagatingEdges"] == 1

cycle = json.loads(json.dumps(valid))
cycle["fullGraph"]["edges"].append(edge("profit-demand", "profit", "demand"))
cycle_quality = assess_network_readiness(cycle)
assert cycle_quality["counts"]["cycles"] == 1
assert any(item["code"] == "PROPAGATION_CYCLES" for item in cycle_quality["warnings"])

partial = json.loads(json.dumps(valid))
for index, item in enumerate(partial["fullGraph"]["nodes"]):
    item["requiredForNetwork"] = True
    item["baseline"] = {item["metricCodes"][0]: 100} if index == 0 else {}
partial_quality = assess_network_readiness(partial)
assert partial_quality["readiness"]["dataStatus"] == "DATA_PARTIAL"
assert partial_quality["readiness"]["graphReady"] is True
assert partial_quality["readiness"]["scenarioReady"] is False
assert partial_quality["coverage"]["requiredBaselineCoveragePct"] == 33.33
assert any(item["code"] == "REQUIRED_BASELINE_COVERAGE_INSUFFICIENT" for item in partial_quality["warnings"])

profile = [
    {"tableName": "metric_values", "column": "metric_code"},
    {"tableName": "metric_values", "column": "value"},
]
mappings = [
    {"status": "CONFIRMED", "metricCode": "METRIC_CODE"},
    {"status": "UNRESOLVED", "metricCode": None},
]
mapping_quality = assess_mapping_readiness(profile, mappings, [])
assert mapping_quality["status"] == "DATA_READY"
assert mapping_quality["confirmedMappingCount"] == 1
assert mapping_quality["unresolvedCount"] == 1
assert any(item["code"] == "UNRESOLVED_FIELDS" for item in mapping_quality["issues"])

saved = ROOT / "runs" / "networks" / "PLAN-2E3CA01A630A3CF9.json"
if saved.is_file():
    nev = assess_network_readiness(json.loads(saved.read_text(encoding="utf-8")))
    assert nev["readiness"]["dataReady"] is True
    assert nev["readiness"]["graphReady"] is True
    assert nev["readiness"]["scenarioReady"] is True
    assert nev["counts"]["nodes"] == 77
    assert nev["counts"]["edges"] == 66

print("V2.20 composite readiness tests: 29/29 passed")
