"""Create normalized, auditable tables for the workspace network.

The source table is never altered. Credentials are accepted only from the
current process environment (MYSQL_PASSWORD) and are never printed.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from typing import Any

import pymysql


SOURCE_TABLE = "sandbox_ai_network_company_2024_v1"


def edge_id(network_id: str, source: str, target: str, mechanism: str) -> str:
    raw = "|".join((network_id, source, target, mechanism))
    return "EDGE-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20].upper()


def connect() -> pymysql.connections.Connection:
    password = os.environ.get("MYSQL_PASSWORD")
    if password is None:
        raise RuntimeError("MYSQL_PASSWORD environment variable is required")
    conn = pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "localhost"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "root"),
        password=password,
        database=os.environ.get("MYSQL_DATABASE", "workspace"),
        charset="utf8mb4",
        autocommit=False,
        connect_timeout=8,
        read_timeout=30,
        write_timeout=10,
    )
    return conn


DDL = [
    """
    CREATE TABLE IF NOT EXISTS sandbox_ai_network_registry (
      network_id VARCHAR(120) NOT NULL,
      network_name VARCHAR(255) NOT NULL,
      network_version VARCHAR(40) NOT NULL,
      network_status VARCHAR(40) NOT NULL,
      data_cutoff DATE NULL,
      source_table VARCHAR(255) NOT NULL,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (network_id, network_version)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS sandbox_ai_company_facts (
      source_record_id BIGINT NOT NULL,
      network_id VARCHAR(120) NOT NULL,
      entity_code VARCHAR(40) NOT NULL,
      entity_name_cn VARCHAR(255) NOT NULL,
      report_period DATE NOT NULL,
      announcement_date DATE NOT NULL,
      data_cutoff DATE NOT NULL,
      currency VARCHAR(12) NOT NULL,
      value_status VARCHAR(40) NOT NULL,
      revenue DECIMAL(30,6) NULL,
      operating_cost DECIMAL(30,6) NULL,
      gross_profit DECIMAL(30,6) NULL,
      operating_profit DECIMAL(30,6) NULL,
      net_profit DECIMAL(30,6) NULL,
      operating_cash_flow DECIMAL(30,6) NULL,
      capex DECIMAL(30,6) NULL,
      free_cash_flow DECIMAL(30,6) NULL,
      cash DECIMAL(30,6) NULL,
      ending_cash DECIMAL(30,6) NULL,
      inventory DECIMAL(30,6) NULL,
      accounts_receivable DECIMAL(30,6) NULL,
      total_assets DECIMAL(30,6) NULL,
      total_liabilities DECIMAL(30,6) NULL,
      short_term_debt DECIMAL(30,6) NULL,
      long_term_debt DECIMAL(30,6) NULL,
      bonds_payable DECIMAL(30,6) NULL,
      lease_liability DECIMAL(30,6) NULL,
      total_debt DECIMAL(30,6) NULL,
      net_debt DECIMAL(30,6) NULL,
      equity DECIMAL(30,6) NULL,
      total_shares DECIMAL(30,6) NULL,
      revenue_growth_pct DECIMAL(20,6) NULL,
      net_profit_growth_pct DECIMAL(20,6) NULL,
      gross_margin_pct DECIMAL(20,6) NULL,
      operating_margin_pct DECIMAL(20,6) NULL,
      net_margin_pct DECIMAL(20,6) NULL,
      fcf_margin_pct DECIMAL(20,6) NULL,
      asset_liability_ratio_pct DECIMAL(20,6) NULL,
      source_income_table VARCHAR(255) NOT NULL,
      source_balance_table VARCHAR(255) NOT NULL,
      source_cashflow_table VARCHAR(255) NOT NULL,
      source_row_version_json JSON NOT NULL,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (source_record_id),
      KEY idx_company_facts_network_entity (network_id, entity_code, report_period)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS sandbox_ai_network_nodes (
      network_id VARCHAR(120) NOT NULL,
      node_id VARCHAR(160) NOT NULL,
      node_name_cn VARCHAR(255) NOT NULL,
      node_description TEXT NULL,
      layer_no TINYINT NOT NULL,
      node_type VARCHAR(40) NOT NULL,
      metric_code VARCHAR(120) NULL,
      metric_name VARCHAR(255) NULL,
      metric_type VARCHAR(40) NULL,
      unit VARCHAR(40) NULL,
      currency VARCHAR(12) NULL,
      baseline_value JSON NULL,
      editable BOOLEAN NOT NULL DEFAULT FALSE,
      value_status VARCHAR(60) NOT NULL,
      entity_code VARCHAR(40) NULL,
      data_cutoff DATE NULL,
      source_record_id BIGINT NULL,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (network_id, node_id),
      KEY idx_network_nodes_layer (network_id, layer_no),
      KEY idx_network_nodes_entity (network_id, entity_code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS sandbox_ai_network_edges (
      edge_id VARCHAR(80) NOT NULL,
      network_id VARCHAR(120) NOT NULL,
      source_node_id VARCHAR(160) NOT NULL,
      target_node_id VARCHAR(160) NOT NULL,
      direction TINYINT NOT NULL,
      weight DECIMAL(20,8) NOT NULL,
      lag_days INT NOT NULL DEFAULT 0,
      impact_cap_pct DECIMAL(20,8) NULL,
      mechanism TEXT NOT NULL,
      confidence DECIMAL(8,6) NULL,
      parameter_status VARCHAR(40) NOT NULL,
      evidence_id VARCHAR(160) NULL,
      evidence_source VARCHAR(255) NULL,
      status VARCHAR(40) NOT NULL,
      source_record_id BIGINT NULL,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (edge_id),
      KEY idx_network_edges_path (network_id, source_node_id, target_node_id),
      KEY idx_network_edges_status (network_id, status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS sandbox_ai_network_valuation (
      network_id VARCHAR(120) NOT NULL,
      entity_code VARCHAR(40) NOT NULL,
      valuation_date DATE NULL,
      price_asof DATE NULL,
      close_price DECIMAL(30,8) NULL,
      diluted_shares DECIMAL(30,8) NULL,
      current_market_cap DECIMAL(30,6) NULL,
      net_debt DECIMAL(30,6) NULL,
      non_operating_assets DECIMAL(30,6) NULL,
      valuation_method VARCHAR(40) NULL,
      valuation_multiple DECIMAL(20,8) NULL,
      discount_rate DECIMAL(20,8) NULL,
      terminal_growth DECIMAL(20,8) NULL,
      baseline_equity_value DECIMAL(30,6) NULL,
      scenario_equity_value DECIMAL(30,6) NULL,
      value_change_amount DECIMAL(30,6) NULL,
      value_change_pct DECIMAL(20,8) NULL,
      upside_downside_pct DECIMAL(20,8) NULL,
      data_cutoff DATE NULL,
      valuation_status VARCHAR(40) NOT NULL,
      evidence_id VARCHAR(160) NULL,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (network_id, entity_code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS sandbox_ai_network_evidence (
      evidence_id VARCHAR(160) NOT NULL,
      network_id VARCHAR(120) NOT NULL,
      entity_code VARCHAR(40) NULL,
      source_database VARCHAR(120) NOT NULL,
      source_table VARCHAR(255) NOT NULL,
      source_row_locator JSON NULL,
      source_column VARCHAR(255) NULL,
      report_period DATE NULL,
      announcement_date DATE NULL,
      data_cutoff DATE NULL,
      original_url TEXT NULL,
      excerpt TEXT NULL,
      evidence_type VARCHAR(40) NOT NULL,
      review_status VARCHAR(40) NOT NULL,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (evidence_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS sandbox_ai_scenario_runs (
      scenario_id VARCHAR(100) NOT NULL,
      network_id VARCHAR(120) NOT NULL,
      scenario_name VARCHAR(255) NOT NULL,
      engine_version VARCHAR(80) NOT NULL,
      data_cutoff DATE NOT NULL,
      parameter_version VARCHAR(80) NOT NULL,
      status VARCHAR(40) NOT NULL,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (scenario_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS sandbox_ai_scenario_changes (
      scenario_id VARCHAR(100) NOT NULL,
      metric_code VARCHAR(120) NOT NULL,
      change_percent DECIMAL(20,8) NOT NULL,
      duration_months INT NOT NULL,
      PRIMARY KEY (scenario_id, metric_code),
      CONSTRAINT fk_scenario_changes_run FOREIGN KEY (scenario_id) REFERENCES sandbox_ai_scenario_runs(scenario_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS sandbox_ai_simulation_results (
      scenario_id VARCHAR(100) NOT NULL,
      result_node_id VARCHAR(160) NOT NULL,
      change_percent DECIMAL(20,8) NULL,
      confidence DECIMAL(8,6) NULL,
      reason TEXT NULL,
      calculation_trace JSON NULL,
      evidence_id VARCHAR(160) NULL,
      PRIMARY KEY (scenario_id, result_node_id),
      CONSTRAINT fk_simulation_results_run FOREIGN KEY (scenario_id) REFERENCES sandbox_ai_scenario_runs(scenario_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


def json_obj(value: Any) -> dict[str, Any] | list[Any] | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except (TypeError, ValueError):
        return None


def main() -> None:
    conn = connect()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            for statement in DDL:
                cur.execute(statement)

            cur.execute(
                f"SELECT * FROM `{SOURCE_TABLE}` ORDER BY record_id"
            )
            rows = cur.fetchall()

            for row in rows:
                network_id = str(row["network_id"])
                cur.execute(
                    """INSERT INTO sandbox_ai_network_registry
                    (network_id,network_name,network_version,network_status,data_cutoff,source_table)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE network_name=VALUES(network_name),
                      network_status=VALUES(network_status), data_cutoff=VALUES(data_cutoff),
                      source_table=VALUES(source_table)""",
                    (network_id, row["network_name"], row["network_version"], row["network_status"], row["data_cutoff"], SOURCE_TABLE),
                )
                fact_columns = [
                    "source_record_id", "network_id", "entity_code", "entity_name_cn", "report_period",
                    "announcement_date", "data_cutoff", "currency", "value_status", "revenue",
                    "operating_cost", "gross_profit", "operating_profit", "net_profit", "operating_cash_flow",
                    "capex", "free_cash_flow", "cash", "ending_cash", "inventory", "accounts_receivable",
                    "total_assets", "total_liabilities", "short_term_debt", "long_term_debt", "bonds_payable",
                    "lease_liability", "total_debt", "net_debt", "equity", "total_shares", "revenue_growth_pct",
                    "net_profit_growth_pct", "gross_margin_pct", "operating_margin_pct", "net_margin_pct",
                    "fcf_margin_pct", "asset_liability_ratio_pct", "source_income_table", "source_balance_table",
                    "source_cashflow_table", "source_row_version_json",
                ]
                fact_values = [row["record_id"]] + [row[column] for column in fact_columns[1:-1]] + [json.dumps(json_obj(row["source_row_version_json"]), ensure_ascii=False)]
                placeholders = ",".join(["%s"] * len(fact_columns))
                updates = ",".join(f"{column}=VALUES({column})" for column in fact_columns[1:])
                cur.execute(
                    f"INSERT INTO sandbox_ai_company_facts ({','.join(fact_columns)}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {updates}",
                    fact_values,
                )

                bundle = json_obj(row["node_bundle_json"])
                nodes = bundle if isinstance(bundle, list) else []
                node_ids: dict[int, str] = {}
                for node in nodes:
                    if not isinstance(node, dict):
                        continue
                    node_id = str(node.get("nodeId") or "")
                    if not node_id:
                        continue
                    layer = int(node.get("layer") or 0)
                    node_ids[layer] = node_id
                    baseline = node.get("value")
                    cur.execute(
                        """INSERT INTO sandbox_ai_network_nodes
                        (network_id,node_id,node_name_cn,node_description,layer_no,node_type,metric_code,metric_name,metric_type,unit,currency,baseline_value,editable,value_status,entity_code,data_cutoff,source_record_id)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON DUPLICATE KEY UPDATE node_name_cn=VALUES(node_name_cn), node_description=VALUES(node_description),
                          baseline_value=VALUES(baseline_value), editable=VALUES(editable), value_status=VALUES(value_status), data_cutoff=VALUES(data_cutoff), source_record_id=VALUES(source_record_id)""",
                        (network_id, node_id, str(node.get("title") or node_id), str(node.get("subtitle") or ""), layer,
                         str(node.get("metricType") or "UNKNOWN"), str(node.get("metricCode") or "") or None,
                         str(node.get("title") or "") or None, str(node.get("metricType") or "") or None,
                         str(node.get("unit") or "") or None, str(row.get("currency") or "") or None,
                         json.dumps(baseline, ensure_ascii=False), bool(node.get("editable")), str(node.get("valueStatus") or "UNKNOWN"),
                         row.get("entity_code") if layer == 4 else None, row.get("data_cutoff"), row.get("record_id")),
                    )

                edges = json_obj(row["outgoing_edges_json"])
                edge_items = edges if isinstance(edges, list) else []
                for item in edge_items:
                    if not isinstance(item, dict):
                        continue
                    source_entity = str(item.get("sourceEntityCode") or "")
                    target_entity = str(item.get("targetEntityCode") or "")
                    source_node = f"company-{source_entity.lower().replace('.', '-') }" if source_entity else ""
                    target_node = f"company-{target_entity.lower().replace('.', '-') }" if target_entity else ""
                    mechanism = str(item.get("mechanism") or "")
                    if not source_node or not target_node:
                        continue
                    cur.execute(
                        """INSERT INTO sandbox_ai_network_edges
                        (edge_id,network_id,source_node_id,target_node_id,direction,weight,lag_days,impact_cap_pct,mechanism,confidence,parameter_status,evidence_id,evidence_source,status,source_record_id)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON DUPLICATE KEY UPDATE weight=VALUES(weight), lag_days=VALUES(lag_days), impact_cap_pct=VALUES(impact_cap_pct), mechanism=VALUES(mechanism), confidence=VALUES(confidence), status=VALUES(status)""",
                        (edge_id(network_id, source_node, target_node, mechanism), network_id, source_node, target_node,
                         1 if float(item.get("direction") or 1) >= 0 else -1, float(item.get("weight") or 0), int(item.get("lagDays") or 0),
                         row.get("impact_cap_pct"), mechanism, float(item.get("confidence") or 0), row.get("parameter_status") or "ANALYST_ASSUMPTION",
                         row.get("evidence_id"), item.get("evidenceSource"), str(item.get("status") or "PENDING_REVIEW"), row.get("record_id")),
                    )

                # Add the six-layer path as explicit candidate edges. These are
                # visible and auditable, but remain excluded from formal runs
                # until a reviewer confirms the mechanism and parameters.
                for left, right in zip(nodes, nodes[1:]):
                    if not isinstance(left, dict) or not isinstance(right, dict):
                        continue
                    source_node = str(left.get("nodeId") or "")
                    target_node = str(right.get("nodeId") or "")
                    if not source_node or not target_node:
                        continue
                    mechanism = f"{left.get('title', source_node)}向{right.get('title', target_node)}传导"
                    cur.execute(
                        """INSERT IGNORE INTO sandbox_ai_network_edges
                        (edge_id,network_id,source_node_id,target_node_id,direction,weight,lag_days,impact_cap_pct,mechanism,confidence,parameter_status,status,source_record_id)
                        VALUES (%s,%s,%s,%s,1,%s,%s,%s,%s,%s,'ANALYST_ASSUMPTION','CANDIDATE',%s)""",
                        (edge_id(network_id, source_node, target_node, mechanism), network_id, source_node, target_node,
                         float(row.get("driver_sensitivity") or 0), int(row.get("lag_days") or 0), row.get("impact_cap_pct"), mechanism,
                         0.3, row.get("record_id")),
                    )

                evidence_id = str(row.get("evidence_id") or "")
                if evidence_id:
                    locator = {
                        "recordId": row.get("record_id"),
                        "sourceRowVersion": json_obj(row.get("source_row_version_json")),
                    }
                    cur.execute(
                        """INSERT INTO sandbox_ai_network_evidence
                        (evidence_id,network_id,entity_code,source_database,source_table,source_row_locator,report_period,announcement_date,data_cutoff,excerpt,evidence_type,review_status)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'REPORTED_ACTUAL',%s)
                        ON DUPLICATE KEY UPDATE source_row_locator=VALUES(source_row_locator), review_status=VALUES(review_status)""",
                        (evidence_id, network_id, row.get("entity_code"), "workspace", SOURCE_TABLE,
                         json.dumps(locator, ensure_ascii=False), row.get("report_period"), row.get("announcement_date"), row.get("data_cutoff"),
                         "公司财务字段来自预编译网络表；原始财务表定位保存在 source_row_version_json。", row.get("evidence_status") or "NEEDS_HUMAN_REVIEW"),
                    )

                cur.execute(
                    """INSERT INTO sandbox_ai_network_valuation
                    (network_id,entity_code,diluted_shares,current_market_cap,net_debt,baseline_equity_value,scenario_equity_value,data_cutoff,valuation_status,evidence_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE diluted_shares=VALUES(diluted_shares), net_debt=VALUES(net_debt), data_cutoff=VALUES(data_cutoff), valuation_status=VALUES(valuation_status), evidence_id=VALUES(evidence_id)""",
                    (network_id, row.get("entity_code"), row.get("total_shares"), row.get("current_market_cap"), row.get("net_debt"),
                     row.get("baseline_equity_value"), row.get("scenario_equity_value"), row.get("data_cutoff"), row.get("valuation_status") or "DATA_MISSING", evidence_id or None),
                )

        conn.commit()
        print(json.dumps({"status": "MIGRATED", "sourceTable": SOURCE_TABLE, "rows": len(rows), "networkId": rows[0]["network_id"] if rows else None}, ensure_ascii=False))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"MIGRATION_FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
