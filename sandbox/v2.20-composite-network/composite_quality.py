from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from generic_network_contract import SUPPORTED_FORMULAS


CONTRACT_VERSION = "data-graph-scenario-readiness-1.0.0"
STRUCTURAL_RELATIONS = {"DATA_LINEAGE", "ENTITY_METRIC", "ACCOUNTING_STRUCTURE"}
CONFIRMED_STATUSES = {"CONFIRMED", "CONFIRMED_DATA", "CONFIRMED_LINEAGE"}
CANDIDATE_STATUSES = {"AI_APPROVED", "CANDIDATE", "NEEDS_HUMAN_REVIEW"}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _unit_family(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    families = (
        ("PERCENT", ("%", "pct", "percent", "比例", "率")),
        ("CURRENCY", ("cny", "rmb", "usd", "eur", "元", "万元", "亿元")),
        ("COUNT", ("辆", "台", "个", "户", "家", "股", "shares")),
        ("ENERGY", ("kwh", "mwh", "gwh", "千瓦时", "兆瓦时")),
        ("POWER", ("kw", "mw", "gw", "千瓦", "兆瓦")),
        ("MASS", ("kg", "ton", "吨", "万吨")),
        ("PRICE", ("/吨", "/辆", "元/", "price")),
    )
    for family, tokens in families:
        if any(token in text for token in tokens):
            return family
    return "OTHER"


def assess_mapping_readiness(
    profile: list[dict[str, Any]] | None,
    mappings: list[dict[str, Any]] | None,
    table_adapters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    profile = profile or []
    mappings = mappings or []
    table_adapters = table_adapters or []
    statuses = Counter(str(item.get("status") or "UNRESOLVED") for item in mappings)
    confirmed = [item for item in mappings if item.get("status") == "CONFIRMED"]
    ai_candidates = [
        item for item in mappings
        if item.get("candidateSource") == "AI_SEMANTIC"
        or item.get("status") in {"AI_APPROVED", "PENDING_REVIEW"}
    ]
    unresolved = [item for item in mappings if item.get("status") == "UNRESOLVED"]
    ignored = [item for item in mappings if item.get("status") == "IGNORED"]
    table_names = sorted({
        str(item.get("tableName") or item.get("table") or item.get("sourceLocator", {}).get("table") or "")
        for item in profile
        if item.get("tableName") or item.get("table") or item.get("sourceLocator", {}).get("table")
    })
    adapter_states = Counter(str(item.get("status") or "UNKNOWN") for item in table_adapters)
    issues: list[dict[str, Any]] = []
    if not profile:
        issues.append({"code": "PROFILE_EMPTY", "severity": "BLOCKING", "detail": "没有可用于画像的字段。"})
    if not confirmed:
        issues.append({"code": "CONFIRMED_MAPPING_MISSING", "severity": "BLOCKING", "detail": "没有已确认字段映射。"})
    if unresolved:
        issues.append({"code": "UNRESOLVED_FIELDS", "severity": "WARNING", "count": len(unresolved), "detail": "未识别字段已隔离，不阻断其他已确认字段。"})
    incomplete_adapters = [item for item in table_adapters if str(item.get("status") or "") in {"INCOMPLETE", "NEEDS_MAPPING", "ERROR"}]
    if incomplete_adapters:
        issues.append({"code": "TABLE_ROLE_INCOMPLETE", "severity": "WARNING", "count": len(incomplete_adapters), "detail": "部分表角色不完整，将跳过这些表。"})
    data_ready = bool(profile and confirmed)
    return {
        "contractVersion": CONTRACT_VERSION,
        "status": "DATA_READY" if data_ready else "DATA_REVIEW_REQUIRED",
        "readiness": {"dataReady": data_ready},
        "tableCount": len(table_names),
        "fieldCount": len(profile),
        "mappingCount": len(mappings),
        "confirmedMappingCount": len(confirmed),
        "aiCandidateCount": len(ai_candidates),
        "unresolvedCount": len(unresolved),
        "ignoredCount": len(ignored),
        "mappingStatuses": dict(statuses),
        "tableRoleStatuses": dict(adapter_states),
        "issues": issues,
    }


def _cycles(adjacency: dict[str, list[str]]) -> list[list[str]]:
    visited: set[str] = set()
    active: set[str] = set()
    stack: list[str] = []
    found: set[tuple[str, ...]] = set()

    def walk(node: str) -> None:
        visited.add(node)
        active.add(node)
        stack.append(node)
        for target in adjacency.get(node, []):
            if target not in visited:
                walk(target)
            elif target in active:
                start = stack.index(target)
                cycle = stack[start:] + [target]
                body = cycle[:-1]
                if body:
                    pivot = min(range(len(body)), key=lambda index: body[index])
                    canonical = tuple(body[pivot:] + body[:pivot])
                    found.add(canonical)
        stack.pop()
        active.discard(node)

    for node in sorted(adjacency):
        if node not in visited:
            walk(node)
    return [list(item) + [item[0]] for item in sorted(found)]


def assess_network_readiness(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    graph = payload.get("fullGraph") or payload.get("graph") or payload
    nodes = list(graph.get("nodes") or [])
    edges = list(graph.get("edges") or [])
    node_ids = [str(item.get("nodeId") or "").strip() for item in nodes]
    valid_node_ids = {item for item in node_ids if item}
    node_counts = Counter(node_ids)
    duplicate_nodes = sorted(item for item, count in node_counts.items() if item and count > 1)
    invalid_layers = [
        item.get("nodeId") for item in nodes
        if not str(item.get("layer") or "").strip() and _number(item.get("layerNo"), 0) <= 0
    ]
    missing_endpoints: list[dict[str, Any]] = []
    duplicate_edge_ids: list[str] = []
    edge_counts = Counter(str(item.get("edgeId") or "").strip() for item in edges)
    duplicate_edge_ids = sorted(item for item, count in edge_counts.items() if item and count > 1)
    quarantined_formula_edges: list[str] = []
    propagating: list[dict[str, Any]] = []
    confirmed_edges = 0
    candidate_edges = 0
    unit_warnings: list[dict[str, Any]] = []
    nodes_by_id = {str(item.get("nodeId") or ""): item for item in nodes if item.get("nodeId")}

    for edge in edges:
        source = str(edge.get("sourceNodeId") or "").strip()
        target = str(edge.get("targetNodeId") or "").strip()
        if source not in valid_node_ids or target not in valid_node_ids:
            missing_endpoints.append({"edgeId": edge.get("edgeId"), "sourceNodeId": source, "targetNodeId": target})
            continue
        relation_type = str(edge.get("relationType") or "").upper()
        if relation_type in STRUCTURAL_RELATIONS:
            continue
        formula = str(edge.get("formulaType") or "LINEAR_WEIGHT").upper()
        if formula not in SUPPORTED_FORMULAS:
            quarantined_formula_edges.append(str(edge.get("edgeId") or ""))
            continue
        status = str(edge.get("status") or "").upper()
        formal_weight = abs(_number(edge.get("weight")))
        candidate_weight = abs(_number(edge.get("candidateWeight")))
        formal = status in CONFIRMED_STATUSES and formal_weight > 0
        candidate = bool(edge.get("candidateSimulation")) and candidate_weight > 0
        if formal:
            confirmed_edges += 1
        if candidate:
            candidate_edges += 1
        if formal or candidate:
            propagating.append(edge)
        if formula in {"ADD", "SUBTRACT"}:
            source_family = _unit_family(nodes_by_id[source].get("unit"))
            target_family = _unit_family(nodes_by_id[target].get("unit"))
            if source_family and target_family and source_family != target_family:
                unit_warnings.append({"edgeId": edge.get("edgeId"), "sourceUnitFamily": source_family, "targetUnitFamily": target_family})

    adjacency: dict[str, list[str]] = defaultdict(list)
    incoming: Counter[str] = Counter()
    outgoing: Counter[str] = Counter()
    connected_nodes: set[str] = set()
    for edge in propagating:
        source = str(edge.get("sourceNodeId"))
        target = str(edge.get("targetNodeId"))
        adjacency[source].append(target)
        outgoing[source] += 1
        incoming[target] += 1
        connected_nodes.update((source, target))

    explicit_editable = {str(item.get("nodeId")) for item in nodes if item.get("editable") is True}
    adjustable_nodes = explicit_editable | set(adjacency)
    terminal_nodes = {node for node in connected_nodes if incoming[node] and not outgoing[node]}
    reachable: set[str] = set(adjustable_nodes)
    queue = list(adjustable_nodes)
    while queue:
        source = queue.pop(0)
        for target in adjacency.get(source, []):
            if target not in reachable:
                reachable.add(target)
                queue.append(target)
    reachable_terminals = sorted(terminal_nodes.intersection(reachable))
    isolated_nodes = sorted(valid_node_ids - {
        str(value) for edge in edges for value in (edge.get("sourceNodeId"), edge.get("targetNodeId")) if value
    })
    cycles = _cycles(adjacency)

    structural_issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not nodes:
        structural_issues.append({"code": "NO_VALID_NODES", "severity": "BLOCKING"})
    if duplicate_nodes:
        structural_issues.append({"code": "DUPLICATE_NODE_ID", "severity": "BLOCKING", "nodeIds": duplicate_nodes})
    if invalid_layers:
        structural_issues.append({"code": "NODE_LAYER_INVALID", "severity": "BLOCKING", "nodeIds": invalid_layers})
    if missing_endpoints:
        structural_issues.append({"code": "EDGE_NODE_NOT_FOUND", "severity": "BLOCKING", "edges": missing_endpoints})
    if duplicate_edge_ids:
        structural_issues.append({"code": "DUPLICATE_EDGE_ID", "severity": "BLOCKING", "edgeIds": duplicate_edge_ids})
    if quarantined_formula_edges:
        warnings.append({"code": "FORMULA_NEEDS_REVIEW", "severity": "WARNING", "edgeIds": quarantined_formula_edges})
    if isolated_nodes:
        warnings.append({"code": "ISOLATED_NODES", "severity": "WARNING", "nodeIds": isolated_nodes})
    if cycles:
        warnings.append({"code": "PROPAGATION_CYCLES", "severity": "WARNING", "cycles": cycles, "detail": "循环路径必须使用收敛和影响上限。"})
    if unit_warnings:
        warnings.append({"code": "UNIT_FAMILY_MISMATCH", "severity": "WARNING", "edges": unit_warnings})
    if not propagating:
        warnings.append({"code": "NO_PROPAGATING_EDGES", "severity": "WARNING"})
    elif not reachable_terminals:
        warnings.append({"code": "NO_ADJUSTABLE_TO_RESULT_PATH", "severity": "WARNING"})

    metric_nodes = [item for item in nodes if str(item.get("nodeType") or "").upper() != "ENTITY"]
    required_nodes = [item for item in metric_nodes if item.get("requiredForNetwork") is True]

    def has_numeric_baseline(item: dict[str, Any]) -> bool:
        baseline = item.get("baseline") or {}
        return any(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            for key, value in baseline.items()
            if key not in {"as_of_date", "evidence_id"}
        )

    observed_nodes = [item for item in metric_nodes if has_numeric_baseline(item)]
    observed_required = [item for item in required_nodes if has_numeric_baseline(item)]
    baseline_coverage = len(observed_nodes) / len(metric_nodes) if metric_nodes else 0.0
    required_coverage = len(observed_required) / len(required_nodes) if required_nodes else baseline_coverage
    explicit_coverage_contract = any("requiredForNetwork" in item for item in metric_nodes)
    coverage_ready = required_coverage >= 0.80 if explicit_coverage_contract else True
    if explicit_coverage_contract and not coverage_ready:
        warnings.append({
            "code": "REQUIRED_BASELINE_COVERAGE_INSUFFICIENT",
            "severity": "WARNING",
            "requiredCoveragePct": round(required_coverage * 100, 2),
            "thresholdPct": 80.0,
            "detail": "必需指标基准覆盖不足，网络保留展示与候选关系，但不标记为情景就绪。",
        })

    data_ready = bool(nodes) and coverage_ready
    graph_ready = bool(nodes) and not structural_issues
    scenario_ready = data_ready and graph_ready and bool(propagating and reachable_terminals)
    overall = "SCENARIO_READY" if scenario_ready else ("GRAPH_READY" if graph_ready else ("DATA_READY" if data_ready else "NOT_READY"))
    return {
        "contractVersion": CONTRACT_VERSION,
        "status": overall,
        "readiness": {
            "dataReady": data_ready,
            "graphReady": graph_ready,
            "scenarioReady": scenario_ready,
            "dataStatus": "DATA_READY" if data_ready else ("DATA_PARTIAL" if observed_nodes else "DATA_NOT_READY"),
            "graphStatus": "GRAPH_READY" if graph_ready else "GRAPH_NOT_READY",
            "scenarioStatus": "SCENARIO_READY" if scenario_ready else "SCENARIO_NOT_READY",
        },
        "counts": {
            "nodes": len(nodes), "edges": len(edges),
            "propagatingEdges": len(propagating), "confirmedEdges": confirmed_edges,
            "candidateEdges": candidate_edges, "adjustableNodes": len(adjustable_nodes),
            "terminalNodes": len(terminal_nodes), "reachableTerminalNodes": len(reachable_terminals),
            "isolatedNodes": len(isolated_nodes), "quarantinedFormulaEdges": len(quarantined_formula_edges),
            "cycles": len(cycles),
        },
        "coverage": {
            "propagationNodeCoveragePct": round(len(connected_nodes) / len(nodes) * 100, 2) if nodes else 0.0,
            "reachableResultCoveragePct": round(len(reachable_terminals) / len(terminal_nodes) * 100, 2) if terminal_nodes else 0.0,
            "baselineCoveragePct": round(baseline_coverage * 100, 2),
            "requiredBaselineCoveragePct": round(required_coverage * 100, 2),
            "baselineCoverageThresholdPct": 80.0 if explicit_coverage_contract else None,
            "metricNodes": len(metric_nodes),
            "metricNodesWithBaseline": len(observed_nodes),
            "requiredMetricNodes": len(required_nodes),
            "requiredMetricNodesWithBaseline": len(observed_required),
        },
        "reachableResultNodeIds": reachable_terminals,
        "blockingIssues": structural_issues,
        "warnings": warnings,
    }


def decorate_network_plan(plan: dict[str, Any]) -> dict[str, Any]:
    quality = assess_network_readiness(plan)
    plan["readiness"] = quality["readiness"]
    plan["qualityReport"] = quality
    plan["compositeContractVersion"] = CONTRACT_VERSION
    if quality["blockingIssues"]:
        plan["activationBlocked"] = True
    if quality["readiness"]["scenarioReady"] and plan.get("candidateScenarioReady"):
        plan["outputLevel"] = "CANDIDATE_SCENARIO"
    return plan
