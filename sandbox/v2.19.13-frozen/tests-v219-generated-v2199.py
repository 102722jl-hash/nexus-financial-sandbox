from db_connectors import profile_rows
from server import _confirm_network_plan_edges
from v218_pipeline import build_generated_network_plan, rule_candidates


profile = profile_rows([("public", "现金流表", "经营现金流", "numeric", "经营活动现金流量净额")], "财务库")
assert profile[0]["columnComment"] == "经营活动现金流量净额"
assert profile[0]["sourceLocator"]["table"] == "现金流表"

known = rule_candidates([{
    "column": "pg.public.cashflow.cash_pay_beh_empl", "columnName": "cash_pay_beh_empl",
    "tableName": "cashflow", "schemaName": "public", "databaseName": "pg",
    "sourceLocator": {"database": "pg", "schema": "public", "table": "cashflow", "column": "cash_pay_beh_empl"},
    "dtype": "numeric", "numericSampleRate": 1,
}], "SOURCE-ZH", "CREATE_NEW_NETWORK")[0]
assert known["metricName"] == "支付给职工以及为职工支付的现金"
assert known["metricDefinition"]["semanticSource"] == "FINANCIAL_FIELD_DICTIONARY"
assert known["confidence"] == 0.9


def metric_value(entity, code, name, value, index):
    return {
        "metricValueId": f"MV-{index}", "entityCode": entity, "metricCode": code,
        "metricName": name, "metricType": "numeric", "networkLayer": "chain",
        "value": value, "unit": "CNY", "reportPeriod": "20251231",
        "dataCutoff": "2026-05-08", "evidenceId": f"EVD-{index}", "version": "V1",
    }


values = [
    metric_value("A", "CUSTOM_A", "指标甲", 10, 1), metric_value("A", "CUSTOM_B", "指标乙", 20, 2),
    metric_value("B", "CUSTOM_A", "指标甲", 30, 3), metric_value("B", "CUSTOM_B", "指标乙", 40, 4),
]
plan = build_generated_network_plan("SOURCE-LINEAGE", values, "完整谱系")
entity_edges = [edge for edge in plan["graph"]["edges"] if edge.get("relationType") == "ENTITY_METRIC"]
assert len(entity_edges) == 4

candidate = {
    "edgeId": "EDGE-SCENARIO", "sourceNodeId": "metric-custom-a", "targetNodeId": "metric-custom-b",
    "direction": "positive", "weight": 0.5, "lagDays": 30, "confidence": 0.8,
    "mechanism": "测试机制", "status": "CANDIDATE",
}
plan["mode"] = "CREATE_NEW_NETWORK"
plan["graph"]["edges"].append(candidate)
if plan["diff"]["addedEdges"] is not plan["graph"]["edges"]:
    plan["diff"]["addedEdges"].append(candidate)
confirmed = _confirm_network_plan_edges(plan, {"EDGE-SCENARIO"})
assert confirmed == [candidate]
assert candidate["status"] == "CONFIRMED"
assert plan["simulationReady"] is True
assert plan["outputLevel"] == "SCENARIO_PATH_ONLY"

print("V2.19.9 generated network quality tests: 10/10 passed")
