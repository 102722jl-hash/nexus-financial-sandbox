"""Build multi-path nodes from current accepted and calculated metrics."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent
NETWORK_ID = "coal_power_v1"

METRICS = {
    "RAW_COAL_OUTPUT": (2, "原煤产量", "flow"),
    "COAL_PRICE_5500": (3, "动力煤5500K价格", "price"),
    "COAL_PRICE_5000": (3, "动力煤5000K价格", "price"),
    "POWER_CONSUMPTION": (4, "全社会用电量", "flow"),
    "STANDARD_COAL_PRICE": (4, "入炉标煤单价", "price"),
    "COAL_PROCUREMENT_VOLUME": (2, "煤炭采购量", "flow"),
    "STANDARD_COAL_INPUT": (2, "入炉标煤量", "flow"),
    "SUPPLY_COAL_CONSUMPTION": (2, "供电煤耗", "ratio"),
    "PLANT_USE_RATE": (4, "厂用电率", "ratio"),
    "UTILIZATION_HOURS": (4, "平均利用小时", "ratio"),
    "UTILIZATION_HOURS_THERMAL": (4, "火电利用小时", "ratio"),
    "THERMAL_UTILIZATION_HOURS": (4, "火电利用小时", "ratio"),
    "CONTROLLABLE_CAPACITY": (4, "可控/控股装机容量", "stock"),
    "INSTALLED_CAPACITY": (4, "装机容量", "stock"),
    "THERMAL_CAPACITY": (4, "火电装机容量", "stock"),
    "POWER_GENERATION": (4, "发电量", "flow"),
    "THERMAL_POWER_GENERATION": (4, "火电发电量", "flow"),
    "GRID_SALES_POWER": (4, "上网电量", "flow"),
    "THERMAL_GRID_SALES_POWER": (4, "火电上网电量", "flow"),
    "ON_GRID_TARIFF": (1, "平均上网电价", "price"),
    "REVENUE": (5, "营业收入", "amount"),
    "OPERATING_COST": (5, "营业成本", "amount"),
    "FUEL_COST": (5, "燃料成本", "amount"),
    "FUEL_COST_PROXY": (5, "火电燃料成本代理", "amount"),
    "DEPRECIATION_AMORTIZATION": (5, "折旧及摊销", "amount"),
    "NET_PROFIT": (5, "归母净利润", "amount"),
    "OPERATING_CASH_FLOW": (5, "经营现金流", "amount"),
    "CAPEX": (5, "现金资本开支", "amount"),
    "FIXED_ASSET_INVESTMENT": (5, "固定资产投资", "amount"),
    "CASH": (5, "货币资金", "amount"),
    "SHORT_TERM_DEBT": (5, "短期借款", "amount"),
    "CURRENT_NONCURRENT_DEBT": (5, "一年内到期的非流动负债", "amount"),
    "LONG_TERM_DEBT": (5, "长期借款", "amount"),
    "BONDS_PAYABLE": (5, "应付债券", "amount"),
    "DISCLOSED_DEBT_COMPONENTS": (5, "已披露债务构成合计", "amount"),
    "NET_DEBT_PROXY": (5, "净债务代理", "amount"),
    "FREE_CASH_FLOW_PROXY": (5, "自由现金流代理", "amount"),
    "SHARE_CAPITAL": (6, "股本", "stock"),
    "CLOSE_PRICE": (6, "收盘价", "price"),
    "CURRENT_MARKET_CAP": (6, "当前市值", "amount"),
}

EDITABLE = {
    "COAL_PRICE_5500", "COAL_PRICE_5000", "POWER_CONSUMPTION",
    "STANDARD_COAL_PRICE", "COAL_PROCUREMENT_VOLUME", "STANDARD_COAL_INPUT",
    "SUPPLY_COAL_CONSUMPTION", "PLANT_USE_RATE", "UTILIZATION_HOURS",
    "UTILIZATION_HOURS_THERMAL", "THERMAL_UTILIZATION_HOURS",
    "CONTROLLABLE_CAPACITY", "INSTALLED_CAPACITY", "THERMAL_CAPACITY",
    "POWER_GENERATION", "THERMAL_POWER_GENERATION", "GRID_SALES_POWER",
    "THERMAL_GRID_SALES_POWER", "ON_GRID_TARIFF", "CLOSE_PRICE",
}


def node_id(code: str, entity: str | None) -> str:
    return "node_" + hashlib.sha256(f"{code}|{entity or 'INDUSTRY'}".encode()).hexdigest()[:18]


def latest(db: sqlite3.Connection, code: str, entity: str | None):
    return db.execute(
        """SELECT value,unit,currency,as_of_date,data_cutoff,value_status,evidence_id
        FROM metric_values WHERE network_id=? AND metric_code=? AND entity_code IS ?
        AND value IS NOT NULL AND value_status IN ('SOURCE_FACT','MARKET_PROXY','CALCULATED')
        ORDER BY CASE
                   WHEN source_table='deep_financial_report_v3' THEN 0
                   WHEN source_table='calculated_metrics_v3' THEN 0
                   WHEN source_table='financial_report' THEN 1
                   WHEN source_table='company_announcement' THEN 2
                   ELSE 3 END,
          COALESCE(as_of_date,report_period,data_cutoff) DESC,
          metric_value_id DESC LIMIT 1""",
        (NETWORK_ID, code, entity),
    ).fetchone()


def build(db: sqlite3.Connection) -> dict:
    pairs = db.execute(
        """SELECT DISTINCT metric_code,entity_code FROM metric_values
        WHERE network_id=? AND value_status IN ('SOURCE_FACT','MARKET_PROXY','CALCULATED')""",
        (NETWORK_ID,),
    ).fetchall()
    created = updated = 0
    for code, entity in pairs:
        if code not in METRICS:
            continue
        row = latest(db, code, entity)
        if not row:
            continue
        value, unit, currency, as_of, cutoff, value_status, evidence = row
        layer, name, metric_type = METRICS[code]
        definition = db.execute(
            """SELECT layer_no,metric_name_cn,metric_type,canonical_unit,editable_default
            FROM metric_definitions WHERE metric_code=?""", (code,)
        ).fetchone()
        if definition:
            layer, name, metric_type, _canonical_unit, editable_default = definition
        else:
            editable_default = int(code in EDITABLE)
        entity_name = ""
        if entity:
            found = db.execute(
                "SELECT entity_name_cn FROM entities WHERE network_id=? AND entity_code=?",
                (NETWORK_ID, entity),
            ).fetchone()
            entity_name = (found[0] if found else entity) + " · "
        identifier = node_id(code, entity)
        baseline = json.dumps(
            {"BASE": value, "as_of_date": as_of, "evidence_id": evidence},
            ensure_ascii=False,
        )
        exists = db.execute(
            "SELECT status FROM network_nodes WHERE network_id=? AND node_id=?",
            (NETWORK_ID, identifier),
        ).fetchone()
        if exists:
            status = exists[0] if exists[0] in ("CONFIRMED", "ACTIVE", "APPROVED") else "AI_CANDIDATE"
            db.execute(
                """UPDATE network_nodes SET layer_no=?,node_name_cn=?,node_description=?,
                node_type='METRIC',metric_code=?,metric_name=?,metric_type=?,unit=?,currency=?,
                baseline_value=?,editable=?,value_status=?,entity_code=?,evidence_id=?,
                data_cutoff=?,status=? WHERE network_id=? AND node_id=?""",
                (
                    layer, entity_name + name, "由已接受事实或可回算公式自动生成",
                    code, name, metric_type, unit, currency, baseline,
                    int(editable_default), value_status, entity, evidence,
                    cutoff, status, NETWORK_ID, identifier,
                ),
            )
            updated += 1
        else:
            db.execute(
                """INSERT INTO network_nodes(
                network_id,node_id,layer_no,node_name_cn,node_description,node_type,
                metric_code,metric_name,metric_type,unit,currency,baseline_value,
                editable,value_status,entity_code,evidence_id,data_cutoff,status)
                VALUES(?,?,?,?,?,'METRIC',?,?,?,?,?,?,?,?,?,?,?,'AI_CANDIDATE')""",
                (
                    NETWORK_ID, identifier, layer, entity_name + name,
                    "由已接受事实或可回算公式自动生成", code, name, metric_type,
                    unit, currency, baseline, int(editable_default), value_status,
                    entity, evidence, cutoff,
                ),
            )
            db.execute(
                """INSERT INTO review_queue(
                object_type,object_id,candidate_value,confidence,reason,evidence_ids,
                required_action,review_status,created_at)
                VALUES(?,?,?,?,?,?,?,'PENDING',datetime('now'))""",
                (
                    "NODE", identifier,
                    json.dumps({"layer_no": layer, "name": entity_name + name}, ensure_ascii=False),
                    0.95, "AUDITABLE_METRIC_MAPPING", json.dumps([evidence]),
                    "AI审核节点映射",
                ),
            )
            created += 1
    db.execute(
        """UPDATE network_registry SET
        network_name='煤炭-电力经营-财务-现金流-估值多链路传导网络',
        network_version='4.0',network_kind='MULTI_PATH'
        WHERE network_id=?""",
        (NETWORK_ID,),
    )
    db.commit()
    return {"nodes_created": created, "nodes_updated": updated}


if __name__ == "__main__":
    connection = sqlite3.connect(ROOT / "coal_network.db")
    connection.execute("PRAGMA foreign_keys=ON")
    print(json.dumps(build(connection), ensure_ascii=False, indent=2))
    connection.close()
