import json

import ai_adapter


calls = []
original_request = ai_adapter._request


def fake_request(config, method, path, body=None):
    calls.append({"method": method, "path": path, "body": json.loads(json.dumps(body)) if body else body})
    if path.endswith("/models"):
        return {"data": [{"id": "claude-sonnet-4-5"}]}
    if body and "response_format" in body:
        raise ai_adapter.AIAdapterError("INVALID_RESPONSE", "HTTP 400", 400)
    user = body["messages"][-1]["content"] if body else ""
    if "metricCatalog" in user:
        request = json.loads(user)
        candidates = [
            {"sourceField": field["sourceField"], "action": "MAP", "metricCode": "REVENUE", "confidence": 0.7, "reason": "测试候选"}
            for field in request["fields"]
        ]
        content = json.dumps({"candidates": candidates}, ensure_ascii=False)
    else:
        content = '{"ok":true}'
    fence = chr(96) * 3
    return {"choices": [{"message": {"content": fence + "json\n" + content + "\n" + fence}}]}


try:
    ai_adapter._request = fake_request
    config, result = ai_adapter.test_session({
        "provider": "openai-compatible",
        "baseUrl": "https://example.test/v1",
        "model": "claude-sonnet-4-5",
        "apiKey": "not-logged",
        "timeoutSeconds": 30,
    })
    assert result["status"] == "CONNECTED"
    assert result["chatVerified"] is True
    assert any(call["body"] and "response_format" in call["body"] for call in calls if call["method"] == "POST")
    assert any(call["body"] and "response_format" not in call["body"] for call in calls if call["method"] == "POST")

    fields = [{"sourceField": f"table.field_{index}", "dataType": "number"} for index in range(30)]
    catalog = [{"metricCode": "REVENUE", "metricName": "营业收入", "metricType": "flow"}]
    candidates = ai_adapter.mapping_candidates(config, fields, catalog)
    assert len(candidates) == 8
    assert all(item["status"] == "PENDING_REVIEW" for item in candidates)
    assert all(item["candidateSource"] == "AI" for item in candidates)
    print("Financial sandbox V2.18 AI adapter tests: 8/8 passed")
finally:
    ai_adapter._request = original_request
