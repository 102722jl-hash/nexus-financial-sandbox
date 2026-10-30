from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from composite_quality import decorate_network_plan
from crawler_contract import stable_id, validate_crawler_payload
from generic_network_contract import normalize_formula_type


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _time_key(item: dict[str, Any]) -> tuple[str, str, int]:
    return (
        _text(item.get("available_at")),
        _text(item.get("as_of_date")),
        int(item.get("revision") or 0),
    )


def _quarantined_ids(report: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (_text(item.get("objectType")), _text(item.get("objectId")))
        for item in report.get("quarantine") or []
        if item.get("objectType") and item.get("objectId")
    }


def _entity_candidates(
    metric: dict[str, Any],
    entities: list[dict[str, Any]],
    observations: list[dict[str, Any]],
) -> list[str | None]:
    scope = _text(metric.get("entity_scope")).upper()
    observed = sorted({_text(item.get("entity_code")) for item in observations if _text(item.get("entity_code"))})
    active = [item for item in entities if item.get("status") == "ACTIVE"]
    if scope == "COMPANY":
        candidates = [_text(item.get("entity_code")) for item in active if item.get("entity_type") == "COMPANY"]
        return sorted(set(candidates or observed))
    if scope == "ENTITY":
        return sorted({_text(item.get("entity_code")) for item in active if _text(item.get("entity_code"))} | set(observed))
    typed = [_text(item.get("entity_code")) for item in active if item.get("entity_type") == scope]
    return sorted(set(typed or observed)) if (typed or observed) else [None]


def _relation_pairs(
    source_nodes: list[dict[str, Any]],
    target_nodes: list[dict[str, Any]],
    entity_scope: str,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    explicit = entity_scope if entity_scope and entity_scope not in {"GLOBAL", "INDUSTRY", "ENTITY", "COMPANY", "REGION", "COMMODITY", "CROSS"} else None
    if explicit:
        source = [item for item in source_nodes if not item.get("entityCode") or item.get("entityCode") == explicit]
        target = [item for item in target_nodes if not item.get("entityCode") or item.get("entityCode") == explicit]
    else:
        source, target = source_nodes, target_nodes
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for left in source:
        for right in target:
            left_entity = left.get("entityCode")
            right_entity = right.get("entityCode")
            if left_entity and right_entity and left_entity != right_entity:
                continue
            pairs.append((left, right))
    return pairs


def compile_crawler_network(payload: dict[str, Any]) -> dict[str, Any]:
    """Compile a validated crawler batch into the browser's standalone graph format."""
    report = validate_crawler_payload(payload)
    if not report["ingestionAllowed"]:
        codes = ",".join(item["code"] for item in report["blockingIssues"])
        raise ValueError(f"CRAWLER_BATCH_BLOCKED:{codes}")
    if not report["networkCompilationAllowed"]:
        raise ValueError("CRAWLER_BATCH_NOT_GRAPH_READY")

    quarantined = _quarantined_ids(report)
    network = payload["network"]
    layers = sorted(payload.get("layers") or [], key=lambda item: (item.get("sort_order", 0), item.get("layer_no", 0)))
    layer_by_code = {_text(item.get("layer_code")): item for item in layers}
    entities = [item for item in payload.get("entities") or [] if ("entity", _text(item.get("entity_code"))) not in quarantined]
    entity_by_code = {_text(item.get("entity_code")): item for item in entities}
    observations = [item for item in payload.get("observations") or [] if ("observation", _text(item.get("observation_id"))) not in quarantined]
    evidence_by_id = {_text(item.get("evidence_id")): item for item in payload.get("evidence") or [] if ("evidence", _text(item.get("evidence_id"))) not in quarantined}
    formula_by_id = {_text(item.get("formula_id")): item for item in payload.get("formulas") or [] if ("formula", _text(item.get("formula_id"))) not in quarantined}

    latest: dict[tuple[str, str | None], dict[str, Any]] = {}
    observations_by_metric: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in observations:
        metric_code = _text(item.get("metric_code"))
        entity_code = _text(item.get("entity_code")) or None
        observations_by_metric[metric_code].append(item)
        key = (metric_code, entity_code)
        if key not in latest or _time_key(item) > _time_key(latest[key]):
            latest[key] = item

    nodes: list[dict[str, Any]] = []
    nodes_by_metric: dict[str, list[dict[str, Any]]] = defaultdict(list)
    nodes_by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    metrics = [item for item in payload.get("metric_definitions") or [] if item.get("status") == "ACTIVE" and ("metric_definition", _text(item.get("metric_code"))) not in quarantined]
    for metric in metrics:
        metric_code = _text(metric.get("metric_code"))
        layer = layer_by_code.get(_text(metric.get("default_layer_code"))) or {}
        for entity_code in _entity_candidates(metric, entities, observations_by_metric.get(metric_code, [])):
            observation = latest.get((metric_code, entity_code)) or (latest.get((metric_code, None)) if entity_code else None)
            entity = entity_by_code.get(entity_code or "") or {}
            observation_id = _text((observation or {}).get("observation_id"))
            evidence_id = _text((observation or {}).get("evidence_id"))
            value = _number((observation or {}).get("value"))
            node_id = stable_id("NODE", network["network_id"], metric_code, entity_code)
            label = _text(metric.get("metric_name"))
            if entity:
                label = f"{_text(entity.get('entity_name'))}｜{label}"
            baseline: dict[str, Any] = {}
            if value is not None:
                baseline[metric_code] = value
                baseline["BASE"] = value
            if observation:
                baseline["as_of_date"] = observation.get("as_of_date")
                baseline["evidence_id"] = evidence_id or None
            node = {
                "nodeId": node_id,
                "layer": _text(layer.get("layer_code")) or "unclassified",
                "layerNo": int(layer.get("layer_no") or 0),
                "nodeType": _text(metric.get("metric_type")) or "INDEX",
                "label": label,
                "sub": _text(entity.get("entity_name")) or _text(layer.get("layer_name")),
                "description": _text(metric.get("description")),
                "unit": metric.get("canonical_unit"),
                "entityCode": entity_code,
                "metricCodes": [metric_code],
                "baseline": baseline,
                "editable": bool(metric.get("editable_default") and value is not None),
                "editableDefinition": bool(metric.get("editable_default")),
                "requiredForNetwork": bool(metric.get("required_for_network")),
                "evidenceIds": [evidence_id] if evidence_id and evidence_id in evidence_by_id else [],
                "valueStatus": (observation or {}).get("quality_status") or "DATA_MISSING",
                "status": "CONFIRMED_DATA" if value is not None else "DATA_MISSING",
                "dataCutoff": network.get("data_cutoff"),
                "source": "NEXUS_CRAWLER_CONTRACT",
                "sourceObservationId": observation_id or None,
            }
            nodes.append(node)
            nodes_by_metric[metric_code].append(node)
            if entity_code:
                nodes_by_entity[entity_code].append(node)

    # Company metrics need an explicit entity node.  Metric nodes retain their
    # business type (PRICE/FLOW/AMOUNT/etc.); the browser must not have to infer
    # company identity from those types or fall back to an industry node.
    entity_layer = max(layers, key=lambda item: int(item.get("layer_no") or 0), default={})
    company_entity_nodes: dict[str, dict[str, Any]] = {}
    for entity in entities:
        if entity.get("status") != "ACTIVE" or _text(entity.get("entity_type")).upper() != "COMPANY":
            continue
        entity_code = _text(entity.get("entity_code"))
        metric_nodes = nodes_by_entity.get(entity_code, [])
        baseline: dict[str, Any] = {}
        metric_codes: list[str] = []
        evidence_ids: list[str] = []
        for metric_node in metric_nodes:
            for metric_code in metric_node.get("metricCodes") or []:
                metric_codes.append(metric_code)
                value = _number((metric_node.get("baseline") or {}).get(metric_code))
                if value is not None:
                    baseline[metric_code] = value
            evidence_ids.extend(metric_node.get("evidenceIds") or [])
        entity_node = {
            "nodeId": stable_id("ENTITY", network["network_id"], entity_code),
            "layer": _text(entity_layer.get("layer_code")) or "company",
            "layerNo": int(entity_layer.get("layer_no") or len(layers) or 1),
            "nodeType": "ENTITY",
            "label": _text(entity.get("entity_name")) or entity_code,
            "sub": entity_code,
            "description": "按公司代码汇总该实体的来源指标。",
            "unit": None,
            "entityCode": entity_code,
            "metricCodes": sorted(set(metric_codes)),
            "baseline": baseline,
            "editable": False,
            "editableDefinition": False,
            "evidenceIds": sorted(set(evidence_ids)),
            "valueStatus": "CONFIRMED_DATA" if baseline else "DATA_MISSING",
            "status": "CONFIRMED_DATA" if baseline else "DATA_MISSING",
            "dataCutoff": network.get("data_cutoff"),
            "source": "NEXUS_CRAWLER_CONTRACT",
            "sourceObservationId": None,
        }
        nodes.append(entity_node)
        company_entity_nodes[entity_code] = entity_node

    edges: list[dict[str, Any]] = []
    for relation in payload.get("relations") or []:
        relation_id = _text(relation.get("relation_id"))
        if ("relation", relation_id) in quarantined or relation.get("status") in {"DISABLED", "NEEDS_HUMAN_REVIEW"}:
            continue
        formula = formula_by_id.get(_text(relation.get("formula_id")))
        if not formula:
            continue
        formula_type, resolution = normalize_formula_type(formula.get("formula_type"), formula.get("formula_expression"))
        if not formula_type:
            continue
        status = _text(relation.get("status")).upper()
        candidate = status in {"AI_APPROVED", "CANDIDATE"}
        formal_weight = abs(_number(relation.get("weight")) or 0.0)
        candidate_weight = abs(_number(relation.get("candidate_weight")) or 0.0)
        parameters = dict(formula.get("parameters") or {})
        for source, target in _relation_pairs(
            nodes_by_metric.get(_text(relation.get("source_metric_code")), []),
            nodes_by_metric.get(_text(relation.get("target_metric_code")), []),
            _text(relation.get("entity_scope")),
        ):
            entity_key = source.get("entityCode") or target.get("entityCode") or "GLOBAL"
            edge = {
                "edgeId": stable_id("EDGE", network["network_id"], relation_id, entity_key),
                "sourceNodeId": source["nodeId"],
                "targetNodeId": target["nodeId"],
                "direction": relation.get("direction"),
                "relationType": relation.get("relation_type"),
                "formulaId": formula.get("formula_id"),
                "formulaType": formula_type,
                "formulaResolution": resolution,
                "formulaParameters": parameters,
                "formulaVersion": "1.0.0",
                "parameterStatus": relation.get("parameter_status"),
                "weight": formal_weight if status == "CONFIRMED" else 0.0,
                "candidateWeight": candidate_weight if candidate else 0.0,
                "candidateSimulation": bool(candidate and candidate_weight != 0),
                "lagDays": int(relation.get("lag_days") or 0),
                "confidence": float(relation.get("confidence") or 0.0),
                "impactCapPct": float(relation.get("impact_cap_pct") or 0.0),
                "mechanism": relation.get("mechanism"),
                "evidenceSource": list(relation.get("evidence_ids") or []),
                "invalidation": relation.get("invalidation"),
                "status": status,
                "sourceStatus": status,
                "runtimeNetwork": True,
            }
            edges.append(edge)

    # One structural edge anchors every company entity in the graph without
    # treating the aggregation as a causal relationship.
    for entity_code, entity_node in company_entity_nodes.items():
        candidates = nodes_by_entity.get(entity_code, [])
        if not candidates:
            continue
        source = max(
            candidates,
            key=lambda item: (
                bool(item.get("baseline")),
                int(item.get("layerNo") or 0),
                _text((item.get("metricCodes") or [""])[0]),
            ),
        )
        edges.append({
            "edgeId": stable_id("ENTITY_EDGE", network["network_id"], entity_code),
            "sourceNodeId": source["nodeId"],
            "targetNodeId": entity_node["nodeId"],
            "direction": "mixed",
            "relationType": "ENTITY_METRIC",
            "formulaId": None,
            "formulaType": "IDENTITY",
            "formulaResolution": "STRUCTURAL",
            "formulaParameters": {},
            "formulaVersion": "1.0.0",
            "parameterStatus": "NOT_APPLICABLE",
            "weight": 0.0,
            "candidateWeight": 0.0,
            "candidateSimulation": False,
            "lagDays": 0,
            "confidence": 1.0,
            "impactCapPct": 0.0,
            "mechanism": "公司指标按证券代码归集到公司实体。",
            "evidenceSource": entity_node["evidenceIds"],
            "invalidation": "公司证券代码或实体登记发生变化。",
            "status": "CONFIRMED_LINEAGE",
            "sourceStatus": "CONFIRMED_LINEAGE",
            "runtimeNetwork": True,
        })

    plan_id = stable_id(
        "PLAN", network["network_id"], network["network_version"], network["data_cutoff"],
        (payload.get("batch") or {}).get("batch_id"),
    )
    plan = {
        "schemaVersion": "composite-network-contract-1.0.0",
        "crawlerContractVersion": payload.get("contract_version"),
        "sourceNetworkId": network["network_id"],
        "networkId": plan_id,
        "networkPlanId": plan_id,
        "networkName": network["network_name"],
        "networkKind": network["network_kind"],
        "networkVersion": network["network_version"],
        "mode": "CREATE_NEW_NETWORK",
        "status": "ACTIVE",
        "dataCutoff": network["data_cutoff"],
        "causalStatus": network.get("causal_status", "ABSTAIN"),
        "outputLevel": "CANDIDATE_SCENARIO" if any(item.get("candidateSimulation") for item in edges) else "GRAPH_ONLY",
        "candidateScenarioReady": any(item.get("candidateSimulation") for item in edges),
        "layerLabels": {_text(item.get("layer_code")): _text(item.get("layer_name")) for item in layers},
        "layers": layers,
        "entities": entities,
        "nodes": nodes,
        "edges": edges,
        "graph": {"nodes": nodes, "edges": edges},
        "fullGraph": {"nodes": nodes, "edges": edges},
        "metricValues": observations,
        "contractValidation": report,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "deletable": True,
    }
    decorate_network_plan(plan)
    return plan
