import server


source_id = "SOURCE-AI-JOB-TEST"
fields = [
    {"sourceField": "table.cash_extra", "dataType": "number"},
    {"sourceField": "table.profit_extra", "dataType": "number"},
] + [{"sourceField": f"table.misc_{index}", "dataType": "number"} for index in range(38)]

server.MAPPINGS.clear()
server.AI_MAPPING_JOBS.clear()
server.AI_MAPPING_CACHE.clear()
for index, field in enumerate(fields):
    mapping_id = f"MAP-{index}"
    server.MAPPINGS[mapping_id] = {
        "mappingId": mapping_id,
        "sourceId": source_id,
        "sourceField": field["sourceField"],
        "sourceColumn": field["sourceField"],
        "metricCode": "UNRESOLVED",
        "metricName": "尚未识别",
        "candidateSource": "RULE_UNRESOLVED",
        "status": "UNRESOLVED",
    }

job_id = "AIJOB-TEST"
server.AI_MAPPING_JOBS[job_id] = {
    "jobId": job_id, "sourceId": source_id, "status": "QUEUED",
    "totalFields": len(fields), "processedFields": 0, "candidates": [], "errors": [],
}
original_candidates = server.ai_mapping_candidates


def fake_candidates(config, batch, catalog):
    return [{
        "sourceField": field["sourceField"], "action": "MAP", "suggestedAction": "MAP",
        "metricCode": "CASH", "confidence": 0.75, "reason": "测试映射",
        "evidence": ["TEST"], "candidateSource": "AI", "status": "PENDING_REVIEW",
    } for field in batch]


original_path = server.AI_MAPPING_CACHE_PATH
test_cache = server.RUNS / "test-ai-mapping-cache.json"
try:
    test_cache.unlink(missing_ok=True)
    server.AI_MAPPING_CACHE_PATH = test_cache
    server.ai_mapping_candidates = fake_candidates
    server._run_ai_mapping_job(job_id, source_id, fields, {"provider": "test"})
    job = server.AI_MAPPING_JOBS[job_id]
    assert job["status"] == "SUCCEEDED"
    assert job["processedFields"] == 40
    assert job["aiQueuedFields"] == 2
    assert job["localSuggestedIgnore"] == 38
    assert job["completedBatches"] == 1
    assert len(job["candidates"]) == 40
    assert server.AI_MAPPING_CACHE_PATH.is_file()
    assert sum(1 for item in server.MAPPINGS.values() if item.get("suggestedAction") == "IGNORE") == 38
    assert sum(1 for item in server.MAPPINGS.values() if item.get("metricCode") == "CASH") == 2
    print("Financial sandbox V2.18 async AI mapping tests: 8/8 passed")
finally:
    server.ai_mapping_candidates = original_candidates
    server.AI_MAPPING_CACHE_PATH = original_path
    test_cache.unlink(missing_ok=True)
