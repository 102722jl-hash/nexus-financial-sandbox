"""Validated evidence and metric ingestion into the fixed NEV blueprint."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from contract_v1 import COMPANIES, METRICS, NETWORK_ID
from initialize import DEFAULT_DB, initialize, node_id


class IngestRejected(ValueError):
    pass


def _iso(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise IngestRejected(f"{field}: INVALID_ISO8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _stable_id(prefix: str, payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{prefix}::{hashlib.sha256(encoded).hexdigest()}"


def _quarantine(conn: sqlite3.Connection, object_type: str, object_id: str, reason: str, payload: dict) -> None:
    conn.execute(
        """INSERT INTO quarantine(object_type,object_id,reason_code,payload_json,created_at,status)
           VALUES (?,?,?,?,?,?)""",
        (object_type, object_id, reason, json.dumps(payload, ensure_ascii=False, sort_keys=True),
         datetime.now(timezone.utc).isoformat(timespec="seconds"), "OPEN"),
    )


def _validate_evidence(evidence: dict[str, Any]) -> tuple[str, str]:
    required = [
        "source_type", "source_name", "publisher", "published_at", "retrieved_at",
        "original_quote", "locator", "source_url", "anchor_at", "source_tier",
    ]
    missing = [field for field in required if not evidence.get(field)]
    if missing:
        return "REJECTED", f"SOURCE_EVIDENCE_INCOMPLETE:{','.join(missing)}"
    tier = evidence["source_tier"]
    statement = evidence["source_type"]
    if tier not in {"T1", "T2", "T3", "T4"}:
        return "REJECTED", "SOURCE_TIER_INVALID"
    if statement == "SOURCE_FACT" and tier not in {"T1", "T2"}:
        return "REJECTED", "SOURCE_TIER_NOT_ELIGIBLE"
    if tier == "T3" and statement != "MARKET_PROXY":
        return "REJECTED", "T3_ONLY_MARKET_PROXY"
    if tier == "T4":
        return "REJECTED", "T4_LEAD_ONLY"
    published = _iso(evidence["published_at"], "published_at")
    anchor = _iso(evidence["anchor_at"], "anchor_at")
    if evidence.get("declared_role") == "POST_EVENT_VALIDATION":
        temporal_role = "POST_EVENT_VALIDATION"
    elif published > anchor:
        return "REJECTED", "CUTOFF_BLOCKED"
    else:
        temporal_role = "AS_OF_EVIDENCE"
    return temporal_role, "GATES_PASSED"


def ingest_record(
    db_path: Path, payload: dict[str, Any], *, initialize_db: bool = True
) -> dict[str, Any]:
    if initialize_db:
        initialize(db_path)
    evidence = dict(payload.get("evidence") or {})
    metric = dict(payload.get("metric") or {})
    metric_code = metric.get("metric_code", "")
    object_id = metric.get("source_row_key") or metric_code or "UNKNOWN"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        temporal_role, reason = _validate_evidence(evidence)
        if temporal_role == "REJECTED":
            with conn:
                _quarantine(conn, "EVIDENCE", object_id, reason, payload)
            raise IngestRejected(reason)
        if metric_code not in METRICS:
            with conn:
                _quarantine(conn, "METRIC_VALUE", object_id, "UNKNOWN_METRIC_CODE", payload)
            raise IngestRejected("UNKNOWN_METRIC_CODE")
        name, _layer, _kind, canonical_unit, scope, _editable, _required = METRICS[metric_code]
        entity_code = metric.get("entity_code")
        if scope == "COMPANY" and entity_code not in COMPANIES:
            reason = "COMPANY_ENTITY_REQUIRED"
            with conn:
                _quarantine(conn, "METRIC_VALUE", object_id, reason, payload)
            raise IngestRejected(reason)
        if scope == "INDUSTRY" and entity_code is not None:
            reason = "INDUSTRY_METRIC_MUST_NOT_HAVE_ENTITY"
            with conn:
                _quarantine(conn, "METRIC_VALUE", object_id, reason, payload)
            raise IngestRejected(reason)
        if metric.get("unit") != canonical_unit:
            reason = f"UNIT_MISMATCH:expected={canonical_unit}"
            with conn:
                _quarantine(conn, "METRIC_VALUE", object_id, reason, payload)
            raise IngestRejected(reason)
        try:
            numeric = float(metric["value"])
        except (KeyError, TypeError, ValueError) as exc:
            raise IngestRejected("VALUE_NOT_NUMERIC") from exc
        if not math.isfinite(numeric):
            raise IngestRejected("VALUE_NOT_FINITE")
        evidence_id = evidence.get("evidence_id") or _stable_id("evidence", evidence)
        snapshot_sha = evidence.get("snapshot_sha256")
        if not snapshot_sha:
            snapshot_sha = hashlib.sha256(evidence["original_quote"].encode("utf-8")).hexdigest()
        supports = [node_id(metric_code, entity_code if scope == "COMPANY" else None)]
        evidence_row = (
            evidence_id, evidence["source_type"], evidence["source_name"], evidence["publisher"],
            evidence["published_at"], evidence["retrieved_at"], evidence["original_quote"],
            evidence["locator"], evidence["source_url"], evidence["anchor_at"],
            evidence.get("data_cutoff") or evidence["anchor_at"][:10], evidence["source_tier"],
            temporal_role, evidence.get("snapshot_path"), snapshot_sha,
            json.dumps(supports, ensure_ascii=False), "ACCEPTED", reason,
        )
        existing = conn.execute("SELECT * FROM evidence WHERE evidence_id=?", (evidence_id,)).fetchone()
        if existing:
            columns = [item[1] for item in conn.execute("PRAGMA table_info(evidence)")]
            current = dict(zip(columns, existing))
            proposed = dict(zip(columns, evidence_row))
            conflict_fields = [
                "source_url", "publisher", "published_at", "original_quote", "locator",
                "source_tier", "supports_node_ids", "temporal_role",
            ]
            if any(current[field] != proposed[field] for field in conflict_fields):
                with conn:
                    _quarantine(conn, "EVIDENCE", evidence_id, "EVIDENCE_CONFLICT", payload)
                raise IngestRejected("EVIDENCE_CONFLICT")

        metric_payload = {
            "metric_code": metric_code, "entity_code": entity_code, "value": numeric,
            "unit": canonical_unit, "report_period": metric.get("report_period"),
            "as_of_date": metric.get("as_of_date"), "evidence_id": evidence_id,
            "source_row_key": metric.get("source_row_key") or object_id,
        }
        metric_value_id = metric.get("metric_value_id") or _stable_id("metric", metric_payload)
        with conn:
            conn.execute(
                """INSERT OR IGNORE INTO evidence
                   (evidence_id,source_type,source_name,publisher,published_at,retrieved_at,
                    original_quote,locator,source_url,anchor_at,data_cutoff,source_tier,
                    temporal_role,snapshot_path,snapshot_sha256,supports_node_ids,
                    acceptance_status,acceptance_reason)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                evidence_row,
            )
            conn.execute(
                """INSERT INTO metric_values
                   (network_id,metric_value_id,metric_code,entity_code,value,unit,currency,
                    report_period,published_at,as_of_date,data_cutoff,value_status,evidence_id,
                    source_table,source_row_key)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(metric_value_id) DO UPDATE SET
                     value=excluded.value,unit=excluded.unit,currency=excluded.currency,
                     report_period=excluded.report_period,published_at=excluded.published_at,
                     as_of_date=excluded.as_of_date,data_cutoff=excluded.data_cutoff,
                     value_status=excluded.value_status""",
                (NETWORK_ID, metric_value_id, metric_code, entity_code, numeric, canonical_unit,
                 metric.get("currency"), metric.get("report_period"), evidence["published_at"],
                 metric.get("as_of_date"), evidence.get("data_cutoff") or evidence["anchor_at"][:10],
                 (
                     "MARKET_PROXY" if evidence["source_type"] == "MARKET_PROXY"
                     else "CALCULATED_LINEAGE" if evidence["source_type"] == "CALCULATED_LINEAGE"
                     else "AI_ASSUMPTION" if evidence["source_type"] == "AI_ASSUMPTION"
                     else "SOURCE_FACT"
                 ),
                 evidence_id, metric.get("source_table", "collector"),
                 metric.get("source_row_key") or object_id),
            )
            nid = node_id(metric_code, entity_code if scope == "COMPANY" else None)
            latest = conn.execute(
                """SELECT value,evidence_id,data_cutoff,value_status
                   FROM metric_values
                   WHERE network_id=? AND metric_code=? AND entity_code IS ?
                   ORDER BY COALESCE(as_of_date,report_period,published_at) DESC, published_at DESC
                   LIMIT 1""",
                (NETWORK_ID, metric_code, entity_code),
            ).fetchone()
            conn.execute(
                """UPDATE network_nodes
                   SET baseline_value=?,evidence_id=?,data_cutoff=?,value_status=?
                   WHERE network_id=? AND node_id=?""",
                (str(latest[0]), latest[1], latest[2], latest[3], NETWORK_ID, nid),
            )
            if conn.execute("SELECT changes()").fetchone()[0] != 1:
                raise IngestRejected(f"FIXED_NODE_NOT_FOUND:{nid}")
        return {
            "status": "ACCEPTED",
            "metric_value_id": metric_value_id,
            "evidence_id": evidence_id,
            "node_id": nid,
            "metric_name": name,
            "value": numeric,
        }
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("json_file", type=Path)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    result = ingest_record(args.db, json.loads(args.json_file.read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, indent=2))
