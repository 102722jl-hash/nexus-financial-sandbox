"""Reproducible company metrics with explicit component-level lineage."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
NETWORK_ID = "coal_power_v1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def latest(db: sqlite3.Connection, entity: str, code: str):
    return db.execute(
        """SELECT metric_value_id,value,unit,report_period,announcement_date,
        as_of_date,data_cutoff,evidence_id
        FROM metric_values
        WHERE network_id=? AND entity_code=? AND metric_code=?
        AND value IS NOT NULL AND value_status IN ('SOURCE_FACT','MARKET_PROXY','CALCULATED')
        ORDER BY CASE
                   WHEN source_table='deep_financial_report_v3' THEN 0
                   WHEN source_table='calculated_metrics_v3' THEN 0
                   WHEN source_table='financial_report' THEN 1
                   WHEN source_table='company_announcement' THEN 2
                   ELSE 3 END,
          COALESCE(as_of_date,report_period,data_cutoff) DESC,
          metric_value_id DESC LIMIT 1""",
        (NETWORK_ID, entity, code),
    ).fetchone()


def ensure_share_metrics(db: sqlite3.Connection) -> int:
    inserted = 0
    rows = db.execute(
        """SELECT v.entity_code,v.diluted_shares,e.entity_name_cn
        FROM valuation v JOIN entities e
          ON e.network_id=v.network_id AND e.entity_code=v.entity_code
        WHERE v.network_id=? AND v.diluted_shares IS NOT NULL
        GROUP BY v.entity_code""",
        (NETWORK_ID,),
    ).fetchall()
    for entity, shares, name in rows:
        if latest(db, entity, "SHARE_CAPITAL"):
            continue
        evidence = db.execute(
            """SELECT evidence_id,published_at,data_cutoff
            FROM evidence WHERE publisher=? AND original_quote LIKE '%股本%'
            AND acceptance_status='ACCEPTED'
            ORDER BY published_at DESC LIMIT 1""",
            (name,),
        ).fetchone()
        if not evidence:
            continue
        evidence_id, published, cutoff = evidence
        metric_id = "mv_" + hashlib.sha256(
            f"{entity}|SHARE_CAPITAL|{shares}|{evidence_id}".encode()
        ).hexdigest()[:24]
        db.execute(
            """INSERT OR IGNORE INTO metric_values(
            network_id,metric_value_id,metric_code,entity_code,value,unit,
            report_period,announcement_date,as_of_date,data_cutoff,value_status,
            evidence_id,source_table,source_column,source_row_key)
            VALUES(?,?,?,?,?,?,'最新定期报告',?,?,?,?,?,?,?,?)""",
            (
                NETWORK_ID, metric_id, "SHARE_CAPITAL", entity, shares, "股",
                published, published, cutoff, "SOURCE_FACT", evidence_id,
                "share_capital", "diluted_shares", entity,
            ),
        )
        inserted += db.execute("SELECT changes()").fetchone()[0]
    return inserted


def write_calculated(
    db: sqlite3.Connection,
    entity: str,
    code: str,
    value: float,
    unit: str,
    formula: str,
    components: list[tuple[str, tuple, float]],
) -> int:
    component_ids = [row[0] for _role, row, _coefficient in components]
    digest = hashlib.sha256(
        f"{entity}|{code}|{formula}|{'|'.join(component_ids)}".encode()
    ).hexdigest()
    evidence_id = "ev_" + digest[:24]
    metric_id = "mv_" + hashlib.sha256(f"{digest}|{value}".encode()).hexdigest()[:24]
    periods = {row[3] for _role, row, _coefficient in components if row[3]}
    report_period = periods.pop() if len(periods) == 1 else None
    announcement = max(row[4] or row[6] for _role, row, _coefficient in components)
    as_of = max(row[5] or row[6] for _role, row, _coefficient in components)
    cutoff = max(row[6] for _role, row, _coefficient in components)
    inputs = [
        {
            "role": role,
            "metric_value_id": row[0],
            "value": row[1],
            "unit": row[2],
            "evidence_id": row[7],
            "coefficient": coefficient,
        }
        for role, row, coefficient in components
    ]
    quote = json.dumps(
        {"formula": formula, "result": value, "unit": unit, "inputs": inputs},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    db.execute(
        """INSERT OR IGNORE INTO evidence(
        evidence_id,source_type,source_name,publisher,published_at,retrieved_at,
        original_quote,page_or_locator,locator,source_url,anchor_at,declared_role,
        data_cutoff,source_tier,temporal_role,raw_storage_status,supports_node_ids,
        acceptance_status,review_status,acceptance_reason,source_table,source_column,source_row_key)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            evidence_id, "CALCULATION", "可回算指标公式", "coal_network_collector",
            announcement, now(), quote, f"formula:{formula}", f"formula:{formula}",
            f"internal://coal-network/calculation/{metric_id}", as_of,
            "CALCULATED_LINEAGE", cutoff, "T4", "AS_OF_EVIDENCE",
            "NOT_APPLICABLE", "[]", "ACCEPTED", "ACCEPTED",
            "ALL_COMPONENTS_PRESENT_NO_ZERO_FILL", "calculated_metrics_v3", code, entity,
        ),
    )
    db.execute(
        """INSERT OR IGNORE INTO metric_values(
        network_id,metric_value_id,metric_code,entity_code,value,unit,currency,
        report_period,announcement_date,as_of_date,data_cutoff,value_status,evidence_id,
        source_table,source_column,source_row_key)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            NETWORK_ID, metric_id, code, entity, value, unit,
            "CNY" if unit == "元" else None, report_period, announcement, as_of,
            cutoff, "CALCULATED", evidence_id, "calculated_metrics_v3", code,
            json.dumps(component_ids, ensure_ascii=False),
        ),
    )
    made = db.execute("SELECT changes()").fetchone()[0]
    if made:
        for role, row, coefficient in components:
            db.execute(
                """INSERT OR IGNORE INTO calculated_metric_lineage(
                network_id,metric_value_id,component_metric_value_id,
                component_evidence_id,input_role,coefficient)
                VALUES(?,?,?,?,?,?)""",
                (NETWORK_ID, metric_id, row[0], row[7], role, coefficient),
            )
    return made


def run(db: sqlite3.Connection) -> dict:
    db.executescript((ROOT / "complete_schema.sql").read_text(encoding="utf-8"))
    result = {"share_facts_inserted": ensure_share_metrics(db), "calculated_inserted": 0, "skipped": []}
    entities = [row[0] for row in db.execute(
        "SELECT entity_code FROM entities WHERE network_id=? AND status='ACTIVE'",
        (NETWORK_ID,),
    )]
    for entity in entities:
        debts = [
            (role, latest(db, entity, code), 1.0)
            for role, code in [
                ("short_term_debt", "SHORT_TERM_DEBT"),
                ("current_noncurrent_debt", "CURRENT_NONCURRENT_DEBT"),
                ("long_term_debt", "LONG_TERM_DEBT"),
                ("bonds_payable", "BONDS_PAYABLE"),
            ]
        ]
        if all(row for _role, row, _coefficient in debts):
            total = sum(row[1] for _role, row, _coefficient in debts)
            result["calculated_inserted"] += write_calculated(
                db, entity, "DISCLOSED_DEBT_COMPONENTS", total, "元",
                "short_term_debt + current_noncurrent_debt + long_term_debt + bonds_payable",
                debts,
            )
        else:
            result["skipped"].append(f"{entity}:DISCLOSED_DEBT_COMPONENTS:DATA_MISSING")

        debt = latest(db, entity, "DISCLOSED_DEBT_COMPONENTS")
        cash = latest(db, entity, "CASH")
        if debt and cash:
            result["calculated_inserted"] += write_calculated(
                db, entity, "NET_DEBT_PROXY", debt[1] - cash[1], "元",
                "disclosed_debt_components - cash",
                [("disclosed_debt_components", debt, 1.0), ("cash", cash, -1.0)],
            )
        else:
            result["skipped"].append(f"{entity}:NET_DEBT_PROXY:DATA_MISSING")

        operating_cash = latest(db, entity, "OPERATING_CASH_FLOW")
        capex = latest(db, entity, "CAPEX")
        if operating_cash and capex:
            result["calculated_inserted"] += write_calculated(
                db, entity, "FREE_CASH_FLOW_PROXY", operating_cash[1] - capex[1], "元",
                "operating_cash_flow - cash_capex",
                [("operating_cash_flow", operating_cash, 1.0), ("cash_capex", capex, -1.0)],
            )
        else:
            result["skipped"].append(f"{entity}:FREE_CASH_FLOW_PROXY:DATA_MISSING")

        thermal_generation = latest(db, entity, "THERMAL_POWER_GENERATION")
        coal_consumption = latest(db, entity, "SUPPLY_COAL_CONSUMPTION")
        standard_coal_price = latest(db, entity, "STANDARD_COAL_PRICE")
        if thermal_generation and coal_consumption and standard_coal_price:
            fuel_cost = (
                thermal_generation[1] * coal_consumption[1]
                * standard_coal_price[1] * 100
            )
            result["calculated_inserted"] += write_calculated(
                db, entity, "FUEL_COST_PROXY", fuel_cost, "元",
                "thermal_generation_100m_kwh * coal_consumption_g_per_kwh * standard_coal_price_yuan_per_t * 100",
                [
                    ("thermal_generation", thermal_generation, 1.0),
                    ("coal_consumption", coal_consumption, 1.0),
                    ("standard_coal_price", standard_coal_price, 1.0),
                ],
            )

        close = latest(db, entity, "CLOSE_PRICE")
        shares = latest(db, entity, "SHARE_CAPITAL")
        if close and shares:
            result["calculated_inserted"] += write_calculated(
                db, entity, "CURRENT_MARKET_CAP", close[1] * shares[1], "元",
                "close_price * share_capital",
                [("close_price", close, 1.0), ("share_capital", shares, 1.0)],
            )
        else:
            result["skipped"].append(f"{entity}:CURRENT_MARKET_CAP:DATA_MISSING")
    db.commit()
    return result


if __name__ == "__main__":
    connection = sqlite3.connect(ROOT / "coal_network.db")
    connection.execute("PRAGMA foreign_keys=ON")
    print(json.dumps(run(connection), ensure_ascii=False, indent=2))
    connection.close()
