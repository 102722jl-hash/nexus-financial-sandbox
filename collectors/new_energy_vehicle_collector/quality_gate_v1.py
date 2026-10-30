"""Fail-closed structural and propagation checks for the NEV V1 network."""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict, deque
from pathlib import Path

from contract_v1 import COMPANIES, METRICS, NETWORK_ID, TEMPLATES
from initialize import DEFAULT_DB, initialize
from scenario_engine_v1 import run_scenario


def _path_exists(graph: dict[str, set[str]], sequence: list[str]) -> bool:
    def reachable(source: str, target: str) -> bool:
        queue = deque([source])
        seen = {source}
        while queue:
            current = queue.popleft()
            if current == target:
                return True
            for nxt in graph.get(current, set()):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return False
    return all(reachable(left, right) for left, right in zip(sequence, sequence[1:]))


def run_quality_gate(db_path: Path = DEFAULT_DB) -> dict:
    initialize(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    def error(code: str, detail: str) -> None:
        errors.append({"code": code, "detail": detail})

    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        error("FOREIGN_KEY_VIOLATION", repr([tuple(row) for row in violations]))

    node_rows = conn.execute(
        "SELECT node_id,metric_code,entity_code,editable,value_status,baseline_value,evidence_id FROM network_nodes WHERE network_id=?",
        (NETWORK_ID,),
    ).fetchall()
    nodes_by_metric: dict[str, list[sqlite3.Row]] = defaultdict(list)
    company_sets: dict[str, set[str]] = {code: set() for code in COMPANIES}
    for row in node_rows:
        nodes_by_metric[row["metric_code"]].append(row)
        if row["entity_code"]:
            company_sets[row["entity_code"]].add(row["metric_code"])
        if row["baseline_value"] is None and row["value_status"] != "DATA_MISSING":
            error("MISSING_VALUE_STATUS_INVALID", row["node_id"])
        if row["baseline_value"] is not None and not row["evidence_id"]:
            error("BASELINE_WITHOUT_EVIDENCE", row["node_id"])

    for code, spec in METRICS.items():
        expected = 1 if spec[4] == "INDUSTRY" else len(COMPANIES)
        actual = len(nodes_by_metric.get(code, []))
        if actual != expected:
            error("METRIC_NODE_CARDINALITY", f"{code}: expected={expected}, actual={actual}")
    company_metric_sets = list(company_sets.values())
    if any(metric_set != company_metric_sets[0] for metric_set in company_metric_sets[1:]):
        error("COMPANY_NODE_SETS_DIFFER", repr({k: sorted(v) for k, v in company_sets.items()}))

    edge_rows = conn.execute(
        """SELECT e.*, f.causal_conclusion
           FROM network_edges e JOIN formulas f ON f.formula_id=e.formula_id
           WHERE e.network_id=?""",
        (NETWORK_ID,),
    ).fetchall()
    edges_by_template: dict[str, list[sqlite3.Row]] = defaultdict(list)
    outgoing: dict[str, int] = defaultdict(int)
    graph: dict[str, set[str]] = defaultdict(set)
    for row in edge_rows:
        edges_by_template[row["template_id"]].append(row)
        outgoing[row["source_node_id"]] += 1
        graph[row["source_node_id"]].add(row["target_node_id"])
        if row["status"] != "AI_APPROVED":
            error("EDGE_NOT_AI_APPROVED", row["edge_id"])
        if row["causal_conclusion"] != "ABSTAIN":
            error("CAUSAL_GATE_CONTRADICTION", row["edge_id"])
        if row["parameter_status"] not in {"AI_ASSUMPTION", "CALCULATED_LINEAGE"}:
            error("PARAMETER_STATUS_INVALID", row["edge_id"])

    for template in TEMPLATES:
        tid, _source, _target, scope, *_rest = template
        expected = 1 if scope == "INDUSTRY" else len(COMPANIES)
        actual = len(edges_by_template.get(tid, []))
        if actual != expected:
            error("EDGE_TEMPLATE_NOT_FULLY_INSTANTIATED", f"{tid}: expected={expected}, actual={actual}")
    for row in node_rows:
        if row["editable"] and outgoing[row["node_id"]] == 0:
            error("EDITABLE_NODE_WITHOUT_DOWNSTREAM", row["node_id"])

    core = [
        "COMPANY_NEV_SALES",
        "VEHICLE_REVENUE_PROXY",
        "GROSS_PROFIT_PROXY",
        "NET_PROFIT",
        "CURRENT_MARKET_CAP",
    ]
    for entity in COMPANIES:
        ids = [f"company::{entity}::{metric}" for metric in core]
        if not _path_exists(graph, ids):
            error("CORE_PATH_MISSING", f"{entity}: {' -> '.join(core)}")
        industry_source = "industry::NEV_INDUSTRY_SALES"
        if not _path_exists(graph, [industry_source, ids[0]]):
            error("INDUSTRY_COMPANY_BRIDGE_MISSING", entity)

    smoke_inputs = {
        "NEV_INDUSTRY_SALES": 1_000_000,
        "LITHIUM_CARBONATE_PRICE": 100_000,
        "BATTERY_KWH_PER_VEHICLE": 60,
        "ASP_PROXY": 200_000,
    }
    smoke_params = {
        "market_share": 0.10,
        "material_coefficient": 0.0005,
        "profit_conversion_ratio": 0.60,
        "valuation_multiple": 12,
    }
    changed_metrics = [
        "COMPANY_NEV_SALES", "VEHICLE_REVENUE_PROXY", "GROSS_PROFIT_PROXY",
        "NET_PROFIT", "CURRENT_MARKET_CAP",
    ]
    changed = dict(smoke_inputs)
    changed["NEV_INDUSTRY_SALES"] = 1_100_000
    scenario_by_entity = {}
    for entity in COMPANIES:
        first = run_scenario(db_path, entity, smoke_inputs, smoke_params, persist=False)
        second = run_scenario(db_path, entity, changed, smoke_params, persist=False)
        propagated = [
            metric for metric in changed_metrics
            if first["values"].get(metric) != second["values"].get(metric)
        ]
        scenario_by_entity[entity] = {
            "changed_metrics": propagated,
            "status": "PASS" if propagated == changed_metrics else "FAIL",
        }
        for metric in changed_metrics:
            if metric not in propagated:
                error("SCENARIO_PROPAGATION_FAILED", f"{entity}:{metric}")

    blocked = run_scenario(
        db_path, "002594.SZ", {"NEV_INDUSTRY_SALES": 1_000_000},
        {"market_share": 0.10}, persist=False,
    )
    missing_input_metrics = ("VEHICLE_REVENUE_PROXY", "GROSS_PROFIT_PROXY", "CURRENT_MARKET_CAP")
    baseline_by_metric = {
        row["metric_code"]: row["baseline_value"]
        for row in node_rows if row["entity_code"] == "002594.SZ"
    }
    for metric in missing_input_metrics:
        if baseline_by_metric.get(metric) is None and blocked["statuses"].get(metric) != "BLOCKED_DATA_MISSING":
            error("MISSING_INPUT_DID_NOT_BLOCK", metric)

    if not edge_rows:
        error("NETWORK_HAS_NO_EDGES", NETWORK_ID)
    isolated_required = []
    connected = {row["source_node_id"] for row in edge_rows} | {row["target_node_id"] for row in edge_rows}
    for row in node_rows:
        required = METRICS[row["metric_code"]][6]
        if required and row["node_id"] not in connected:
            isolated_required.append(row["node_id"])
    if isolated_required:
        error("REQUIRED_NODE_ISOLATED", repr(isolated_required))

    required_rows = [row for row in node_rows if METRICS[row["metric_code"]][6]]
    required_with_baseline = [row for row in required_rows if row["baseline_value"] is not None]
    all_with_baseline = [row for row in node_rows if row["baseline_value"] is not None]
    status_counts: dict[str, int] = defaultdict(int)
    for row in node_rows:
        status_counts[row["value_status"]] += 1
    required_coverage = len(required_with_baseline) / len(required_rows) if required_rows else 1.0
    baseline_status = "DATA_READY" if required_coverage >= 0.80 else "DATA_PARTIAL"
    if baseline_status != "DATA_READY":
        warnings.append({
            "code": "REQUIRED_BASELINE_COVERAGE_INSUFFICIENT",
            "detail": f"required coverage={required_coverage:.2%}; threshold=80%",
        })

    report = {
        "network_id": NETWORK_ID,
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "nodes": len(node_rows),
            "edges": len(edge_rows),
            "templates": len(TEMPLATES),
            "companies": len(COMPANIES),
        },
        "scenario_smoke": {
            "changed_metrics": changed_metrics,
            "by_entity": scenario_by_entity,
            "missing_input_behavior": "ACCEPTED_BASELINE_OR_BLOCKED_DATA_MISSING",
        },
        "baseline_coverage": {
            "status": baseline_status,
            "threshold_pct": 80.0,
            "all_nodes": len(node_rows),
            "all_with_baseline": len(all_with_baseline),
            "all_coverage_pct": round(len(all_with_baseline) / len(node_rows) * 100, 2) if node_rows else 0.0,
            "required_nodes": len(required_rows),
            "required_with_baseline": len(required_with_baseline),
            "required_coverage_pct": round(required_coverage * 100, 2),
            "value_status_counts": dict(status_counts),
        },
    }
    conn.close()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    result = run_quality_gate(args.db)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
