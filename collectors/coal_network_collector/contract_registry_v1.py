"""Canonical metric and edge contracts used by node/graph builders."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent
VERSION = "1.0"

DEFINITIONS = {
    "COAL_PRICE_5500": ("动力煤5500K价格", 3, "price", "元/吨", 1, 1, "INDUSTRY"),
    "COAL_PRICE_5000": ("动力煤5000K价格", 3, "price", "元/吨", 1, 0, "INDUSTRY"),
    "POWER_CONSUMPTION": ("全社会用电量", 4, "flow", "亿千瓦时", 1, 0, "INDUSTRY"),
    "RAW_COAL_OUTPUT": ("原煤产量", 2, "flow", "万吨", 0, 0, "INDUSTRY"),
    "COAL_PROCUREMENT_VOLUME": ("煤炭采购量", 2, "flow", "万吨", 1, 0, "COMPANY"),
    "STANDARD_COAL_INPUT": ("入炉标煤量", 2, "flow", "万吨", 1, 0, "COMPANY"),
    "SUPPLY_COAL_CONSUMPTION": ("供电煤耗", 2, "ratio", "克/千瓦时", 1, 0, "COMPANY"),
    "STANDARD_COAL_PRICE": ("入炉标煤单价", 4, "price", "元/吨", 1, 1, "COMPANY"),
    "PLANT_USE_RATE": ("厂用电率", 4, "ratio", "%", 1, 0, "COMPANY"),
    "UTILIZATION_HOURS": ("平均利用小时", 4, "ratio", "小时", 1, 0, "COMPANY"),
    "THERMAL_UTILIZATION_HOURS": ("火电利用小时", 4, "ratio", "小时", 1, 0, "COMPANY"),
    "UTILIZATION_HOURS_THERMAL": ("火电利用小时", 4, "ratio", "小时", 1, 0, "COMPANY"),
    "CONTROLLABLE_CAPACITY": ("可控/控股装机容量", 4, "stock", "万千瓦", 1, 1, "COMPANY"),
    "INSTALLED_CAPACITY": ("装机容量", 4, "stock", "万千瓦", 1, 0, "COMPANY"),
    "THERMAL_CAPACITY": ("火电装机容量", 4, "stock", "万千瓦", 1, 1, "COMPANY"),
    "POWER_GENERATION": ("发电量", 4, "flow", "亿千瓦时", 1, 1, "COMPANY"),
    "THERMAL_POWER_GENERATION": ("火电发电量", 4, "flow", "亿千瓦时", 1, 1, "COMPANY"),
    "GRID_SALES_POWER": ("上网电量", 4, "flow", "亿千瓦时", 1, 1, "COMPANY"),
    "THERMAL_GRID_SALES_POWER": ("火电上网电量", 4, "flow", "亿千瓦时", 1, 0, "COMPANY"),
    "ON_GRID_TARIFF": ("平均上网电价", 4, "price", "元/兆瓦时", 1, 1, "COMPANY"),
    "REVENUE": ("营业收入", 5, "amount", "元", 0, 1, "COMPANY"),
    "OPERATING_COST": ("营业成本", 5, "amount", "元", 0, 1, "COMPANY"),
    "FUEL_COST": ("燃料成本", 5, "amount", "元", 0, 0, "COMPANY"),
    "FUEL_COST_PROXY": ("火电燃料成本代理", 5, "amount", "元", 0, 1, "COMPANY"),
    "DEPRECIATION_AMORTIZATION": ("折旧及摊销", 5, "amount", "元", 0, 0, "COMPANY"),
    "NET_PROFIT": ("归母净利润", 5, "amount", "元", 0, 1, "COMPANY"),
    "OPERATING_CASH_FLOW": ("经营现金流", 5, "amount", "元", 0, 1, "COMPANY"),
    "CAPEX": ("现金资本开支", 5, "amount", "元", 0, 1, "COMPANY"),
    "FIXED_ASSET_INVESTMENT": ("固定资产投资", 5, "amount", "元", 0, 0, "COMPANY"),
    "TOTAL_ASSETS": ("资产总额", 5, "amount", "元", 0, 0, "COMPANY"),
    "TOTAL_LIABILITIES": ("负债合计", 5, "amount", "元", 0, 0, "COMPANY"),
    "CASH": ("货币资金", 5, "amount", "元", 0, 1, "COMPANY"),
    "SHORT_TERM_DEBT": ("短期借款", 5, "amount", "元", 0, 1, "COMPANY"),
    "CURRENT_NONCURRENT_DEBT": ("一年内到期的非流动负债", 5, "amount", "元", 0, 1, "COMPANY"),
    "LONG_TERM_DEBT": ("长期借款", 5, "amount", "元", 0, 1, "COMPANY"),
    "BONDS_PAYABLE": ("应付债券", 5, "amount", "元", 0, 1, "COMPANY"),
    "DISCLOSED_DEBT_COMPONENTS": ("已披露债务构成合计", 5, "amount", "元", 0, 1, "COMPANY"),
    "NET_DEBT_PROXY": ("净债务代理", 5, "amount", "元", 0, 1, "COMPANY"),
    "FREE_CASH_FLOW_PROXY": ("自由现金流代理", 5, "amount", "元", 0, 1, "COMPANY"),
    "SHARE_CAPITAL": ("股本", 6, "stock", "股", 0, 1, "COMPANY"),
    "CLOSE_PRICE": ("收盘价", 6, "price", "元/股", 1, 1, "COMPANY"),
    "CURRENT_MARKET_CAP": ("当前市值", 6, "amount", "元", 0, 1, "COMPANY"),
}

TEMPLATES = [
    ("industry_coal_to_company_coal", "COAL_PRICE_5500", "STANDARD_COAL_PRICE", "PRICE_BASIS_BRIDGE", "PRICE_EXPOSURE", ["COAL_PRICE_5500"], ["COAL_PRICE_5500"], "行业煤价通过 beta 传导到公司入炉标煤价"),
    ("capacity_to_generation", "CONTROLLABLE_CAPACITY", "POWER_GENERATION", "CAPACITY_UTILIZATION", "OPERATING_IDENTITY", ["CONTROLLABLE_CAPACITY", "UTILIZATION_HOURS"], ["CONTROLLABLE_CAPACITY", "UTILIZATION_HOURS"], "装机容量乘利用小时形成发电量"),
    ("thermal_capacity_to_generation", "THERMAL_CAPACITY", "THERMAL_POWER_GENERATION", "CAPACITY_UTILIZATION", "OPERATING_IDENTITY", ["THERMAL_CAPACITY", "THERMAL_UTILIZATION_HOURS"], ["THERMAL_CAPACITY", "THERMAL_UTILIZATION_HOURS"], "火电装机乘火电利用小时形成火电发电量"),
    ("generation_to_grid_sales", "POWER_GENERATION", "GRID_SALES_POWER", "POWER_BALANCE", "OPERATING_IDENTITY", ["POWER_GENERATION", "PLANT_USE_RATE"], ["POWER_GENERATION", "PLANT_USE_RATE"], "发电量扣除厂用电形成上网电量"),
    ("grid_sales_to_revenue", "GRID_SALES_POWER", "REVENUE", "REVENUE_BRIDGE", "OPERATING_TO_FINANCIAL", ["GRID_SALES_POWER", "ON_GRID_TARIFF"], ["GRID_SALES_POWER", "ON_GRID_TARIFF"], "上网电量乘上网电价形成售电收入"),
    ("thermal_to_fuel_cost", "THERMAL_POWER_GENERATION", "FUEL_COST_PROXY", "FUEL_COST_IDENTITY", "CALCULATED_LINEAGE", ["THERMAL_POWER_GENERATION", "SUPPLY_COAL_CONSUMPTION", "STANDARD_COAL_PRICE"], ["THERMAL_POWER_GENERATION", "SUPPLY_COAL_CONSUMPTION", "STANDARD_COAL_PRICE"], "火电发电量、煤耗和标煤价形成燃料成本代理"),
    ("fuel_to_cost", "FUEL_COST_PROXY", "OPERATING_COST", "COST_PASS_THROUGH", "COST_PRESSURE", ["FUEL_COST_PROXY"], ["FUEL_COST_PROXY"], "燃料成本变动传导到营业成本"),
    ("revenue_cost_to_profit", "REVENUE", "NET_PROFIT", "MARGIN_BRIDGE", "ACCOUNTING_STRUCTURE", ["REVENUE", "OPERATING_COST"], ["REVENUE", "OPERATING_COST"], "收入和营业成本形成利润变化代理"),
    ("cashflow_to_fcf", "OPERATING_CASH_FLOW", "FREE_CASH_FLOW_PROXY", "CASH_FLOW_IDENTITY", "CALCULATED_LINEAGE", ["OPERATING_CASH_FLOW", "CAPEX"], ["OPERATING_CASH_FLOW", "CAPEX"], "经营现金流减资本开支"),
    ("debt_to_net_debt", "DISCLOSED_DEBT_COMPONENTS", "NET_DEBT_PROXY", "ACCOUNTING_IDENTITY", "CALCULATED_LINEAGE", ["DISCLOSED_DEBT_COMPONENTS", "CASH"], ["DISCLOSED_DEBT_COMPONENTS", "CASH"], "债务构成减货币资金"),
    ("price_shares_to_market_cap", "CLOSE_PRICE", "CURRENT_MARKET_CAP", "MARKET_CAP_IDENTITY", "CALCULATED_LINEAGE", ["CLOSE_PRICE", "SHARE_CAPITAL"], ["CLOSE_PRICE", "SHARE_CAPITAL"], "股价乘股本形成市值"),
]


def ensure(db: sqlite3.Connection) -> dict:
    db.executescript((ROOT / "complete_schema.sql").read_text(encoding="utf-8"))
    for code, (name, layer, metric_type, unit, editable, required, scope) in DEFINITIONS.items():
        db.execute(
            """INSERT INTO metric_definitions(
            metric_code,metric_name_cn,layer_no,metric_type,canonical_unit,
            editable_default,required_for_network,entity_scope,description,
            contract_version,status)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(metric_code) DO UPDATE SET
              metric_name_cn=excluded.metric_name_cn,layer_no=excluded.layer_no,
              metric_type=excluded.metric_type,canonical_unit=excluded.canonical_unit,
              editable_default=excluded.editable_default,
              required_for_network=excluded.required_for_network,
              entity_scope=excluded.entity_scope,contract_version=excluded.contract_version,
              status=excluded.status""",
            (code, name, layer, metric_type, unit, editable, required, scope, f"{name}的标准化字段契约", VERSION, "ACTIVE"),
        )
    for template_id, source, target, ftype, relation, required, editable, desc in TEMPLATES:
        db.execute(
            """INSERT INTO network_edge_templates(
            template_id,source_metric_code,target_metric_code,formula_type,
            relation_type,required_inputs_json,editable_inputs_json,description,
            contract_version,status)
            VALUES(?,?,?,?,?,?,?,?,?,'ACTIVE')
            ON CONFLICT(template_id) DO UPDATE SET
              source_metric_code=excluded.source_metric_code,
              target_metric_code=excluded.target_metric_code,
              formula_type=excluded.formula_type,relation_type=excluded.relation_type,
              required_inputs_json=excluded.required_inputs_json,
              editable_inputs_json=excluded.editable_inputs_json,
              description=excluded.description,contract_version=excluded.contract_version,
              status=excluded.status""",
            (template_id, source, target, ftype, relation, json.dumps(required, ensure_ascii=False), json.dumps(editable, ensure_ascii=False), desc, VERSION),
        )
    db.commit()
    return {"metric_definitions": len(DEFINITIONS), "edge_templates": len(TEMPLATES)}


if __name__ == "__main__":
    connection = sqlite3.connect(ROOT / "coal_network.db")
    print(json.dumps(ensure(connection), ensure_ascii=False, indent=2))
    connection.close()
