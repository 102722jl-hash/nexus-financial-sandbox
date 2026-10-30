"""Loopback-only connector and static server for the auditable sandbox."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg
from psycopg import sql
from cryptography.fernet import Fernet, InvalidToken
from db_connectors import profile_database, public_config, table_adapters
from ai_adapter import AIAdapterError, AI_MAPPING_BATCH_SIZE, edge_candidates as ai_edge_candidates, explain_result as ai_explain_result, mapping_candidates as ai_mapping_candidates, public_config as public_ai_config, test_session as test_ai_session
from v218_pipeline import (
    METRICS,
    active_graph,
    auto_confirm_precompiled_candidates,
    build_network_plan,
    rule_candidates,
    simulate,
    sync_database,
    sync_records,
    table_adapter_candidates,
)


ROOT = Path(__file__).resolve().parent
STAGING = ROOT / "staging"
RUNS = ROOT / "runs"
NETWORKS_DIR = RUNS / "networks"
AI_MAPPING_CACHE_PATH = RUNS / "ai-mapping-cache-v1.json"
MAX_BODY = 30 * 1024 * 1024
CLIENT_ID = re.compile(r"^CLIENT-[A-Za-z0-9-]{8,96}$")
ALLOWED_TABLES = ("asharebalancesheet", "asharecashflow", "ashareincome")
TASKS: dict[str, dict[str, Any]] = {}
CONNECTIONS: dict[str, dict[str, Any]] = {}
SOURCES: dict[str, dict[str, Any]] = {}
MAPPINGS: dict[str, dict[str, Any]] = {}
SCENARIOS: dict[str, dict[str, Any]] = {}
SCENARIO_RESULTS: dict[str, dict[str, Any]] = {}
METRIC_VALUES: dict[str, list[dict[str, Any]]] = {}
EVIDENCE: dict[str, dict[str, Any]] = {}
SOURCE_SNAPSHOTS: dict[str, dict[str, Any]] = {}
NETWORK_PLANS: dict[str, dict[str, Any]] = {}
ACTIVE_PLANS: dict[str, str] = {}
AI_SESSIONS: dict[str, dict[str, Any]] = {}
AI_MAPPING_JOBS: dict[str, dict[str, Any]] = {}
AI_MAPPING_CACHE: dict[str, dict[str, Any]] = {}
AI_MAPPING_LOCK = threading.RLock()
SYNC_CANCELLED: set[str] = set()
CREDENTIAL_VAULT = Fernet(Fernet.generate_key())
POSTGRES = {
    "host": "rsshub.weixiewen.cn",
    "port": 5589,
    "dbname": "pg",
    "user": "dwzq",
    "sslmode": "prefer",
    "options": "-c default_transaction_read_only=on -c statement_timeout=60000",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def persisted_network(network_id: str) -> dict[str, Any] | None:
    if not network_id or network_id != Path(network_id).name:
        return None
    path = NETWORKS_DIR / (network_id + ".json")
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def persist_active_network(plan: dict[str, Any]) -> dict[str, Any]:
    """Atomically persist a complete standalone network for later switching."""
    network_id = str(plan.get("networkPlanId") or "")
    if not network_id.startswith("PLAN-") or network_id != Path(network_id).name or len(network_id) > 128:
        raise ValueError("NETWORK_ID_INVALID")
    graph = plan.get("fullGraph") or plan.get("graph") or {}
    full_graph = {
        "nodes": list(graph.get("nodes") or []),
        "edges": list(graph.get("edges") or []),
    }
    saved = {
        **plan,
        "networkId": network_id,
        "networkPlanId": network_id,
        "mode": "CREATE_NEW_NETWORK",
        "graph": full_graph,
        "fullGraph": full_graph,
        "nodes": full_graph["nodes"],
        "edges": full_graph["edges"],
        "deletable": True,
    }
    NETWORKS_DIR.mkdir(parents=True, exist_ok=True)
    target = NETWORKS_DIR / f"{network_id}.json"
    temporary = NETWORKS_DIR / f".{network_id}.{threading.get_ident()}.tmp"
    try:
        temporary.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return saved

def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def task(task_type: str, input_value: Any, detail: str) -> dict[str, Any]:
    input_hash = stable_hash({"type": task_type, "input": input_value})
    task_id = f"TASK-{input_hash[:12].upper()}"
    existing = TASKS.get(task_id)
    if existing:
        return existing
    item = {
        "taskId": task_id,
        "type": task_type,
        "status": "SUCCEEDED",
        "detail": detail,
        "inputHash": input_hash,
        "createdAt": now(),
    }
    TASKS[task_id] = item
    return item


def resource_id(prefix: str, payload: Any) -> str:
    return f"{prefix}-{stable_hash(payload)[:12].upper()}"


AI_RELEVANCE_TOKENS = (
    "cash", "money", "monet", "invent", "rcv", "receiv", "prepay", "asset", "liab",
    "debt", "borrow", "bond", "lease", "equity", "shrhldr", "share", "shr", "revenue",
    "oper_rev", "income", "profit", "cost", "ebit", "eps", "capex", "cash_flow", "cash_flows",
)


def _mapping_cache_key(field: dict[str, Any]) -> str:
    parts = str(field.get("sourceField") or "").lower().split(".")
    return stable_hash({"field": ".".join(parts[-2:]), "dtype": str(field.get("dataType") or ""), "catalog": "STEEL-40-V1"})


def _load_mapping_cache() -> None:
    if AI_MAPPING_CACHE or not AI_MAPPING_CACHE_PATH.is_file():
        return
    try:
        loaded = json.loads(AI_MAPPING_CACHE_PATH.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            AI_MAPPING_CACHE.update({str(key): value for key, value in loaded.items() if isinstance(value, dict)})
    except (OSError, json.JSONDecodeError):
        return


def _save_mapping_cache() -> None:
    RUNS.mkdir(exist_ok=True)
    temporary = AI_MAPPING_CACHE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(AI_MAPPING_CACHE, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(AI_MAPPING_CACHE_PATH)


def _mapping_relevance(field: dict[str, Any]) -> int:
    name = str(field.get("sourceField") or "").lower()
    return sum(1 for token in AI_RELEVANCE_TOKENS if token in name)


def _apply_ai_mapping_candidate(source_id: str, candidate: dict[str, Any]) -> dict[str, Any] | None:
    mapping = next((item for item in MAPPINGS.values() if item.get("sourceId") == source_id and item.get("sourceField") == candidate.get("sourceField")), None)
    if not mapping or mapping.get("status") != "UNRESOLVED":
        return None
    action = str(candidate.get("suggestedAction") or candidate.get("action") or "MAP").upper()
    if action == "IGNORE":
        enriched = {**candidate, "action": "IGNORE", "suggestedAction": "IGNORE", "metricCode": "UNRESOLVED", "metricName": "建议忽略", "status": "PENDING_REVIEW"}
    else:
        metric = next((item for item in METRICS if item["metricCode"] == candidate.get("metricCode")), None)
        if not metric:
            return None
        enriched = {**candidate, "action": "MAP", "suggestedAction": "MAP", "metricName": metric["metricName"], "status": "PENDING_REVIEW"}
    mapping.update({**enriched, "mappingId": mapping["mappingId"], "sourceId": source_id, "sourceColumn": mapping["sourceField"]})
    return dict(mapping)


def _run_ai_mapping_job(job_id: str, source_id: str, fields: list[dict[str, Any]], config: dict[str, Any]) -> None:
    with AI_MAPPING_LOCK:
        job = AI_MAPPING_JOBS[job_id]
        job.update({"status": "RUNNING", "startedAt": now()})
        _load_mapping_cache()
    ranked = sorted(fields, key=lambda item: (-_mapping_relevance(item), item["sourceField"]))
    ai_fields = [item for item in ranked if _mapping_relevance(item) > 0][:32]
    ai_field_names = {item["sourceField"] for item in ai_fields}
    local_ignored = [item for item in fields if item["sourceField"] not in ai_field_names]
    initial_candidates = []
    for field in local_ignored:
        candidate = {
            "sourceField": field["sourceField"], "action": "IGNORE", "suggestedAction": "IGNORE",
            "metricCode": "UNRESOLVED", "confidence": 0.86,
            "reason": "未命中金融标准指标关键词，建议不纳入当前领域",
            "evidence": ["LOCAL_SCHEMA_PREFILTER"], "candidateSource": "LOCAL_PREFILTER", "status": "PENDING_REVIEW",
        }
        applied = _apply_ai_mapping_candidate(source_id, candidate)
        if applied:
            initial_candidates.append(applied)
    uncached = []
    for field in ai_fields:
        cached = AI_MAPPING_CACHE.get(_mapping_cache_key(field))
        applied = _apply_ai_mapping_candidate(source_id, {**cached, "sourceField": field["sourceField"], "candidateSource": "AI_CACHE"}) if cached else None
        if applied:
            initial_candidates.append(applied)
        else:
            uncached.append(field)
    batches = [uncached[index:index + AI_MAPPING_BATCH_SIZE] for index in range(0, len(uncached), AI_MAPPING_BATCH_SIZE)]
    with AI_MAPPING_LOCK:
        job.update({
            "processedFields": len(initial_candidates), "aiQueuedFields": len(uncached),
            "localSuggestedIgnore": len(local_ignored), "cachedCandidates": len(ai_fields) - len(uncached),
            "totalBatches": len(batches), "completedBatches": 0, "candidates": initial_candidates,
        })
    if batches:
        with ThreadPoolExecutor(max_workers=min(3, len(batches)), thread_name_prefix="nexus-ai-map") as executor:
            futures = {executor.submit(ai_mapping_candidates, config, batch, METRICS): batch for batch in batches}
            for future in as_completed(futures):
                batch = futures[future]
                try:
                    candidates = future.result()
                    applied_candidates = []
                    with AI_MAPPING_LOCK:
                        for candidate in candidates:
                            applied = _apply_ai_mapping_candidate(source_id, candidate)
                            if applied:
                                applied_candidates.append(applied)
                                AI_MAPPING_CACHE[_mapping_cache_key({"sourceField": candidate["sourceField"], "dataType": next((item["dataType"] for item in batch if item["sourceField"] == candidate["sourceField"]), "unknown")})] = {key: candidate.get(key) for key in ("action", "suggestedAction", "metricCode", "confidence", "reason", "evidence", "candidateSource", "status")}
                        job["candidates"].extend(applied_candidates)
                        job["processedFields"] += len(batch)
                        job["completedBatches"] += 1
                        _save_mapping_cache()
                except AIAdapterError as exc:
                    with AI_MAPPING_LOCK:
                        job["processedFields"] += len(batch)
                        job["completedBatches"] += 1
                        job["errors"].append({"code": exc.status, "detail": exc.detail, "fieldCount": len(batch)})
    with AI_MAPPING_LOCK:
        job.update({"status": "PARTIAL" if job["errors"] else "SUCCEEDED", "finishedAt": now(), "remainingUnresolved": sum(1 for item in MAPPINGS.values() if item.get("sourceId") == source_id and item.get("status") == "UNRESOLVED")})


def public_connection(config: dict[str, Any], connection_id: str) -> dict[str, Any]:
    return {
        "id": connection_id,
        "type": config.get("type"),
        "host": config.get("host"),
        "port": config.get("port"),
        "database": config.get("database"),
        "schema": config.get("schema"),
        "user": config.get("user"),
        "readOnly": True,
        "credentialPersisted": False,
    }


def seal_credential(value: str | None) -> str | None:
    if not value:
        return None
    return CREDENTIAL_VAULT.encrypt(value.encode("utf-8")).decode("ascii")


def open_credential(blob: str | None) -> str | None:
    if not blob:
        return None
    try:
        return CREDENTIAL_VAULT.decrypt(blob.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("CREDENTIAL_SESSION_EXPIRED") from exc


def connection_config(item: dict[str, Any]) -> dict[str, Any]:
    config = dict(item["config"])
    password = open_credential(item.get("credentialBlob"))
    if password:
        config["password"] = password
    return config


def steel_nodes() -> list[dict[str, Any]]:
    return [
        {"nodeId": "coking-coal-price", "layer": "macro", "label": "焦煤价格", "unit": "%", "source": "DOMAIN_PACKAGE"},
        {"nodeId": "raw-material-cost", "layer": "demand", "label": "钢铁原料成本", "unit": "%", "source": "DOMAIN_PACKAGE"},
        {"nodeId": "steel-orders", "layer": "demand", "label": "钢材订单", "unit": "%", "source": "DOMAIN_PACKAGE"},
        {"nodeId": "blast-furnace-margin", "layer": "chain", "label": "高炉炼钢利润", "unit": "%", "source": "DOMAIN_PACKAGE"},
        {"nodeId": "steel-company", "layer": "company", "label": "钢铁公司", "unit": "%", "source": "DOMAIN_PACKAGE"},
    ]


def steel_edges() -> list[dict[str, Any]]:
    return [
        {"edgeId": "edge-12", "sourceNodeId": "coking-coal-price", "targetNodeId": "raw-material-cost", "direction": "negative", "weight": 0.70, "lagDays": 30, "confidence": 0.82, "mechanism": "焦煤价格进入高炉原料成本", "evidenceSource": "DOMAIN_PACKAGE", "status": "CONFIRMED"},
        {"edgeId": "edge-13", "sourceNodeId": "raw-material-cost", "targetNodeId": "blast-furnace-margin", "direction": "negative", "weight": 0.60, "lagDays": 45, "confidence": 0.78, "mechanism": "原料成本变化进入钢材价差", "evidenceSource": "DOMAIN_PACKAGE", "status": "CONFIRMED"},
        {"edgeId": "edge-14", "sourceNodeId": "steel-orders", "targetNodeId": "blast-furnace-margin", "direction": "positive", "weight": 0.58, "lagDays": 60, "confidence": 0.74, "mechanism": "订单量变化影响高炉利用率和利润", "evidenceSource": "DOMAIN_PACKAGE", "status": "CANDIDATE"},
        {"edgeId": "edge-15", "sourceNodeId": "blast-furnace-margin", "targetNodeId": "steel-company", "direction": "positive", "weight": 0.72, "lagDays": 90, "confidence": 0.68, "mechanism": "利润池变化进入公司经营结果", "evidenceSource": "DOMAIN_PACKAGE", "status": "CANDIDATE"},
    ]


def scenario_result(changes: list[dict[str, Any]]) -> dict[str, Any]:
    change = next((float(item.get("changePercent", 0)) for item in changes if item.get("metricCode") in {"JM_PRICE", "cokingCoalPrice"}), 0.0)
    nodes = steel_nodes()
    factors = [-0.70, 0.42, 0.58, 0.30, 0.22]
    reasons = [
        "焦煤价格下降降低高炉炼钢原料成本",
        "原料成本变化经过库存与采购周期传递",
        "订单未变时，成本下降提高高炉价差",
        "产业利润池变化进入公司经营结果",
        "公司节点结果需结合分部暴露和财务桥接",
    ]
    affected = [
        {"nodeId": node["nodeId"], "changePercent": round(change * factors[index], 2), "confidence": [0.82, 0.78, 0.74, 0.68, 0.45][index], "reason": reasons[index]}
        for index, node in enumerate(nodes)
        if index < len(factors) and change
    ]
    return {
        "affectedNodes": affected,
        "affectedEdges": [edge["edgeId"] for edge in steel_edges() if change and edge["edgeId"] in {"edge-12", "edge-13", "edge-14", "edge-15"}],
        "summary": "焦煤成本下降对高炉炼钢利润形成正向影响" if change < 0 else "焦煤价格变化对高炉炼钢利润形成候选影响",
        "status": "CALCULATED" if affected else "PARTIAL",
        "evidenceStatus": "NEEDS_HUMAN_REVIEW",
        "causalStatus": "ABSTAIN",
    }


def mapping_candidates(columns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aliases = {
        "coking_coal_price": ("JM_PRICE", 0.86, "字段名称与焦煤价格词典匹配"),
        "steel_demand": ("STEEL_DEMAND", 0.84, "字段名称与钢材需求词典匹配"),
        "revenue": ("REVENUE", 0.80, "字段名称与营业收入词典匹配"),
        "net_profit": ("NET_PROFIT", 0.80, "字段名称与净利润词典匹配"),
        "operating_cash_flow": ("OCF", 0.78, "字段名称与经营现金流词典匹配"),
        "free_cash_flow": ("FCF", 0.78, "字段名称与自由现金流词典匹配"),
    }
    candidates = []
    for column in columns:
        source = str(column.get("column") or "")
        leaf = source.rsplit(".", 1)[-1].lower().replace("-", "_").replace(" ", "_")
        metric, confidence, reason = aliases.get(leaf, ("UNMAPPED", 0.0, "规则词典未识别，等待 AI 或人工审核"))
        candidates.append({
            "id": resource_id("MAP", {"source": source, "metric": metric}),
            "sourceColumn": source,
            "metricCode": metric,
            "status": "PENDING_REVIEW",
            "confidence": confidence,
            "reason": reason,
            "evidence": ["SCHEMA_PROFILE"],
        })
    return candidates


def postgres_profile() -> dict[str, Any]:
    with psycopg.connect(**POSTGRES) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        read_only = conn.execute("SHOW transaction_read_only").fetchone()[0]
        if read_only != "on":
            raise RuntimeError("READ_ONLY_GUARD_FAILED")
        identity = conn.execute(
            "SELECT current_user, current_database(), inet_server_addr(), inet_server_port()"
        ).fetchone()
        tables = []
        for table in ALLOWED_TABLES:
            query = sql.SQL(
                """
                SELECT count(*), count(DISTINCT s_info_windcode),
                       min(report_period), max(report_period),
                       max(COALESCE(NULLIF(actual_ann_dt, ''), ann_dt))
                  FROM public.{table}
                 WHERE statement_type = '408001000'
                """
            ).format(table=sql.Identifier(table))
            row = conn.execute(query).fetchone()
            tables.append({
                "table": table,
                "rows": row[0],
                "securities": row[1],
                "periodMin": row[2],
                "periodMax": row[3],
                "visibleDateMax": row[4],
            })
        column_rows = conn.execute(
            """
            SELECT table_name, column_name, data_type
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name = ANY(%s)
             ORDER BY table_name, ordinal_position
            """,
            (list(ALLOWED_TABLES),),
        ).fetchall()
        profile = [{
            "column": f"{row[0]}.{row[1]}",
            "dtype": row[2],
            "nullRate": None,
            "candidateValue": None,
            "candidateStatus": "SCHEMA_ONLY",
        } for row in column_rows]
        conn.rollback()
    return {
        "status": "PROFILED_READ_ONLY",
        "summary": {
            "current_user": identity[0],
            "current_database": identity[1],
            "server": f"{identity[2]}:{identity[3]}",
            "transaction_read_only": read_only,
            "allowed_tables": len(tables),
            "preferred_statement_type": "408001000",
            "rows": sum(int(item["rows"]) for item in tables),
            "securities_max": max(int(item["securities"]) for item in tables),
            "columns_profiled": len(profile),
        },
        "tables": tables,
        "profile": profile,
        "entityHints": [],
    }


def read_frame(path: Path) -> tuple[pd.DataFrame, str]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, nrows=5000), "CSV"
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, nrows=5000), "EXCEL"
    if suffix == ".json":
        return pd.read_json(path), "JSON"
    if suffix in {".sqlite", ".db"}:
        with sqlite3.connect(path) as conn:
            tables = [row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()]
            if not tables:
                raise ValueError("SQLITE_TABLE_MISSING")
            safe_table = tables[0].replace('"', '""')
            return pd.read_sql_query(f'SELECT * FROM "{safe_table}" LIMIT 5000', conn), f"SQLITE:{tables[0]}"
    raise ValueError("FILE_TYPE_NOT_ALLOWED")


def json_scalar(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def file_profile(name: str, content: str, cutoff: str | None = None) -> dict[str, Any]:
    safe_name = Path(name).name
    if not safe_name or Path(safe_name).suffix.lower() not in {".csv", ".xlsx", ".xls", ".json", ".sqlite", ".db"}:
        raise ValueError("FILE_TYPE_NOT_ALLOWED")
    raw = base64.b64decode(content, validate=True)
    if len(raw) > MAX_BODY:
        raise ValueError("FILE_TOO_LARGE")
    digest = hashlib.sha256(raw).hexdigest()
    target_dir = STAGING / digest[:16]
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / safe_name
    path.write_bytes(raw)
    frame, source_type = read_frame(path)
    profile = []
    entity_hints: list[str] = []
    temporal_max: str | None = None
    cutoff_ts = pd.to_datetime(cutoff, errors="coerce", utc=True) if cutoff else None
    cutoff_violation = False
    for column in frame.columns:
        series = frame[column]
        non_null = series.dropna()
        normalized = str(column).lower().replace("-", "_").replace(" ", "_")
        candidate_value = json_scalar(non_null.iloc[-1]) if len(non_null) and pd.api.types.is_numeric_dtype(series) else None
        item = {
            "column": str(column),
            "dtype": str(series.dtype),
            "nullRate": round(float(series.isna().mean()), 4),
            "nonNull": int(series.notna().sum()),
            "uniqueCount": int(series.nunique(dropna=True)),
            "candidateValue": candidate_value,
            "candidateStatus": "UNORDERED_LAST_NON_NULL" if candidate_value is not None else None,
        }
        if any(token in normalized for token in ("date", "_dt", "period", "日期", "报告期", "公告日")):
            parsed = pd.to_datetime(series, errors="coerce", utc=True).dropna()
            if len(parsed):
                item["temporalMin"] = parsed.min().isoformat()
                item["temporalMax"] = parsed.max().isoformat()
                temporal_max = max(temporal_max or item["temporalMax"], item["temporalMax"])
                if cutoff_ts is not None and not pd.isna(cutoff_ts) and parsed.max() > cutoff_ts:
                    item["cutoffStatus"] = "AFTER_CUTOFF"
                    cutoff_violation = True
        if any(token in normalized for token in ("ticker", "windcode", "security_code", "company", "证券代码", "公司")):
            values = [str(value)[:80] for value in non_null.astype(str).drop_duplicates().head(20)]
            entity_hints.extend(values)
            item["entityCandidates"] = values
        profile.append(item)
    manifest = {
        "sourceType": source_type,
        "fileName": safe_name,
        "sha256": digest,
        "rowsProfiled": int(len(frame)),
        "columns": profile,
        "entityHints": sorted(set(entity_hints)),
        "dataCutoff": cutoff,
        "temporalMax": temporal_max,
        "cutoffViolation": cutoff_violation,
        "createdAt": now(),
        "rawSamplesExported": False,
    }
    (target_dir / "schema_profile.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {
        "status": "PROFILED_QUARANTINED" if cutoff_violation else "PROFILED_WAITING_REVIEW",
        "summary": {
            "source_type": source_type,
            "file_name": safe_name,
            "rows_profiled": len(frame),
            "columns": len(frame.columns),
            "sha256": digest[:16] + "...",
            "raw_samples_exported": "false",
            "temporal_max": temporal_max or "NOT_IDENTIFIED",
            "cutoff_status": "QUARANTINED_AFTER_CUTOFF" if cutoff_violation else "PASS_OR_NOT_IDENTIFIED",
        },
        "profile": profile,
        "entityHints": sorted(set(entity_hints)),
        "cutoffViolation": cutoff_violation,
        "snapshot": str(target_dir.relative_to(ROOT)),
        "sourceHash": digest,
    }


class Handler(SimpleHTTPRequestHandler):
    server_version = "NexusConnector/2.18"

    def end_headers(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in {"", "/"} or path.endswith((".html", ".js", ".css")):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {self.command} {self.path.split('?')[0]} {args[1] if len(args)>1 else ''}")

    def json_response(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_BODY * 2:
            raise ValueError("REQUEST_SIZE_INVALID")
        return json.loads(self.rfile.read(length))

    def authorized_client(self) -> bool:
        return bool(CLIENT_ID.fullmatch(str(self.headers.get("X-Client-Id") or "")))

    def client_id(self) -> str:
        return str(self.headers.get("X-Client-Id") or "")

    def require_client(self, route: str) -> bool:
        if route.startswith("/api/") and route != "/api/health" and not self.authorized_client():
            self.json_response({"error": "PERMISSION_DENIED", "detail": "X-Client-Id is required for local API access."}, HTTPStatus.FORBIDDEN)
            return False
        return True

    def do_GET(self) -> None:
        route = self.path.split("?", 1)[0]
        if not self.require_client(route):
            return
        if route == "/api/health":
            self.json_response({
                "status": "ok",
                "version": "local-connector-2.18.4",
                "apiVersion": "sandbox-resource-api-1.1.0",
                "bind": "127.0.0.1",
                "readOnly": True,
                "authMode": "LOCAL_CLIENT_ID",
                "credentialPolicy": "EPHEMERAL_OR_ENCRYPTED_MEMORY_ONLY",
                "aiPolicy": "CANDIDATE_ONLY",
                "pipeline": "ACTUAL_ROWS_TO_DETERMINISTIC_RESULTS",
                "fileTypes": ["CSV", "Excel", "JSON", "SQLite"],
                "databaseTypes": ["PostgreSQL", "MySQL", "SQLite file"],
                "aiMode": "BYOK / LOCAL OPTIONAL",
            })
            return
        if route == "/api/networks":
            items = []
            if NETWORKS_DIR.is_dir():
                for path in NETWORKS_DIR.glob("PLAN-*.json"):
                    saved = persisted_network(path.stem)
                    if not saved:
                        continue
                    graph = saved.get("fullGraph") or {}
                    items.append({"networkId": saved.get("networkId", path.stem), "networkName": saved.get("networkName"), "networkKind": saved.get("networkKind"), "outputLevel": saved.get("outputLevel"), "createdAt": saved.get("createdAt"), "activatedAt": saved.get("activatedAt"), "deletable": saved.get("deletable", True), "nodeCount": len(graph.get("nodes", saved.get("nodes", []))), "edgeCount": len(graph.get("edges", saved.get("edges", [])))})
            items.sort(key=lambda item: str(item.get("activatedAt") or item.get("createdAt") or ""))
            self.json_response({"status": "READY", "networks": items})
            return
        network_match = re.fullmatch(r"/api/networks/([^/]+)", route)
        if network_match:
            saved = persisted_network(network_match.group(1))
            if saved:
                self.json_response(saved)
                return
            self.json_response({"error": "NETWORK_NOT_FOUND"}, HTTPStatus.NOT_FOUND)
            return
        if route == "/api/tasks":
            self.json_response({"tasks": list(TASKS.values())})
            return
        if route == "/api/metrics":
            self.json_response({"status": "READY", "metrics": METRICS})
            return
        ai_job_match = re.fullmatch(r"/api/ai/mapping-jobs/([^/]+)", route)
        if ai_job_match:
            job = AI_MAPPING_JOBS.get(ai_job_match.group(1))
            if not job or job.get("ownerClientId") != self.client_id():
                self.json_response({"error": "PERMISSION_DENIED"}, HTTPStatus.FORBIDDEN)
                return
            with AI_MAPPING_LOCK:
                self.json_response(dict(job))
            return
        metric_values_match = re.fullmatch(r"/api/sources/([^/]+)/metric-values", route)
        if metric_values_match:
            source_id = metric_values_match.group(1)
            source = SOURCES.get(source_id)
            if not source or source.get("ownerClientId") != self.client_id():
                self.json_response({"error": "PERMISSION_DENIED"}, HTTPStatus.FORBIDDEN)
                return
            values = METRIC_VALUES.get(source_id, [])
            self.json_response({"sourceId": source_id, "status": "READY" if values else "EMPTY", "total": len(values), "metricValues": values[:500]})
            return
        plan_match = re.fullmatch(r"/api/network-plans/([^/]+)", route)
        if plan_match:
            plan = NETWORK_PLANS.get(plan_match.group(1))
            if not plan or plan.get("ownerClientId") != self.client_id():
                self.json_response({"error": "PERMISSION_DENIED"}, HTTPStatus.FORBIDDEN)
                return
            self.json_response(plan)
            return
        evidence_match = re.fullmatch(r"/api/evidence/([^/]+)", route)
        if evidence_match:
            item = EVIDENCE.get(evidence_match.group(1))
            source = SOURCES.get(item.get("sourceId"), {}) if item else {}
            if not item or source.get("ownerClientId") != self.client_id():
                self.json_response({"error": "PERMISSION_DENIED"}, HTTPStatus.FORBIDDEN)
                return
            self.json_response(item)
            return
        connection_match = re.fullmatch(r"/api/connections/([^/]+)/tables", route)
        if connection_match:
            connection_id = connection_match.group(1)
            item = CONNECTIONS.get(connection_id)
            if not item or item.get("ownerClientId") != self.client_id():
                self.json_response({"error": "PERMISSION_DENIED"}, HTTPStatus.FORBIDDEN)
                return
            result = profile_database({**connection_config(item), "tables": []})
            self.json_response({
                "connectionId": connection_id,
                "status": "READY",
                "readOnly": True,
                "tables": [{"name": name, "schema": item["config"]["schema"], "selected": False} for name in result["tables"]],
            })
            return
        if route == "/api/sandbox/nodes":
            plan = NETWORK_PLANS.get(ACTIVE_PLANS.get(self.client_id(), ""))
            nodes, _ = active_graph(plan)
            self.json_response({"status": "READY", "networkPlanId": plan.get("networkPlanId") if plan else None, "nodes": nodes})
            return
        if route == "/api/sandbox/edges":
            plan = NETWORK_PLANS.get(ACTIVE_PLANS.get(self.client_id(), ""))
            _, edges = active_graph(plan)
            self.json_response({"status": "READY", "networkPlanId": plan.get("networkPlanId") if plan else None, "edges": edges})
            return
        scenario_match = re.fullmatch(r"/api/scenarios/([^/]+)/results", route)
        if scenario_match:
            scenario_id = scenario_match.group(1)
            if scenario_id not in SCENARIOS or SCENARIOS[scenario_id].get("ownerClientId") != self.client_id():
                self.json_response({"error": "PERMISSION_DENIED"}, HTTPStatus.FORBIDDEN)
                return
            self.json_response(SCENARIO_RESULTS.get(scenario_id, {"scenarioId": scenario_id, "status": "EMPTY", "results": []}))
            return
        if route.startswith("/api/packages/"):
            package_id = route.removeprefix("/api/packages/")
            if not package_id or package_id != Path(package_id).name:
                self.json_response({"error": "PACKAGE_ID_INVALID"}, HTTPStatus.BAD_REQUEST)
                return
            run_dir = RUNS / package_id
            if not run_dir.is_dir():
                self.json_response({"error": "PACKAGE_NOT_FOUND"}, HTTPStatus.NOT_FOUND)
                return
            artifacts = {}
            for path in sorted(run_dir.glob("*.json")):
                artifacts[path.name] = json.loads(path.read_text(encoding="utf-8"))
            self.json_response({"packageId": package_id, "artifacts": artifacts})
            return
        super().do_GET()

    def do_POST(self) -> None:
        route = self.path.split("?", 1)[0]
        if not self.require_client(route):
            return
        try:
            payload = self.read_json()
            if route == "/api/connections/test":
                config = payload.get("connection") or payload
                result = profile_database(config)
                self.json_response({
                    "status": "CONNECTION_TESTED",
                    "readOnly": True,
                    "credentialPersisted": False,
                    "connection": public_connection(config, resource_id("CONN", public_config(config))),
                    "tables": [{"name": name, "schema": config.get("schema") or "public"} for name in result["tables"]],
                    "summary": result["summary"],
                })
                return
            if route == "/api/connections":
                config = payload.get("connection") or payload
                result = profile_database({**config, "tables": []})
                connection_id = resource_id("CONN", {**public_config(config), "sourceHash": result["sourceHash"], "owner": self.client_id()})
                CONNECTIONS[connection_id] = {
                    "config": public_config(config),
                    "credentialBlob": seal_credential(str(config.get("password") or "")),
                    "public": public_connection(config, connection_id),
                    "createdAt": now(),
                    "ownerClientId": self.client_id(),
                }
                source_id = resource_id("SOURCE", {"connectionId": connection_id, "owner": self.client_id()})
                SOURCES[source_id] = {"sourceId": source_id, "connectionId": connection_id, "status": "CONNECTED", "ownerClientId": self.client_id(), "sourceType": "DATABASE"}
                self.json_response({
                    "status": "CREATED",
                    "connection": public_connection(config, connection_id),
                    "connectionId": connection_id,
                    "sourceId": source_id,
                    "readOnly": True,
                    "credentialPersisted": False,
                    "tables": [{"name": name, "schema": config.get("schema") or "public"} for name in result["tables"]],
                })
                return
            if route == "/api/sources/profile":
                source_type = payload.get("sourceType")
                if source_type == "postgresql" and payload.get("preset") == "workspace":
                    result = postgres_profile()
                    created = task("PROFILE_SOURCE", {"preset": "workspace-postgres", "cutoff": payload.get("cutoff")}, "只读字段画像完成")
                    preset_config = {"type": "postgresql", "host": POSTGRES["host"], "port": POSTGRES["port"], "database": POSTGRES["dbname"], "user": POSTGRES["user"], "schema": "public", "sslmode": POSTGRES["sslmode"]}
                    connection_id = resource_id("CONN", {"config": preset_config, "owner": self.client_id()})
                    CONNECTIONS[connection_id] = {"config": preset_config, "credentialBlob": None, "public": public_connection(preset_config, connection_id), "createdAt": now(), "ownerClientId": self.client_id()}
                    source_id = resource_id("SOURCE", {"connectionId": connection_id, "owner": self.client_id()})
                    candidates = rule_candidates(result.get("profile") or [], source_id)
                    for candidate in candidates:
                        MAPPINGS[candidate["mappingId"]] = candidate
                    SOURCES[source_id] = {"sourceId": source_id, "connectionId": connection_id, "sourceType": "DATABASE", "status": "PROFILED", "ownerClientId": self.client_id(), "profile": result.get("profile") or [], "selectedTables": list(ALLOWED_TABLES)}
                    result.update({"sourceId": source_id, "mappings": candidates, "metricCatalog": METRICS})
                elif source_type == "file":
                    result = file_profile(str(payload.get("name", "")), str(payload.get("content", "")), str(payload.get("cutoff") or "") or None)
                    created = task("PROFILE_SOURCE", {"sha256": result["summary"]["sha256"]}, "文件字段画像完成，等待映射审核")
                    source_id = resource_id("SOURCE", {"hash": result["sourceHash"], "owner": self.client_id()})
                    source_path = ROOT / result["snapshot"] / Path(str(payload.get("name") or "")).name
                    source_table = Path(str(payload.get("name") or "uploaded_file")).name
                    file_profile_rows = []
                    for item in result.get("profile") or []:
                        column_name = str(item.get("column") or "")
                        file_profile_rows.append({
                            **item,
                            "column": column_name,
                            "columnName": column_name,
                            "tableName": source_table,
                            "schemaName": "file",
                            "databaseName": "uploaded_file",
                            "sourceLocator": {"database": "uploaded_file", "schema": "file", "table": source_table, "column": column_name},
                        })
                    network_intent = str(payload.get("networkIntent") or "CREATE_NEW_NETWORK")
                    adapters = table_adapters("uploaded_file", "file", [source_table], file_profile_rows)
                    candidates = rule_candidates(file_profile_rows, source_id, network_intent)
                    candidates += table_adapter_candidates(adapters, candidates, source_id, network_intent)
                    precompiled_adapter = auto_confirm_precompiled_candidates(adapters, candidates)
                    for candidate in candidates:
                        MAPPINGS[candidate["mappingId"]] = candidate
                    SOURCES[source_id] = {
                        "sourceId": source_id, "sourceType": "FILE", "path": str(source_path),
                        "status": "PROFILED", "ownerClientId": self.client_id(), "profile": file_profile_rows,
                        "tableAdapters": adapters, "networkIntent": network_intent,
                    }
                    result.update({
                        "sourceId": source_id, "mappings": candidates, "metricCatalog": METRICS,
                        "profile": file_profile_rows, "tableAdapters": adapters,
                        "precompiledAdapter": precompiled_adapter, "networkIntent": network_intent,
                    })
                else:
                    raise ValueError("SOURCE_TYPE_NOT_ALLOWED")
                result["tasks"] = [[created["type"], created["status"], created["detail"]], ["AI_MAPPING", "WAITING_REVIEW", "未知字段只能生成候选映射"]]
                self.json_response(result)
                return
            if route == "/api/databases/profile":
                config = payload.get("connection") or {}
                credential = payload.get("credential")
                credential_ref = payload.get("credentialRef")
                if credential not in (None, ""):
                    config = {**config, "password": credential}
                if credential_ref:
                    config = {**config, "credentialRef": credential_ref}
                result = profile_database(config)
                safe_config = public_config(config)
                created = task(
                    "PROFILE_DATABASE",
                    {"connection": safe_config, "sourceHash": result["sourceHash"]},
                    "自定义数据库只读元数据画像完成",
                )
                result["tasks"] = [
                    [created["type"], created["status"], created["detail"]],
                    ["CREDENTIAL_DISPOSAL", "SUCCEEDED", "密码未保存、未写日志、未进入任务哈希"],
                    ["AI_MAPPING", "WAITING_REVIEW", "未知字段只能生成候选映射"],
                ]
                self.json_response(result)
                return
            source_analyze = re.fullmatch(r"/api/sources/([^/]+)/analyze", route)
            if source_analyze:
                source_id = source_analyze.group(1)
                source = SOURCES.get(source_id)
                if not source or source.get("ownerClientId") != self.client_id():
                    raise ValueError("SOURCE_NOT_FOUND")
                connection = CONNECTIONS[source["connectionId"]]
                selected_tables = [str(item) for item in (payload.get("tables") or [])]
                # The UI profiles one table per request.  Respect its append/reset
                # contract so the final review contains every selected table,
                # rather than only the last table in the loop.
                if payload.get("reset") or not payload.get("append"):
                    for mapping_id, mapping in list(MAPPINGS.items()):
                        if mapping.get("sourceId") == source_id:
                            del MAPPINGS[mapping_id]
                    source["profile"] = []
                    source["selectedTables"] = []
                    source["tableAdapters"] = []
                profile = profile_database({**connection_config(connection), "tables": selected_tables})
                current_profile = profile.get("profile") or []
                current_tables = set(selected_tables)
                previous_profile = [
                    item for item in (source.get("profile") or [])
                    if str(item.get("tableName") or "") not in current_tables
                ]
                source["profile"] = previous_profile + current_profile
                source["selectedTables"] = list(dict.fromkeys([*(source.get("selectedTables") or []), *selected_tables]))
                current_adapters = profile.get("tableAdapters") or []
                previous_adapters = [
                    item for item in (source.get("tableAdapters") or [])
                    if str(item.get("tableName") or "") not in current_tables
                ]
                source["tableAdapters"] = previous_adapters + current_adapters
                network_intent = str(payload.get("networkIntent") or source.get("networkIntent") or "CREATE_NEW_NETWORK")
                source["networkIntent"] = network_intent
                candidates = rule_candidates(current_profile, source_id, network_intent)
                candidates += table_adapter_candidates(current_adapters, candidates, source_id, network_intent)
                for candidate in candidates:
                    MAPPINGS[candidate["mappingId"]] = candidate
                source["status"] = "PROFILED"
                all_mappings = [item for item in MAPPINGS.values() if item.get("sourceId") == source_id]
                precompiled_adapter = auto_confirm_precompiled_candidates(source["tableAdapters"], all_mappings)
                self.json_response({
                    "sourceId": source_id, "status": "PROFILED", "summary": profile.get("summary") or {},
                    "mappings": all_mappings, "profile": source["profile"],
                    "selectedTables": source["selectedTables"], "tableAdapters": source["tableAdapters"],
                    "precompiledAdapter": precompiled_adapter, "networkIntent": network_intent,
                    "metricCatalog": METRICS,
                })
                return
            mapping_confirm = re.fullmatch(r"/api/mappings/([^/]+)/confirm", route)
            if mapping_confirm:
                mapping_id = mapping_confirm.group(1)
                mapping = MAPPINGS.get(mapping_id)
                if not mapping or SOURCES.get(mapping.get("sourceId"), {}).get("ownerClientId") != self.client_id():
                    raise ValueError("MAPPING_NOT_FOUND")
                body = payload.get("mapping") or payload
                action = str(body.get("action") or "confirm").lower()
                if action == "ignore":
                    mapping.update({"status": "IGNORED", "ignoredReason": str(body.get("reason") or "用户确认不纳入当前领域")})
                elif action == "reset":
                    mapping.update({"status": "PENDING_REVIEW" if mapping.get("candidateSource") != "RULE_UNRESOLVED" else "UNRESOLVED"})
                else:
                    metric_code = str(body.get("metricCode") or mapping.get("metricCode") or "")
                    metric = next((item for item in METRICS if item["metricCode"] == metric_code), None)
                    definition = mapping.get("metricDefinition") if isinstance(mapping.get("metricDefinition"), dict) else None
                    if (
                        not metric
                        and metric_code.startswith("CUSTOM_")
                        and mapping.get("candidateSource") in {"CUSTOM_NUMERIC", "AI_SEMANTIC"}
                        and definition
                        and definition.get("sourceDefined") is True
                        and definition.get("metricCode") == metric_code
                    ):
                        metric = definition
                    if not metric:
                        raise ValueError("METRIC_CODE_INVALID")
                    mapping.update({"status": "CONFIRMED", "metricCode": metric_code, "metricName": metric["metricName"], "candidateSource": "MANUAL" if metric_code != mapping.get("metricCode") else mapping.get("candidateSource"), "confirmedBy": self.client_id(), "confirmedAt": now()})
                self.json_response({"mappingId": mapping_id, "status": mapping["status"], "mapping": mapping})
                return
            source_sync = re.fullmatch(r"/api/sources/([^/]+)/sync", route)
            if source_sync:
                source_id = source_sync.group(1)
                source = SOURCES.get(source_id)
                if not source or source.get("ownerClientId") != self.client_id():
                    raise ValueError("SOURCE_NOT_FOUND")
                mappings = [item for item in MAPPINGS.values() if item.get("sourceId") == source_id]
                cutoff = str(payload.get("dataCutoff") or "2026-05-08")
                SYNC_CANCELLED.discard(source_id)
                if source.get("sourceType") == "FILE":
                    frame, _ = read_frame(Path(source["path"]))
                    records = [{str(key): json_scalar(value) for key, value in row.items()} for row in frame.to_dict(orient="records")]
                    synced = sync_records(records, mappings, source_id, cutoff, Path(source["path"]).name, payload.get("rowLimit") or 500)
                else:
                    connection = CONNECTIONS[source["connectionId"]]
                    synced = sync_database(connection_config(connection), mappings, source_id, cutoff, payload.get("entityCodes") or [], payload.get("rowLimit") or 500, payload.get("page") or 0, lambda: source_id in SYNC_CANCELLED)
                source["status"] = "SYNCED"
                source["snapshotId"] = synced["sourceSnapshotId"]
                source["dataCutoff"] = cutoff
                source["snapshot"] = {key: value for key, value in synced.items() if key not in {"metricValues", "evidence"}}
                existing = {item["metricValueId"]: item for item in METRIC_VALUES.get(source_id, [])}
                existing.update({item["metricValueId"]: item for item in synced["metricValues"]})
                METRIC_VALUES[source_id] = list(existing.values())
                for item in synced["evidence"]:
                    EVIDENCE[item["evidenceId"]] = item
                SOURCE_SNAPSHOTS[synced["sourceSnapshotId"]] = source["snapshot"]
                self.json_response({"sourceId": source_id, "status": "SYNCED", **source["snapshot"], "formalReady": False})
                return
            source_cancel = re.fullmatch(r"/api/sources/([^/]+)/cancel", route)
            if source_cancel:
                SYNC_CANCELLED.add(source_cancel.group(1))
                self.json_response({"sourceId": source_cancel.group(1), "status": "CANCEL_REQUESTED"})
                return
            if route == "/api/ai/sessions/test":
                try:
                    config, tested = test_ai_session(payload)
                    AI_SESSIONS[self.client_id()] = {**public_ai_config(config), "apiKeyBlob": seal_credential(config.get("apiKey"))}
                    self.json_response(tested)
                except AIAdapterError as exc:
                    self.json_response({"status": exc.status, "detail": exc.detail, "apiKeyPersisted": False}, HTTPStatus.BAD_REQUEST)
                return
            ai_mapping_job = re.fullmatch(r"/api/sources/([^/]+)/ai-mapping-jobs", route)
            if ai_mapping_job:
                source_id = ai_mapping_job.group(1)
                source = SOURCES.get(source_id)
                session = AI_SESSIONS.get(self.client_id())
                if not source or source.get("ownerClientId") != self.client_id():
                    raise ValueError("SOURCE_NOT_FOUND")
                if not session:
                    raise ValueError("AI_NOT_CONNECTED")
                unresolved = [item for item in MAPPINGS.values() if item.get("sourceId") == source_id and item.get("status") == "UNRESOLVED"]
                fields = [{"sourceField": item["sourceField"], "dataType": next((column.get("dtype") for column in source.get("profile", []) if column.get("column") == item["sourceField"]), "unknown")} for item in unresolved]
                job_id = resource_id("AIJOB", {"source": source_id, "fields": [item["sourceField"] for item in fields], "owner": self.client_id(), "created": now()})
                job = {
                    "jobId": job_id, "sourceId": source_id, "type": "AI_MAPPING", "status": "QUEUED",
                    "totalFields": len(fields), "processedFields": 0, "aiQueuedFields": 0,
                    "completedBatches": 0, "totalBatches": 0, "candidates": [], "errors": [],
                    "ownerClientId": self.client_id(), "createdAt": now(),
                }
                AI_MAPPING_JOBS[job_id] = job
                config = {**session, "apiKey": open_credential(session.get("apiKeyBlob"))}
                threading.Thread(target=_run_ai_mapping_job, args=(job_id, source_id, fields, config), daemon=True, name=f"nexus-{job_id}").start()
                self.json_response({key: value for key, value in job.items() if key != "ownerClientId"}, HTTPStatus.ACCEPTED)
                return
            ai_mapping = re.fullmatch(r"/api/sources/([^/]+)/ai-mapping-candidates", route)
            if ai_mapping:
                source_id = ai_mapping.group(1)
                source = SOURCES.get(source_id)
                session = AI_SESSIONS.get(self.client_id())
                if not source or source.get("ownerClientId") != self.client_id():
                    raise ValueError("SOURCE_NOT_FOUND")
                if not session:
                    raise ValueError("AI_NOT_CONNECTED")
                config = {**session, "apiKey": open_credential(session.get("apiKeyBlob"))}
                unresolved = [item for item in MAPPINGS.values() if item.get("sourceId") == source_id and item.get("status") == "UNRESOLVED"]
                candidates = ai_mapping_candidates(config, [{"sourceField": item["sourceField"], "dataType": next((column.get("dtype") for column in source.get("profile", []) if column.get("column") == item["sourceField"]), "unknown")} for item in unresolved], METRICS)
                for candidate in candidates:
                    _apply_ai_mapping_candidate(source_id, candidate)
                remaining = sum(1 for item in MAPPINGS.values() if item.get("sourceId") == source_id and item.get("status") == "UNRESOLVED")
                self.json_response({"sourceId": source_id, "status": "PENDING_REVIEW", "candidates": candidates, "remainingUnresolved": remaining, "batchLimit": AI_MAPPING_BATCH_SIZE})
                return
            if route == "/api/network-plans":
                source_id = str(payload.get("sourceId") or "")
                source = SOURCES.get(source_id)
                if not source or source.get("ownerClientId") != self.client_id():
                    raise ValueError("SOURCE_NOT_FOUND")
                domain_id = str(payload.get("domainId") or "coal-steel")
                mode = str(payload.get("mode") or source.get("networkIntent") or "UPDATE_EXISTING").upper()
                if mode not in {"CREATE_NEW_NETWORK", "EXTEND_EXISTING", "REPLACE_EXISTING", "UPDATE_EXISTING"}:
                    raise ValueError("NETWORK_MODE_INVALID")
                network_name = str(payload.get("networkName") or "").strip() or None
                snapshot = source.get("snapshot") if isinstance(source.get("snapshot"), dict) else {}
                precompiled_network = snapshot.get("precompiledNetwork")
                source_network_id = str(payload.get("sourceNetworkId") or "").strip()
                if source_network_id:
                    precompiled_network = next(
                        (item for item in (snapshot.get("precompiledNetworks") or []) if str(item.get("networkId") or "") == source_network_id),
                        None,
                    )
                    if precompiled_network is None:
                        raise ValueError("SOURCE_NETWORK_NOT_FOUND")
                plan = build_network_plan(
                    source_id,
                    METRIC_VALUES.get(source_id, []),
                    domain_id,
                    mode,
                    network_name,
                    precompiled_network,
                    snapshot.get("precompiledColumnar"),
                )
                if mode != "CREATE_NEW_NETWORK" and domain_id != "coal-steel":
                    plan.update({"status": "CANDIDATE_ONLY", "causalStatus": "ABSTAIN"})
                    plan["diff"]["unavailableNodes"].append({"domainId": domain_id, "reason": "当前版本只允许焦煤—钢铁领域进入正式推演"})
                plan["ownerClientId"] = self.client_id()
                NETWORK_PLANS[plan["networkPlanId"]] = plan
                self.json_response(plan)
                return
            plan_confirm = re.fullmatch(r"/api/network-plans/([^/]+)/confirm", route)
            if plan_confirm:
                plan = NETWORK_PLANS.get(plan_confirm.group(1))
                if not plan or plan.get("ownerClientId") != self.client_id():
                    raise ValueError("NETWORK_PLAN_NOT_FOUND")
                confirmed_edge_ids = set(payload.get("confirmedEdgeIds") or [])
                for edge in plan.get("diff", {}).get("addedEdges", []):
                    edge["status"] = "CONFIRMED" if edge.get("edgeId") in confirmed_edge_ids else "CANDIDATE"
                plan.update({"status": "CONFIRMED", "confirmedAt": now(), "confirmedBy": self.client_id()})
                self.json_response(plan)
                return
            plan_ai_edges = re.fullmatch(r"/api/network-plans/([^/]+)/ai-edge-candidates", route)
            if plan_ai_edges:
                plan = NETWORK_PLANS.get(plan_ai_edges.group(1))
                session = AI_SESSIONS.get(self.client_id())
                if not plan or plan.get("ownerClientId") != self.client_id():
                    raise ValueError("NETWORK_PLAN_NOT_FOUND")
                if not session:
                    raise ValueError("AI_NOT_CONNECTED")
                config = {**session, "apiKey": open_credential(session.get("apiKeyBlob"))}
                nodes, _ = active_graph({**plan, "status": "ACTIVE"})
                candidates = ai_edge_candidates(config, nodes)
                for candidate in candidates:
                    candidate["edgeId"] = resource_id("EDGE", {"plan": plan["networkPlanId"], "source": candidate["sourceNodeId"], "target": candidate["targetNodeId"], "mechanism": candidate["mechanism"]})
                plan["diff"]["addedEdges"].extend(candidates)
                self.json_response({"networkPlanId": plan["networkPlanId"], "status": "PENDING_REVIEW", "candidates": candidates})
                return
            plan_activate = re.fullmatch(r"/api/network-plans/([^/]+)/activate", route)
            if plan_activate:
                plan = NETWORK_PLANS.get(plan_activate.group(1))
                if not plan or plan.get("ownerClientId") != self.client_id():
                    raise ValueError("NETWORK_PLAN_NOT_FOUND")
                if plan.get("status") != "CONFIRMED":
                    raise ValueError("NETWORK_PLAN_CONFIRMATION_REQUIRED")
                if plan.get("activationBlocked"):
                    raise ValueError("NETWORK_PLAN_VALIDATION_FAILED")
                if plan.get("mode") != "CREATE_NEW_NETWORK" and plan.get("domainId") != "coal-steel":
                    raise ValueError("DOMAIN_NOT_SUPPORTED_FOR_ACTIVATION")
                activation = {"status": "ACTIVE", "activatedAt": now(), "formalReady": False}
                if plan.get("mode") == "CREATE_NEW_NETWORK":
                    persist_active_network({**plan, **activation})
                plan.update(activation)
                ACTIVE_PLANS[self.client_id()] = plan["networkPlanId"]
                self.json_response(plan)
                return
            if route == "/api/scenarios":
                scenario_id = resource_id("SCENARIO", {"payload": payload, "owner": self.client_id()})
                scenario = {"scenarioId": scenario_id, "changes": payload.get("changes") or [], "dataCutoff": payload.get("dataCutoff") or "2026-05-08", "createdAt": now(), "status": "CREATED", "ownerClientId": self.client_id()}
                SCENARIOS[scenario_id] = scenario
                self.json_response(scenario)
                return
            scenario_run = re.fullmatch(r"/api/scenarios/([^/]+)/run", route)
            if scenario_run:
                scenario_id = scenario_run.group(1)
                if scenario_id not in SCENARIOS or SCENARIOS[scenario_id].get("ownerClientId") != self.client_id():
                    raise ValueError("SCENARIO_NOT_FOUND")
                changes = payload.get("changes") or SCENARIOS[scenario_id].get("changes") or []
                plan = NETWORK_PLANS.get(ACTIVE_PLANS.get(self.client_id(), ""))
                if not plan:
                    raise ValueError("ACTIVE_NETWORK_PLAN_REQUIRED")
                values = METRIC_VALUES.get(plan["sourceId"], [])
                calculated = simulate(scenario_id, changes, plan, values, SCENARIOS[scenario_id]["dataCutoff"])
                output = {"scenarioId": scenario_id, **calculated}
                SCENARIO_RESULTS[scenario_id] = output
                self.json_response(output)
                return
            scenario_explain = re.fullmatch(r"/api/scenarios/([^/]+)/explain", route)
            if scenario_explain:
                scenario_id = scenario_explain.group(1)
                result = SCENARIO_RESULTS.get(scenario_id)
                if not result:
                    raise ValueError("SCENARIO_RESULT_NOT_FOUND")
                session = AI_SESSIONS.get(self.client_id())
                if not session:
                    self.json_response({"scenarioId": scenario_id, "status": "AI_NOT_CONNECTED", "detail": "确定性结果可用；连接 AI 后可生成候选解释。", "confidence": 0, "evidence": result.get("evidenceIds", []), "formalReady": False})
                    return
                config = {**session, "apiKey": open_credential(session.get("apiKeyBlob"))}
                self.json_response({"scenarioId": scenario_id, **ai_explain_result(config, result)})
                return
            if route == "/api/packages/build":
                mapping = payload.get("mapping") or {}
                if mapping.get("status") != "HUMAN_CONFIRMED":
                    raise ValueError("MAPPING_REVIEW_REQUIRED")
                compiler = payload.get("compiler") or {}
                if compiler.get("reviewStatus") != "HUMAN_CONFIRMED":
                    raise ValueError("DOMAIN_PLAN_REVIEW_REQUIRED")
                manifest = payload.get("manifest") or {}
                package_id = str(manifest.get("packageId") or "").replace("/", "-").replace("\\", "-")
                if not package_id or len(package_id) > 120:
                    raise ValueError("PACKAGE_ID_INVALID")
                run_dir = RUNS / package_id
                run_dir.mkdir(parents=True, exist_ok=False)
                artifacts = {
                    "package_manifest.json": manifest,
                    "domain.json": payload.get("domain") or {},
                    "metric_mapping.json": mapping,
                    "data_snapshot.json": payload.get("snapshot") or {},
                    "company_adapters.json": payload.get("companyAdapters") or {},
                    "network_diff.json": compiler,
                    "activation.json": payload.get("activation") or {},
                    "quality_report.json": payload.get("quality") or {},
                    "quarantine.json": payload.get("quarantine") or [],
                }
                hashes = {}
                for name, value in artifacts.items():
                    body = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
                    (run_dir / name).write_text(body, encoding="utf-8")
                    hashes[name] = hashlib.sha256(body.encode("utf-8")).hexdigest()
                (run_dir / "hashes.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
                created = task("BUILD_PACKAGE", {"packageId": package_id, "hashes": hashes}, "标准候选数据包构建完成")
                self.json_response({"status": "PACKAGE_BUILT", "packageId": package_id, "runPath": str(run_dir.relative_to(ROOT)), "hashes": hashes, "activationAllowed": bool((payload.get("activation") or {}).get("allowed")), "quarantine": payload.get("quarantine") or [], "tasks": [[created["type"], created["status"], created["detail"]]]})
                return
            if route == "/api/ai/test":
                provider = str(payload.get("provider") or "disabled")
                if provider not in {"disabled", "openai-compatible", "ollama"}:
                    raise ValueError("AI_PROVIDER_NOT_ALLOWED")
                if provider == "disabled":
                    self.json_response({"status": "DISABLED", "detail": "规则和手工映射模式可用。"})
                elif not payload.get("baseUrl") or not payload.get("model"):
                    raise ValueError("AI_SESSION_CONFIG_INCOMPLETE")
                else:
                    self.json_response({"status": "DEPRECATED_USE_AI_SESSIONS_TEST", "detail": "请使用 /api/ai/sessions/test 执行真实连接测试。"})
                return
            self.json_response({"error": "NOT_FOUND"}, HTTPStatus.NOT_FOUND)
        except AIAdapterError as exc:
            self.json_response({"error": exc.status, "status": exc.status, "detail": exc.detail}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.json_response({"error": type(exc).__name__, "detail": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_DELETE(self) -> None:
        route = self.path.split("?", 1)[0]
        if not self.require_client(route):
            return
        network_match = re.fullmatch(r"/api/networks/([^/]+)", route)
        if not network_match:
            self.json_response({"error": "NOT_FOUND"}, HTTPStatus.NOT_FOUND)
            return
        network_id = network_match.group(1)
        if (
            network_id != Path(network_id).name
            or not network_id.startswith("PLAN-")
            or len(network_id) > 128
        ):
            self.json_response({"error": "NETWORK_ID_INVALID"}, HTTPStatus.BAD_REQUEST)
            return
        path = NETWORKS_DIR / f"{network_id}.json"
        saved = persisted_network(network_id)
        if not saved or not path.is_file():
            self.json_response({"error": "NETWORK_NOT_FOUND"}, HTTPStatus.NOT_FOUND)
            return
        if saved.get("deletable", True) is not True:
            self.json_response(
                {
                    "error": "NETWORK_NOT_DELETABLE",
                    "status": "NETWORK_NOT_DELETABLE",
                    "detail": "系统固定网络不可删除；数据库源和原始证据保持不变。",
                },
                HTTPStatus.CONFLICT,
            )
            return
        try:
            path.unlink()
        except OSError as exc:
            self.json_response(
                {"error": "NETWORK_DELETE_FAILED", "detail": str(exc)},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return
        self.json_response(
            {
                "status": "DELETED",
                "networkId": network_id,
                "deletedPath": str(path.relative_to(ROOT)),
                "databaseSourceDeleted": False,
                "rawEvidenceDeleted": False,
            }
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="NEXUS local read-only workbench connector")
    parser.add_argument("--port", type=int, default=4179)
    args = parser.parse_args()
    STAGING.mkdir(exist_ok=True)
    RUNS.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"NEXUS auditable workbench: http://127.0.0.1:{args.port}/")
    print("Connector bind is loopback-only; database sessions enforce transaction_read_only=on.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
