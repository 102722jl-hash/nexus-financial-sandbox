from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict, deque
from datetime import date, datetime, timezone
from typing import Any

from generic_network_contract import SUPPORTED_FORMULAS, normalize_formula_type


CONTRACT_VERSION = "nexus-crawler-batch-1.0.0"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TOP_LEVEL_ARRAYS = (
    "sources",
    "documents",
    "evidence",
    "layers",
    "entities",
    "metric_definitions",
    "observations",
    "formulas",
    "relations",
)


def stable_id(prefix: str, *parts: Any) -> str:
    """Create a repeatable ID from canonical JSON values."""
    body = json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return f"{prefix}-{hashlib.sha256(body.encode('utf-8')).hexdigest()[:24].upper()}"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _timestamp(value: Any) -> datetime | None:
    raw = _text(value)
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _date(value: Any) -> date | None:
    try:
        return date.fromisoformat(_text(value))
    except ValueError:
        return None


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _required(item: dict[str, Any], fields: tuple[str, ...] | list[str]) -> list[str]:
    return [field for field in fields if item.get(field) is None or (isinstance(item.get(field), str) and not item.get(field).strip())]


def _issue(
    code: str,
    severity: str,
    path: str,
    message: str,
    *,
    object_type: str | None = None,
    object_id: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"code": code, "severity": severity, "path": path, "message": message}
    if object_type:
        result["objectType"] = object_type
    if object_id:
        result["objectId"] = object_id
    return result


def _duplicates(items: list[dict[str, Any]], id_field: str) -> tuple[set[str], set[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for item in items:
        key = _text(item.get(id_field))
        if key:
            grouped[key].append(_canonical(item))
    exact = {key for key, values in grouped.items() if len(values) > 1 and len(set(values)) == 1}
    conflicts = {key for key, values in grouped.items() if len(set(values)) > 1}
    return exact, conflicts


def _path_exists(adjacency: dict[str, set[str]], starts: set[str], sinks: set[str]) -> tuple[bool, list[str]]:
    queue: deque[tuple[str, list[str]]] = deque((node, [node]) for node in sorted(starts))
    visited = set(starts)
    while queue:
        node, path = queue.popleft()
        if node in sinks and len(path) > 1:
            return True, path
        for target in sorted(adjacency.get(node, set())):
            if target not in visited:
                visited.add(target)
                queue.append((target, [*path, target]))
    return False, []


def validate_crawler_payload(payload: Any) -> dict[str, Any]:
    """Validate one crawler batch without mutating it or writing to a database."""
    blocking: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []

    if not isinstance(payload, dict):
        blocking.append(_issue("PAYLOAD_NOT_OBJECT", "BLOCKING", "$", "批次必须是 JSON 对象。"))
        return _report(payload, blocking, warnings, quarantined, {}, {}, [], [])

    if payload.get("contract_version") != CONTRACT_VERSION:
        blocking.append(_issue("CONTRACT_VERSION_UNSUPPORTED", "BLOCKING", "$.contract_version", f"仅支持 {CONTRACT_VERSION}。"))

    network = payload.get("network")
    if not isinstance(network, dict):
        blocking.append(_issue("NETWORK_IDENTITY_REQUIRED", "BLOCKING", "$.network", "缺少网络身份和总标题。"))
        network = {}
    missing_network = _required(network, ("network_id", "domain_code", "network_name", "network_version", "network_kind", "network_status", "data_cutoff", "causal_status"))
    if missing_network:
        blocking.append(_issue("NETWORK_FIELDS_REQUIRED", "BLOCKING", "$.network", "网络身份缺少字段：" + ", ".join(missing_network)))
    if network.get("network_status") not in {"DRAFT", "CANDIDATE", "ACTIVE", "FROZEN", "DISABLED"}:
        blocking.append(_issue("NETWORK_STATUS_INVALID", "BLOCKING", "$.network.network_status", "network_status 不在允许范围。"))
    if network.get("causal_status") not in {"ABSTAIN", "CONDITIONAL", "IDENTIFIED"}:
        blocking.append(_issue("CAUSAL_STATUS_INVALID", "BLOCKING", "$.network.causal_status", "causal_status 不在允许范围。"))
    if network.get("data_cutoff") and not _date(network.get("data_cutoff")):
        blocking.append(_issue("NETWORK_CUTOFF_INVALID", "BLOCKING", "$.network.data_cutoff", "网络 data_cutoff 必须是 YYYY-MM-DD。"))

    batch = payload.get("batch")
    if not isinstance(batch, dict):
        blocking.append(_issue("BATCH_REQUIRED", "BLOCKING", "$.batch", "缺少采集批次对象。"))
        batch = {}
    missing_batch = _required(batch, ("batch_id", "domain_code", "collector_code", "collector_version", "started_at", "completed_at", "data_cutoff", "run_type", "status"))
    if missing_batch:
        blocking.append(_issue("BATCH_FIELDS_REQUIRED", "BLOCKING", "$.batch", "批次缺少字段：" + ", ".join(missing_batch)))
    started_at = _timestamp(batch.get("started_at"))
    completed_at = _timestamp(batch.get("completed_at"))
    cutoff = _date(batch.get("data_cutoff"))
    if batch.get("started_at") and not started_at:
        blocking.append(_issue("STARTED_AT_INVALID", "BLOCKING", "$.batch.started_at", "started_at 必须是带时区的 ISO-8601 时间。"))
    if batch.get("completed_at") and not completed_at:
        blocking.append(_issue("COMPLETED_AT_INVALID", "BLOCKING", "$.batch.completed_at", "completed_at 必须是带时区的 ISO-8601 时间。"))
    if started_at and completed_at and completed_at < started_at:
        blocking.append(_issue("BATCH_TIME_REVERSED", "BLOCKING", "$.batch.completed_at", "completed_at 不能早于 started_at。"))
    if batch.get("data_cutoff") and not cutoff:
        blocking.append(_issue("DATA_CUTOFF_INVALID", "BLOCKING", "$.batch.data_cutoff", "data_cutoff 必须是 YYYY-MM-DD。"))
    if batch.get("run_type") not in {"DAILY", "BACKFILL", "MANUAL", "REPAIR"}:
        blocking.append(_issue("RUN_TYPE_INVALID", "BLOCKING", "$.batch.run_type", "run_type 不在允许范围。"))
    if batch.get("status") not in {"SUCCEEDED", "PARTIAL", "FAILED"}:
        blocking.append(_issue("BATCH_STATUS_INVALID", "BLOCKING", "$.batch.status", "批次 status 不在允许范围。"))
    elif batch.get("status") == "FAILED":
        warnings.append(_issue("FAILED_BATCH_DATA_ONLY", "WARNING", "$.batch.status", "失败批次只允许保存原始数据，不允许编译网络。"))
    if network and network.get("domain_code") != batch.get("domain_code"):
        blocking.append(_issue("NETWORK_DOMAIN_MISMATCH", "BLOCKING", "$.network.domain_code", "网络与批次的 domain_code 必须一致。"))
    if network and network.get("data_cutoff") != batch.get("data_cutoff"):
        blocking.append(_issue("NETWORK_CUTOFF_MISMATCH", "BLOCKING", "$.network.data_cutoff", "网络与批次的 data_cutoff 必须一致。"))

    collections: dict[str, list[dict[str, Any]]] = {}
    for name in TOP_LEVEL_ARRAYS:
        value = payload.get(name)
        if not isinstance(value, list):
            blocking.append(_issue("COLLECTION_REQUIRED", "BLOCKING", f"$.{name}", f"{name} 必须是数组。"))
            collections[name] = []
        else:
            collections[name] = [item for item in value if isinstance(item, dict)]
            invalid_count = len(value) - len(collections[name])
            if invalid_count:
                warnings.append(_issue("NON_OBJECT_ITEMS_QUARANTINED", "WARNING", f"$.{name}", f"{invalid_count} 条非对象记录已隔离。"))

    id_fields = {
        "sources": "source_code", "documents": "document_id", "evidence": "evidence_id",
        "layers": "layer_code", "entities": "entity_code", "metric_definitions": "metric_code",
        "observations": "observation_id", "formulas": "formula_id", "relations": "relation_id",
    }
    for name, id_field in id_fields.items():
        exact, conflicts = _duplicates(collections[name], id_field)
        if conflicts:
            blocking.append(_issue("DUPLICATE_ID_CONFLICT", "BLOCKING", f"$.{name}", f"重复主键内容冲突：{', '.join(sorted(conflicts))}"))
        if exact:
            warnings.append(_issue("EXACT_DUPLICATE_IGNORED", "WARNING", f"$.{name}", f"完全重复记录可幂等忽略：{', '.join(sorted(exact))}"))

    document_by_id = {_text(item.get("document_id")): item for item in collections["documents"] if _text(item.get("document_id"))}
    entity_by_id = {_text(item.get("entity_code")): item for item in collections["entities"] if _text(item.get("entity_code"))}
    metric_by_id = {_text(item.get("metric_code")): item for item in collections["metric_definitions"] if _text(item.get("metric_code"))}
    formula_by_id = {_text(item.get("formula_id")): item for item in collections["formulas"] if _text(item.get("formula_id"))}
    layer_by_id = {_text(item.get("layer_code")): item for item in collections["layers"] if _text(item.get("layer_code"))}

    valid_sources: set[str] = set()
    for index, item in enumerate(collections["sources"]):
        object_id = _text(item.get("source_code"))
        path = f"$.sources[{index}]"
        missing = _required(item, ("source_code", "source_name", "source_type", "publisher", "base_url", "source_tier", "license_status", "status"))
        invalid_enum = (
            item.get("source_type") not in {"WEB", "API", "CSV", "PDF", "DATABASE"}
            or item.get("source_tier") not in {"T1", "T2", "T3", "MARKET_PROXY"}
            or item.get("license_status") not in {"ALLOWED", "RESTRICTED", "UNKNOWN"}
            or item.get("status") not in {"ACTIVE", "PAUSED", "DISABLED"}
        )
        if missing or invalid_enum:
            quarantined.append(_issue("SOURCE_QUARANTINED", "WARNING", path, "来源字段缺失或枚举值非法。", object_type="source", object_id=object_id))
        elif item.get("status") == "ACTIVE":
            valid_sources.add(object_id)

    valid_documents: set[str] = set()
    for index, item in enumerate(collections["documents"]):
        object_id = _text(item.get("document_id"))
        path = f"$.documents[{index}]"
        missing = _required(item, ("document_id", "batch_id", "source_code", "source_url", "canonical_url", "retrieved_at", "content_type", "http_status", "content_sha256", "parse_status"))
        local_errors = []
        if missing:
            local_errors.append("缺少字段：" + ", ".join(missing))
        if item.get("batch_id") != batch.get("batch_id"):
            local_errors.append("batch_id 与当前批次不一致")
        if _text(item.get("source_code")) not in valid_sources:
            local_errors.append("source_code 未登记或来源未启用")
        if not SHA256_RE.fullmatch(_text(item.get("content_sha256"))):
            blocking.append(_issue("DOCUMENT_SHA256_INVALID", "BLOCKING", path + ".content_sha256", "原始文档哈希必须是 64 位小写 SHA-256。", object_type="document", object_id=object_id))
            local_errors.append("content_sha256 非法")
        if not _timestamp(item.get("retrieved_at")):
            local_errors.append("retrieved_at 不是带时区时间")
        if not isinstance(item.get("http_status"), int) or not 100 <= item.get("http_status", 0) <= 599:
            local_errors.append("http_status 非法")
        if item.get("parse_status") not in {"FETCHED", "PARSED", "NEEDS_REVIEW", "QUARANTINED", "ERROR"}:
            local_errors.append("parse_status 非法")
        if not item.get("snapshot_path") and item.get("raw_payload") is None:
            local_errors.append("snapshot_path 与 raw_payload 至少填写一个")
        if local_errors:
            quarantined.append(_issue("DOCUMENT_QUARANTINED", "WARNING", path, "；".join(local_errors), object_type="document", object_id=object_id))
        else:
            valid_documents.add(object_id)

    valid_evidence: set[str] = set()
    for index, item in enumerate(collections["evidence"]):
        object_id = _text(item.get("evidence_id"))
        path = f"$.evidence[{index}]"
        missing = _required(item, ("evidence_id", "document_id", "source_type", "source_tier", "original_quote", "locator", "retrieved_at", "anchor_at", "temporal_role", "snapshot_sha256", "acceptance_status", "acceptance_reason"))
        local_errors = []
        if missing:
            local_errors.append("缺少字段：" + ", ".join(missing))
        if _text(item.get("document_id")) not in valid_documents:
            local_errors.append("document_id 未通过原始文档校验")
        document = document_by_id.get(_text(item.get("document_id"))) or {}
        if item.get("snapshot_sha256") != document.get("content_sha256"):
            local_errors.append("snapshot_sha256 与原始文档不一致")
        if not _timestamp(item.get("retrieved_at")) or not _timestamp(item.get("anchor_at")):
            local_errors.append("证据时间不是带时区 ISO-8601")
        if item.get("source_tier") not in {"T1", "T2", "T3", "MARKET_PROXY"}:
            local_errors.append("source_tier 非法")
        if item.get("temporal_role") not in {"SOURCE_FACT", "PRE_EVENT", "AT_EVENT", "POST_EVENT_VALIDATION", "UNDATED"}:
            local_errors.append("temporal_role 非法")
        if item.get("acceptance_status") not in {"ACCEPTED", "AI_APPROVED", "PENDING_REVIEW", "REJECTED"}:
            local_errors.append("acceptance_status 非法")
        if local_errors:
            quarantined.append(_issue("EVIDENCE_QUARANTINED", "WARNING", path, "；".join(local_errors), object_type="evidence", object_id=object_id))
        elif item.get("acceptance_status") not in {"REJECTED", "PENDING_REVIEW"}:
            valid_evidence.add(object_id)

    invalid_layers = []
    layer_numbers = Counter()
    for index, item in enumerate(collections["layers"]):
        missing = _required(item, ("layer_no", "layer_code", "layer_name", "path_role", "sort_order"))
        if missing or not isinstance(item.get("layer_no"), int) or item.get("layer_no", 0) <= 0 or item.get("path_role") not in {"SOURCE", "INTERMEDIATE", "SINK", "EVIDENCE_ONLY"}:
            invalid_layers.append(_text(item.get("layer_code")) or f"index:{index}")
        if isinstance(item.get("layer_no"), int):
            layer_numbers[item["layer_no"]] += 1
    repeated_layer_numbers = sorted(number for number, count in layer_numbers.items() if count > 1)
    if invalid_layers or repeated_layer_numbers:
        blocking.append(_issue("NETWORK_LAYERS_INVALID", "BLOCKING", "$.layers", f"非法层级：{invalid_layers}；重复层号：{repeated_layer_numbers}"))

    for index, item in enumerate(collections["entities"]):
        object_id = _text(item.get("entity_code"))
        missing = _required(item, ("entity_code", "entity_name", "entity_type", "status"))
        parent = _text(item.get("parent_entity_code"))
        invalid_enum = item.get("entity_type") not in {"COMPANY", "INDUSTRY", "COMMODITY", "REGION", "MACRO", "POLICY", "MARKET"} or item.get("status") not in {"ACTIVE", "INACTIVE", "MERGED", "DELISTED"}
        if missing or invalid_enum or (parent and parent not in entity_by_id) or parent == object_id:
            quarantined.append(_issue("ENTITY_QUARANTINED", "WARNING", f"$.entities[{index}]", "实体字段缺失、上级不存在或形成自引用。", object_type="entity", object_id=object_id))

    valid_metrics: set[str] = set()
    for index, item in enumerate(collections["metric_definitions"]):
        object_id = _text(item.get("metric_code"))
        missing = _required(item, ("metric_code", "metric_name", "metric_type", "canonical_unit", "unit_family", "frequency", "entity_scope", "default_layer_code", "editable_default", "status"))
        invalid_enum = (
            item.get("metric_type") not in {"FLOW", "STOCK", "PRICE", "RATIO", "AMOUNT", "COUNT", "INDEX", "TEXT_SIGNAL"}
            or item.get("unit_family") not in {"CURRENCY", "COUNT", "MASS", "ENERGY", "POWER", "PERCENT", "PRICE", "INDEX", "TEXT", "OTHER"}
            or item.get("frequency") not in {"REALTIME", "DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "ANNUAL", "EVENT"}
            or item.get("entity_scope") not in {"GLOBAL", "INDUSTRY", "ENTITY", "COMPANY", "REGION", "COMMODITY"}
            or item.get("status") not in {"ACTIVE", "DEPRECATED", "DISABLED"}
        )
        if missing or invalid_enum or _text(item.get("default_layer_code")) not in layer_by_id:
            quarantined.append(_issue("METRIC_DEFINITION_QUARANTINED", "WARNING", f"$.metric_definitions[{index}]", "指标定义字段缺失或默认层级不存在。", object_type="metric_definition", object_id=object_id))
        elif item.get("status") == "ACTIVE":
            valid_metrics.add(object_id)

    valid_observations: set[str] = set()
    for index, item in enumerate(collections["observations"]):
        object_id = _text(item.get("observation_id"))
        metric_code = _text(item.get("metric_code"))
        path = f"$.observations[{index}]"
        missing = _required(item, ("observation_id", "metric_code", "unit", "as_of_date", "available_at", "data_cutoff", "evidence_id", "quality_status", "source_row_key", "revision"))
        local_errors = []
        if missing or (item.get("value") is None and item.get("text_value") is None):
            local_errors.append("缺少必填字段或数值/文本值")
        if metric_code not in metric_by_id:
            blocking.append(_issue("OBSERVATION_METRIC_NOT_FOUND", "BLOCKING", path + ".metric_code", "观测引用了不存在的指标。", object_type="observation", object_id=object_id))
            local_errors.append("metric_code 不存在")
        definition = metric_by_id.get(metric_code) or {}
        entity_code = _text(item.get("entity_code"))
        if definition.get("entity_scope") in {"COMPANY", "ENTITY"} and not entity_code:
            local_errors.append("公司或实体指标缺少 entity_code")
        if entity_code and entity_code not in entity_by_id:
            local_errors.append("entity_code 未登记")
        if _text(item.get("evidence_id")) not in valid_evidence:
            local_errors.append("evidence_id 未通过证据校验")
        if definition and item.get("unit") != definition.get("canonical_unit"):
            local_errors.append("unit 与 canonical_unit 不一致，需显式换算")
        available = _timestamp(item.get("available_at"))
        item_cutoff = _date(item.get("data_cutoff"))
        if not _date(item.get("as_of_date")) or not available or not item_cutoff:
            local_errors.append("业务日期、可获得时间或截止日格式非法")
        elif available.date() > item_cutoff:
            local_errors.append("available_at 晚于 data_cutoff，存在未来数据泄漏")
        if cutoff and item_cutoff and cutoff != item_cutoff:
            local_errors.append("观测 data_cutoff 与批次不一致")
        if not isinstance(item.get("revision"), int) or item.get("revision", 0) <= 0:
            local_errors.append("revision 必须为正整数")
        if item.get("quality_status") not in {"SOURCE_FACT", "REPORTED_ACTUAL", "MARKET_PROXY", "AI_EXTRACTED", "CALCULATED_LINEAGE", "PENDING_REVIEW", "REJECTED"}:
            local_errors.append("quality_status 非法")
        if local_errors:
            quarantined.append(_issue("OBSERVATION_QUARANTINED", "WARNING", path, "；".join(local_errors), object_type="observation", object_id=object_id))
        elif item.get("quality_status") not in {"REJECTED", "PENDING_REVIEW"}:
            valid_observations.add(object_id)

    valid_formulas: set[str] = set()
    normalized_formulas: list[dict[str, Any]] = []
    for index, item in enumerate(collections["formulas"]):
        object_id = _text(item.get("formula_id"))
        missing = _required(item, ("formula_id", "formula_type", "formula_expression", "parameters", "parameter_status", "causal_conclusion", "status"))
        formula_type, resolution = normalize_formula_type(item.get("formula_type"), item.get("formula_expression"))
        normalized_formulas.append({"formulaId": object_id, "inputFormulaType": item.get("formula_type"), "formulaType": formula_type, "resolution": resolution})
        invalid_enum = item.get("parameter_status") not in {"CALIBRATED", "HUMAN_CONFIRMED", "CALCULATED_LINEAGE", "AI_ASSUMPTION", "MISSING"} or item.get("causal_conclusion") not in {"ABSTAIN", "CONDITIONAL", "IDENTIFIED"} or item.get("status") not in {"ACTIVE", "NEEDS_REVIEW", "DISABLED"}
        if missing or invalid_enum or not formula_type or formula_type not in SUPPORTED_FORMULAS or item.get("status") == "NEEDS_REVIEW":
            quarantined.append(_issue("FORMULA_NEEDS_REVIEW", "WARNING", f"$.formulas[{index}]", "公式缺少字段或无法映射到安全公式注册中心。", object_type="formula", object_id=object_id))
        elif item.get("status") == "ACTIVE":
            valid_formulas.add(object_id)

    propagating_relations: list[dict[str, Any]] = []
    normalized_relations: list[dict[str, Any]] = []
    for index, item in enumerate(collections["relations"]):
        object_id = _text(item.get("relation_id"))
        source = _text(item.get("source_metric_code"))
        target = _text(item.get("target_metric_code"))
        formula_id = _text(item.get("formula_id"))
        path = f"$.relations[{index}]"
        missing = _required(item, ("relation_id", "source_metric_code", "target_metric_code", "direction", "relation_type", "formula_id", "status", "parameter_status", "mechanism"))
        if source not in metric_by_id or target not in metric_by_id:
            blocking.append(_issue("RELATION_ENDPOINT_NOT_FOUND", "BLOCKING", path, "关系起点或终点指标不存在。", object_type="relation", object_id=object_id))
            continue
        candidate = item.get("status") in {"AI_APPROVED", "CANDIDATE"}
        confirmed = item.get("status") == "CONFIRMED"
        weight = _number(item.get("weight"))
        candidate_weight = _number(item.get("candidate_weight"))
        candidate_simulation = candidate and candidate_weight is not None and candidate_weight > 0
        normalized_relations.append({
            "relationId": object_id,
            "status": item.get("status"),
            "candidateSimulation": candidate_simulation,
            "effectiveWeight": abs(weight) if confirmed and weight is not None else (abs(candidate_weight) if candidate_weight is not None else None),
            "causalConclusion": "ABSTAIN" if candidate else (formula_by_id.get(formula_id) or {}).get("causal_conclusion"),
        })
        local_errors = []
        if missing:
            local_errors.append("缺少字段：" + ", ".join(missing))
        if source == target:
            local_errors.append("关系不能自连接")
        if formula_id not in valid_formulas:
            local_errors.append("formula_id 未通过公式校验")
        if confirmed and (weight is None or weight <= 0):
            local_errors.append("CONFIRMED 关系缺少正数 weight；正负方向只能写入 direction")
        if candidate and not candidate_simulation:
            local_errors.append("候选关系缺少正数 candidate_weight；正负方向只能写入 direction")
        if item.get("direction") not in {"positive", "negative", "mixed"}:
            local_errors.append("direction 非法")
        if item.get("status") not in {"CONFIRMED", "AI_APPROVED", "CANDIDATE", "NEEDS_HUMAN_REVIEW", "DISABLED"}:
            local_errors.append("status 非法")
        if item.get("parameter_status") not in {"CALIBRATED", "HUMAN_CONFIRMED", "CALCULATED_LINEAGE", "AI_ASSUMPTION", "MISSING"}:
            local_errors.append("parameter_status 非法")
        if local_errors:
            quarantined.append(_issue("RELATION_QUARANTINED", "WARNING", path, "；".join(local_errors), object_type="relation", object_id=object_id))
        elif confirmed or candidate_simulation:
            propagating_relations.append(item)

    adjacency: dict[str, set[str]] = defaultdict(set)
    outgoing = Counter()
    incoming = Counter()
    for relation in propagating_relations:
        source = _text(relation.get("source_metric_code"))
        target = _text(relation.get("target_metric_code"))
        adjacency[source].add(target)
        outgoing[source] += 1
        incoming[target] += 1
    editable = {code for code in valid_metrics if metric_by_id[code].get("editable_default") is True}
    explicit_sinks = {code for code in valid_metrics if (layer_by_id.get(_text(metric_by_id[code].get("default_layer_code"))) or {}).get("path_role") == "SINK"}
    inferred_sinks = {code for code in valid_metrics if incoming[code] and not outgoing[code]}
    sinks = explicit_sinks or inferred_sinks
    path_ready, example_path = _path_exists(adjacency, editable, sinks)

    valid_counts = {
        "documents": len(valid_documents), "evidence": len(valid_evidence), "metrics": len(valid_metrics),
        "observations": len(valid_observations), "formulas": len(valid_formulas),
        "propagatingRelations": len(propagating_relations), "editableMetrics": len(editable), "resultMetrics": len(sinks),
    }
    context = {"validObservations": valid_observations, "validMetrics": valid_metrics, "pathReady": path_ready, "batchFailed": batch.get("status") == "FAILED"}
    graph_context = {"examplePropagationPath": example_path, "normalizedFormulas": normalized_formulas}
    return _report(payload, blocking, warnings, quarantined, valid_counts, context, normalized_relations, graph_context)


def _report(
    payload: Any,
    blocking: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    quarantined: list[dict[str, Any]],
    valid_counts: dict[str, int],
    context: dict[str, Any],
    normalized_relations: list[dict[str, Any]],
    graph_context: Any,
) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    valid_observations = context.get("validObservations", set())
    valid_metrics = context.get("validMetrics", set())
    data_ready = bool(valid_observations and valid_metrics)
    graph_ready = data_ready and not blocking and bool(valid_metrics) and not context.get("batchFailed")
    scenario_ready = graph_ready and bool(context.get("pathReady"))
    decision = "REJECTED" if blocking else ("PARTIAL" if quarantined or warnings else "ACCEPTED")
    counts = {name: len(payload.get(name) or []) if isinstance(payload.get(name), list) else 0 for name in TOP_LEVEL_ARRAYS}
    counts.update(valid_counts)
    result = {
        "contractVersion": CONTRACT_VERSION,
        "batchId": (payload.get("batch") or {}).get("batch_id") if isinstance(payload.get("batch"), dict) else None,
        "networkId": (payload.get("network") or {}).get("network_id") if isinstance(payload.get("network"), dict) else None,
        "networkName": (payload.get("network") or {}).get("network_name") if isinstance(payload.get("network"), dict) else None,
        "status": decision,
        "ingestionAllowed": not blocking,
        "networkCompilationAllowed": graph_ready,
        "readiness": {
            "dataStatus": "DATA_READY" if data_ready else "DATA_NOT_READY",
            "graphStatus": "GRAPH_READY" if graph_ready else "GRAPH_NOT_READY",
            "scenarioStatus": "SCENARIO_READY" if scenario_ready else "SCENARIO_NOT_READY",
        },
        "counts": counts,
        "blockingIssues": blocking,
        "warnings": warnings,
        "quarantine": quarantined,
        "normalizedRelations": normalized_relations,
    }
    if isinstance(graph_context, dict):
        result.update(graph_context)
    return result
