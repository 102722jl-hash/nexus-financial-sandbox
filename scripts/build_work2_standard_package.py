"""Build the V2 standard network package in the local MySQL work2 schema.

The source schema is read only.  The target schema is an explicitly separate
database created for the normalized package.  Credentials are read from the
process environment and never printed.
"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

import pymysql


HOST = os.environ.get("MYSQL_HOST", "localhost")
PORT = int(os.environ.get("MYSQL_PORT", "3306"))
USER = os.environ.get("MYSQL_USER", "root")
PASSWORD = os.environ.get("MYSQL_PASSWORD")
SOURCE_DB = os.environ.get("MYSQL_SOURCE_DATABASE", "workspace")
TARGET_DB = os.environ.get("MYSQL_TARGET_DATABASE", "work2")
SOURCE_TABLE = "sandbox_ai_network_complete_v1"


def connect(database: str):
    if PASSWORD is None:
        raise RuntimeError("MYSQL_PASSWORD is required in the process environment")
    return pymysql.connect(
        host=HOST,
        port=PORT,
        user=USER,
        password=PASSWORD,
        database=database,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
        read_timeout=30,
        write_timeout=30,
    )


def qident(value: str) -> str:
    return "`" + value.replace("`", "``") + "`"


def stable_evidence_id(edge_id: str) -> str:
    return "EVD-EDGE-" + edge_id.replace("EDGE-", "", 1)


def ensure_column(cur, table: str, column: str, definition: str) -> None:
    cur.execute(
        "SELECT COUNT(*) AS n FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s",
        (TARGET_DB, table, column),
    )
    if not cur.fetchone()["n"]:
        cur.execute(f"ALTER TABLE {qident(table)} ADD COLUMN {qident(column)} {definition}")


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main() -> None:
    source = connect(SOURCE_DB)
    target = connect(TARGET_DB)
    try:
        with source.cursor() as cur:
            cur.execute(f"SELECT * FROM {qident(SOURCE_TABLE)} LIMIT 1")
            source_row = cur.fetchone()
            if not source_row:
                raise RuntimeError("source precompiled network row is empty")
            network_id = str(source_row["network_id"])
            cur.execute(f"SELECT * FROM {qident(SOURCE_TABLE)}")
            # The package is expected to contain one network row per network.
            rows = cur.fetchall()

        with target.cursor() as cur:
            cur.execute(
                """CREATE TABLE IF NOT EXISTS network_registry (
                    network_id VARCHAR(160) NOT NULL PRIMARY KEY,
                    network_name VARCHAR(255) NOT NULL,
                    network_version VARCHAR(80) NOT NULL,
                    network_status VARCHAR(40) NOT NULL,
                    network_kind VARCHAR(80) NOT NULL,
                    data_cutoff DATE NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) CHARACTER SET utf8mb4"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS network_nodes (
                    network_id VARCHAR(160) NOT NULL,
                    node_id VARCHAR(160) NOT NULL,
                    layer_no TINYINT NOT NULL,
                    node_name_cn VARCHAR(255) NOT NULL,
                    node_description TEXT NULL,
                    node_type VARCHAR(40) NOT NULL,
                    metric_code VARCHAR(160) NULL,
                    metric_name VARCHAR(255) NULL,
                    metric_type VARCHAR(80) NULL,
                    unit VARCHAR(80) NULL,
                    currency VARCHAR(16) NULL,
                    baseline_value JSON NULL,
                    editable TINYINT(1) NOT NULL DEFAULT 0,
                    value_status VARCHAR(80) NULL,
                    entity_code VARCHAR(80) NULL,
                    evidence_id VARCHAR(160) NULL,
                    data_cutoff DATE NULL,
                    status VARCHAR(40) NOT NULL DEFAULT 'CONFIRMED_DATA',
                    PRIMARY KEY (network_id, node_id),
                    KEY idx_nodes_layer (network_id, layer_no)
                ) CHARACTER SET utf8mb4"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS entities (
                    network_id VARCHAR(160) NOT NULL,
                    entity_code VARCHAR(80) NOT NULL,
                    entity_name_cn VARCHAR(255) NOT NULL,
                    entity_type VARCHAR(80) NULL,
                    industry_code VARCHAR(160) NULL,
                    exchange_code VARCHAR(40) NULL,
                    country VARCHAR(80) NULL,
                    company_model_family VARCHAR(160) NULL,
                    valuation_method VARCHAR(80) NULL,
                    status VARCHAR(40) NOT NULL DEFAULT 'CONFIRMED_DATA',
                    PRIMARY KEY (network_id, entity_code)
                ) CHARACTER SET utf8mb4"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS metric_values (
                    network_id VARCHAR(160) NOT NULL,
                    metric_value_id VARCHAR(220) NOT NULL PRIMARY KEY,
                    metric_code VARCHAR(160) NOT NULL,
                    node_id VARCHAR(160) NULL,
                    entity_code VARCHAR(80) NULL,
                    value DECIMAL(38,10) NULL,
                    unit VARCHAR(80) NULL,
                    currency VARCHAR(16) NULL,
                    report_period DATE NULL,
                    announcement_date DATE NULL,
                    opdate DATETIME NULL,
                    as_of_date DATE NULL,
                    data_cutoff DATE NULL,
                    value_status VARCHAR(80) NULL,
                    evidence_id VARCHAR(160) NULL,
                    source_table VARCHAR(255) NULL,
                    source_column VARCHAR(255) NULL,
                    source_row_key VARCHAR(255) NULL,
                    KEY idx_metric_node (network_id, node_id),
                    KEY idx_metric_entity (network_id, entity_code, metric_code)
                ) CHARACTER SET utf8mb4"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS formulas (
                    network_id VARCHAR(160) NOT NULL,
                    formula_id VARCHAR(220) NOT NULL PRIMARY KEY,
                    formula_type VARCHAR(80) NOT NULL,
                    formula_expression TEXT NULL,
                    parameters_json JSON NOT NULL,
                    formula_version VARCHAR(80) NOT NULL,
                    parameter_status VARCHAR(80) NOT NULL,
                    unit_in VARCHAR(80) NULL,
                    unit_out VARCHAR(80) NULL,
                    lag_days INT NULL,
                    impact_cap_pct DECIMAL(12,4) NULL,
                    invalidation_condition TEXT NULL,
                    evidence_id VARCHAR(160) NULL,
                    status VARCHAR(40) NOT NULL,
                    KEY idx_formula_network (network_id)
                ) CHARACTER SET utf8mb4"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id VARCHAR(160) NOT NULL PRIMARY KEY,
                    network_id VARCHAR(160) NOT NULL,
                    entity_code VARCHAR(80) NULL,
                    source_type VARCHAR(80) NOT NULL,
                    source_name VARCHAR(255) NOT NULL,
                    source_database VARCHAR(160) NULL,
                    source_schema VARCHAR(160) NULL,
                    source_table VARCHAR(255) NULL,
                    source_row_locator JSON NULL,
                    source_column VARCHAR(255) NULL,
                    report_period DATE NULL,
                    announcement_date DATE NULL,
                    data_cutoff DATE NULL,
                    original_url TEXT NULL,
                    excerpt TEXT NULL,
                    evidence_type VARCHAR(80) NULL,
                    review_status VARCHAR(80) NOT NULL,
                    KEY idx_evidence_network (network_id)
                ) CHARACTER SET utf8mb4"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS valuation (
                    network_id VARCHAR(160) NOT NULL,
                    entity_code VARCHAR(80) NOT NULL,
                    valuation_date DATE NULL,
                    price_asof DATE NULL,
                    close_price DECIMAL(38,10) NULL,
                    diluted_shares DECIMAL(38,10) NULL,
                    current_market_cap DECIMAL(38,10) NULL,
                    net_debt DECIMAL(38,10) NULL,
                    non_operating_assets DECIMAL(38,10) NULL,
                    valuation_method VARCHAR(80) NULL,
                    valuation_multiple DECIMAL(20,10) NULL,
                    discount_rate DECIMAL(20,10) NULL,
                    terminal_growth DECIMAL(20,10) NULL,
                    baseline_equity_value DECIMAL(38,10) NULL,
                    scenario_equity_value DECIMAL(38,10) NULL,
                    value_change_amount DECIMAL(38,10) NULL,
                    value_change_pct DECIMAL(20,10) NULL,
                    upside_downside_pct DECIMAL(20,10) NULL,
                    data_cutoff DATE NULL,
                    valuation_status VARCHAR(80) NULL,
                    evidence_id VARCHAR(160) NULL,
                    PRIMARY KEY (network_id, entity_code)
                ) CHARACTER SET utf8mb4"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS review_queue (
                    review_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    network_id VARCHAR(160) NOT NULL,
                    object_type VARCHAR(40) NOT NULL,
                    object_id VARCHAR(220) NOT NULL,
                    issue_code VARCHAR(120) NOT NULL,
                    reason TEXT NOT NULL,
                    status VARCHAR(40) NOT NULL DEFAULT 'OPEN',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_review (network_id, object_type, object_id, issue_code)
                ) CHARACTER SET utf8mb4"""
            )

            # Extend the legacy tables so the existing importer can consume the
            # repaired package without requiring a second table-selection path.
            for column, definition in {
                "evidence_id": "VARCHAR(160) NULL",
                "relation_type": "VARCHAR(80) NULL",
                "formula_id": "VARCHAR(220) NULL",
                "formula_type": "VARCHAR(80) NULL",
                "formula_parameters_json": "JSON NULL",
                "formula_version": "VARCHAR(80) NULL",
                "invalidation_condition": "TEXT NULL",
            }.items():
                ensure_column(cur, "sandbox_ai_network_edges", column, definition)
            ensure_column(cur, "sandbox_ai_network_nodes", "evidence_id", "VARCHAR(160) NULL")
            ensure_column(cur, "sandbox_ai_network_nodes", "status", "VARCHAR(40) NULL")

            layers = json.loads(source_row["layers_json"])
            nodes = json.loads(source_row["nodes_json"])
            edges = json.loads(source_row["edges_json"])
            valuations = json.loads(source_row["valuation_json"])
            cutoff = source_row.get("data_cutoff")
            network_name = source_row.get("network_name") or network_id
            network_version = source_row.get("network_version") or "2.0.0"

            cur.execute(
                """INSERT INTO network_registry
                    (network_id,network_name,network_version,network_status,network_kind,data_cutoff)
                    VALUES (%s,%s,%s,'DRAFT_REVIEW_REQUIRED','PRECOMPILED_NETWORK',%s)
                    ON DUPLICATE KEY UPDATE network_name=VALUES(network_name),
                    network_version=VALUES(network_version), data_cutoff=VALUES(data_cutoff)""",
                (network_id, network_name, network_version, cutoff),
            )
            for index, layer in enumerate(layers, 1):
                code = str(layer.get("id") or f"layer-{index}")
                cur.execute(
                    """INSERT INTO network_layers
                       (network_id,layer_no,layer_code,layer_name_cn,layer_subtitle_cn,
                        semantic_role,path_role,description,sort_order,status,confidence,reason)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'CONFIRMED',1.0,%s)
                       ON DUPLICATE KEY UPDATE layer_name_cn=VALUES(layer_name_cn),
                       layer_subtitle_cn=VALUES(layer_subtitle_cn), status='CONFIRMED'""",
                    (network_id, index, code, layer.get("label") or code, layer.get("subtitle"),
                     layer.get("label") or code, "SOURCE" if index == 1 else ("SINK" if index == 6 else "INTERMEDIATE"),
                     "来自预编译网络层定义", index, "预编译网络明确提供六层定义"),
                )

            evidence_by_entity: dict[str, str] = {}
            for valuation_row in valuations:
                entity = str(valuation_row.get("entityCode") or "")
                if entity and valuation_row.get("evidenceId"):
                    evidence_by_entity[entity] = str(valuation_row["evidenceId"])

            for node in nodes:
                node_id = str(node.get("nodeId"))
                entity = node.get("entityCode")
                evidence_id = evidence_by_entity.get(str(entity)) if entity else None
                baseline = node.get("baseline")
                if not baseline and node.get("baselineValue") is not None:
                    baseline = {"BASE": node.get("baselineValue")}
                cur.execute(
                    """INSERT INTO network_nodes
                       (network_id,node_id,layer_no,node_name_cn,node_description,node_type,
                        metric_code,metric_name,metric_type,unit,currency,baseline_value,
                        editable,value_status,entity_code,evidence_id,data_cutoff,status)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'CONFIRMED_DATA')
                       ON DUPLICATE KEY UPDATE node_name_cn=VALUES(node_name_cn),
                       node_description=VALUES(node_description), baseline_value=VALUES(baseline_value),
                       editable=VALUES(editable), evidence_id=VALUES(evidence_id), status='CONFIRMED_DATA'""",
                    (network_id, node_id, int(node.get("layerNo") or 0), node.get("label") or node_id,
                     node.get("description"), node.get("nodeType") or "METRIC", node.get("metricCode"),
                     node.get("metricName"), node.get("metricType"), node.get("unit"), node.get("currency"),
                     json_text(baseline) if baseline is not None else None, int(bool(node.get("editable"))),
                     node.get("valueStatus"), entity, evidence_id, node.get("dataCutoff") or cutoff),
                )
                cur.execute(
                    "UPDATE sandbox_ai_network_nodes SET evidence_id=%s,status='CONFIRMED_DATA' "
                    "WHERE network_id=%s AND node_id=%s",
                    (evidence_id, network_id, node_id),
                )

            # Company facts become entities plus point-in-time metric values.
            cur.execute("SELECT * FROM sandbox_ai_company_facts WHERE network_id=%s", (network_id,))
            company_rows = cur.fetchall()
            metric_columns = [
                ("revenue", "REVENUE", "amount"), ("operating_cost", "OPERATING_COST", "amount"),
                ("gross_profit", "GROSS_PROFIT", "amount"), ("operating_profit", "OPERATING_PROFIT", "amount"),
                ("net_profit", "NET_PROFIT", "amount"), ("operating_cash_flow", "OPERATING_CASH_FLOW", "amount"),
                ("capex", "CAPEX", "amount"), ("free_cash_flow", "FREE_CASH_FLOW", "amount"),
                ("cash", "CASH", "amount"), ("ending_cash", "ENDING_CASH", "amount"),
                ("inventory", "INVENTORY", "amount"), ("accounts_receivable", "ACCOUNTS_RECEIVABLE", "amount"),
                ("total_assets", "TOTAL_ASSETS", "amount"), ("total_liabilities", "TOTAL_LIABILITIES", "amount"),
                ("short_term_debt", "SHORT_TERM_DEBT", "amount"), ("long_term_debt", "LONG_TERM_DEBT", "amount"),
                ("bonds_payable", "BONDS_PAYABLE", "amount"), ("total_debt", "TOTAL_DEBT", "amount"),
                ("net_debt", "NET_DEBT", "amount"), ("equity", "EQUITY", "amount"),
                ("total_shares", "TOTAL_SHARES", "shares"), ("revenue_growth_pct", "REVENUE_GROWTH_PCT", "percent"),
                ("net_profit_growth_pct", "NET_PROFIT_GROWTH_PCT", "percent"), ("gross_margin_pct", "GROSS_MARGIN_PCT", "percent"),
                ("operating_margin_pct", "OPERATING_MARGIN_PCT", "percent"), ("net_margin_pct", "NET_MARGIN_PCT", "percent"),
                ("fcf_margin_pct", "FCF_MARGIN_PCT", "percent"), ("asset_liability_ratio_pct", "ASSET_LIABILITY_RATIO_PCT", "percent"),
            ]
            for company in company_rows:
                entity = str(company["entity_code"])
                cur.execute(
                    """INSERT INTO entities
                       (network_id,entity_code,entity_name_cn,entity_type,industry_code,
                        exchange_code,country,company_model_family,valuation_method,status)
                       VALUES (%s,%s,%s,'COMPANY',%s,%s,'CN',NULL,NULL,'CONFIRMED_DATA')
                       ON DUPLICATE KEY UPDATE entity_name_cn=VALUES(entity_name_cn),
                       industry_code=VALUES(industry_code), exchange_code=VALUES(exchange_code)""",
                    (network_id, entity, company.get("entity_name_cn") or entity,
                     company.get("industry_l1"), company.get("exchange_code")),
                )
                evidence_id = evidence_by_entity.get(entity)
                for column, code, metric_type in metric_columns:
                    value = number(company.get(column))
                    if value is None:
                        continue
                    metric_id = f"{network_id}:{entity}:{company.get('report_period')}:{code}"
                    cur.execute(
                        """INSERT INTO metric_values
                           (network_id,metric_value_id,metric_code,node_id,entity_code,value,unit,
                            currency,report_period,announcement_date,opdate,as_of_date,data_cutoff,
                            value_status,evidence_id,source_table,source_column,source_row_key)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           ON DUPLICATE KEY UPDATE value=VALUES(value), data_cutoff=VALUES(data_cutoff),
                           evidence_id=VALUES(evidence_id)""",
                        (network_id, metric_id, code, None, entity, value, metric_type, company.get("currency"),
                         company.get("report_period"), company.get("announcement_date"), company.get("opdate"),
                         company.get("report_period"), company.get("data_cutoff") or cutoff, company.get("value_status"),
                         evidence_id, "sandbox_ai_company_facts", column, str(company.get("source_record_id"))),
                    )

            # Add node-level baseline metrics (drivers, demand and route indices).
            for node in nodes:
                baseline = node.get("baseline") or {}
                if not isinstance(baseline, dict):
                    baseline = {"BASE": baseline}
                for code, raw_value in baseline.items():
                    value = number(raw_value)
                    if value is None:
                        continue
                    metric_code = str(node.get("metricCode") or code)
                    metric_id = f"{network_id}:{node.get('nodeId')}:{metric_code}"
                    cur.execute(
                        """INSERT INTO metric_values
                           (network_id,metric_value_id,metric_code,node_id,value,unit,currency,
                            as_of_date,data_cutoff,value_status,evidence_id,source_table,source_column,source_row_key)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           ON DUPLICATE KEY UPDATE value=VALUES(value),data_cutoff=VALUES(data_cutoff)""",
                        (network_id, metric_id, metric_code, node.get("nodeId"), value, node.get("unit"),
                         node.get("currency"), node.get("dataCutoff") or cutoff, node.get("dataCutoff") or cutoff,
                         node.get("valueStatus") or "SCENARIO_BASELINE", evidence_by_entity.get(str(node.get("entityCode"))) if node.get("entityCode") else None,
                         SOURCE_TABLE, "nodes_json", str(node.get("nodeId"))),
                    )

            # Formulas are explicit, safe enum formulas.  They remain analyst
            # assumptions until the source package's mechanism is reviewed.
            for edge in edges:
                edge_id = str(edge.get("edgeId"))
                formula_id = f"FORMULA-{edge_id}"
                params = {"weight": abs(number(edge.get("weight")) or 0), "lagDays": int(edge.get("lagDays") or 0), "impactCapPct": abs(number(edge.get("impactCapPct")) or 0)}
                evidence_id = str(edge.get("evidenceId") or stable_evidence_id(edge_id))
                cur.execute(
                    """INSERT INTO formulas
                       (network_id,formula_id,formula_type,formula_expression,parameters_json,
                        formula_version,parameter_status,unit_in,unit_out,lag_days,impact_cap_pct,
                        invalidation_condition,evidence_id,status)
                       VALUES (%s,%s,'LINEAR_WEIGHT',%s,%s,'1.0','ANALYST_ASSUMPTION',NULL,NULL,%s,%s,%s,%s,%s)
                       ON DUPLICATE KEY UPDATE parameters_json=VALUES(parameters_json), evidence_id=VALUES(evidence_id)""",
                    (network_id, formula_id, "下游变化 = 上游变化 × 方向 × 权重 × 时间滞后系数",
                     json_text(params), int(edge.get("lagDays") or 0), number(edge.get("impactCapPct")),
                     "关系机制或参数不再成立", evidence_id,
                     "CONFIRMED" if str(edge.get("status")).upper() == "CONFIRMED" else "CANDIDATE"),
                )
                edge_status = str(edge.get("status") or "CANDIDATE").upper()
                cur.execute(
                    """INSERT INTO network_edges
                       (network_id,edge_id,source_node_id,target_node_id,direction,relation_type,
                        formula_id,formula_type,weight,lag_days,impact_cap_pct,confidence,mechanism,
                        parameter_status,evidence_id,evidence_source,status)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,'LINEAR_WEIGHT',%s,%s,%s,%s,%s,'ANALYST_ASSUMPTION',%s,%s,%s)
                       ON DUPLICATE KEY UPDATE source_node_id=VALUES(source_node_id),target_node_id=VALUES(target_node_id),
                       direction=VALUES(direction),formula_id=VALUES(formula_id),formula_type='LINEAR_WEIGHT',
                       formula_parameters_json=VALUES(formula_parameters_json),status=VALUES(status),evidence_id=VALUES(evidence_id)""",
                    (network_id, edge_id, edge.get("sourceNodeId"), edge.get("targetNodeId"),
                     edge.get("direction") or "positive", edge.get("relationType") or "CAUSAL", formula_id,
                     abs(number(edge.get("weight")) or 0), int(edge.get("lagDays") or 0), number(edge.get("impactCapPct")),
                     number(edge.get("confidence")), edge.get("mechanism"), evidence_id,
                     edge.get("evidenceSource") or "PRECOMPILED_NETWORK", edge_status),
                )
                # Also repair the legacy table used by the existing table picker.
                cur.execute(
                    """UPDATE sandbox_ai_network_edges SET status=%s,evidence_id=%s,relation_type=%s,
                       formula_id=%s,formula_type='LINEAR_WEIGHT',formula_parameters_json=%s,
                       formula_version='1.0',invalidation_condition=%s
                       WHERE network_id=%s AND edge_id=%s""",
                    (edge_status, evidence_id, edge.get("relationType") or "CAUSAL", formula_id,
                     json_text(params), "关系机制或参数不再成立", network_id, edge_id),
                )

                if not edge.get("evidenceId"):
                    cur.execute(
                        """INSERT INTO review_queue (network_id,object_type,object_id,issue_code,reason)
                           VALUES (%s,'EDGE',%s,'EVIDENCE_NEEDS_REVIEW',%s)
                           ON DUPLICATE KEY UPDATE reason=VALUES(reason),status='OPEN'""",
                        (network_id, edge_id, "预编译网络提供了机制声明，但未提供外部原文证据定位。"),
                    )

                cur.execute(
                    """INSERT INTO evidence
                       (evidence_id,network_id,source_type,source_name,source_database,source_table,
                        source_row_locator,data_cutoff,excerpt,evidence_type,review_status)
                       VALUES (%s,%s,'PRECOMPILED_NETWORK',%s,%s,%s,%s,%s,%s,'NETWORK_DECLARATION',%s)
                       ON DUPLICATE KEY UPDATE excerpt=VALUES(excerpt),review_status=VALUES(review_status)""",
                    (evidence_id, network_id, SOURCE_TABLE, SOURCE_DB, SOURCE_TABLE,
                     json_text({"networkId": network_id, "edgeId": edge_id}), cutoff,
                     edge.get("mechanism") or "预编译网络关系声明", "NEEDS_HUMAN_REVIEW" if not edge.get("evidenceId") else "PENDING_REVIEW"),
                )

            for valuation_row in valuations:
                entity = str(valuation_row.get("entityCode") or "")
                if not entity:
                    continue
                cur.execute(
                    """INSERT INTO valuation
                       (network_id,entity_code,valuation_date,price_asof,close_price,diluted_shares,
                        current_market_cap,net_debt,non_operating_assets,valuation_method,
                        baseline_equity_value,scenario_equity_value,value_change_amount,value_change_pct,
                        upside_downside_pct,data_cutoff,valuation_status,evidence_id)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON DUPLICATE KEY UPDATE valuation_status=VALUES(valuation_status),data_cutoff=VALUES(data_cutoff),
                       evidence_id=VALUES(evidence_id)""",
                    (network_id, entity, valuation_row.get("valuationDate"), valuation_row.get("priceAsOf"),
                     valuation_row.get("closePrice"), valuation_row.get("dilutedShares"), valuation_row.get("currentMarketCap"),
                     valuation_row.get("netDebt"), valuation_row.get("nonOperatingAssets"), valuation_row.get("valuationMethod"),
                     valuation_row.get("baselineEquityValue"), valuation_row.get("scenarioEquityValue"), valuation_row.get("valueChangeAmount"),
                     valuation_row.get("valueChangePct"), valuation_row.get("upsideDownsidePct"), cutoff,
                     valuation_row.get("valuationStatus") or "DATA_MISSING", valuation_row.get("evidenceId")),
                )

            cur.execute(
                """INSERT INTO manifest
                   (network_id,package_version,network_name,data_cutoff,package_status,summary_json)
                   VALUES (%s,%s,%s,%s,'PARTIAL',%s)
                   ON DUPLICATE KEY UPDATE package_version=VALUES(package_version),
                   data_cutoff=VALUES(data_cutoff),summary_json=VALUES(summary_json)""",
                (network_id, "work2-v2.0-2026-09-04", network_name, cutoff,
                 json_text({"source": f"{SOURCE_DB}.{SOURCE_TABLE}", "networkEdges": len(edges),
                            "confirmedSourceEdges": sum(str(x.get("status")).upper() == "CONFIRMED" for x in edges),
                            "reviewPolicy": "source-confirmed edges are executable conditionally; evidence gaps remain in review_queue"})),
            )
        target.commit()
        print(json.dumps({"status": "BUILT", "targetDatabase": TARGET_DB, "networkId": network_id,
                          "nodes": len(nodes), "edges": len(edges), "sourceConfirmedEdges": sum(str(x.get("status")).upper() == "CONFIRMED" for x in edges)}, ensure_ascii=False))
    except Exception:
        target.rollback()
        raise
    finally:
        source.close()
        target.close()


if __name__ == "__main__":
    main()
