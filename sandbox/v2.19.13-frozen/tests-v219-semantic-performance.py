import threading
import time

import server
from ai_adapter import AIAdapterError


def candidate(field):
    return {
        "sourceField": field["sourceField"],
        "metricCode": field.get("currentMetricCode", "CUSTOM_TEST"),
        "metricName": "测试指标",
        "metricDefinition": {
            "metricCode": field.get("currentMetricCode", "CUSTOM_TEST"),
            "metricName": "测试指标",
            "metricType": "numeric",
            "unit": "SOURCE_UNIT_UNKNOWN",
            "networkLayer": "chain",
        },
        "candidateSource": "AI_SEMANTIC",
        "status": "PENDING_REVIEW",
        "confidence": 0.8,
        "reason": "测试候选",
    }


assert server.AI_SEMANTIC_BATCH_SIZE == 4
assert server.AI_SEMANTIC_WORKERS == 3
assert server._semantic_job_config({"timeoutSeconds": 90})["timeoutSeconds"] == 90
assert server._semantic_job_config({"timeoutSeconds": 5})["timeoutSeconds"] == 20
assert server._semantic_job_config({})["timeoutSeconds"] == 60

fields = [{"sourceField": f"field-{index}", "currentMetricCode": f"CUSTOM_{index}"} for index in range(104)]
active = 0
max_active = 0
calls = []
counter_lock = threading.Lock()
original_semantic = server.ai_semantic_candidates
original_apply = server._apply_ai_semantic_candidate


def fast_semantic(config, batch, catalog):
    global active, max_active
    with counter_lock:
        active += 1
        max_active = max(max_active, active)
        calls.append(len(batch))
    time.sleep(0.02)
    with counter_lock:
        active -= 1
    return [candidate(field) for field in batch]


try:
    server.ai_semantic_candidates = fast_semantic
    server._apply_ai_semantic_candidate = lambda source_id, item: item
    server.AI_MAPPING_JOBS["AIJOB-PERF"] = {
        "status": "QUEUED", "processedFields": 0, "errors": [], "candidates": []
    }
    server._run_ai_semantic_job("AIJOB-PERF", "SOURCE-PERF", fields, {"timeoutSeconds": 60}, [])
finally:
    server.ai_semantic_candidates = original_semantic
    server._apply_ai_semantic_candidate = original_apply

job = server.AI_MAPPING_JOBS.pop("AIJOB-PERF")
assert len(calls) == 26
assert set(calls) == {4}
assert max_active == 3
assert job["totalBatches"] == 26 and job["completedBatches"] == 26
assert job["processedFields"] == 104 and len(job["candidates"]) == 104
assert job["batchSize"] == 4 and job["maxWorkers"] == 3 and job["timeoutSeconds"] == 60

fallback_calls = []


def invalid_batch_then_single(config, batch, catalog):
    fallback_calls.append(len(batch))
    if len(batch) > 1:
        raise AIAdapterError("INVALID_RESPONSE", "批量响应格式错误")
    return [candidate(batch[0])]


try:
    server.ai_semantic_candidates = invalid_batch_then_single
    recovered, errors = server._semantic_batch_with_fallback({}, fields[:4], [])
finally:
    server.ai_semantic_candidates = original_semantic

assert fallback_calls == [4, 1, 1, 1, 1]
assert len(recovered) == 4 and not errors

missing_calls = []


def omit_one_then_single(config, batch, catalog):
    missing_calls.append(len(batch))
    return [candidate(field) for field in (batch[:-1] if len(batch) > 1 else batch)]


try:
    server.ai_semantic_candidates = omit_one_then_single
    recovered, errors = server._semantic_batch_with_fallback({}, fields[:4], [])
finally:
    server.ai_semantic_candidates = original_semantic

assert missing_calls == [4, 1]
assert len(recovered) == 4 and not errors

# A wide financial table must be routed locally before any gateway call:
# 14 standard fields are already resolved, 41 use the local financial
# dictionary, 49 are empty in the profile, and only 22 require remote AI.
source_id = "SOURCE-CASHFLOW-126"
saved_mappings = dict(server.MAPPINGS)
server.MAPPINGS.clear()
profile = []
for index in range(126):
    locator = {"database": "pg", "schema": "public", "table": "asharecashflow", "column": f"field_{index}"}
    profile_item = {
        "sourceLocator": locator, "columnName": f"field_{index}", "tableName": "asharecashflow",
        "dtype": "numeric", "sampleNonNull": 3, "sampleValues": [index + 1],
        "numericSampleRate": 1.0, "distinctSampleCount": 3,
    }
    profile.append(profile_item)
    if index < 14:
        candidate_source, status, definition, metric_name = "RULE", "PENDING_REVIEW", {"metricCode": f"STD_{index}", "metricName": f"标准指标 {index}"}, f"标准指标 {index}"
    elif index < 55:
        candidate_source, status, definition, metric_name = "CUSTOM_NUMERIC", "PENDING_REVIEW", {"metricCode": f"CUSTOM_{index}", "metricName": f"本地财务指标 {index}", "semanticSource": "FINANCIAL_FIELD_DICTIONARY"}, f"本地财务指标 {index}"
    else:
        candidate_source, status, definition, metric_name = "CUSTOM_NUMERIC", "PENDING_REVIEW", {"metricCode": f"CUSTOM_{index}", "metricName": f"field_{index}"}, f"field_{index}"
        if index < 104:
            profile_item["sampleNonNull"] = 0
            profile_item["sampleValues"] = []
    mapping = {
        "mappingId": f"MAP-{index}", "sourceId": source_id,
        "sourceField": f"pg.public.asharecashflow.field_{index}", "sourceColumn": f"field_{index}",
        "sourceLocator": locator, "columnName": f"field_{index}", "tableName": "asharecashflow",
        "candidateSource": candidate_source, "status": status,
        "metricCode": definition["metricCode"], "metricName": metric_name, "metricDefinition": definition,
    }
    server.MAPPINGS[mapping["mappingId"]] = mapping

routed_fields, local_candidates, counts = server._prepare_semantic_job_inputs(source_id, {"profile": profile})
assert len(routed_fields) == 22
assert counts == {"totalFields": 112, "localResolvedFields": 41, "localSuggestedIgnore": 49, "aiQueuedFields": 22}
assert len(local_candidates) == 90
assert sum(item["candidateSource"] == "LOCAL_EMPTY_PROFILE" for item in local_candidates) == 49
assert all(item["sourceField"] not in {field["sourceField"] for field in routed_fields} for item in local_candidates)

# Starting the remote worker must preserve local candidates and include them in
# processed progress instead of resetting the audit result.
server.AI_MAPPING_JOBS["AIJOB-LOCAL"] = {
    "status": "QUEUED", "totalFields": 92, "processedFields": 90,
    "aiQueuedFields": 2, "localResolvedFields": 41, "localSuggestedIgnore": 49,
    "errors": [], "candidates": local_candidates,
}
try:
    server.ai_semantic_candidates = fast_semantic
    server._apply_ai_semantic_candidate = lambda source_id, item: item
    server._run_ai_semantic_job("AIJOB-LOCAL", source_id, routed_fields[:2], {"timeoutSeconds": 60}, [])
finally:
    server.ai_semantic_candidates = original_semantic
    server._apply_ai_semantic_candidate = original_apply
    server.MAPPINGS.clear()
    server.MAPPINGS.update(saved_mappings)
local_job = server.AI_MAPPING_JOBS.pop("AIJOB-LOCAL")
assert local_job["processedFields"] == 92 and len(local_job["candidates"]) == 92
assert local_job["localResolvedFields"] == 41 and local_job["localSuggestedIgnore"] == 49

print("V2.19 semantic performance tests: 26/26 passed")
