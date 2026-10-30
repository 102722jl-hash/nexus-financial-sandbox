from db_connectors import table_adapters
from v218_pipeline import (
    _extract_columnar_precompiled_controls,
    _mapping_by_table,
    _row_values,
    auto_confirm_precompiled_candidates,
    build_network_plan,
    rule_candidates,
    stable_id,
    table_adapter_candidates,
)


TABLE = "sandbox_ai_network_company_2024_v1"
SOURCE = "SOURCE-WORK-COLUMNAR"


def profile(name: str, dtype: str = "text") -> dict:
    locator = {"database": "work", "schema": "work", "table": TABLE, "column": name}
    return {
        "column": f"work.work.{TABLE}.{name}", "columnName": name, "tableName": TABLE,
        "schemaName": "work", "databaseName": "work", "sourceLocator": locator,
        "dtype": dtype, "sampleNonNull": 10, "numericSampleRate": 1.0 if dtype == "numeric" else 0.0,
        "sampleValues": [100] if dtype == "numeric" else ["sample"],
    }


text_fields = [
    "record_id", "company_code", "company_name", "report_period", "actual_ann_dt", "currency",
    "editable_metric_name", "editable_metric_type", "editable_metric_unit",
]
numeric_fields = [
    "revenue", "operating_cost", "gross_profit", "operating_profit", "net_profit",
    "operating_cash_flow", "capex", "free_cash_flow", "cash", "ending_cash", "inventory",
    "accounts_receivable", "total_assets", "total_liabilities", "short_term_debt", "long_term_debt",
    "bonds_payable", "lease_liability", "total_debt", "net_debt", "equity", "total_shares",
    "revenue_growth_pct", "net_profit_growth_pct", "gross_margin_pct", "operating_margin_pct",
    "net_margin_pct", "fcf_margin_pct", "asset_liability_ratio_pct", "chain_layer_no",
    "editable_baseline_value", "driver_sensitivity", "lag_days", "impact_cap_pct",
]
columns = [profile(name) for name in text_fields] + [profile(name, "numeric") for name in numeric_fields]
adapters = table_adapters("work", "work", [TABLE], columns)
assert adapters[0]["adapterMode"] == "PRECOMPILED_NETWORK_COLUMNS"
assert set(adapters[0]["columnarControlFields"]) >= {
    "editable_metric_name", "editable_metric_type", "editable_metric_unit", "editable_baseline_value",
    "driver_sensitivity", "lag_days", "impact_cap_pct", "chain_layer_no", "record_id",
}

candidates = rule_candidates(columns, SOURCE, "CREATE_NEW_NETWORK")
candidates += table_adapter_candidates(adapters, candidates, SOURCE, "CREATE_NEW_NETWORK")
summary = auto_confirm_precompiled_candidates(adapters, candidates)
assert summary["detected"] is True
assert summary["adapterModes"] == ["PRECOMPILED_NETWORK_COLUMNS"]
assert summary["needsReview"] == 0
assert all(item["status"] == "CONFIRMED" for item in candidates)
by_column = {item.get("columnName"): item for item in candidates}
expected = {
    "total_assets": ("TOTAL_ASSETS", "资产总额"),
    "total_liabilities": ("TOTAL_LIABILITIES", "负债总额"),
    "short_term_debt": ("SHORT_TERM_DEBT", "短期借款"),
    "long_term_debt": ("LONG_TERM_DEBT", "长期借款"),
    "gross_profit": ("GROSS_PROFIT", "毛利润"),
    "net_debt": ("NET_DEBT", "净债务"),
    "gross_margin_pct": ("GROSS_MARGIN_PCT", "毛利率"),
    "asset_liability_ratio_pct": ("ASSET_LIABILITY_RATIO_PCT", "资产负债率"),
    "editable_metric_name": ("NETWORK_EDITABLE_METRIC_NAME", "可调指标名称"),
    "driver_sensitivity": ("NETWORK_DRIVER_SENSITIVITY", "驱动敏感度"),
    "lag_days": ("NETWORK_LAG_DAYS", "传导滞后天数"),
    "impact_cap_pct": ("NETWORK_IMPACT_CAP_PCT", "影响幅度上限"),
}
for column, contract in expected.items():
    assert (by_column[column]["metricCode"], by_column[column]["metricName"]) == contract

grouped = _mapping_by_table(candidates, "work", "work")
mappings = grouped[("work", TABLE)]
rows = []
for index in range(10):
    rows.append({
        "record_id": index + 1, "company_code": f"COMPANY-{index + 1:02d}", "company_name": f"测试公司{index + 1:02d}",
        "report_period": "2024-12-31", "actual_ann_dt": "2025-03-31", "currency": "CNY",
        "revenue": 1000 + index, "operating_cost": 700 + index, "gross_profit": 300,
        "operating_profit": 180, "net_profit": 120, "operating_cash_flow": 160,
        "capex": 60, "free_cash_flow": 100, "cash": 250, "ending_cash": 240,
        "inventory": 80, "accounts_receivable": 90, "total_assets": 2000,
        "total_liabilities": 800, "short_term_debt": 100, "long_term_debt": 160,
        "bonds_payable": 40, "lease_liability": 20, "total_debt": 320, "net_debt": 70,
        "equity": 1200, "total_shares": 500, "revenue_growth_pct": 12,
        "net_profit_growth_pct": 15, "gross_margin_pct": 30, "operating_margin_pct": 18,
        "net_margin_pct": 12, "fcf_margin_pct": 10, "asset_liability_ratio_pct": 40,
        "chain_layer_no": 3, "editable_metric_name": "AI服务器资本开支",
        "editable_metric_type": "demand", "editable_metric_unit": "%", "editable_baseline_value": 100,
        "driver_sensitivity": [0.5, 0.9, 0.4, 0.65, 0.35, 0.3, 0.8, 0.55, 0.75, 0.85][index],
        "lag_days": [120, 60, 90, 90, 90, 180, 60, 180, 90, 90][index],
        "impact_cap_pct": [20, 35, 20, 25, 18, 15, 30, 25, 30, 35][index],
    })

snapshot = stable_id("SNAP", {"source": SOURCE})
values, _, rejected = _row_values(rows, mappings, SOURCE, "2025-05-01", snapshot, f"work.{TABLE}")
assert not rejected
assert not any(item["metricCode"].startswith("NETWORK_") for item in values)
assert {item["valueStatus"] for item in values if item["metricCode"].endswith("_PCT")} == {"CALCULATED_RESULT"}
controls = _extract_columnar_precompiled_controls(rows, mappings, f"work.{TABLE}")
assert controls["validationStatus"] == "VALIDATED" and controls["rowCount"] == 10

plan = build_network_plan(SOURCE, values, "generated", "CREATE_NEW_NETWORK", "AI公司对标网络", None, controls)
assert plan["networkKind"] == "PRECOMPILED_COLUMN_NETWORK"
assert plan["outputLevel"] == "SCENARIO_PATH_ONLY" and plan["simulationReady"] is True
driver_nodes = [item for item in plan["graph"]["nodes"] if item.get("editableDefinition")]
parameter_edges = [item for item in plan["graph"]["edges"] if item.get("relationType") == "PRECOMPILED_PARAMETER_EDGE"]
assert len(driver_nodes) == 1 and driver_nodes[0]["label"] == "AI服务器资本开支"
assert len(parameter_edges) == 10
assert {item["lagDays"] for item in parameter_edges} == {60, 90, 120, 180}
assert max(item["impactCapPct"] for item in parameter_edges) == 35
labels = {item["label"] for item in plan["graph"]["nodes"]}
assert "total_liabilities" not in labels and "driver_sensitivity" not in labels and "editable_baseline_value" not in labels
assert {"负债总额", "短期借款", "长期借款", "毛利率", "资产负债率"}.issubset(labels)

print("V2.19 work columnar network adapter tests: 45/45 passed")
