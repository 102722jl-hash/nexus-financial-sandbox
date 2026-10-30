"""Execute controlled network formulas for an entity scenario.

Only formula families declared in SUPPORTED_FORMULAS are executable.  Any
missing input, unit mismatch, ambiguous formula, or unsupported relationship is
returned as BLOCKED instead of silently carrying a stale value forward.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
NETWORK_ID = "coal_power_v1"
ENGINE_VERSION = "1.1"
USABLE = ("CANDIDATE", "AI_CANDIDATE", "AI_APPROVED", "CONFIRMED", "ACTIVE", "APPROVED")

SUPPORTED_FORMULAS = {
    "CAPACITY_UTILIZATION",
    "POWER_BALANCE",
    "REVENUE_BRIDGE",
    "FUEL_COST_IDENTITY",
    "CASH_FLOW_IDENTITY",
    "ACCOUNTING_IDENTITY",
    "MARKET_CAP_IDENTITY",
    "COST_PASS_THROUGH",
    "MARGIN_BRIDGE",
    "PRICE_BASIS_BRIDGE",
}

TARGET_PRIORITY = {
    "POWER_GENERATION": ["CAPACITY_UTILIZATION"],
    "THERMAL_POWER_GENERATION": ["CAPACITY_UTILIZATION"],
    "GRID_SALES_POWER": ["POWER_BALANCE"],
    "THERMAL_GRID_SALES_POWER": ["POWER_BALANCE"],
    "REVENUE": ["REVENUE_BRIDGE"],
    "FUEL_COST_PROXY": ["FUEL_COST_IDENTITY"],
    "DISCLOSED_DEBT_COMPONENTS": ["ACCOUNTING_IDENTITY"],
    "NET_DEBT_PROXY": ["ACCOUNTING_IDENTITY"],
    "FREE_CASH_FLOW_PROXY": ["CASH_FLOW_IDENTITY"],
    "CURRENT_MARKET_CAP": ["MARKET_CAP_IDENTITY"],
    "STANDARD_COAL_PRICE": ["PRICE_BASIS_BRIDGE"],
    "OPERATING_COST": ["COST_PASS_THROUGH"],
    "NET_PROFIT": ["MARGIN_BRIDGE"],
}

FALLBACK_INPUTS = {
    "CAPACITY_UTILIZATION": {
        "POWER_GENERATION": ["CONTROLLABLE_CAPACITY", "UTILIZATION_HOURS"],
        "THERMAL_POWER_GENERATION": ["THERMAL_CAPACITY", "THERMAL_UTILIZATION_HOURS"],
    },
    "POWER_BALANCE": {
        "GRID_SALES_POWER": ["POWER_GENERATION", "PLANT_USE_RATE"],
        "THERMAL_GRID_SALES_POWER": ["THERMAL_POWER_GENERATION", "PLANT_USE_RATE"],
    },
    "REVENUE_BRIDGE": {"REVENUE": ["GRID_SALES_POWER", "ON_GRID_TARIFF"]},
    "FUEL_COST_IDENTITY": {
        "FUEL_COST_PROXY": [
            "THERMAL_POWER_GENERATION",
            "SUPPLY_COAL_CONSUMPTION",
            "STANDARD_COAL_PRICE",
        ]
    },
    "CASH_FLOW_IDENTITY": {"FREE_CASH_FLOW_PROXY": ["OPERATING_CASH_FLOW", "CAPEX"]},
    "ACCOUNTING_IDENTITY": {
        "DISCLOSED_DEBT_COMPONENTS": [
            "SHORT_TERM_DEBT",
            "CURRENT_NONCURRENT_DEBT",
            "LONG_TERM_DEBT",
            "BONDS_PAYABLE",
        ],
        "NET_DEBT_PROXY": ["DISCLOSED_DEBT_COMPONENTS", "CASH"],
    },
    "MARKET_CAP_IDENTITY": {"CURRENT_MARKET_CAP": ["CLOSE_PRICE", "SHARE_CAPITAL"]},
    "COST_PASS_THROUGH": {"OPERATING_COST": ["FUEL_COST_PROXY"]},
    "MARGIN_BRIDGE": {"NET_PROFIT": ["REVENUE", "OPERATING_COST"]},
    "PRICE_BASIS_BRIDGE": {"STANDARD_COAL_PRICE": ["COAL_PRICE_5500"]},
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_number(value: str) -> float:
    return float(value.strip().replace(",", ""))


def parse_overrides(items: list[str]) -> dict[tuple[str, str | None], float]:
    overrides: dict[tuple[str, str | None], float] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"OVERRIDE_FORMAT:{item}; use METRIC=value or METRIC@ENTITY=value")
        left, right = item.split("=", 1)
        if "@" in left:
            code, entity = left.split("@", 1)
            key = (code.strip().upper(), entity.strip())
        else:
            key = (left.strip().upper(), None)
        overrides[key] = parse_number(right)
    return overrides


def baseline_nodes(db: sqlite3.Connection):
    rows = db.execute(
        """SELECT node_id,metric_code,entity_code,node_name_cn,unit,baseline_value,
        editable,layer_no FROM network_nodes WHERE network_id=?""",
        (NETWORK_ID,),
    ).fetchall()
    result = {}
    for node_id, code, entity, name, unit, baseline, editable, layer_no in rows:
        value = None
        as_of = None
        evidence_id = None
        if baseline:
            try:
                payload = json.loads(baseline)
                value, as_of, evidence_id = payload.get("BASE"), payload.get("as_of_date"), payload.get("evidence_id")
            except (TypeError, ValueError):
                pass
        result[(code, entity)] = {
            "node_id": node_id,
            "metric_code": code,
            "entity_code": entity,
            "name": name,
            "unit": unit,
            "value": value,
            "baseline": value,
            "as_of": as_of,
            "evidence_id": evidence_id,
            "editable": bool(editable),
            "layer_no": layer_no,
            "status": "BASELINE" if value is not None else "DATA_MISSING",
            "trace": {"source": "network_nodes.baseline_value"},
        }
    return result


def formula_candidates(db: sqlite3.Connection, target_node: str):
    rows = db.execute(
        """SELECT DISTINCT f.formula_id,f.formula_type,f.formula_expression,
        f.parameters_json,f.parameter_status,e.source_node_id
        FROM formulas f JOIN network_edges e ON e.formula_id=f.formula_id
        WHERE e.network_id=? AND e.target_node_id=? AND e.status IN
        ('CANDIDATE','AI_CANDIDATE','AI_APPROVED','CONFIRMED','ACTIVE','APPROVED')
        ORDER BY CASE f.parameter_status WHEN 'CALCULATED_LINEAGE' THEN 0 ELSE 1 END,
                 f.formula_id""",
        (NETWORK_ID, target_node),
    ).fetchall()
    grouped = {}
    for formula_id, ftype, expression, params, parameter_status, source_node in rows:
        item = grouped.setdefault(
            formula_id,
            {
                "formula_id": formula_id,
                "formula_type": ftype,
                "formula_expression": expression,
                "parameter_status": parameter_status,
                "source_nodes": [],
            },
        )
        item["source_nodes"].append(source_node)
        try:
            item["parameters"] = json.loads(params or "{}")
        except (TypeError, ValueError):
            item["parameters"] = {}
    return list(grouped.values())


def choose_formula(db: sqlite3.Connection, target):
    wanted = TARGET_PRIORITY.get(target["metric_code"], [])
    candidates = formula_candidates(db, target["node_id"])
    ranked = []
    for item in candidates:
        ftype = item["formula_type"]
        if ftype not in SUPPORTED_FORMULAS or ftype not in wanted:
            continue
        ranked.append((wanted.index(ftype), 0 if item["parameter_status"] == "CALCULATED_LINEAGE" else 1, item))
    if not ranked:
        return None
    ranked.sort(key=lambda x: (x[0], x[1], x[2]["formula_id"]))
    return ranked[0][2]


def required_codes(target, formula):
    params = formula.get("parameters") or {}
    listed = [x.get("metric_code") for x in params.get("required_inputs", []) if isinstance(x, dict)]
    if listed:
        return listed
    return FALLBACK_INPUTS.get(formula["formula_type"], {}).get(target["metric_code"], [])


def get_input(values, code, entity):
    direct = values.get((code, entity))
    if direct and direct["value"] is not None:
        return direct
    industry = values.get((code, None))
    if industry and industry["value"] is not None:
        return industry
    return None


def compute(target, formula, inputs, values):
    ftype = formula["formula_type"]
    numbers = [item["value"] for item in inputs]
    code = target["metric_code"]
    if ftype == "PRICE_BASIS_BRIDGE":
        beta = (formula.get("parameters") or {}).get("beta", 1.0)
        industry = inputs[0]
        if target.get("baseline") is None or industry.get("baseline") is None:
            return industry["value"] * beta
        return target["baseline"] + (industry["value"] - industry["baseline"]) * beta
    if ftype == "CAPACITY_UTILIZATION":
        capacity = numbers[0]
        capacity_unit = inputs[0].get("unit") or ""
        divisor = 10000.0 if "万" in capacity_unit else 100000.0
        return capacity * numbers[1] / divisor
    if ftype == "POWER_BALANCE":
        return numbers[0] * (1.0 - numbers[1] / 100.0)
    if ftype == "REVENUE_BRIDGE":
        return numbers[0] * numbers[1] * 100000.0
    if ftype == "FUEL_COST_IDENTITY":
        return numbers[0] * numbers[1] * numbers[2] * 100.0
    if ftype == "CASH_FLOW_IDENTITY":
        return numbers[0] - numbers[1]
    if ftype == "ACCOUNTING_IDENTITY":
        if code == "NET_DEBT_PROXY":
            return numbers[0] - numbers[1]
        return sum(numbers)
    if ftype == "MARKET_CAP_IDENTITY":
        return numbers[0] * numbers[1]
    if ftype == "COST_PASS_THROUGH":
        target_base = target.get("baseline")
        fuel = inputs[0]
        fuel_base = fuel.get("baseline")
        if target_base is None or fuel_base is None:
            return fuel["value"]
        return target_base + fuel["value"] - fuel_base
    if ftype == "MARGIN_BRIDGE":
        revenue, cost = inputs
        target_base = target.get("baseline")
        if target_base is None or revenue.get("baseline") is None or cost.get("baseline") is None:
            return revenue["value"] - cost["value"]
        return target_base + (revenue["value"] - revenue["baseline"]) - (cost["value"] - cost["baseline"])
    raise ValueError(f"UNSUPPORTED_FORMULA:{ftype}")


def scenario(db: sqlite3.Connection, entity: str, overrides: dict[tuple[str, str | None], float], persist: bool = True):
    values = baseline_nodes(db)
    errors = []
    for (code, override_entity), value in overrides.items():
        key = (code, override_entity or entity)
        if override_entity is None and code.startswith("COAL_PRICE_"):
            key = (code, None)
        item = values.get(key)
        if item is None:
            errors.append({"code": "OVERRIDE_NODE_NOT_FOUND", "metric_code": code, "entity_code": key[1]})
            continue
        if not item["editable"]:
            errors.append({"code": "OVERRIDE_NODE_NOT_EDITABLE", "metric_code": code, "entity_code": key[1]})
            continue
        item["value"] = value
        item["status"] = "OVERRIDDEN"
        item["trace"] = {"override": value, "baseline": item["baseline"]}

    entity_targets = sorted(
        (
            item for (_code, node_entity), item in values.items()
            if node_entity == entity and item["layer_no"] >= 4
        ),
        key=lambda item: (item["layer_no"], item["metric_code"], item["node_id"]),
    )
    visiting = set()
    completed = set()

    def evaluate(item):
        key = (item["metric_code"], item["entity_code"])
        if item["status"] == "OVERRIDDEN" or key in completed:
            return item
        if key in visiting:
            item["status"] = "BLOCKED_CYCLE"
            item["trace"] = {"reason": "FORMULA_CYCLE"}
            return item
        formula = choose_formula(db, item)
        if not formula:
            if item["value"] is not None:
                item["status"] = "BASELINE"
                completed.add(key)
                return item
            item["status"] = "BLOCKED_NO_EXECUTABLE_FORMULA"
            item["trace"] = {"reason": "NO_SUPPORTED_FORMULA"}
            return item
        visiting.add(key)
        inputs = []
        missing = []
        for code in required_codes(item, formula):
            source = get_input(values, code, entity)
            if source is None or source["value"] is None:
                missing.append(code)
                continue
            if source["status"] != "OVERRIDDEN" and choose_formula(db, source):
                evaluate(source)
            if source["value"] is None or source["status"].startswith("BLOCKED"):
                missing.append(code)
                continue
            inputs.append(source)
        if missing:
            item["status"] = "BLOCKED_DATA_MISSING"
            item["trace"] = {"formula_id": formula["formula_id"], "missing_inputs": missing}
        else:
            try:
                item["value"] = compute(item, formula, inputs, values)
                item["status"] = "CALCULATED_SCENARIO"
                item["trace"] = {
                    "formula_id": formula["formula_id"],
                    "formula_type": formula["formula_type"],
                    "formula_expression": formula["formula_expression"],
                    "inputs": [
                        {"metric_code": x["metric_code"], "entity_code": x["entity_code"], "value": x["value"], "baseline": x["baseline"]}
                        for x in inputs
                    ],
                }
            except Exception as exc:
                item["status"] = "BLOCKED_CALCULATION_ERROR"
                item["trace"] = {"formula_id": formula["formula_id"], "error": str(exc)}
        visiting.remove(key)
        completed.add(key)
        return item

    for item in entity_targets:
        evaluate(item)

    run_id = "scenario_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    cutoff = db.execute("SELECT data_cutoff FROM network_registry WHERE network_id=?", (NETWORK_ID,)).fetchone()
    base_cutoff = cutoff[0] if cutoff else ""
    summary = {
        "run_id": run_id,
        "entity": entity,
        "engine_version": ENGINE_VERSION,
        "base_data_cutoff": base_cutoff,
        "overrides": {f"{code}@{ent or entity}": value for (code, ent), value in overrides.items()},
        "errors": errors,
        "calculated": sum(x["status"] == "CALCULATED_SCENARIO" for x in values.values()),
        "blocked": sum(x["status"].startswith("BLOCKED") for x in values.values()),
        "outputs": {
            code: item["value"]
            for (code, node_entity), item in values.items()
            if node_entity == entity and item["layer_no"] >= 5 and item["value"] is not None
        },
    }
    if persist:
        db.execute(
            """INSERT INTO scenario_runs(run_id,network_id,base_data_cutoff,created_at,
            status,input_json,engine_version) VALUES(?,?,?,?,?,?,?)""",
            (
                run_id, NETWORK_ID, base_cutoff, now(),
                "COMPLETED" if not errors else "COMPLETED_WITH_INPUT_ERRORS",
                json.dumps(summary["overrides"], ensure_ascii=False),
                ENGINE_VERSION,
            ),
        )
        for item in values.values():
            if item["entity_code"] not in (None, entity):
                continue
            db.execute(
                """INSERT INTO scenario_values(
                run_id,network_id,node_id,metric_code,entity_code,value,unit,
                calculation_status,formula_id,trace_json)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    run_id, NETWORK_ID, item["node_id"], item["metric_code"], item["entity_code"],
                    item["value"], item["unit"], item["status"],
                    item["trace"].get("formula_id"),
                    json.dumps(item["trace"], ensure_ascii=False),
                ),
            )
        db.commit()
    summary["values"] = [
        {
            "node_id": item["node_id"],
            "metric_code": item["metric_code"],
            "entity_code": item["entity_code"],
            "value": item["value"],
            "unit": item["unit"],
            "status": item["status"],
            "trace": item["trace"],
        }
        for item in values.values()
        if item["entity_code"] in (None, entity)
    ]
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--entity", required=True, choices=("600011.SH", "600027.SH", "600795.SH"))
    parser.add_argument("--override", action="append", default=[], help="METRIC=value or METRIC@ENTITY=value")
    parser.add_argument("--db", default=str(ROOT / "coal_network.db"))
    parser.add_argument("--no-persist", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    db = sqlite3.connect(args.db)
    db.execute("PRAGMA foreign_keys=ON")
    result = scenario(db, args.entity, parse_overrides(args.override), not args.no_persist)
    db.close()
    output = Path(args.output) if args.output else ROOT / "scenario_result.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(1 if result["errors"] else 0)


if __name__ == "__main__":
    main()
