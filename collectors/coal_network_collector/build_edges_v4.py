"""Build auditable multi-input transmission paths for each company."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from build_nodes_v3 import NETWORK_ID
from status_policy_v2 import USABLE_STATUSES, placeholders

ROOT = Path(__file__).parent


def stable(prefix: str, *parts: str) -> str:
    return prefix + hashlib.sha256("|".join(parts).encode()).hexdigest()[:18]


def node_map(db: sqlite3.Connection):
    rows = db.execute(
        f"""SELECT node_id,metric_code,entity_code FROM network_nodes
        WHERE network_id=? AND status IN ({placeholders(USABLE_STATUSES)})""",
        (NETWORK_ID, *USABLE_STATUSES),
    ).fetchall()
    return {(code, entity): node for node, code, entity in rows}


def add_group(
    db: sqlite3.Connection,
    nodes: dict,
    entity: str,
    target_code: str,
    input_codes: list[tuple[str, float]],
    expression: str,
    formula_type: str,
    relation_type: str,
    mechanism: str,
    exact: bool = False,
) -> int:
    target = nodes.get((target_code, entity))
    inputs = [(nodes.get((code, entity)), code, coefficient) for code, coefficient in input_codes]
    if not target or any(not node for node, _code, _coefficient in inputs):
        return 0
    parameter_status = "CALCULATED_LINEAGE" if exact else "AI_ASSUMPTION"
    confidence = 0.99 if exact else 0.65
    formula_id = stable("formula_", target, expression)
    params = json.dumps(
        {
            "required_inputs": [
                {"metric_code": code, "coefficient": coefficient}
                for _node, code, coefficient in inputs
            ],
            "editable_inputs": [code for _node, code, _coefficient in inputs],
            "status": "READY" if exact else "REQUIRES_CALIBRATION",
            "causal_conclusion": "ABSTAIN",
            "calculation_kind": "ACCOUNTING_IDENTITY" if exact else "SCENARIO_PROXY",
        },
        ensure_ascii=False,
    )
    db.execute(
        """INSERT INTO formulas(
        network_id,formula_id,formula_type,formula_expression,parameters_json,
        formula_version,parameter_status,lag_days,impact_cap_pct,
        invalidation_condition,status)
        VALUES(?,?,?,?,?,'4.0',?,0,?,?,'CANDIDATE')
        ON CONFLICT(formula_id) DO UPDATE SET
          formula_type=excluded.formula_type,
          formula_expression=excluded.formula_expression,
          parameters_json=excluded.parameters_json,
          formula_version=excluded.formula_version,
          parameter_status=excluded.parameter_status,
          impact_cap_pct=excluded.impact_cap_pct,
          invalidation_condition=excluded.invalidation_condition,
          status='CANDIDATE'""",
        (
            NETWORK_ID, formula_id, formula_type, expression, params,
            parameter_status, None if exact else 0.25,
            "任一输入缺失、单位不匹配或披露口径发生变化",
        ),
    )
    made = 0
    for source, code, coefficient in inputs:
        existing = db.execute(
            """SELECT edge_id FROM network_edges
            WHERE network_id=? AND source_node_id=? AND target_node_id=?
            ORDER BY edge_id LIMIT 1""",
            (NETWORK_ID, source, target),
        ).fetchone()
        edge_id = existing[0] if existing else stable("edge_", source, target, formula_id)
        edge_params = json.dumps(
            {
                "input_metric_code": code,
                "coefficient": coefficient,
                "formula_inputs": json.loads(params)["required_inputs"],
                "causal_conclusion": "ABSTAIN",
            },
            ensure_ascii=False,
        )
        if existing:
            db.execute(
                """UPDATE network_edges SET direction='FORWARD',relation_type=?,
                formula_id=?,formula_type=?,weight=?,lag_days=0,impact_cap_pct=?,
                confidence=?,mechanism=?,parameter_status=?,evidence_source=?,
                parameters_json=?,status='CANDIDATE'
                WHERE network_id=? AND edge_id=?""",
                (
                    relation_type, formula_id, formula_type, coefficient,
                    None if exact else 0.25, confidence, mechanism, parameter_status,
                    "CALCULATED_LINEAGE" if exact else "AI_MECHANISM_CANDIDATE",
                    edge_params, NETWORK_ID, edge_id,
                ),
            )
        else:
            db.execute(
                """INSERT INTO network_edges(
                network_id,edge_id,source_node_id,target_node_id,direction,
                relation_type,formula_id,formula_type,weight,lag_days,impact_cap_pct,
                confidence,mechanism,parameter_status,evidence_source,parameters_json,status)
                VALUES(?,?,?,?,'FORWARD',?,?,?,?,0,?,?,?,?,?,?,'CANDIDATE')""",
                (
                    NETWORK_ID, edge_id, source, target, relation_type, formula_id,
                    formula_type, coefficient, None if exact else 0.25, confidence,
                    mechanism, parameter_status,
                    "CALCULATED_LINEAGE" if exact else "AI_MECHANISM_CANDIDATE",
                    edge_params,
                ),
            )
            made += 1
        db.execute(
            """INSERT INTO review_queue(
            object_type,object_id,candidate_value,confidence,reason,evidence_ids,
            required_action,review_status,created_at)
            SELECT 'EDGE',?,?,?,?,?,'AI审核关系、公式和参数','PENDING',datetime('now')
            WHERE NOT EXISTS(
              SELECT 1 FROM review_queue WHERE object_type='EDGE' AND object_id=?
              AND reason='MULTI_PATH_FORMULA_V4')""",
            (
                edge_id,
                json.dumps({"formula_id": formula_id, "input": code, "target": target_code}, ensure_ascii=False),
                confidence, "MULTI_PATH_FORMULA_V4", "[]", edge_id,
            ),
        )
    return made


def add_industry_exposure(
    db: sqlite3.Connection, nodes: dict, entity: str, company_price: str
) -> int:
    target = nodes.get((company_price, entity))
    if not target:
        return 0
    made = 0
    for industry_code in ("COAL_PRICE_5500", "COAL_PRICE_5000"):
        source = nodes.get((industry_code, None))
        if not source:
            continue
        formula_id = stable("formula_", source, target, "coal-basis")
        params = json.dumps(
            {
                "basis": "company_standard_coal_price - industry_coal_price",
                "status": "REQUIRES_HISTORICAL_CALIBRATION",
                "causal_conclusion": "ABSTAIN",
            },
            ensure_ascii=False,
        )
        db.execute(
            """INSERT OR IGNORE INTO formulas(
            network_id,formula_id,formula_type,formula_expression,parameters_json,
            formula_version,parameter_status,lag_days,impact_cap_pct,
            invalidation_condition,status)
            VALUES(?,?,?,'company_coal_price_change = industry_coal_price_change * beta',
            ?,'4.0','AI_ASSUMPTION',0,0.25,'煤种、热值或采购结构不可比','CANDIDATE')""",
            (NETWORK_ID, formula_id, "PRICE_BASIS_BRIDGE", params),
        )
        existing = db.execute(
            """SELECT edge_id FROM network_edges WHERE network_id=?
            AND source_node_id=? AND target_node_id=?""",
            (NETWORK_ID, source, target),
        ).fetchone()
        if existing:
            continue
        edge_id = stable("edge_", source, target, formula_id)
        db.execute(
            """INSERT INTO network_edges(
            network_id,edge_id,source_node_id,target_node_id,direction,relation_type,
            formula_id,formula_type,weight,lag_days,impact_cap_pct,confidence,mechanism,
            parameter_status,evidence_source,parameters_json,status)
            VALUES(?,?,?,?,'FORWARD','PRICE_EXPOSURE',?,'PRICE_BASIS_BRIDGE',1,0,
            0.25,0.6,'行业煤价向公司入炉标煤价传导','AI_ASSUMPTION',
            'AI_MECHANISM_CANDIDATE',?,'CANDIDATE')""",
            (NETWORK_ID, edge_id, source, target, formula_id, params),
        )
        made += 1
    return made


def build(db: sqlite3.Connection) -> dict:
    nodes = node_map(db)
    entities = sorted({entity for _code, entity in nodes if entity})
    created = 0
    for entity in entities:
        created += add_industry_exposure(db, nodes, entity, "STANDARD_COAL_PRICE")
        groups = [
            ("POWER_GENERATION", [("CONTROLLABLE_CAPACITY", 1), ("UTILIZATION_HOURS", 1)],
             "power_generation_100m_kwh = capacity_mw * utilization_hours / 100000",
             "CAPACITY_UTILIZATION", "OPERATING_IDENTITY", "装机容量与利用小时形成发电量代理", False),
            ("THERMAL_POWER_GENERATION", [("THERMAL_CAPACITY", 1), ("THERMAL_UTILIZATION_HOURS", 1)],
             "thermal_generation_100m_kwh = thermal_capacity_10k_kw * utilization_hours / 10000",
             "CAPACITY_UTILIZATION", "OPERATING_IDENTITY", "火电装机与火电利用小时形成火电发电量代理", False),
            ("GRID_SALES_POWER", [("POWER_GENERATION", 1), ("PLANT_USE_RATE", -1)],
             "grid_sales = generation * (1 - plant_use_rate / 100)",
             "POWER_BALANCE", "OPERATING_IDENTITY", "发电量扣除厂用电后形成上网电量代理", False),
            ("REVENUE", [("GRID_SALES_POWER", 1), ("ON_GRID_TARIFF", 1)],
             "power_revenue_yuan = grid_sales_100m_kwh * tariff_yuan_per_mwh * 100000",
             "REVENUE_BRIDGE", "OPERATING_TO_FINANCIAL", "电量与电价形成售电收入代理，其他收入另计", False),
            ("FUEL_COST", [("THERMAL_POWER_GENERATION", 1), ("SUPPLY_COAL_CONSUMPTION", 1), ("STANDARD_COAL_PRICE", 1)],
             "fuel_cost_yuan = thermal_generation_100m_kwh * coal_consumption_g_per_kwh * standard_coal_price_yuan_per_t * 100",
             "FUEL_COST_BRIDGE", "OPERATING_TO_FINANCIAL", "只使用火电发电量计算燃料成本代理", False),
            ("FUEL_COST_PROXY", [("THERMAL_POWER_GENERATION", 1), ("SUPPLY_COAL_CONSUMPTION", 1), ("STANDARD_COAL_PRICE", 1)],
             "fuel_cost_proxy_yuan = thermal_generation_100m_kwh * coal_consumption_g_per_kwh * standard_coal_price_yuan_per_t * 100",
             "FUEL_COST_IDENTITY", "CALCULATED_LINEAGE", "只使用火电发电量形成可回算燃料成本代理", True),
            ("OPERATING_COST", [("FUEL_COST", 1)],
             "operating_cost_change = fuel_cost_change",
             "COST_PASS_THROUGH", "COST_PRESSURE", "燃料成本变动传导至营业成本，其他成本保持不变", False),
            ("OPERATING_COST", [("FUEL_COST_PROXY", 1)],
             "operating_cost_change = fuel_cost_proxy_change",
             "COST_PASS_THROUGH", "COST_PRESSURE", "火电燃料成本代理变动传导至营业成本，其他成本保持不变", False),
            ("NET_PROFIT", [("REVENUE", 1), ("OPERATING_COST", -1)],
             "profit_change_proxy = revenue_change - operating_cost_change",
             "MARGIN_BRIDGE", "ACCOUNTING_STRUCTURE", "收入与成本变化形成利润变化代理，税费等另计", False),
            ("DISCLOSED_DEBT_COMPONENTS", [
                ("SHORT_TERM_DEBT", 1), ("CURRENT_NONCURRENT_DEBT", 1),
                ("LONG_TERM_DEBT", 1), ("BONDS_PAYABLE", 1)],
             "disclosed_debt_components = short_term_debt + current_noncurrent_debt + long_term_debt + bonds_payable",
             "ACCOUNTING_IDENTITY", "CALCULATED_LINEAGE", "四项已披露债务构成的可回算合计", True),
            ("NET_DEBT_PROXY", [("DISCLOSED_DEBT_COMPONENTS", 1), ("CASH", -1)],
             "net_debt_proxy = disclosed_debt_components - cash",
             "ACCOUNTING_IDENTITY", "CALCULATED_LINEAGE", "已披露债务构成扣除货币资金", True),
            ("FREE_CASH_FLOW_PROXY", [("OPERATING_CASH_FLOW", 1), ("CAPEX", -1)],
             "free_cash_flow_proxy = operating_cash_flow - cash_capex",
             "CASH_FLOW_IDENTITY", "CALCULATED_LINEAGE", "经营现金流扣除现金资本开支", True),
            ("CURRENT_MARKET_CAP", [("CLOSE_PRICE", 1), ("SHARE_CAPITAL", 1)],
             "current_market_cap = close_price * share_capital",
             "MARKET_CAP_IDENTITY", "CALCULATED_LINEAGE", "收盘价乘以股本", True),
            ("CURRENT_MARKET_CAP", [("NET_PROFIT", 1)],
             "market_cap_change = net_profit_change * valuation_multiple",
             "PE_MULTIPLE", "VALUATION_BRIDGE", "净利润经估值倍数映射至市值情景", False),
            ("CURRENT_MARKET_CAP", [("FREE_CASH_FLOW_PROXY", 1)],
             "market_cap_change = discounted_free_cash_flow_change",
             "DCF", "VALUATION_BRIDGE", "自由现金流代理经折现映射至市值情景", False),
            ("CURRENT_MARKET_CAP", [("NET_DEBT_PROXY", -1)],
             "equity_value_change = -net_debt_proxy_change",
             "EV_EQUITY_BRIDGE", "VALUATION_BRIDGE", "净债务变化对权益价值的反向影响", False),
        ]
        for target, inputs, expression, formula_type, relation, mechanism, exact in groups:
            created += add_group(
                db, nodes, entity, target, inputs, expression,
                formula_type, relation, mechanism, exact,
            )
    db.commit()
    return {"candidate_edges_created": created, "entities_processed": len(entities)}


if __name__ == "__main__":
    connection = sqlite3.connect(ROOT / "coal_network.db")
    connection.execute("PRAGMA foreign_keys=ON")
    print(json.dumps(build(connection), ensure_ascii=False, indent=2))
    connection.close()
