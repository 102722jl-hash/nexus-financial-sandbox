from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import calendar
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from contract_v1 import NETWORK_ID
from initialize import DEFAULT_DB, ROOT


CONTRACT_VERSION = "nexus-crawler-batch-1.0.0"
SANDBOX = ROOT.parent / "financial-world-sandbox-v2.20-composite-network"
DEFAULT_OUTPUT_DIR = ROOT / "standard_batches"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable(prefix: str, *parts) -> str:
    raw = json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24].upper()}"


def rows(connection: sqlite3.Connection, table: str) -> list[dict]:
    connection.row_factory = sqlite3.Row
    return [dict(item) for item in connection.execute(f'SELECT * FROM "{table}"')]


def iso(value: str | None, fallback: str) -> str:
    raw = str(value or fallback).strip()
    if len(raw) == 10:
        return raw + "T00:00:00Z"
    if raw.endswith("Z") or "+" in raw[10:]:
        return raw
    return raw + "Z"


def business_date(value: str | None, fallback: str) -> str:
    raw = str(value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    match = re.fullmatch(r"(\d{4})-(\d{2})", raw)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        return f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"
    match = re.fullmatch(r"(\d{4})-Q([1-4])", raw, re.I)
    if match:
        year, quarter = int(match.group(1)), int(match.group(2))
        month = quarter * 3
        return f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"
    match = re.fullmatch(r"(\d{4})-H([12])", raw, re.I)
    if match:
        year, half = int(match.group(1)), int(match.group(2))
        return f"{year:04d}-{'06-30' if half == 1 else '12-31'}"
    if re.fullmatch(r"\d{4}", raw):
        return raw + "-12-31"
    return str(fallback)[:10]


def valid_sha(value: str | None, fallback: str) -> str:
    raw = str(value or "").lower()
    if len(raw) == 64 and all(char in "0123456789abcdef" for char in raw):
        return raw
    return hashlib.sha256(fallback.encode("utf-8")).hexdigest()


def unit_family(metric_type: str, unit: str) -> str:
    kind = metric_type.upper()
    if unit == "%" or kind == "RATIO":
        return "PERCENT" if unit == "%" else "OTHER"
    if kind == "PRICE":
        return "PRICE"
    if kind == "AMOUNT":
        return "CURRENCY"
    if kind == "COUNT":
        return "COUNT"
    if kind == "INDEX":
        return "INDEX"
    if any(token in unit for token in ("吨", "千克", "kg")):
        return "MASS"
    if any(token in unit for token in ("GWh", "MWh", "kWh")):
        return "ENERGY"
    return "COUNT" if kind in {"FLOW", "STOCK"} and unit in {"辆", "个", "股"} else "OTHER"


def frequency(metric_code: str, metric_type: str) -> str:
    if metric_code in {"CLOSE_PRICE", "CURRENT_MARKET_CAP"}:
        return "DAILY"
    if metric_code in {"REVENUE", "OPERATING_COST", "NET_PROFIT", "RND_EXPENSE", "OPERATING_CASH_FLOW", "CAPEX", "CASH", "DEBT_COMPONENTS"}:
        return "QUARTERLY"
    if "SALES" in metric_code or "PRODUCTION" in metric_code or "EXPORT" in metric_code:
        return "MONTHLY"
    return "EVENT" if metric_type.upper() == "TEXT_SIGNAL" else "DAILY"


def direction(source: str, target: str, relation_type: str) -> str:
    negative_pairs = {
        ("VEHICLE_UNIT_COST_PROXY", "VEHICLE_COST_PROXY"),
        ("VEHICLE_COST_PROXY", "GROSS_PROFIT_PROXY"),
        ("OPERATING_COST", "NET_PROFIT"),
        ("CAPEX", "FREE_CASH_FLOW_PROXY"),
        ("CASH", "NET_DEBT_PROXY"),
    }
    if (source, target) in negative_pairs or "COST_PRESSURE" in relation_type:
        return "negative"
    return "positive"


def source_transport(evidence: dict) -> str:
    path = str(evidence.get("snapshot_path") or "").lower()
    url = str(evidence.get("source_url") or "").lower()
    if path.endswith(".pdf") or url.endswith(".pdf"):
        return "PDF"
    if "api" in url or "json" in str(evidence.get("locator") or "").lower():
        return "API"
    return "WEB"


def export_batch(
    db_path: Path = DEFAULT_DB,
    *,
    run_status: str = "SUCCEEDED",
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    compile_network: bool = True,
) -> dict:
    started = utc_now()
    connection = sqlite3.connect(db_path)
    try:
        registry = rows(connection, "network_registry")[0]
        layer_rows = rows(connection, "network_layers")
        entity_rows = rows(connection, "entities")
        metric_rows = rows(connection, "metric_definitions")
        value_rows = rows(connection, "metric_values")
        evidence_rows = rows(connection, "evidence")
        raw_rows = rows(connection, "raw_documents")
        template_rows = rows(connection, "edge_templates")
        formula_rows = rows(connection, "formulas")
        edge_rows = rows(connection, "network_edges")
    finally:
        connection.close()

    cutoff = str(registry.get("data_cutoff") or started[:10])[:10]
    completed = utc_now()
    batch_id = stable("BATCH", NETWORK_ID, completed)
    layer_code_by_no = {item["layer_no"]: item["layer_code"] for item in layer_rows}
    raw_by_path = {str(item.get("snapshot_path") or ""): item for item in raw_rows if item.get("snapshot_path")}
    raw_by_url = {str(item.get("source_url") or ""): item for item in raw_rows if item.get("source_url")}
    formula_by_template = {}
    for item in formula_rows:
        formula_by_template.setdefault(item["template_id"], item)
    edges_by_template = {}
    for item in edge_rows:
        edges_by_template.setdefault(item["template_id"], []).append(item)

    sources = {}
    documents = {}
    evidence = []
    for item in evidence_rows:
        source_url = str(item.get("source_url") or "urn:nexus:source:unknown")
        publisher = str(item.get("publisher") or item.get("source_name") or "UNKNOWN")
        transport = source_transport(item)
        source_code = stable("SOURCE", publisher, transport, urlsplit(source_url).netloc)
        tier = item.get("source_tier") if item.get("source_tier") in {"T1", "T2", "T3"} else "T3"
        sources[source_code] = {
            "source_code": source_code,
            "source_name": item.get("source_name") or publisher,
            "source_type": transport,
            "publisher": publisher,
            "base_url": f"{urlsplit(source_url).scheme}://{urlsplit(source_url).netloc}" if urlsplit(source_url).netloc else source_url,
            "source_tier": tier,
            "license_status": "UNKNOWN",
            "status": "ACTIVE",
        }
        raw = raw_by_path.get(str(item.get("snapshot_path") or "")) or raw_by_url.get(source_url) or {}
        quote = str(item.get("original_quote") or "")
        content_sha = valid_sha(raw.get("content_sha256") or item.get("snapshot_sha256"), quote)
        document_id = str(raw.get("document_id") or stable("DOC", source_code, source_url, item.get("published_at"), content_sha))
        snapshot_path = raw.get("snapshot_path") or item.get("snapshot_path")
        document = {
            "document_id": document_id,
            "batch_id": batch_id,
            "source_code": source_code,
            "source_url": source_url,
            "canonical_url": source_url,
            "title": item.get("source_name") or publisher,
            "published_at": iso(item.get("published_at"), cutoff),
            "retrieved_at": iso(raw.get("retrieved_at") or item.get("retrieved_at"), completed),
            "content_type": raw.get("content_type") or ("application/pdf" if transport == "PDF" else "text/html"),
            "http_status": int(raw.get("http_status") or 200),
            "content_sha256": content_sha,
            "snapshot_path": snapshot_path,
            "parser_version": "nev-to-nexus-1.0.0",
            "parse_status": raw.get("parse_status") if raw.get("parse_status") in {"FETCHED", "PARSED", "NEEDS_REVIEW", "QUARANTINED", "ERROR"} else "PARSED",
        }
        if not snapshot_path:
            document["raw_payload"] = quote
        documents[document_id] = document
        acceptance = item.get("acceptance_status")
        if acceptance not in {"ACCEPTED", "AI_APPROVED", "PENDING_REVIEW", "REJECTED"}:
            acceptance = "PENDING_REVIEW"
        evidence.append({
            "evidence_id": item["evidence_id"],
            "document_id": document_id,
            "source_type": transport,
            "source_tier": tier,
            "published_at": iso(item.get("published_at"), cutoff),
            "retrieved_at": iso(item.get("retrieved_at"), completed),
            "original_quote": quote,
            "locator": item.get("locator") or "LEGACY:unlocated",
            "anchor_at": iso(item.get("anchor_at"), cutoff),
            "temporal_role": "POST_EVENT_VALIDATION" if item.get("temporal_role") == "POST_EVENT_VALIDATION" else "SOURCE_FACT",
            "snapshot_sha256": content_sha,
            "acceptance_status": acceptance,
            "acceptance_reason": item.get("acceptance_reason") or "LEGACY_MIGRATION",
        })

    evidence_by_id = {item["evidence_id"]: item for item in evidence}
    metric_by_code = {item["metric_code"]: item for item in metric_rows}
    observations = []
    for item in value_rows:
        ev = evidence_by_id.get(item["evidence_id"])
        metric = metric_by_code.get(item["metric_code"])
        if not ev or not metric:
            continue
        quality = item.get("value_status")
        quality_map = {"CALCULATED": "CALCULATED_LINEAGE", "CONFIRMED_DATA": "REPORTED_ACTUAL"}
        quality = quality_map.get(quality, quality)
        if quality not in {"SOURCE_FACT", "REPORTED_ACTUAL", "MARKET_PROXY", "AI_EXTRACTED", "CALCULATED_LINEAGE", "PENDING_REVIEW", "REJECTED"}:
            quality = "PENDING_REVIEW"
        as_of = business_date(item.get("as_of_date") or item.get("report_period"), item.get("published_at") or cutoff)
        available = iso(item.get("published_at") or ev.get("published_at"), cutoff)
        observations.append({
            "observation_id": item["metric_value_id"],
            "metric_code": item["metric_code"],
            "entity_code": item.get("entity_code"),
            "value": item.get("value"),
            "unit": item["unit"],
            "currency": item.get("currency"),
            "frequency": frequency(item["metric_code"], metric["metric_type"]),
            "report_period": item.get("report_period"),
            "published_at": iso(item.get("published_at"), cutoff) if item.get("published_at") else None,
            "as_of_date": as_of,
            "available_at": available,
            # The crawler contract defines this as the enclosing batch cutoff.
            # Historical timing remains available through as_of_date,
            # available_at, published_at and the linked evidence record.
            "data_cutoff": cutoff,
            "dimensions": {},
            "revision": 1,
            "quality_status": quality,
            "evidence_id": item["evidence_id"],
            "source_table": item.get("source_table"),
            "source_row_key": item.get("source_row_key") or item["metric_value_id"],
        })

    formulas = []
    relations = []
    for template in template_rows:
        instance = formula_by_template.get(template["template_id"]) or {}
        try:
            parameters = json.loads(instance.get("parameters_json") or "{}")
        except json.JSONDecodeError:
            parameters = {}
        formula_id = stable("FORMULA", NETWORK_ID, template["template_id"])
        parameter_status = template.get("parameter_status")
        if parameter_status not in {"CALIBRATED", "HUMAN_CONFIRMED", "CALCULATED_LINEAGE", "AI_ASSUMPTION", "MISSING"}:
            parameter_status = "AI_ASSUMPTION"
        formulas.append({
            "formula_id": formula_id,
            "formula_name": template.get("mechanism"),
            "formula_type": template["formula_type"],
            "formula_expression": template["formula_expression"],
            "parameters": parameters,
            "parameter_status": parameter_status,
            "causal_conclusion": "ABSTAIN",
            "evidence_ids": [],
            "status": "ACTIVE",
        })
        instances = edges_by_template.get(template["template_id"], [])
        confidence = sum(float(edge.get("confidence") or 0.35) for edge in instances) / max(1, len(instances))
        candidate_weight = parameters.get("candidate_weight") or parameters.get("weight") or parameters.get("beta") or parameters.get("coefficient")
        try:
            candidate_weight = abs(float(candidate_weight))
        except (TypeError, ValueError):
            candidate_weight = min(0.6, max(0.1, confidence * 0.5))
        relations.append({
            "relation_id": stable("REL", NETWORK_ID, template["template_id"]),
            "source_metric_code": template["source_metric_code"],
            "target_metric_code": template["target_metric_code"],
            "direction": direction(template["source_metric_code"], template["target_metric_code"], template["relation_type"]),
            "relation_type": template["relation_type"],
            "formula_id": formula_id,
            "entity_scope": template.get("scope") or "CROSS",
            "candidate_weight": candidate_weight,
            "lag_days": 0,
            "confidence": confidence,
            "impact_cap_pct": 30,
            "status": "AI_APPROVED",
            "parameter_status": parameter_status,
            "mechanism": template.get("mechanism") or f"{template['source_metric_code']} → {template['target_metric_code']}",
            "evidence_ids": [],
            "invalidation": "候选参数经历史数据校准后应生成新版本",
        })

    payload = {
        "contract_version": CONTRACT_VERSION,
        "network": {
            "network_id": NETWORK_ID,
            "domain_code": "NEW_ENERGY_VEHICLE",
            "network_name": registry["network_name"],
            "network_version": registry["network_version"],
            "network_kind": registry["network_kind"],
            "network_status": "CANDIDATE",
            "data_cutoff": cutoff,
            "causal_status": "ABSTAIN",
        },
        "batch": {
            "batch_id": batch_id,
            "domain_code": "NEW_ENERGY_VEHICLE",
            "collector_code": "NEV_LEGACY_ADAPTER",
            "collector_version": "1.0.0",
            "started_at": started,
            "completed_at": completed,
            "data_cutoff": cutoff,
            "run_type": "DAILY",
            "status": run_status if run_status in {"SUCCEEDED", "PARTIAL", "FAILED"} else "PARTIAL",
        },
        "sources": list(sources.values()),
        "documents": list(documents.values()),
        "evidence": evidence,
        "layers": [
            {"layer_no": item["layer_no"], "layer_code": item["layer_code"], "layer_name": item["layer_name_cn"], "path_role": item["path_role"], "sort_order": item["sort_order"], "status": item["status"]}
            for item in layer_rows
        ],
        "entities": [
            {"entity_code": item["entity_code"], "entity_name": item["entity_name_cn"], "entity_type": "COMPANY", "stock_code": item["entity_code"], "exchange_code": item.get("exchange_code"), "country": item.get("country"), "currency": "CNY", "aliases": [], "status": "ACTIVE" if item.get("status") == "ACTIVE" else "INACTIVE"}
            for item in entity_rows
        ],
        "metric_definitions": [
            {"metric_code": item["metric_code"], "metric_name": item["metric_name_cn"], "description": item["description"], "metric_type": item["metric_type"].upper(), "canonical_unit": item["canonical_unit"], "unit_family": unit_family(item["metric_type"], item["canonical_unit"]), "frequency": frequency(item["metric_code"], item["metric_type"]), "entity_scope": item["entity_scope"], "default_layer_code": layer_code_by_no[item["layer_no"]], "editable_default": bool(item["editable_default"]), "required_for_network": bool(item["required_for_network"]), "contract_version": CONTRACT_VERSION, "status": item["status"]}
            for item in metric_rows
        ],
        "observations": observations,
        "formulas": formulas,
        "relations": relations,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{batch_id}.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = {"status": "EXPORTED", "batch_id": batch_id, "output": str(output_path), "counts": {name: len(payload[name]) for name in ("sources", "documents", "evidence", "layers", "entities", "metric_definitions", "observations", "formulas", "relations")}}
    if compile_network and run_status != "FAILED":
        sys.path.insert(0, str(SANDBOX))
        from crawler_network_compiler import compile_crawler_network

        plan = compile_crawler_network(payload)
        plan_path = SANDBOX / "runs" / "networks" / f"{plan['networkPlanId']}.json"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result["network"] = {"networkPlanId": plan["networkPlanId"], "output": str(plan_path), "readiness": plan["readiness"], "nodeCount": len(plan["nodes"]), "edgeCount": len(plan["edges"])}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export the NEV collector database as a NEXUS crawler batch.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-status", choices=("SUCCEEDED", "PARTIAL", "FAILED"), default="SUCCEEDED")
    parser.add_argument("--no-compile", action="store_true")
    args = parser.parse_args()
    print(json.dumps(export_batch(args.db, run_status=args.run_status, output_dir=args.output_dir, compile_network=not args.no_compile), ensure_ascii=False, indent=2))
