"""Deterministic scenario engine for the NEV V1 network."""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from contract_v1 import COMPANIES, METRICS, NETWORK_ID
from initialize import DEFAULT_DB, initialize

ENGINE_VERSION = "nev-scenario-v1"


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def _baseline(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return _number(value, "baseline_value")
    except ValueError:
        return None


def run_scenario(
    db_path: Path,
    entity_code: str,
    inputs: dict[str, Any],
    parameters: dict[str, Any] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    if entity_code not in COMPANIES:
        raise ValueError(f"unknown entity_code: {entity_code}")
    initialize(db_path)
    parameters = parameters or {}
    clean_inputs = {code: _number(value, f"inputs.{code}") for code, value in inputs.items()}
    unknown = sorted(set(clean_inputs) - set(METRICS))
    if unknown:
        raise ValueError(f"unknown metrics: {unknown}")
    clean_params = {key: _number(value, f"parameters.{key}") for key, value in parameters.items()}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT node_id,metric_code,unit,baseline_value,value_status,entity_code
           FROM network_nodes
           WHERE network_id=? AND (entity_code IS NULL OR entity_code=?)""",
        (NETWORK_ID, entity_code),
    ).fetchall()
    state: dict[str, dict[str, Any]] = {}
    for row in rows:
        state[row["metric_code"]] = {
            "node_id": row["node_id"],
            "unit": row["unit"],
            "value": _baseline(row["baseline_value"]),
            "calculation_status": "BASELINE" if _baseline(row["baseline_value"]) is not None else "DATA_MISSING",
            "formula_id": None,
            "trace": {"source": "network_nodes.baseline_value"} if row["baseline_value"] is not None else {},
        }
    for code, value in clean_inputs.items():
        if code not in state:
            raise ValueError(f"metric {code} is outside entity scenario scope")
        state[code].update(
            value=value,
            calculation_status="USER_INPUT",
            formula_id=None,
            trace={"source": "explicit_scenario_input", "not_source_fact": True},
        )

    def value(code: str) -> float | None:
        item = state.get(code)
        return None if item is None else item["value"]

    def formula_id(target: str, formula_type: str) -> str | None:
        target_node = state[target]["node_id"]
        row = conn.execute(
            """SELECT formula_id FROM network_edges
               WHERE network_id=? AND target_node_id=? AND formula_type=?
               ORDER BY edge_id LIMIT 1""",
            (NETWORK_ID, target_node, formula_type),
        ).fetchone()
        return row[0] if row else None

    def calculate(
        target: str,
        result: float,
        formula_type: str,
        required: list[str],
        used_parameters: list[str] | None = None,
    ) -> bool:
        if target in clean_inputs:
            return False
        if not math.isfinite(result):
            raise ValueError(f"non-finite calculation for {target}")
        parameter_status = "AI_ASSUMPTION" if used_parameters else "CALCULATED_LINEAGE"
        state[target].update(
            value=result,
            calculation_status="CALCULATED",
            formula_id=formula_id(target, formula_type),
            trace={
                "formula_type": formula_type,
                "inputs": {code: value(code) for code in required},
                "parameters": {key: clean_params[key] for key in used_parameters or []},
                "parameter_status": parameter_status,
                "causal_conclusion": "ABSTAIN",
            },
        )
        return True

    # Layer 1: demand inputs can derive industry sales only when the target was not supplied.
    if "NEV_INDUSTRY_SALES" not in clean_inputs:
        if value("NEV_PENETRATION_RATE") is not None and "demand_beta" in clean_params:
            calculate("NEV_INDUSTRY_SALES", value("NEV_PENETRATION_RATE") * clean_params["demand_beta"],
                      "DEMAND_BRIDGE", ["NEV_PENETRATION_RATE"], ["demand_beta"])
        elif value("CHARGING_PILES") is not None and "charging_beta" in clean_params:
            calculate("NEV_INDUSTRY_SALES", value("CHARGING_PILES") * clean_params["charging_beta"],
                      "DEMAND_BRIDGE", ["CHARGING_PILES"], ["charging_beta"])

    # Layers 2-4: material cost and company operating bridge.
    if value("NEV_INDUSTRY_SALES") is not None and "market_share" in clean_params:
        calculate("COMPANY_NEV_SALES", value("NEV_INDUSTRY_SALES") * clean_params["market_share"],
                  "MARKET_SHARE_BRIDGE", ["NEV_INDUSTRY_SALES"], ["market_share"])
    if value("LITHIUM_CARBONATE_PRICE") is not None and "material_coefficient" in clean_params:
        calculate("BATTERY_UNIT_COST_PROXY", value("LITHIUM_CARBONATE_PRICE") * clean_params["material_coefficient"],
                  "MATERIAL_COST_BRIDGE", ["LITHIUM_CARBONATE_PRICE"], ["material_coefficient"])
    if value("BATTERY_UNIT_COST_PROXY") is not None and value("BATTERY_KWH_PER_VEHICLE") is not None:
        calculate("VEHICLE_UNIT_COST_PROXY", value("BATTERY_UNIT_COST_PROXY") * value("BATTERY_KWH_PER_VEHICLE"),
                  "BATTERY_COST_BRIDGE", ["BATTERY_UNIT_COST_PROXY", "BATTERY_KWH_PER_VEHICLE"])

    # Layer 5: exact operating and accounting identities.
    if value("COMPANY_NEV_SALES") is not None and value("ASP_PROXY") is not None:
        calculate("VEHICLE_REVENUE_PROXY", value("COMPANY_NEV_SALES") * value("ASP_PROXY"),
                  "MULTIPLY", ["COMPANY_NEV_SALES", "ASP_PROXY"])
    if value("COMPANY_NEV_SALES") is not None and value("VEHICLE_UNIT_COST_PROXY") is not None:
        calculate("VEHICLE_COST_PROXY", value("COMPANY_NEV_SALES") * value("VEHICLE_UNIT_COST_PROXY"),
                  "MULTIPLY", ["COMPANY_NEV_SALES", "VEHICLE_UNIT_COST_PROXY"])
    if value("VEHICLE_REVENUE_PROXY") is not None and value("VEHICLE_COST_PROXY") is not None:
        calculate("GROSS_PROFIT_PROXY", value("VEHICLE_REVENUE_PROXY") - value("VEHICLE_COST_PROXY"),
                  "SUBTRACT", ["VEHICLE_REVENUE_PROXY", "VEHICLE_COST_PROXY"])
    if value("GROSS_PROFIT_PROXY") is not None and "profit_conversion_ratio" in clean_params:
        calculate("NET_PROFIT", value("GROSS_PROFIT_PROXY") * clean_params["profit_conversion_ratio"],
                  "PROFIT_BRIDGE", ["GROSS_PROFIT_PROXY"], ["profit_conversion_ratio"])
    if value("OPERATING_CASH_FLOW") is not None and value("CAPEX") is not None:
        calculate("FREE_CASH_FLOW_PROXY", value("OPERATING_CASH_FLOW") - value("CAPEX"),
                  "SUBTRACT", ["OPERATING_CASH_FLOW", "CAPEX"])
    if value("DEBT_COMPONENTS") is not None and value("CASH") is not None:
        calculate("NET_DEBT_PROXY", value("DEBT_COMPONENTS") - value("CASH"),
                  "SUBTRACT", ["DEBT_COMPONENTS", "CASH"])

    # Layer 6: exact market identity has priority, otherwise use one explicit valuation assumption.
    if "CURRENT_MARKET_CAP" not in clean_inputs:
        if value("NET_PROFIT") is not None and "valuation_multiple" in clean_params:
            calculate("CURRENT_MARKET_CAP", value("NET_PROFIT") * clean_params["valuation_multiple"],
                      "VALUATION_BRIDGE", ["NET_PROFIT"], ["valuation_multiple"])
        elif value("FREE_CASH_FLOW_PROXY") is not None and "fcf_multiple" in clean_params:
            calculate("CURRENT_MARKET_CAP", value("FREE_CASH_FLOW_PROXY") * clean_params["fcf_multiple"],
                      "VALUATION_BRIDGE", ["FREE_CASH_FLOW_PROXY"], ["fcf_multiple"])
        elif value("CLOSE_PRICE") is not None and value("SHARE_CAPITAL") is not None:
            calculate("CURRENT_MARKET_CAP", value("CLOSE_PRICE") * value("SHARE_CAPITAL"),
                      "MULTIPLY", ["CLOSE_PRICE", "SHARE_CAPITAL"])

    incoming = {
        row[0] for row in conn.execute(
            """SELECT DISTINCT target_node_id FROM network_edges
               WHERE network_id=? AND target_node_id IN
                 (SELECT node_id FROM network_nodes WHERE network_id=? AND (entity_code IS NULL OR entity_code=?))""",
            (NETWORK_ID, NETWORK_ID, entity_code),
        )
    }
    for code, item in state.items():
        if item["value"] is None and item["node_id"] in incoming:
            item["calculation_status"] = "BLOCKED_DATA_MISSING"
            item["trace"] = {"reason": "required input or explicit AI parameter is missing", "causal_conclusion": "ABSTAIN"}

    run_id = f"nev::{entity_code}::{uuid.uuid4().hex}"
    blocked = sum(item["calculation_status"] == "BLOCKED_DATA_MISSING" for item in state.values())
    calculated = sum(item["calculation_status"] == "CALCULATED" for item in state.values())
    run_status = "COMPLETE" if blocked == 0 else "COMPLETE_WITH_BLOCKED"
    if persist:
        with conn:
            conn.execute(
                """INSERT INTO scenario_runs
                   (run_id,network_id,entity_code,created_at,status,input_json,engine_version)
                   VALUES (?,?,?,?,?,?,?)""",
                (run_id, NETWORK_ID, entity_code, datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 run_status, json.dumps({"inputs": clean_inputs, "parameters": clean_params},
                                        ensure_ascii=False, sort_keys=True), ENGINE_VERSION),
            )
            for code, item in state.items():
                conn.execute(
                    """INSERT INTO scenario_values
                       (run_id,network_id,node_id,metric_code,entity_code,value,unit,
                        calculation_status,formula_id,trace_json)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (run_id, NETWORK_ID, item["node_id"], code,
                     entity_code if METRICS[code][4] == "COMPANY" else None,
                     item["value"], item["unit"], item["calculation_status"],
                     item["formula_id"], json.dumps(item["trace"], ensure_ascii=False, sort_keys=True)),
                )
    conn.close()
    return {
        "run_id": run_id,
        "status": run_status,
        "entity_code": entity_code,
        "calculated_count": calculated,
        "blocked_count": blocked,
        "values": {code: item["value"] for code, item in state.items()},
        "statuses": {code: item["calculation_status"] for code, item in state.items()},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--entity", required=True, choices=sorted(COMPANIES))
    parser.add_argument("--inputs", default="{}")
    parser.add_argument("--parameters", default="{}")
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args()
    result = run_scenario(
        args.db, args.entity, json.loads(args.inputs), json.loads(args.parameters),
        persist=not args.no_persist,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
