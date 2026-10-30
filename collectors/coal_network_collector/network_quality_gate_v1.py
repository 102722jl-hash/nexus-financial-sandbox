"""Structural and execution quality gate for every network refresh."""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

from scenario_engine_v1 import scenario

ROOT = Path(__file__).parent
NETWORK_ID = "coal_power_v1"
REQUIRED_TABLES = (
    "network_registry", "network_layers", "entities", "evidence",
    "metric_values", "calculated_metric_lineage", "formulas",
    "network_nodes", "network_edges", "valuation", "review_queue",
    "raw_documents", "scenario_runs", "scenario_values",
)
KNOWN_UNITS = {
    "ON_GRID_TARIFF": {"元/兆瓦时", "元/千瓦时"},
    "STANDARD_COAL_PRICE": {"元/吨"},
    "SUPPLY_COAL_CONSUMPTION": {"克/千瓦时"},
    "PLANT_USE_RATE": {"%"},
    "UTILIZATION_HOURS": {"小时"},
    "THERMAL_UTILIZATION_HOURS": {"小时"},
    "POWER_GENERATION": {"亿千瓦时"},
    "GRID_SALES_POWER": {"亿千瓦时"},
    "THERMAL_POWER_GENERATION": {"亿千瓦时"},
    "THERMAL_GRID_SALES_POWER": {"亿千瓦时"},
    "CAPEX": {"元"},
    "CASH": {"元"},
    "REVENUE": {"元"},
    "OPERATING_COST": {"元"},
    "FUEL_COST": {"元"},
    "FUEL_COST_PROXY": {"元"},
    "NET_PROFIT": {"元"},
    "OPERATING_CASH_FLOW": {"元"},
}


def run(db: sqlite3.Connection) -> dict:
    errors: list[dict] = []
    warnings: list[dict] = []
    tables = {
        row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    for table in REQUIRED_TABLES:
        if table not in tables:
            errors.append({"code": "MISSING_TABLE", "table": table})
    if errors:
        result = {"errors": errors, "warnings": warnings, "status": "BLOCKED"}
        (ROOT / "network_quality_report.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result

    foreign_keys = db.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_keys:
        errors.append({"code": "FOREIGN_KEY_VIOLATIONS", "count": len(foreign_keys)})

    incomplete = db.execute(
        """SELECT count(*) FROM evidence
        WHERE acceptance_status='ACCEPTED'
        AND (coalesce(source_url,'')='' OR coalesce(original_quote,'')=''
             OR coalesce(page_or_locator,'')='' OR coalesce(published_at,'')='')"""
    ).fetchone()[0]
    if incomplete:
        errors.append({"code": "ACCEPTED_EVIDENCE_INCOMPLETE", "count": incomplete})

    bad_facts = db.execute(
        """SELECT count(*) FROM metric_values m
        LEFT JOIN evidence e ON e.evidence_id=m.evidence_id
        WHERE m.value_status='SOURCE_FACT'
        AND (m.value IS NULL OR e.evidence_id IS NULL
             OR e.acceptance_status NOT IN ('ACCEPTED','SUPERSEDED'))"""
    ).fetchone()[0]
    if bad_facts:
        errors.append({"code": "SOURCE_FACT_WITHOUT_ACCEPTED_EVIDENCE", "count": bad_facts})

    for code, units in KNOWN_UNITS.items():
        placeholders = ",".join("?" for _ in units)
        count = db.execute(
            f"""SELECT count(*) FROM metric_values
            WHERE metric_code=? AND value_status IN ('SOURCE_FACT','MARKET_PROXY','CALCULATED')
            AND unit NOT IN ({placeholders})""",
            (code, *units),
        ).fetchone()[0]
        if count:
            warnings.append({"code": "UNIT_OUTSIDE_CONTRACT", "metric_code": code, "count": count})

    missing_definitions = db.execute(
        """SELECT count(*) FROM network_nodes n LEFT JOIN metric_definitions d
        ON d.metric_code=n.metric_code WHERE n.metric_code IS NOT NULL AND d.metric_code IS NULL"""
    ).fetchone()[0]
    if missing_definitions:
        errors.append({"code": "NODE_METRIC_DEFINITION_MISSING", "count": missing_definitions})

    conflicts = db.execute(
        """SELECT metric_code,coalesce(entity_code,'INDUSTRY'),
        coalesce(report_period,''),coalesce(as_of_date,''),count(*),min(value),max(value)
        FROM metric_values
        WHERE value_status='SOURCE_FACT' AND value IS NOT NULL
        GROUP BY metric_code,entity_code,report_period,as_of_date
        HAVING count(*)>1 AND abs(max(value)-min(value))>0.000001"""
    ).fetchall()
    for row in conflicts[:50]:
        warnings.append({"code": "CONFLICTING_ACTIVE_FACTS", "key": list(row)})
    if len(conflicts) > 50:
        warnings.append({"code": "CONFLICTING_ACTIVE_FACTS_TRUNCATED", "count": len(conflicts)})

    node_ids = {
        row[0]: row for row in db.execute(
            "SELECT node_id,layer_no,metric_code,entity_code,editable,status,evidence_id FROM network_nodes WHERE network_id=?",
            (NETWORK_ID,),
        )
    }
    edge_rows = db.execute(
        """SELECT edge_id,source_node_id,target_node_id,formula_id,status,
        parameter_status FROM network_edges WHERE network_id=?""",
        (NETWORK_ID,),
    ).fetchall()
    out_degree = defaultdict(int)
    referenced_formulas = set()
    for edge_id, source, target, formula_id, status, parameter_status in edge_rows:
        if source not in node_ids or target not in node_ids:
            errors.append({"code": "DANGLING_EDGE", "edge_id": edge_id})
        out_degree[source] += 1
        if formula_id:
            referenced_formulas.add(formula_id)
            if not db.execute("SELECT 1 FROM formulas WHERE formula_id=?", (formula_id,)).fetchone():
                errors.append({"code": "MISSING_EDGE_FORMULA", "edge_id": edge_id, "formula_id": formula_id})
        if status in ("AI_APPROVED", "CANDIDATE", "AI_CANDIDATE") and parameter_status == "AI_ASSUMPTION":
            warnings.append({"code": "UNCALIBRATED_CANDIDATE_EDGE", "edge_id": edge_id})

    for node_id, (_id, layer, code, entity, editable, status, evidence_id) in node_ids.items():
        if not db.execute(
            "SELECT 1 FROM network_layers WHERE network_id=? AND layer_no=?",
            (NETWORK_ID, layer),
        ).fetchone():
            errors.append({"code": "NODE_LAYER_NOT_FOUND", "node_id": node_id})
        if evidence_id and not db.execute(
            "SELECT 1 FROM evidence WHERE evidence_id=?", (evidence_id,)
        ).fetchone():
            errors.append({"code": "NODE_EVIDENCE_NOT_FOUND", "node_id": node_id})
        if editable and out_degree[node_id] == 0:
            warnings.append({"code": "EDITABLE_NODE_HAS_NO_DOWNSTREAM", "node_id": node_id, "metric_code": code})

    lineage_errors = db.execute(
        """SELECT count(*) FROM calculated_metric_lineage l
        LEFT JOIN metric_values m ON m.metric_value_id=l.metric_value_id
        LEFT JOIN metric_values c ON c.metric_value_id=l.component_metric_value_id
        LEFT JOIN evidence e ON e.evidence_id=l.component_evidence_id
        WHERE m.metric_value_id IS NULL OR c.metric_value_id IS NULL OR e.evidence_id IS NULL"""
    ).fetchone()[0]
    if lineage_errors:
        errors.append({"code": "BROKEN_CALCULATED_LINEAGE", "count": lineage_errors})

    formulas_missing = db.execute(
        """SELECT count(*) FROM formulas
        WHERE status IN ('AI_APPROVED','CANDIDATE') AND coalesce(formula_expression,'')=''"""
    ).fetchone()[0]
    if formulas_missing:
        errors.append({"code": "FORMULA_EXPRESSION_MISSING", "count": formulas_missing})

    smoke_db = sqlite3.connect(":memory:")
    db.backup(smoke_db)
    smoke = scenario(
        smoke_db, "600795.SH",
        {("STANDARD_COAL_PRICE", "600795.SH"): 900.0},
        persist=False,
    )
    smoke_db.close()
    if smoke["errors"] or smoke["calculated"] == 0:
        errors.append({"code": "SCENARIO_SMOKE_FAILED", "errors": smoke["errors"], "calculated": smoke["calculated"]})
    else:
        changed = [
            row for row in smoke["values"]
            if row["status"] == "CALCULATED_SCENARIO"
            and row["value"] is not None
            and row["trace"].get("inputs")
        ]
        if not changed:
            errors.append({"code": "SCENARIO_HAS_NO_DOWNSTREAM_TRACE"})

    result = {
        "status": "PASSED" if not errors else "BLOCKED",
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "nodes": len(node_ids),
            "edges": len(edge_rows),
            "referenced_formulas": len(referenced_formulas),
            "foreign_key_errors": len(foreign_keys),
            "editable_nodes": sum(bool(row[4]) for row in node_ids.values()),
            "accepted_evidence_incomplete": incomplete,
            "lineage_errors": lineage_errors,
        },
    }
    (ROOT / "network_quality_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    connection = sqlite3.connect(ROOT / "coal_network.db")
    connection.execute("PRAGMA foreign_keys=ON")
    report = run(connection)
    connection.close()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(1 if report["errors"] else 0)
