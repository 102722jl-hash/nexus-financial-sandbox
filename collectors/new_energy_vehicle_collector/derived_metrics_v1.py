"""Build auditable derived baselines from accepted observations."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from contract_v1 import COMPANIES, NETWORK_ID
from ingest_v1 import ingest_record
from initialize import DEFAULT_DB, initialize


FORMULAS = {
    "GROSS_PROFIT_PROXY": ("REVENUE", "OPERATING_COST", "SUBTRACT", "营业收入 - 营业成本"),
    "FREE_CASH_FLOW_PROXY": ("OPERATING_CASH_FLOW", "CAPEX", "SUBTRACT", "经营现金流 - 资本开支"),
    "NET_DEBT_PROXY": ("DEBT_COMPONENTS", "CASH", "SUBTRACT", "已披露债务构成 - 货币资金"),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _same_period_inputs(conn: sqlite3.Connection, entity_code: str, left: str, right: str):
    return conn.execute(
        """SELECT l.value,l.unit,l.report_period,l.published_at,l.evidence_id,
                  r.value,r.unit,r.published_at,r.evidence_id
           FROM metric_values l
           JOIN metric_values r
             ON r.network_id=l.network_id AND r.entity_code=l.entity_code
            AND r.report_period=l.report_period
           WHERE l.network_id=? AND l.entity_code=?
             AND l.metric_code=? AND r.metric_code=?
             AND l.unit=r.unit AND l.report_period IS NOT NULL
           ORDER BY l.report_period DESC,l.published_at DESC,r.published_at DESC
           LIMIT 1""",
        (NETWORK_ID, entity_code, left, right),
    ).fetchone()


def _market_cap_inputs(conn: sqlite3.Connection, entity_code: str):
    price = conn.execute(
        """SELECT value,unit,as_of_date,published_at,evidence_id
           FROM metric_values WHERE network_id=? AND entity_code=? AND metric_code='CLOSE_PRICE'
           ORDER BY as_of_date DESC,published_at DESC LIMIT 1""",
        (NETWORK_ID, entity_code),
    ).fetchone()
    shares = conn.execute(
        """SELECT value,unit,report_period,published_at,evidence_id
           FROM metric_values WHERE network_id=? AND entity_code=? AND metric_code='SHARE_CAPITAL'
           ORDER BY report_period DESC,published_at DESC LIMIT 1""",
        (NETWORK_ID, entity_code),
    ).fetchone()
    return price, shares


def _derived_payload(entity_code: str, metric_code: str, value: float, unit: str,
                     period: str | None, as_of_date: str | None, published_at: str,
                     formula: str, inputs: list[dict]) -> dict:
    lineage = json.dumps(inputs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    key = f"{entity_code}|{metric_code}|{period}|{as_of_date}|{formula}"
    metric_digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    evidence_digest = hashlib.sha256(f"{key}|{lineage}".encode("utf-8")).hexdigest()
    quote = f"公式：{formula}；输入：" + "；".join(
        f"{item['metric_code']}={item['value']} {item['unit']} ({item['evidence_id']})"
        for item in inputs
    )
    return {
        "evidence": {
            "evidence_id": f"evidence::calculated::{evidence_digest}",
            "source_type": "CALCULATED_LINEAGE",
            "source_name": "NEXUS可审计派生指标",
            "publisher": "NEXUS规则计算器",
            "published_at": published_at,
            "retrieved_at": utc_now(),
            "original_quote": quote,
            "locator": f"formula:{metric_code};lineage:{lineage}",
            "source_url": f"urn:nexus:formula:{metric_code}",
            "anchor_at": utc_now(),
            "source_tier": "T2",
        },
        "metric": {
            "metric_value_id": f"metric::calculated::{metric_digest}",
            "metric_code": metric_code,
            "entity_code": entity_code,
            "value": value,
            "unit": unit,
            "currency": "CNY",
            "report_period": period,
            "as_of_date": as_of_date,
            "source_table": "derived_metrics_v1",
            "source_row_key": key,
        },
    }


def build_derived_metrics(db_path: Path = DEFAULT_DB) -> dict:
    initialize(db_path)
    conn = sqlite3.connect(db_path)
    created = []
    skipped = []
    try:
        for entity_code in COMPANIES:
            for target, (left, right, _operation, label) in FORMULAS.items():
                row = _same_period_inputs(conn, entity_code, left, right)
                if not row:
                    skipped.append({"entity_code": entity_code, "metric_code": target, "reason": "SAME_PERIOD_INPUT_MISSING"})
                    continue
                left_value, unit, period, left_published, left_evidence, right_value, _, right_published, right_evidence = row
                published = max(left_published, right_published)
                inputs = [
                    {"metric_code": left, "value": left_value, "unit": unit, "evidence_id": left_evidence},
                    {"metric_code": right, "value": right_value, "unit": unit, "evidence_id": right_evidence},
                ]
                with conn:
                    conn.execute(
                        """DELETE FROM metric_values
                           WHERE network_id=? AND entity_code=? AND metric_code=?
                             AND report_period IS ? AND as_of_date IS NULL
                             AND source_table='derived_metrics_v1'""",
                        (NETWORK_ID, entity_code, target, period),
                    )
                result = ingest_record(
                    db_path,
                    _derived_payload(entity_code, target, left_value - right_value, unit, period, None, published, label, inputs),
                    initialize_db=False,
                )
                created.append(result)

            price, shares = _market_cap_inputs(conn, entity_code)
            if not price or not shares:
                skipped.append({"entity_code": entity_code, "metric_code": "CURRENT_MARKET_CAP", "reason": "PRICE_OR_SHARE_CAPITAL_MISSING"})
                continue
            price_value, price_unit, as_of_date, price_published, price_evidence = price
            share_value, share_unit, share_period, share_published, share_evidence = shares
            inputs = [
                {"metric_code": "CLOSE_PRICE", "value": price_value, "unit": price_unit, "evidence_id": price_evidence},
                {"metric_code": "SHARE_CAPITAL", "value": share_value, "unit": share_unit, "evidence_id": share_evidence},
            ]
            with conn:
                conn.execute(
                    """DELETE FROM metric_values
                       WHERE network_id=? AND entity_code=? AND metric_code='CURRENT_MARKET_CAP'
                         AND report_period IS ? AND as_of_date IS ?
                         AND source_table='derived_metrics_v1'""",
                    (NETWORK_ID, entity_code, share_period, as_of_date),
                )
            result = ingest_record(
                db_path,
                _derived_payload(
                    entity_code, "CURRENT_MARKET_CAP", price_value * share_value, "元",
                    share_period, as_of_date, max(price_published, share_published),
                    "收盘价 × 股本", inputs,
                ),
                initialize_db=False,
            )
            created.append(result)
    finally:
        conn.close()
    return {"created": len(created), "skipped": skipped, "metrics": created}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    print(json.dumps(build_derived_metrics(args.db), ensure_ascii=False, indent=2))
