"""Transactional SQLite-to-PostgreSQL sync for the independent NEV network."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path

import psycopg
from psycopg import sql

from contract_v1 import NETWORK_ID
from initialize import DEFAULT_DB

TABLES = [
    "network_registry", "network_layers", "entities", "metric_definitions",
    "edge_templates", "raw_documents", "evidence", "metric_values", "formulas",
    "network_nodes", "network_edges", "quarantine", "announcement_catalogue",
    "discovery_runs", "scenario_runs", "scenario_values",
]


def pg_type(declared: str | None) -> str:
    value = (declared or "").upper()
    if "INT" in value:
        return "BIGINT"
    if any(token in value for token in ("REAL", "DOUBLE", "FLOAT")):
        return "DOUBLE PRECISION"
    return "TEXT"


def metadata(connection: sqlite3.Connection, table: str):
    info = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    if not info:
        raise RuntimeError(f"SQLITE_TABLE_MISSING:{table}")
    names = [row[1] for row in info]
    definitions = []
    for _cid, name, declared, notnull, _default, _pk in info:
        definition = sql.SQL("{} {}").format(sql.Identifier(name), sql.SQL(pg_type(declared)))
        if notnull:
            definition += sql.SQL(" NOT NULL")
        definitions.append(definition)
    primary = [row[1] for row in info if row[5]]
    if primary:
        definitions.append(
            sql.SQL("PRIMARY KEY ({})").format(
                sql.SQL(",").join(sql.Identifier(name) for name in primary)
            )
        )
    return names, definitions, primary


def create_published_views(cursor, schema: str, readonly_user: str) -> None:
    target = sql.Identifier(schema)
    views = {
        "published_networks": sql.SQL(
            "SELECT network_id,network_name,network_version,network_status,network_kind,data_cutoff,created_at "
            "FROM {}.network_registry"
        ).format(target),
        "published_layers": sql.SQL(
            "SELECT network_id,layer_no,layer_code,layer_name_cn,path_role,sort_order,status "
            "FROM {}.network_layers WHERE status='ACTIVE'"
        ).format(target),
        "published_nodes": sql.SQL(
            "SELECT network_id,node_id,layer_no,node_name_cn,node_type,metric_code,metric_name,metric_type,unit,"
            "baseline_value,editable,value_status,entity_code,evidence_id,data_cutoff,status "
            "FROM {}.network_nodes WHERE status='ACTIVE'"
        ).format(target),
        "published_edges": sql.SQL(
            "SELECT e.network_id,e.edge_id,e.template_id,e.source_node_id,e.target_node_id,e.direction,"
            "e.relation_type,e.formula_id,e.formula_type,e.parameter_status,e.confidence,e.mechanism,"
            "e.parameters_json,e.status FROM {}.network_edges e "
            "JOIN {}.network_nodes s ON s.network_id=e.network_id AND s.node_id=e.source_node_id AND s.status='ACTIVE' "
            "JOIN {}.network_nodes t ON t.network_id=e.network_id AND t.node_id=e.target_node_id AND t.status='ACTIVE' "
            "JOIN {}.formulas f ON f.formula_id=e.formula_id AND f.status='ACTIVE' "
            "WHERE e.status='AI_APPROVED'"
        ).format(target, target, target, target),
        "published_metric_values": sql.SQL(
            "SELECT v.network_id,v.metric_value_id,v.metric_code,v.entity_code,v.value,v.unit,v.currency,"
            "v.report_period,v.published_at,v.as_of_date,v.data_cutoff,v.value_status,v.evidence_id,"
            "v.source_table,v.source_row_key FROM {}.metric_values v "
            "JOIN {}.evidence e ON e.evidence_id=v.evidence_id "
            "WHERE e.acceptance_status IN ('ACCEPTED','AI_APPROVED')"
        ).format(target, target),
        "published_evidence": sql.SQL(
            "SELECT e.evidence_id,e.source_type,e.source_name,e.publisher,e.published_at,e.retrieved_at,"
            "e.original_quote,e.locator,e.source_url,e.anchor_at,e.data_cutoff,e.source_tier,e.temporal_role,"
            "e.snapshot_sha256,e.supports_node_ids,e.acceptance_status,e.acceptance_reason "
            "FROM {}.evidence e WHERE e.acceptance_status IN ('ACCEPTED','AI_APPROVED') AND "
            "(EXISTS (SELECT 1 FROM {}.network_nodes n WHERE n.evidence_id=e.evidence_id AND n.status='ACTIVE') "
            "OR EXISTS (SELECT 1 FROM {}.metric_values v WHERE v.evidence_id=e.evidence_id))"
        ).format(target, target, target),
    }
    for name, query in views.items():
        cursor.execute(
            sql.SQL("CREATE OR REPLACE VIEW {}.{} AS ").format(target, sql.Identifier(name)) + query
        )
    cursor.execute(
        sql.SQL("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA {} FROM {}").format(
            target, sql.Identifier(readonly_user)
        )
    )
    cursor.execute(
        sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
            target, sql.Identifier(readonly_user)
        )
    )
    cursor.execute(
        sql.SQL("GRANT SELECT ON {} TO {}").format(
            sql.SQL(",").join(
                sql.SQL("{}.{}").format(target, sql.Identifier(name)) for name in views
            ),
            sql.Identifier(readonly_user),
        )
    )


def sync(args) -> dict:
    password = os.environ.get(args.password_env)
    if not password:
        raise ValueError(f"missing environment variable: {args.password_env}")
    local = sqlite3.connect(args.sqlite)
    remote = psycopg.connect(
        host=args.host, port=args.port, dbname=args.database, user=args.user,
        password=password, sslmode="prefer", connect_timeout=10,
    )
    try:
        with remote.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM information_schema.schemata WHERE schema_name=%s",
                (args.schema,),
            )
            if not cursor.fetchone():
                raise RuntimeError("TARGET_SCHEMA_MISSING")
            for table in TABLES:
                names, definitions, _primary = metadata(local, table)
                cursor.execute(
                    sql.SQL("CREATE TABLE IF NOT EXISTS {}.{} ({})").format(
                        sql.Identifier(args.schema), sql.Identifier(table),
                        sql.SQL(",").join(definitions),
                    )
                )
            counts = {}
            for table in TABLES:
                names, _definitions, primary = metadata(local, table)
                rows = local.execute(f'SELECT * FROM "{table}"').fetchall()
                counts[table] = len(rows)
                if rows:
                    mutable = [name for name in names if name not in primary]
                    if mutable:
                        conflict_action = sql.SQL("DO UPDATE SET {} ").format(
                            sql.SQL(",").join(
                                sql.SQL("{}=EXCLUDED.{}").format(
                                    sql.Identifier(name), sql.Identifier(name)
                                ) for name in mutable
                            )
                        )
                    else:
                        conflict_action = sql.SQL("DO NOTHING")
                    cursor.executemany(
                        sql.SQL("INSERT INTO {}.{} ({}) VALUES ({}) ON CONFLICT ({}) {}").format(
                            sql.Identifier(args.schema), sql.Identifier(table),
                            sql.SQL(",").join(sql.Identifier(name) for name in names),
                            sql.SQL(",").join(sql.Placeholder() for _ in names),
                            sql.SQL(",").join(sql.Identifier(name) for name in primary),
                            conflict_action,
                        ),
                        rows,
                    )
            create_published_views(cursor, args.schema, args.readonly_user)
        remote.commit()
        return {
            "status": "SYNCED",
            "database": args.database,
            "schema": args.schema,
            "network_id": NETWORK_ID,
            "counts": counts,
        }
    except Exception:
        remote.rollback()
        raise
    finally:
        local.close()
        remote.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", type=Path, default=DEFAULT_DB)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--database", default="new_energy_vehicle")
    parser.add_argument("--schema", default="new_energy_vehicle")
    parser.add_argument("--user", default="new_energy_vehicle_writer")
    parser.add_argument("--readonly-user", default="new_energy_vehicle_readonly")
    parser.add_argument("--password-env", default="NEV_PG_WRITER_PASSWORD")
    print(json.dumps(sync(parser.parse_args()), ensure_ascii=False, indent=2))
