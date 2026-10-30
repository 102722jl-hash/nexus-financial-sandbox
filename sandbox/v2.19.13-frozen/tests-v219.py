from v218_pipeline import active_graph, build_network_plan


def value(entity: str, code: str, amount: float, index: int) -> dict:
    return {
        "metricValueId": f"MV-{index}",
        "entityCode": entity,
        "metricCode": code,
        "value": amount,
        "reportPeriod": "20251231",
        "announcementDate": "20260430",
        "opdate": "2026-04-30",
        "dataCutoff": "2026-05-08",
        "evidenceId": f"EVD-{index}",
        "version": "2026-04-30",
    }


codes = {
    "REVENUE": 317_508_000_000,
    "OPERATING_COST": 286_000_000_000,
    "TOTAL_ASSETS": 410_000_000_000,
    "TOTAL_LIABILITIES": 180_000_000_000,
    "CASH": 24_000_000_000,
    "OPERATING_PROFIT": 18_000_000_000,
    "NET_PROFIT": 12_000_000_000,
    "OPERATING_CASH_FLOW": 26_000_000_000,
    "CAPEX": 12_000_000_000,
    "FREE_CASH_FLOW": 14_000_000_000,
}
values = [value("600019.SH", code, amount, index) for index, (code, amount) in enumerate(codes.items(), 1)]
plan = build_network_plan("SOURCE-GENERATED", values, "generated-financial", "CREATE_NEW_NETWORK", "宝钢披露网络")

assert plan["mode"] == "CREATE_NEW_NETWORK"
assert plan["networkKind"] == "FINANCIAL_DISCLOSURE_NETWORK"
assert plan["outputLevel"] == "EXPOSURE_ONLY"
assert plan["causalStatus"] == "ABSTAIN"
assert plan["networkName"] == "宝钢披露网络"
node_ids = {node["nodeId"] for node in plan["graph"]["nodes"]}
assert "import-snapshot" in node_ids and "entity-600019-sh" in node_ids
assert not {"cokingCoalPrice", "steelRawCost", "blastFurnacePool"} & node_ids
assert {node["layer"] for node in plan["graph"]["nodes"]} == {"macro", "demand", "route", "constraint", "chain", "company"}
statuses = {edge["status"] for edge in plan["graph"]["edges"]}
assert statuses <= {"CONFIRMED_LINEAGE", "CONFIRMED_STRUCTURE"}
assert any(edge["relationType"] == "ACCOUNTING_STRUCTURE" for edge in plan["graph"]["edges"])

nodes, edges = active_graph({**plan, "status": "ACTIVE"})
assert {node["nodeId"] for node in nodes} == node_ids
assert edges == plan["graph"]["edges"]
assert all(node.get("networkPlanId") == plan["networkPlanId"] for node in nodes)
print("Financial sandbox V2.19 generated network tests: 13/13 passed")
