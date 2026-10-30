"""Verify NEV PostgreSQL counts and readonly enforcement."""
from __future__ import annotations

import argparse
import json
import os

import psycopg
from psycopg import sql

from contract_v1 import NETWORK_ID


def verify(args) -> dict:
    password = os.environ.get(args.password_env)
    if not password:
        raise ValueError(f"missing environment variable: {args.password_env}")
    connection = psycopg.connect(
        host=args.host, port=args.port, dbname=args.database, user=args.user,
        password=password, sslmode="prefer", connect_timeout=10,
    )
    counts = {}
    published_views = (
        "published_networks", "published_layers", "published_nodes",
        "published_edges", "published_metric_values", "published_evidence",
    )
    with connection.cursor() as cursor:
        for table in published_views:
            cursor.execute(
                sql.SQL("SELECT count(*) FROM {}.{}").format(
                    sql.Identifier(args.schema), sql.Identifier(table)
                )
            )
            counts[table] = cursor.fetchone()[0]
        cursor.execute(
            sql.SQL("SELECT network_id FROM {}.published_networks").format(
                sql.Identifier(args.schema)
            )
        )
        network_ids = [row[0] for row in cursor.fetchall()]
        cursor.execute("SHOW default_transaction_read_only")
        default_readonly = cursor.fetchone()[0]
    connection.rollback()
    raw_access_denied = False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("SELECT 1 FROM {}.raw_documents LIMIT 1").format(
                    sql.Identifier(args.schema)
                )
            )
    except Exception:
        connection.rollback()
        raw_access_denied = True
    write_blocked = False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("DELETE FROM {}.published_networks WHERE 1=0").format(
                    sql.Identifier(args.schema)
                )
            )
        connection.commit()
    except Exception:
        connection.rollback()
        write_blocked = True
    connection.close()
    errors = []
    if network_ids != [NETWORK_ID]:
        errors.append(f"NETWORK_ID_MISMATCH:{network_ids}")
    if counts["published_nodes"] == 0 or counts["published_edges"] == 0:
        errors.append("EMPTY_NETWORK")
    if not raw_access_denied:
        errors.append("RAW_TABLE_ACCESS_NOT_DENIED")
    if not write_blocked:
        errors.append("READONLY_WRITE_NOT_BLOCKED")
    if default_readonly.lower() != "on":
        errors.append(f"DEFAULT_READONLY_OFF:{default_readonly}")
    return {
        "status": "PASS" if not errors else "FAIL",
        "database": args.database,
        "schema": args.schema,
        "user": args.user,
        "network_ids": network_ids,
        "counts": counts,
        "default_transaction_read_only": default_readonly,
        "raw_access_denied": raw_access_denied,
        "write_blocked": write_blocked,
        "errors": errors,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--database", default="new_energy_vehicle")
    parser.add_argument("--schema", default="new_energy_vehicle")
    parser.add_argument("--user", default="new_energy_vehicle_readonly")
    parser.add_argument("--password-env", default="NEV_PG_READONLY_PASSWORD")
    result = verify(parser.parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
