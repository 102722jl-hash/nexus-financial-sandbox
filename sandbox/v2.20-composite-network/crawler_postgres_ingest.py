from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from crawler_contract import CONTRACT_VERSION, validate_crawler_payload
from crawler_network_compiler import compile_crawler_network


ROOT = Path(__file__).resolve().parent


def _text(value: Any) -> str:
    return str(value or "").strip()


def _json(value: Any) -> Jsonb:
    return Jsonb(value if value is not None else {})


def _quarantined_ids(report: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (_text(item.get("objectType")), _text(item.get("objectId")))
        for item in report.get("quarantine") or []
        if item.get("objectType") and item.get("objectId")
    }


def _raw_bytes(value: Any) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")


def _upsert_many(
    cursor: psycopg.Cursor[Any],
    schema: str,
    table: str,
    columns: list[str],
    conflict_columns: list[str],
    rows: Iterable[tuple[Any, ...]],
    update_columns: list[str] | None = None,
) -> int:
    rows = list(rows)
    if not rows:
        return 0
    if update_columns:
        action = sql.SQL("DO UPDATE SET ") + sql.SQL(",").join(
            sql.SQL("{}=excluded.{}").format(sql.Identifier(name), sql.Identifier(name))
            for name in update_columns
        )
    else:
        action = sql.SQL("DO NOTHING")
    statement = sql.SQL("INSERT INTO {}.{} ({}) VALUES ({}) ON CONFLICT ({}) {}").format(
        sql.Identifier(schema),
        sql.Identifier(table),
        sql.SQL(",").join(sql.Identifier(name) for name in columns),
        sql.SQL(",").join(sql.Placeholder() for _ in columns),
        sql.SQL(",").join(sql.Identifier(name) for name in conflict_columns),
        action,
    )
    cursor.executemany(statement, rows)
    return len(rows)


def ingest_crawler_payload(
    connection: psycopg.Connection[Any],
    payload: dict[str, Any],
    *,
    schema: str = "nexus",
) -> dict[str, Any]:
    """Incrementally and idempotently write one validated batch to PostgreSQL."""
    report = validate_crawler_payload(payload)
    if not report["ingestionAllowed"]:
        codes = ",".join(item["code"] for item in report["blockingIssues"])
        raise ValueError(f"CRAWLER_BATCH_BLOCKED:{codes}")

    network = payload["network"]
    batch = payload["batch"]
    network_id = network["network_id"]
    batch_id = batch["batch_id"]
    quarantined = _quarantined_ids(report)
    compiled = compile_crawler_network(payload) if report["networkCompilationAllowed"] else None
    counts: dict[str, int] = {}

    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("SELECT 1 FROM {}.contract_meta WHERE contract_version=%s AND status='ACTIVE'").format(sql.Identifier(schema)),
                (CONTRACT_VERSION,),
            )
            if not cursor.fetchone():
                raise RuntimeError("CRAWLER_CONTRACT_NOT_INSTALLED")

            counts["network_registry"] = _upsert_many(
                cursor, schema, "network_registry",
                ["network_id", "domain_code", "network_name", "network_version", "schema_version", "network_status", "network_kind", "data_cutoff", "causal_status"],
                ["network_id"],
                [(network_id, network["domain_code"], network["network_name"], network["network_version"], "composite-network-1.0.0", network["network_status"], network["network_kind"], network["data_cutoff"], network["causal_status"])],
                ["network_name", "network_version", "network_status", "network_kind", "data_cutoff", "causal_status", "updated_at"],
            )

            active_sources = [item for item in payload.get("sources") or [] if ("source", _text(item.get("source_code"))) not in quarantined]
            counts["source_registry"] = _upsert_many(
                cursor, schema, "source_registry",
                ["source_code", "source_name", "source_type", "publisher", "base_url", "source_tier", "license_status", "robots_policy", "rate_limit_per_minute", "status"],
                ["source_code"],
                [(item["source_code"], item["source_name"], item["source_type"], item["publisher"], item["base_url"], item["source_tier"], item["license_status"], item.get("robots_policy"), item.get("rate_limit_per_minute"), item["status"]) for item in active_sources],
                ["source_name", "publisher", "base_url", "source_tier", "license_status", "robots_policy", "rate_limit_per_minute", "status", "updated_at"],
            )

            counts["ingestion_runs"] = _upsert_many(
                cursor, schema, "ingestion_runs",
                ["batch_id", "contract_version", "domain_code", "collector_code", "collector_version", "run_type", "started_at", "completed_at", "data_cutoff", "status", "document_count", "evidence_count", "observation_count", "quarantine_count", "manifest_sha256", "error_summary"],
                ["batch_id"],
                [(batch_id, payload["contract_version"], batch["domain_code"], batch["collector_code"], batch["collector_version"], batch["run_type"], batch["started_at"], batch["completed_at"], batch["data_cutoff"], "PARTIAL" if report["quarantine"] else batch["status"], len(payload.get("documents") or []), len(payload.get("evidence") or []), len(payload.get("observations") or []), len(report["quarantine"]), batch.get("manifest_sha256"), _json(batch.get("error_summary") or {}))],
                ["status", "document_count", "evidence_count", "observation_count", "quarantine_count", "manifest_sha256", "error_summary"],
            )

            documents = [item for item in payload.get("documents") or [] if ("document", _text(item.get("document_id"))) not in quarantined]
            counts["raw_documents"] = _upsert_many(
                cursor, schema, "raw_documents",
                ["document_id", "batch_id", "source_code", "source_url", "canonical_url", "title", "published_at", "retrieved_at", "content_type", "http_status", "content_sha256", "snapshot_path", "raw_payload", "language", "encoding", "etag", "last_modified", "parser_version", "parse_status", "error_code", "error_message"],
                ["document_id"],
                [(item["document_id"], batch_id, item["source_code"], item["source_url"], item["canonical_url"], item.get("title"), item.get("published_at"), item["retrieved_at"], item["content_type"], item["http_status"], item["content_sha256"], item.get("snapshot_path"), _raw_bytes(item.get("raw_payload")), item.get("language"), item.get("encoding"), item.get("etag"), item.get("last_modified"), item.get("parser_version"), item["parse_status"], item.get("error_code"), item.get("error_message")) for item in documents],
            )

            evidence = [item for item in payload.get("evidence") or [] if ("evidence", _text(item.get("evidence_id"))) not in quarantined]
            counts["evidence"] = _upsert_many(
                cursor, schema, "evidence",
                ["evidence_id", "document_id", "source_type", "source_tier", "published_at", "retrieved_at", "original_quote", "locator", "page_number", "table_name", "row_label", "column_label", "json_pointer", "anchor_at", "temporal_role", "snapshot_sha256", "acceptance_status", "acceptance_reason", "reviewed_by", "reviewed_at"],
                ["evidence_id"],
                [(item["evidence_id"], item["document_id"], item["source_type"], item["source_tier"], item.get("published_at"), item["retrieved_at"], item["original_quote"], item["locator"], item.get("page_number"), item.get("table_name"), item.get("row_label"), item.get("column_label"), item.get("json_pointer"), item["anchor_at"], item["temporal_role"], item["snapshot_sha256"], item["acceptance_status"], item["acceptance_reason"], item.get("reviewed_by"), item.get("reviewed_at")) for item in evidence],
            )

            layers = payload.get("layers") or []
            counts["network_layers"] = _upsert_many(
                cursor, schema, "network_layers",
                ["network_id", "layer_no", "layer_code", "layer_name", "layer_subtitle", "path_role", "sort_order", "status"],
                ["network_id", "layer_no"],
                [(network_id, item["layer_no"], item["layer_code"], item["layer_name"], item.get("layer_subtitle"), item["path_role"], item["sort_order"], item.get("status", "ACTIVE")) for item in layers],
                ["layer_code", "layer_name", "layer_subtitle", "path_role", "sort_order", "status"],
            )

            entities = [item for item in payload.get("entities") or [] if ("entity", _text(item.get("entity_code"))) not in quarantined]
            entities.sort(key=lambda item: bool(item.get("parent_entity_code")))
            counts["entities"] = _upsert_many(
                cursor, schema, "entities",
                ["network_id", "entity_code", "entity_name", "entity_type", "parent_entity_code", "stock_code", "exchange_code", "industry_code", "country", "currency", "aliases", "valid_from", "valid_to", "status"],
                ["network_id", "entity_code"],
                [(network_id, item["entity_code"], item["entity_name"], item["entity_type"], item.get("parent_entity_code"), item.get("stock_code"), item.get("exchange_code"), item.get("industry_code"), item.get("country"), item.get("currency"), _json(item.get("aliases") or []), item.get("valid_from"), item.get("valid_to"), item["status"]) for item in entities],
                ["entity_name", "entity_type", "parent_entity_code", "stock_code", "exchange_code", "industry_code", "country", "currency", "aliases", "valid_from", "valid_to", "status", "updated_at"],
            )

            metrics = [item for item in payload.get("metric_definitions") or [] if ("metric_definition", _text(item.get("metric_code"))) not in quarantined]
            counts["metric_definitions"] = _upsert_many(
                cursor, schema, "metric_definitions",
                ["network_id", "metric_code", "metric_name", "aliases", "description", "metric_type", "canonical_unit", "unit_family", "frequency", "entity_scope", "default_layer_code", "editable_default", "aggregation_method", "value_min", "value_max", "currency_policy", "required_for_network", "contract_version", "status"],
                ["network_id", "metric_code"],
                [(network_id, item["metric_code"], item["metric_name"], _json(item.get("aliases") or []), item.get("description", ""), item["metric_type"], item["canonical_unit"], item["unit_family"], item["frequency"], item["entity_scope"], item["default_layer_code"], item["editable_default"], item.get("aggregation_method"), item.get("value_min"), item.get("value_max"), item.get("currency_policy"), item.get("required_for_network", False), item.get("contract_version", CONTRACT_VERSION), item["status"]) for item in metrics],
                ["metric_name", "aliases", "description", "metric_type", "canonical_unit", "unit_family", "frequency", "entity_scope", "default_layer_code", "editable_default", "aggregation_method", "value_min", "value_max", "currency_policy", "required_for_network", "status", "updated_at"],
            )

            observations = [item for item in payload.get("observations") or [] if ("observation", _text(item.get("observation_id"))) not in quarantined]
            counts["metric_values"] = _upsert_many(
                cursor, schema, "metric_values",
                ["network_id", "observation_id", "batch_id", "metric_code", "entity_code", "value", "text_value", "unit", "currency", "frequency", "report_period", "as_of_date", "published_at", "available_at", "data_cutoff", "dimensions", "revision", "quality_status", "evidence_id", "source_table", "source_column", "source_row_key"],
                ["observation_id"],
                [(network_id, item["observation_id"], batch_id, item["metric_code"], item.get("entity_code"), item.get("value"), item.get("text_value"), item["unit"], item.get("currency"), item.get("frequency") or next((m["frequency"] for m in metrics if m["metric_code"] == item["metric_code"]), "EVENT"), item.get("report_period"), item["as_of_date"], item.get("published_at"), item["available_at"], item["data_cutoff"], _json(item.get("dimensions") or {}), item["revision"], item["quality_status"], item["evidence_id"], item.get("source_table"), item.get("source_column"), item["source_row_key"]) for item in observations],
            )

            formulas = [item for item in payload.get("formulas") or [] if ("formula", _text(item.get("formula_id"))) not in quarantined]
            counts["formulas"] = _upsert_many(
                cursor, schema, "formulas",
                ["network_id", "formula_id", "formula_name", "formula_type", "formula_expression", "parameters", "formula_version", "parameter_status", "causal_conclusion", "evidence_ids", "invalidation", "status"],
                ["network_id", "formula_id"],
                [(network_id, item["formula_id"], item.get("formula_name"), item["formula_type"], item["formula_expression"], _json(item["parameters"]), "1.0.0", item["parameter_status"], item["causal_conclusion"], _json(item.get("evidence_ids") or []), item.get("invalidation"), item["status"]) for item in formulas],
                ["formula_name", "formula_type", "formula_expression", "parameters", "formula_version", "parameter_status", "causal_conclusion", "evidence_ids", "invalidation", "status", "updated_at"],
            )

            if compiled:
                counts["network_nodes"] = _upsert_many(
                    cursor, schema, "network_nodes",
                    ["network_id", "node_id", "layer_no", "node_name_cn", "node_type", "metric_code", "metric_name", "metric_type", "unit", "baseline_value", "editable", "quality_status", "entity_code", "evidence_id", "source_observation_id", "data_cutoff", "description", "sort_order", "status"],
                    ["network_id", "node_id"],
                    [(network_id, item["nodeId"], item["layerNo"], item["label"], item["nodeType"], item["metricCodes"][0], item["label"].split("｜")[-1], item["nodeType"], item["unit"], item.get("baseline", {}).get("BASE"), item["editable"], item["valueStatus"], item.get("entityCode"), (item.get("evidenceIds") or [None])[0], item.get("sourceObservationId"), network["data_cutoff"], item.get("description"), index, "CONFIRMED_DATA" if item["status"] == "CONFIRMED_DATA" else "DATA_MISSING") for index, item in enumerate(compiled["nodes"])],
                    ["layer_no", "node_name_cn", "node_type", "metric_code", "metric_name", "metric_type", "unit", "baseline_value", "editable", "quality_status", "entity_code", "evidence_id", "source_observation_id", "data_cutoff", "description", "sort_order", "status", "updated_at"],
                )
                counts["network_edges"] = _upsert_many(
                    cursor, schema, "network_edges",
                    ["network_id", "edge_id", "source_node_id", "target_node_id", "direction", "relation_type", "formula_id", "formula_type", "parameter_status", "weight", "candidate_weight", "lag_days", "confidence", "impact_cap_pct", "mechanism", "parameters", "evidence_ids", "invalidation", "status"],
                    ["network_id", "edge_id"],
                    [(network_id, item["edgeId"], item["sourceNodeId"], item["targetNodeId"], item["direction"], item["relationType"], item["formulaId"], item["formulaType"], item["parameterStatus"], item["weight"] or None, item["candidateWeight"] or None, item["lagDays"], item["confidence"], item["impactCapPct"] or None, item["mechanism"], _json(item.get("formulaParameters") or {}), _json(item.get("evidenceSource") or []), item.get("invalidation"), item["status"]) for item in compiled["edges"]],
                    ["source_node_id", "target_node_id", "direction", "relation_type", "formula_id", "formula_type", "parameter_status", "weight", "candidate_weight", "lag_days", "confidence", "impact_cap_pct", "mechanism", "parameters", "evidence_ids", "invalidation", "status", "updated_at"],
                )
            else:
                counts["network_nodes"] = 0
                counts["network_edges"] = 0

            quarantine_rows = []
            for issue in [*report["warnings"], *report["quarantine"]]:
                quarantine_rows.append((batch_id, issue.get("objectType") or "BATCH", issue.get("objectId") or batch_id, issue["code"], issue["severity"], _json(issue), "OPEN"))
            counts["quarantine"] = _upsert_many(
                cursor, schema, "quarantine",
                ["batch_id", "object_type", "object_id", "reason_code", "severity", "payload_json", "status"],
                ["batch_id", "object_type", "object_id", "reason_code"],
                quarantine_rows,
                ["severity", "payload_json", "status"],
            )

            if compiled:
                canonical = json.dumps(compiled["fullGraph"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                graph_sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                counts["network_versions"] = _upsert_many(
                    cursor, schema, "network_versions",
                    ["network_id", "version_id", "parent_version_id", "source_batch_ids_json", "mapping_version", "formula_registry_version", "graph_sha256", "readiness_json", "quality_report_json", "activation_status"],
                    ["network_id", "version_id"],
                    [(network_id, compiled["networkPlanId"], None, _json([batch_id]), CONTRACT_VERSION, "generic-formula-registry-1.0.0", graph_sha, _json(compiled["readiness"]), _json(compiled["qualityReport"]), "CANDIDATE")],
                    ["source_batch_ids_json", "graph_sha256", "readiness_json", "quality_report_json", "activation_status"],
                )
            else:
                counts["network_versions"] = 0

    return {
        "status": "INGESTED" if not report["quarantine"] else "PARTIAL",
        "batchId": batch_id,
        "networkId": network_id,
        "networkPlanId": compiled.get("networkPlanId") if compiled else None,
        "readiness": compiled.get("readiness") if compiled else report["readiness"],
        "counts": counts,
        "quarantineCount": len(report["quarantine"]) + len(report["warnings"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Idempotently ingest a NEXUS crawler batch into PostgreSQL.")
    parser.add_argument("payload", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--database", required=True)
    parser.add_argument("--schema", default="nexus")
    parser.add_argument("--user", required=True)
    parser.add_argument("--password-env", required=True)
    args = parser.parse_args()
    password = os.environ.get(args.password_env)
    if not password:
        raise ValueError(f"missing environment variable: {args.password_env}")
    payload = json.loads(args.payload.read_text(encoding="utf-8"))
    with psycopg.connect(host=args.host, port=args.port, dbname=args.database, user=args.user, password=password, sslmode="prefer", connect_timeout=10) as connection:
        result = ingest_crawler_payload(connection, payload, schema=args.schema)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
