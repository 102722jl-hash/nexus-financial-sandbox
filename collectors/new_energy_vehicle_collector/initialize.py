"""Initialize the independent NEV database and its immutable network blueprint."""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from contract_v1 import COMPANIES, LAYERS, METRICS, NETWORK_ID, TEMPLATES, VERSION

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "new_energy_vehicle.db"
SCHEMA = ROOT / "schema.sql"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def node_id(metric_code: str, entity_code: str | None = None) -> str:
    if entity_code:
        return f"company::{entity_code}::{metric_code}"
    return f"industry::{metric_code}"


def metric_node(metric_code: str, entity_code: str | None) -> str:
    scope = METRICS[metric_code][4]
    return node_id(metric_code, entity_code if scope == "COMPANY" else None)


def initialize(db_path: Path = DEFAULT_DB) -> dict[str, int]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    now = utc_now()
    cutoff = now[:10]

    with conn:
        conn.execute(
            """INSERT INTO network_registry
               (network_id,network_name,network_version,network_status,network_kind,data_cutoff,created_at)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(network_id) DO UPDATE SET
                 network_name=excluded.network_name,
                 network_version=excluded.network_version,
                 network_status=excluded.network_status,
                 network_kind=excluded.network_kind,
                 data_cutoff=excluded.data_cutoff""",
            (NETWORK_ID, "新能源汽车多链路传导网络", VERSION, "BLUEPRINT_READY",
             "NEW_ENERGY_VEHICLE", cutoff, now),
        )
        for layer_no, code, name, role in LAYERS:
            conn.execute(
                """INSERT INTO network_layers
                   (network_id,layer_no,layer_code,layer_name_cn,path_role,sort_order,status)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(network_id,layer_no) DO UPDATE SET
                     layer_code=excluded.layer_code,layer_name_cn=excluded.layer_name_cn,
                     path_role=excluded.path_role,sort_order=excluded.sort_order,status=excluded.status""",
                (NETWORK_ID, layer_no, code, name, role, layer_no, "ACTIVE"),
            )
        for code, name in COMPANIES.items():
            conn.execute(
                """INSERT INTO entities
                   (network_id,entity_code,entity_name_cn,entity_type,exchange_code,country,business_model,status)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(network_id,entity_code) DO UPDATE SET
                     entity_name_cn=excluded.entity_name_cn,exchange_code=excluded.exchange_code,
                     business_model=excluded.business_model,status=excluded.status""",
                (NETWORK_ID, code, name, "LISTED_COMPANY", code, "CN",
                 "新能源汽车整车制造及相关业务", "ACTIVE"),
            )
        for code, spec in METRICS.items():
            name, layer, kind, unit, scope, editable, required = spec
            conn.execute(
                """INSERT INTO metric_definitions
                   (metric_code,metric_name_cn,layer_no,metric_type,canonical_unit,entity_scope,
                    editable_default,required_for_network,description,contract_version,status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(metric_code) DO UPDATE SET
                     metric_name_cn=excluded.metric_name_cn,layer_no=excluded.layer_no,
                     metric_type=excluded.metric_type,canonical_unit=excluded.canonical_unit,
                     entity_scope=excluded.entity_scope,editable_default=excluded.editable_default,
                     required_for_network=excluded.required_for_network,
                     description=excluded.description,contract_version=excluded.contract_version,
                     status=excluded.status""",
                (code, name, layer, kind, unit, scope, editable, required,
                 f"{name}；由V1指标合同固定，不由采集器临时创建。", VERSION, "ACTIVE"),
            )
        for template in TEMPLATES:
            tid, source, target, scope, formula_type, expression, required, relation, parameter = template
            conn.execute(
                """INSERT INTO edge_templates
                   (template_id,source_metric_code,target_metric_code,scope,formula_type,
                    formula_expression,required_inputs_json,relation_type,parameter_status,
                    mechanism,contract_version,status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(template_id) DO UPDATE SET
                     source_metric_code=excluded.source_metric_code,
                     target_metric_code=excluded.target_metric_code,scope=excluded.scope,
                     formula_type=excluded.formula_type,formula_expression=excluded.formula_expression,
                     required_inputs_json=excluded.required_inputs_json,
                     relation_type=excluded.relation_type,parameter_status=excluded.parameter_status,
                     mechanism=excluded.mechanism,contract_version=excluded.contract_version,
                     status=excluded.status""",
                (tid, source, target, scope, formula_type, expression,
                 json.dumps(required, ensure_ascii=False), relation, parameter,
                 f"{METRICS[source][0]} → {METRICS[target][0]}", VERSION, "ACTIVE"),
            )

        _upsert_nodes(conn, cutoff)
        _rebuild_edges(conn)

    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(f"foreign key violations: {violations}")
    counts = {
        "layers": conn.execute("SELECT count(*) FROM network_layers WHERE network_id=?", (NETWORK_ID,)).fetchone()[0],
        "entities": conn.execute("SELECT count(*) FROM entities WHERE network_id=?", (NETWORK_ID,)).fetchone()[0],
        "metrics": conn.execute("SELECT count(*) FROM metric_definitions").fetchone()[0],
        "nodes": conn.execute("SELECT count(*) FROM network_nodes WHERE network_id=?", (NETWORK_ID,)).fetchone()[0],
        "edges": conn.execute("SELECT count(*) FROM network_edges WHERE network_id=?", (NETWORK_ID,)).fetchone()[0],
    }
    conn.close()
    return counts


def _upsert_nodes(conn: sqlite3.Connection, cutoff: str) -> None:
    for metric_code, spec in METRICS.items():
        name, layer, kind, unit, scope, editable, _required = spec
        entities = [None] if scope == "INDUSTRY" else list(COMPANIES)
        for entity_code in entities:
            nid = node_id(metric_code, entity_code)
            display = name if entity_code is None else f"{COMPANIES[entity_code]}｜{name}"
            conn.execute(
                """INSERT INTO network_nodes
                   (network_id,node_id,layer_no,node_name_cn,node_type,metric_code,metric_name,
                    metric_type,unit,baseline_value,editable,value_status,entity_code,evidence_id,
                    data_cutoff,status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(network_id,node_id) DO UPDATE SET
                     layer_no=excluded.layer_no,node_name_cn=excluded.node_name_cn,
                     node_type=excluded.node_type,metric_code=excluded.metric_code,
                     metric_name=excluded.metric_name,metric_type=excluded.metric_type,
                     unit=excluded.unit,editable=excluded.editable,data_cutoff=excluded.data_cutoff,
                     status=excluded.status""",
                (NETWORK_ID, nid, layer, display, scope, metric_code, name, kind, unit,
                 None, editable, "DATA_MISSING", entity_code, None, cutoff, "ACTIVE"),
            )


def _rebuild_edges(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM network_edges WHERE network_id=?", (NETWORK_ID,))
    conn.execute("DELETE FROM formulas WHERE network_id=?", (NETWORK_ID,))
    for template in TEMPLATES:
        tid, source, target, scope, formula_type, expression, _required, relation, parameter = template
        instances = [None] if scope == "INDUSTRY" else list(COMPANIES)
        for entity_code in instances:
            suffix = entity_code or "INDUSTRY"
            formula_id = f"formula::{tid}::{suffix}"
            edge_id = f"edge::{tid}::{suffix}"
            source_id = metric_node(source, entity_code)
            target_id = metric_node(target, entity_code)
            conn.execute(
                """INSERT INTO formulas
                   (network_id,formula_id,template_id,formula_type,formula_expression,
                    parameters_json,parameter_status,causal_conclusion,status)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (NETWORK_ID, formula_id, tid, formula_type, expression, "{}", parameter,
                 "ABSTAIN", "ACTIVE"),
            )
            conn.execute(
                """INSERT INTO network_edges
                   (network_id,edge_id,template_id,source_node_id,target_node_id,direction,
                    relation_type,formula_id,formula_type,parameter_status,confidence,
                    mechanism,parameters_json,status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (NETWORK_ID, edge_id, tid, source_id, target_id, "FORWARD", relation,
                 formula_id, formula_type, parameter, 1.0 if parameter == "CALCULATED_LINEAGE" else 0.35,
                 f"{METRICS[source][0]} → {METRICS[target][0]}", "{}", "AI_APPROVED"),
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    print(json.dumps(initialize(args.db), ensure_ascii=False, indent=2))
