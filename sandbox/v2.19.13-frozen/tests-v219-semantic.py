import json

import ai_adapter
import db_connectors
import server
from v218_pipeline import build_generated_network_plan


columns = [
    {"column": "db.public.demo.column_76", "columnName": "column_76", "tableName": "demo"},
    {"column": "db.public.demo.secret_token", "columnName": "secret_token", "tableName": "demo"},
]
db_connectors.apply_sample_profile(columns, "demo", [(88.2, "do-not-send"), (91.4, "hidden"), (None, None)])
assert columns[0]["sampleValues"] == [88.2, 91.4]
assert columns[0]["numericMin"] == 88.2 and columns[0]["numericMax"] == 91.4
assert columns[0]["nullRate"] == 0.3333
assert columns[1]["sampleValues"] == []

captured = {}
original_content = ai_adapter._content


def fake_content(config, system, user, max_tokens=1600):
    request = json.loads(user)
    captured.update(request)
    output = []
    for field in request["fields"]:
        if field["columnName"] == "column_76":
            output.append({
                "sourceField": field["sourceField"], "action": "DEFINE_CUSTOM",
                "metricCode": field["currentMetricCode"], "displayNameZh": "客户增长评分",
                "descriptionZh": "衡量客户增长表现的来源评分", "metricType": "score",
                "unit": "SCORE", "layer": "chain", "confidence": 0.78,
                "reason": "样例位于百分制评分区间",
            })
        else:
            output.append({
                "sourceField": field["sourceField"], "action": "MAP_EXISTING",
                "metricCode": "ENTITY_NAME", "displayNameZh": "实体名称",
                "descriptionZh": "数据实体的名称", "metricType": "numeric",
                "unit": "SOURCE_UNIT_UNKNOWN", "layer": "demand", "confidence": 0.84,
                "reason": "样例为重复出现的公司名称",
            })
    return json.dumps({"candidates": output}, ensure_ascii=False)


try:
    ai_adapter._content = fake_content
    fields = [
        {"sourceField": "db.public.demo.column_76", "columnName": "column_76", "tableName": "demo", "dataType": "numeric", "sampleNonNull": 2, "numericSampleRate": 1, "distinctSampleCount": 2, "numericMin": 88.2, "numericMax": 91.4, "sampleValues": [88.2, 91.4], "currentMetricCode": "CUSTOM_ABC123", "currentMetricName": "column_76", "allowCustomMetric": True},
        {"sourceField": "db.public.demo.column_02", "columnName": "column_02", "tableName": "demo", "dataType": "text", "sampleNonNull": 2, "numericSampleRate": 0, "distinctSampleCount": 2, "sampleValues": ["甲公司", "乙公司"], "currentMetricCode": "UNRESOLVED", "currentMetricName": "尚未识别", "allowCustomMetric": False},
    ]
    catalog = [{"metricCode": "ENTITY_NAME", "metricName": "实体名称", "metricType": "dimension", "unit": None}]
    candidates = ai_adapter.semantic_candidates({"provider": "test"}, fields, catalog)
finally:
    ai_adapter._content = original_content

assert captured["fields"][0]["sampleValues"] == [88.2, 91.4]
assert candidates[0]["metricName"] == "客户增长评分"
assert candidates[0]["metricDefinition"]["networkLayer"] == "chain"
assert candidates[0]["status"] == "PENDING_REVIEW"
assert candidates[1]["metricCode"] == "ENTITY_NAME"
assert all(item["candidateSource"] == "AI_SEMANTIC" for item in candidates)

source_id = "SOURCE-SEMANTIC-TEST"
server.MAPPINGS.clear()
server.MAPPINGS["MAP-SEMANTIC"] = {
    "mappingId": "MAP-SEMANTIC", "sourceId": source_id,
    "sourceField": "db.public.demo.column_76", "sourceColumn": "db.public.demo.column_76",
    "metricCode": "CUSTOM_ABC123", "metricName": "column_76",
    "metricDefinition": {"metricCode": "CUSTOM_ABC123", "metricName": "column_76", "metricType": "numeric", "unit": "SOURCE_UNIT_UNKNOWN"},
    "candidateSource": "CUSTOM_NUMERIC", "status": "CONFIRMED",
}
applied = server._apply_ai_semantic_candidate(source_id, candidates[0])
assert applied["status"] == "PENDING_REVIEW"
assert applied["metricName"] == "客户增长评分"
assert applied["semanticStatus"] == "CANDIDATE"

values = [{
    "metricValueId": "MV-SEMANTIC", "metricCode": "CUSTOM_ABC123", "metricName": "客户增长评分",
    "metricType": "score", "networkLayer": "chain", "metricDescription": "衡量客户增长表现的来源评分",
    "semanticSource": "AI_CANDIDATE", "semanticConfidence": 0.78, "semanticReason": "样例位于百分制评分区间",
    "entityCode": "ROW-1234567890ABCDEF", "entityName": None, "value": 88.2, "unit": "SCORE", "currency": None,
    "reportPeriod": "20251231", "announcementDate": "20260508", "dataCutoff": "2026-05-08",
    "sourceId": source_id, "sourceTable": "demo", "sourceColumn": "column_76", "sourceRowKey": "ROW-1",
    "valueStatus": "REPORTED_ACTUAL", "evidenceId": "EVD-SEMANTIC", "version": "20260508", "opdate": None,
}]
plan = build_generated_network_plan(source_id, values, "语义网络测试")
metric_node = next(node for node in plan["graph"]["nodes"] if node["nodeId"].startswith("metric-"))
entity_node = next(node for node in plan["graph"]["nodes"] if node["layer"] == "company")
assert metric_node["label"] == "客户增长评分"
assert metric_node["sub"] == "评分 · SCORE"
assert metric_node["layer"] == "chain"
assert metric_node["description"] == "衡量客户增长表现的来源评分"
assert entity_node["label"] == "数据记录 01"
assert entity_node["sub"].startswith("自动行标识")
print("V2.19 AI semantic enrichment tests: 20/20 passed")