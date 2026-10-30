from v218_pipeline import active_graph, build_network_plan


def metric(entity: str, code: str, value: float, evidence: str) -> dict:
    return {
        "metricValueId": f"MV-{entity}-{code}",
        "entityCode": entity,
        "metricCode": code,
        "value": value,
        "reportPeriod": "20251231",
        "announcementDate": "20260430",
        "opdate": "20260430",
        "evidenceId": evidence,
    }


values = [
    metric("600019.SH", "REVENUE", 317_508_000_000, "EVD-BAOSTEEL"),
    metric("999999.SH", "REVENUE", 1_000_000, "EVD-UNKNOWN"),
]
plan = build_network_plan("SOURCE-RUNTIME-TEST", values)
assert plan["diff"]["updatedNodes"][0]["nodeId"] == "baosteel"
assert plan["diff"]["addedNodes"][0]["status"] == "COMPANY_ADAPTER_REQUIRED"

nodes, edges = active_graph({**plan, "status": "ACTIVE"})
by_id = {node["nodeId"]: node for node in nodes}
assert by_id["baosteel"]["status"] == "CONFIRMED"
assert by_id["company-999999-sh"]["status"] == "COMPANY_ADAPTER_REQUIRED"
assert {"cokingCoalPrice", "steelRawCost", "steelOrders", "blastFurnacePool"}.issubset(by_id)
assert any(edge["targetNodeId"] == "baosteel" for edge in edges)
assert not any(edge["targetNodeId"] == "company-999999-sh" for edge in edges)
assert all(edge["status"] == "CONFIRMED" for edge in edges)
print("Financial sandbox V2.18 runtime graph tests: 9/9 passed")
