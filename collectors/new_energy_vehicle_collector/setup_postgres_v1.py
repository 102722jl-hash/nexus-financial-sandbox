"""Create the independent NEV PostgreSQL database, schema, and roles."""
from __future__ import annotations

import argparse
import json
import os

import psycopg
from psycopg import sql


def setup(args) -> dict:
    admin_password = os.environ.get(args.admin_password_env)
    writer_password = os.environ.get(args.writer_password_env)
    readonly_password = os.environ.get(args.readonly_password_env)
    missing = [
        name for name, value in (
            (args.admin_password_env, admin_password),
            (args.writer_password_env, writer_password),
            (args.readonly_password_env, readonly_password),
        ) if not value
    ]
    if missing:
        raise ValueError(f"missing environment variables: {missing}")
    admin = psycopg.connect(
        host=args.host, port=args.port, dbname="postgres", user=args.admin_user,
        password=admin_password, sslmode="prefer", connect_timeout=10, autocommit=True,
    )
    with admin.cursor() as cursor:
        for role, password in (
            (args.writer_user, writer_password),
            (args.readonly_user, readonly_password),
        ):
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,))
            if cursor.fetchone():
                cursor.execute(
                    sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier(role), sql.Literal(password)
                    )
                )
            else:
                cursor.execute(
                    sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier(role), sql.Literal(password)
                    )
                )
        cursor.execute("SELECT 1 FROM pg_database WHERE datname=%s", (args.database,))
        if not cursor.fetchone():
            cursor.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(args.database), sql.Identifier(args.admin_user)
                )
            )
        cursor.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}, {}").format(
                sql.Identifier(args.database), sql.Identifier(args.writer_user),
                sql.Identifier(args.readonly_user),
            )
        )
    admin.close()

    target = psycopg.connect(
        host=args.host, port=args.port, dbname=args.database, user=args.admin_user,
        password=admin_password, sslmode="prefer", connect_timeout=10,
    )
    with target.cursor() as cursor:
        cursor.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {} AUTHORIZATION {}").format(
                sql.Identifier(args.schema), sql.Identifier(args.admin_user)
            )
        )
        cursor.execute(
            sql.SQL("GRANT USAGE, CREATE ON SCHEMA {} TO {}").format(
                sql.Identifier(args.schema), sql.Identifier(args.writer_user)
            )
        )
        cursor.execute(
            sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                sql.Identifier(args.schema), sql.Identifier(args.readonly_user)
            )
        )
        cursor.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} "
                "GRANT SELECT ON TABLES TO {}"
            ).format(
                sql.Identifier(args.writer_user), sql.Identifier(args.schema),
                sql.Identifier(args.readonly_user),
            )
        )
        cursor.execute(
            sql.SQL("ALTER ROLE {} SET default_transaction_read_only=on").format(
                sql.Identifier(args.readonly_user)
            )
        )
    target.commit()
    target.close()
    return {
        "status": "READY",
        "database": args.database,
        "schema": args.schema,
        "writer_user": args.writer_user,
        "readonly_user": args.readonly_user,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--database", default="new_energy_vehicle")
    parser.add_argument("--schema", default="new_energy_vehicle")
    parser.add_argument("--admin-user", default="coal_network_admin")
    parser.add_argument("--writer-user", default="new_energy_vehicle_writer")
    parser.add_argument("--readonly-user", default="new_energy_vehicle_readonly")
    parser.add_argument("--admin-password-env", default="COAL_PG_ADMIN_PASSWORD")
    parser.add_argument("--writer-password-env", default="NEV_PG_WRITER_PASSWORD")
    parser.add_argument("--readonly-password-env", default="NEV_PG_READONLY_PASSWORD")
    print(json.dumps(setup(parser.parse_args()), ensure_ascii=False, indent=2))
