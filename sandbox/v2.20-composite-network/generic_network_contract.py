from __future__ import annotations

"""Role-aware contract for user supplied financial network packages."""

from dataclasses import dataclass
from typing import Any


ROLE_REQUIREMENTS: dict[str, tuple[tuple[str, ...], ...]] = {
    "REGISTRY": (("NETWORK_ID",), ("NETWORK_NAME",)),
    "LAYERS": (("NETWORK_ID",), ("NETWORK_LAYER_NO",), ("NETWORK_LAYER_NAME",)),
    "NODES": (("NETWORK_ID",), ("NETWORK_NODE_ID",), ("NETWORK_NODE_LAYER",), ("NETWORK_NODE_LABEL",)),
    "EDGES": (("NETWORK_ID",), ("NETWORK_EDGE_SOURCE",), ("NETWORK_EDGE_TARGET",)),
    "FORMULAS": (("NETWORK_ID",), ("FORMULA_ID",), ("FORMULA_TYPE",)),
    "EVIDENCE": (("EVIDENCE_ID",),),
    "METRIC_VALUES": (("NETWORK_ID",), ("METRIC_CODE",), ("METRIC_VALUE",), ("AS_OF_DATE", "REPORT_PERIOD")),
    "FINANCIALS": (("ENTITY_CODE",), ("REPORT_PERIOD",), ("ANNOUNCEMENT_DATE", "OPDATE")),
    "VALUATION": (("ENTITY_CODE",), ("VALUATION_DATE", "AS_OF_DATE")),
    "METRICS": (("ENTITY_CODE",), ("REPORT_PERIOD",), ("ANNOUNCEMENT_DATE", "OPDATE")),
}


STRUCTURAL_ROLES = {"REGISTRY", "LAYERS", "NODES", "EDGES", "FORMULAS", "EVIDENCE"}


def role_missing(role: str, codes: set[str]) -> list[str]:
    groups = ROLE_REQUIREMENTS.get(role, ())
    return ["/".join(group) for group in groups if not any(code in codes for code in group)]


def role_status(role: str, codes: set[str]) -> tuple[str, list[str]]:
    if role == "UNKNOWN":
        return "NEEDS_MAPPING", []
    missing = role_missing(role, codes)
    return ("INCOMPLETE", missing) if missing else ("READY", [])


def parse_json_object(value: Any) -> dict[str, Any]:
    import json

    if isinstance(value, dict):
        return value
    if value in (None, ""):
        return {}
    parsed = json.loads(str(value))
    if not isinstance(parsed, dict):
        raise ValueError("JSON_OBJECT_REQUIRED")
    return parsed


def normalized_direction(value: Any) -> str:
    raw = str(value or "positive").strip().lower()
    if raw in {"-1", "negative", "inverse", "负", "负向"}:
        return "negative"
    if raw in {"1", "+1", "positive", "direct", "正", "正向"}:
        return "positive"
    return "mixed"


SUPPORTED_FORMULAS = {
    "ADD",
    "SUBTRACT",
    "MULTIPLY",
    "DIVIDE",
    "IDENTITY",
    "PERCENT_CHANGE",
    "MIN",
    "MAX",
    "CLAMP",
    "LAG",
    "LINEAR_WEIGHT",
    "PRICE_VOLUME",
    "REVENUE_BRIDGE",
    "MARGIN_BRIDGE",
    "CAPACITY_UTILIZATION",
    "INVENTORY_FLOW",
    "WORKING_CAPITAL",
    "DCF",
    "PE_MULTIPLE",
    "EV_EBITDA",
    "ACCOUNTING_IDENTITY",
    "CASH_FLOW_IDENTITY",
    "MARKET_CAP_IDENTITY",
    "EV_EQUITY_BRIDGE",
    "PRICE_BASIS_BRIDGE",
    "POWER_BALANCE",
    "FUEL_COST_IDENTITY",
    "FUEL_COST_BRIDGE",
    "COST_PASS_THROUGH",
}


# Source databases may use domain-specific formula names. They are metadata,
# not executable code. Resolve them to a small deterministic formula registry.
FORMULA_ALIASES = {
    "DEMAND_BRIDGE": "LINEAR_WEIGHT",
    "DEMAND_EXPOSURE": "LINEAR_WEIGHT",
    "MARKET_SHARE_BRIDGE": "MULTIPLY",
    "MATERIAL_COST_BRIDGE": "COST_PASS_THROUGH",
    "BATTERY_COST_BRIDGE": "MULTIPLY",
    "BATTERY_DEMAND_BRIDGE": "MULTIPLY",
    "PROFIT_BRIDGE": "MARGIN_BRIDGE",
    "VALUATION_BRIDGE": "PE_MULTIPLE",
    "OPERATING_IDENTITY": "IDENTITY",
    "FINANCIAL_BRIDGE": "LINEAR_WEIGHT",
}


def normalize_formula_type(value: Any, expression: Any = None) -> tuple[str | None, str]:
    """Return a safe registry formula and the resolution method.

    Unknown formula names are never executed. A conservative token classifier
    handles future domain aliases; unresolved formulas are quarantined locally.
    """
    raw = str(value or "").strip().upper()
    if not raw:
        return "LINEAR_WEIGHT", "DEFAULT"
    if raw in SUPPORTED_FORMULAS:
        return raw, "DIRECT"
    if raw in FORMULA_ALIASES:
        return FORMULA_ALIASES[raw], "ALIAS"

    text = f"{raw} {str(expression or '').upper()}"
    if any(token in text for token in ("SUBTRACT", "MINUS", "DEDUCT", "NET_DEBT", "FREE_CASH_FLOW")):
        return "SUBTRACT", "TOKEN_INFERENCE"
    if any(token in text for token in ("MULTIPLY", "PRODUCT", "PRICE_VOLUME", "MARKET_SHARE", "UNIT_COST", "INSTALLATION")):
        return "MULTIPLY", "TOKEN_INFERENCE"
    if any(token in text for token in ("DIVIDE", "RATIO", "PER_UNIT")):
        return "DIVIDE", "TOKEN_INFERENCE"
    if any(token in text for token in ("VALUATION", "MARKET_CAP", "MULTIPLE", "PRICE_EARNINGS")):
        return "PE_MULTIPLE", "TOKEN_INFERENCE"
    if any(token in text for token in ("MARGIN", "PROFIT")):
        return "MARGIN_BRIDGE", "TOKEN_INFERENCE"
    if any(token in text for token in ("COST", "PASS_THROUGH", "MATERIAL")):
        return "COST_PASS_THROUGH", "TOKEN_INFERENCE"
    if any(token in text for token in ("IDENTITY", "ACCOUNTING")):
        return "ACCOUNTING_IDENTITY", "TOKEN_INFERENCE"
    if any(token in text for token in ("BRIDGE", "EXPOSURE", "DEMAND", "ELASTICITY", "SENSITIVITY")):
        return "LINEAR_WEIGHT", "TOKEN_INFERENCE"
    return None, "FORMULA_NEEDS_REVIEW"
