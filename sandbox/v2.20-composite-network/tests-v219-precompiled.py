import json

from db_connectors import table_adapters
from v218_pipeline import (
    _extract_precompiled_network,
    _mapping_by_table,
    auto_confirm_precompiled_candidates,
    build_network_plan,
    rule_candidates,
    table_adapter_candidates,
)


def column(name, dtype="text"):
    locator = {"database": "demo", "schema": "public", "table": "金融世界网络", "column": name}
    return {
        "column": f"demo.public.金融世界网络.{name}", "columnName": name, "tableName": "金融世界网络",
        "schemaName": "public", "databaseName": "demo", "sourceLocator": locator, "dtype": dtype,
        "sampleNonNull": 1, "sampleValues": [], "numericSampleRate": 1.0 if dtype == "numeric" else 0.0,
    }


profile = [
    column("network_id"), column("network_name"), column("schema_version"),
    column("nodes_json", "jsonb"), column("edges_json", "jsonb"), column("layers_json", "jsonb"),
    column("calculated_score", "numeric"),
]
adapters = table_adapters("demo", "public", ["金融世界网络"], profile)
assert adapters[0]["adapterMode"] == "PRECOMPILED_NETWORK_JSON"
assert adapters[0]["precompiledStatus"] == "STRUCTURE_SIGNATURE_MATCHED"

source_id = "SOURCE-PRECOMPILED"
candidates = rule_candidates(profile, source_id, "CREATE_NEW_NETWORK")
candidates += table_adapter_candidates(adapters, candidates, source_id, "CREATE_NEW_NETWORK")
summary = auto_confirm_precompiled_candidates(adapters, candidates)
assert summary["detected"] is True and summary["needsReview"] == 0
assert summary["autoConfirmed"] == len(candidates)
assert all(item["status"] == "CONFIRMED" for item in candidates)
assert any(item["metricCode"].startswith("CUSTOM_") and item["candidateSource"] == "PRECOMPILED_SCHEMA" for item in candidates)

grouped = _mapping_by_table(candidates, "public", "demo")
mappings = grouped[("public", "金融世界网络")]
nodes = [
    {"nodeId": "cash", "label": "货币资金", "layer": "capital", "metricCode": "CASH", "baselineValue": 100, "unit": "万元"},
    {"nodeId": "profit", "label": "营业利润", "layer": "outcome", "metricCode": "OPERATING_PROFIT", "baselineValue": 30, "unit": "万元"},
    {"nodeId": "company-a", "label": "测试公司", "layer": "entity", "entityCode": "A"},
]
edges = [
    {"edgeId": "cash-profit", "sourceNodeId": "cash", "targetNodeId": "profit", "direction": "positive", "weight": 0.4, "lagDays": 30, "confidence": 0.8, "mechanism": "流动性变化进入经营结果", "evidenceSource": "USER_NETWORK_TABLE", "status": "CONFIRMED"},
    {"edgeId": "profit-company", "sourceNodeId": "profit", "targetNodeId": "company-a", "direction": "positive", "weight": 0.5, "lagDays": 0, "confidence": 0.7, "mechanism": "利润变化进入公司结果", "evidenceSource": "USER_NETWORK_TABLE", "status": "CONFIRMED"},
]
rows = [{
    "network_id": "benchmark-network", "network_name": "对标金融网络", "schema_version": "1.0",
    "nodes_json": json.dumps(nodes, ensure_ascii=False), "edges_json": json.dumps(edges, ensure_ascii=False),
    "layers_json": json.dumps([{"id": "capital", "label": "资本与风险"}, {"id": "outcome", "label": "结果与质量"}, {"id": "entity", "label": "公司实体"}], ensure_ascii=False),
    "calculated_score": 88,
}]
compiled = _extract_precompiled_network(rows, mappings, source_id, "2026-09-03", "public.金融世界网络")
assert compiled["validationStatus"] == "VALIDATED"
assert compiled["networkName"] == "对标金融网络"
assert compiled["nodeCount"] == 3 and compiled["edgeCount"] == 2
assert compiled["nodes"][0]["baseline"] == {"BASE": 100.0}
assert compiled["edges"][0]["status"] == "CONFIRMED"
plan = build_network_plan(source_id, [], "generated", "CREATE_NEW_NETWORK", None, compiled)
assert plan["networkKind"] == "PRECOMPILED_NETWORK"
assert plan["outputLevel"] == "SCENARIO_PATH_ONLY" and plan["simulationReady"] is True
assert len(plan["graph"]["nodes"]) == 3 and len(plan["graph"]["edges"]) == 2

candidate_definition = {
    "networkId": "candidate-network", "networkName": "候选传播放大测试", "schemaVersion": "multi-table-network-2.0",
    "nodes": [
        {"nodeId": "price", "layer": "macro", "label": "动力煤价格", "baselineValue": 700},
        {"nodeId": "cost", "layer": "route", "label": "燃料成本", "baselineValue": 400},
    ],
    "edges": [{"edgeId": "price-cost", "sourceNodeId": "price", "targetNodeId": "cost", "direction": "positive", "confidence": 0.8, "status": "AI_APPROVED", "relationType": "COST_PRESSURE", "formulaType": "LINEAR_WEIGHT"}],
    "layerLabels": [], "validationStatus": "VALIDATED_WITH_WARNINGS", "formalReady": False,
    "candidateScenarioReady": True, "candidateGraph": {"nodes": [], "edges": [{"edgeId": "price-cost", "candidateWeight": 0.4}]},
}
candidate_plan = build_network_plan(source_id, [], "generated", "CREATE_NEW_NETWORK", None, candidate_definition)
assert candidate_plan["candidateScenarioReady"] is True
assert candidate_plan["candidateGraph"]["edges"][0]["candidateWeight"] == 0.4

normal = table_adapters("demo", "public", ["普通财务表"], [
    {**column("revenue", "numeric"), "tableName": "普通财务表", "sourceLocator": {"database": "demo", "schema": "public", "table": "普通财务表", "column": "revenue"}},
])
assert normal[0]["adapterMode"] == "MAPPED_POINT_IN_TIME"
standard_edge_profile = [
    {**column(name, dtype), "tableName": "network_edges", "sourceLocator": {"database": "demo", "schema": "public", "table": "network_edges", "column": name}}
    for name, dtype in [
        ("network_id", "text"), ("edge_id", "text"), ("source_node_id", "text"),
        ("target_node_id", "text"), ("direction", "text"), ("relation_type", "text"),
        ("weight", "numeric"), ("lag_days", "integer"), ("impact_cap_pct", "numeric"),
        ("mechanism", "text"), ("status", "text"),
    ]
]
standard_edge_adapter = table_adapters("demo", "public", ["network_edges"], standard_edge_profile)[0]
assert standard_edge_adapter["networkRole"] == "EDGES"
assert standard_edge_adapter["adapterMode"] == "MULTI_TABLE_EDGES"
custom_node_column = {**column("结构正文"), "sampleValues": ['[{"nodeId":"cash","layer":"constraint"}]']}
custom_edge_column = {**column("传播正文"), "sampleValues": ['[{"sourceNodeId":"cash","targetNodeId":"profit"}]']}
content_detected = table_adapters("demo", "public", ["金融世界网络"], [custom_node_column, custom_edge_column])
assert content_detected[0]["adapterMode"] == "PRECOMPILED_NETWORK_JSON"
content_candidates = rule_candidates([custom_node_column, custom_edge_column], source_id, "CREATE_NEW_NETWORK")
assert {item["metricCode"] for item in content_candidates} == {"NETWORK_NODES_JSON", "NETWORK_EDGES_JSON"}
bundle_column = {**column("graph_json"), "sampleValues": ['{"nodes":[{"nodeId":"cash","layer":"constraint"}],"edges":[]}']}
bundle_adapter = table_adapters("demo", "public", ["金融世界网络"], [bundle_column])
assert bundle_adapter[0]["adapterMode"] == "PRECOMPILED_NETWORK_JSON"
bundle_candidates = rule_candidates([bundle_column], source_id, "CREATE_NEW_NETWORK")
auto_confirm_precompiled_candidates(bundle_adapter, bundle_candidates)
bundle_mappings = _mapping_by_table(bundle_candidates, "public", "demo")[("public", "金融世界网络")]
bundle = _extract_precompiled_network([{"graph_json": json.dumps({"networkName": "单列网络包", "nodes": nodes, "edges": edges}, ensure_ascii=False)}], bundle_mappings, source_id, "2026-09-03", "public.金融世界网络")
assert bundle["networkName"] == "单列网络包" and bundle["nodeCount"] == 3 and bundle["edgeCount"] == 2

bad_rows = [{**rows[0], "edges_json": json.dumps([{**edges[0], "targetNodeId": "missing"}])}]
try:
    _extract_precompiled_network(bad_rows, mappings, source_id, "2026-09-03", "public.金融世界网络")
    raise AssertionError("invalid endpoint should fail closed")
except ValueError as exc:
    assert str(exc).startswith("PRECOMPILED_NETWORK_INVALID:EDGE_ENDPOINT")

print("V2.19 precompiled network adapter tests: 30/30 passed")
