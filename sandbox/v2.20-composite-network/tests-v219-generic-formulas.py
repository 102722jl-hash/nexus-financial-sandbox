from __future__ import annotations

import sqlite3
from pathlib import Path

from generic_network_contract import normalize_formula_type
from v218_pipeline import _extract_multi_table_network, build_precompiled_network_plan, evaluate_formula, simulate


ROOT = Path(__file__).resolve().parent
NEV_DB = ROOT.parent / "new_energy_vehicle_collector" / "new_energy_vehicle.db"


def rows(connection: sqlite3.Connection, table: str) -> list[dict]:
    connection.row_factory = sqlite3.Row
    return [dict(item) for item in connection.execute(f'SELECT * FROM "{table}"')]


def mappings(pairs: dict[str, str]) -> list[dict]:
    return [{"column": column, "metricCode": code} for column, code in pairs.items()]


assert normalize_formula_type("MARKET_SHARE_BRIDGE")[0] == "MULTIPLY"
assert normalize_formula_type("MATERIAL_COST_BRIDGE")[0] == "COST_PASS_THROUGH"
assert normalize_formula_type("FUTURE_DEMAND_ELASTICITY")[0] == "LINEAR_WEIGHT"
assert normalize_formula_type("QUANTUM_MAGIC")[0] is None
assert evaluate_formula("MULTIPLY", 10, 0.4, "positive", {})[0] == 4
assert evaluate_formula("SUBTRACT", 10, 0.4, "negative", {})[0] == -4

connection = sqlite3.connect(NEV_DB)
entries = [
    ("REGISTRY", rows(connection, "network_registry"), mappings({
        "network_id": "NETWORK_ID", "network_name": "NETWORK_NAME",
        "network_version": "NETWORK_VERSION",
    }), "new_energy_vehicle.network_registry"),
    ("LAYERS", rows(connection, "network_layers"), mappings({
        "network_id": "NETWORK_ID", "layer_no": "NETWORK_LAYER_NO",
        "layer_code": "NETWORK_LAYER_CODE", "layer_name_cn": "NETWORK_LAYER_NAME",
        "sort_order": "NETWORK_LAYER_SORT",
    }), "new_energy_vehicle.network_layers"),
    ("NODES", rows(connection, "network_nodes"), mappings({
        "network_id": "NETWORK_ID", "node_id": "NETWORK_NODE_ID",
        "layer_no": "NETWORK_NODE_LAYER", "node_name_cn": "NETWORK_NODE_LABEL",
        "node_type": "NETWORK_NODE_TYPE", "metric_code": "NETWORK_NODE_METRIC_CODE",
        "metric_name": "NETWORK_NODE_METRIC_NAME", "unit": "NETWORK_NODE_UNIT",
        "baseline_value": "NETWORK_NODE_BASELINE", "editable": "NETWORK_NODE_EDITABLE",
        "value_status": "NETWORK_NODE_VALUE_STATUS",
    }), "new_energy_vehicle.network_nodes"),
    ("FORMULAS", rows(connection, "formulas"), mappings({
        "network_id": "NETWORK_ID", "formula_id": "FORMULA_ID",
        "formula_type": "FORMULA_TYPE", "formula_expression": "FORMULA_EXPRESSION",
        "parameters_json": "FORMULA_PARAMETERS", "status": "NETWORK_STATUS",
    }), "new_energy_vehicle.formulas"),
    ("EDGES", rows(connection, "network_edges"), mappings({
        "network_id": "NETWORK_ID", "edge_id": "NETWORK_EDGE_ID",
        "source_node_id": "NETWORK_EDGE_SOURCE", "target_node_id": "NETWORK_EDGE_TARGET",
        "direction": "NETWORK_EDGE_DIRECTION", "relation_type": "NETWORK_EDGE_RELATION_TYPE",
        "formula_id": "FORMULA_ID", "formula_type": "FORMULA_TYPE",
        "parameters_json": "FORMULA_PARAMETERS", "parameter_status": "NETWORK_EDGE_PARAMETER_STATUS",
        "confidence": "NETWORK_EDGE_CONFIDENCE", "mechanism": "NETWORK_EDGE_MECHANISM",
        "status": "NETWORK_EDGE_STATUS",
    }), "new_energy_vehicle.network_edges"),
]
compiled = _extract_multi_table_network(entries, "SOURCE-NEV", "2026-09-16")[0]
assert compiled["validationStatus"] != "INVALID", compiled["validationIssues"]
assert compiled["nodeCount"] == 77
assert compiled["edgeCount"] == 66
assert compiled["candidateScenarioReady"] is True
assert compiled["candidateEdgeCount"] == 66
assert all(edge["status"] == "CANDIDATE" for edge in compiled["edges"])
assert all(edge["sourceStatus"] == "AI_APPROVED" for edge in compiled["edges"])
assert all(edge["candidateSimulation"] for edge in compiled["edges"])
assert all(edge["formulaSupported"] for edge in compiled["edges"])

# Candidate relations propagate through the generic backend engine without
# being promoted to formal causal conclusions.
plan = build_precompiled_network_plan("SOURCE-NEV", compiled, "新能源汽车测试网络")
plan["status"] = "ACTIVE"
source_edge = next(edge for edge in compiled["edges"] if edge["candidateWeight"] > 0)
scenario = simulate(
    "SCENARIO-NEV",
    [{"metricCode": source_edge["sourceNodeId"], "changePercent": 10}],
    plan,
    [],
    "2026-09-16",
)
affected = {item["nodeId"]: item["changePercent"] for item in scenario["affectedNodes"]}
assert scenario["status"] == "CALCULATED"
assert scenario["causalStatus"] == "ABSTAIN"
assert scenario["outputLevel"] == "CANDIDATE_SCENARIO"
assert scenario["calculationLedger"]
assert abs(affected.get(source_edge["targetNodeId"], 0)) > 0

# A future unknown formula quarantines only its relations and does not block
# the remaining network from opening and propagating.
unknown_entries = list(entries)
formula_rows = [dict(item) for item in unknown_entries[3][1]]
unknown_id = formula_rows[0]["formula_id"]
formula_rows[0]["formula_type"] = "QUANTUM_MAGIC"
formula_rows[0]["formula_expression"] = "quantum tensor transform"
unknown_entries[3] = (unknown_entries[3][0], formula_rows, unknown_entries[3][2], unknown_entries[3][3])
compiled_unknown = _extract_multi_table_network(unknown_entries, "SOURCE-NEV-UNKNOWN", "2026-09-16")[0]
assert compiled_unknown["validationStatus"] != "INVALID"
unknown_edges = [edge for edge in compiled_unknown["edges"] if edge["formulaId"] == unknown_id]
assert unknown_edges and all(not edge["formulaSupported"] for edge in unknown_edges)
assert all(edge["candidateWeight"] == 0 for edge in unknown_edges)
assert any(edge["candidateSimulation"] for edge in compiled_unknown["edges"] if edge["formulaId"] != unknown_id)
connection.close()

print("V2.19 generic formula registry tests: 25/25 passed")
