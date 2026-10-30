"""Read-only PostgreSQL adapter for point-in-time financial statement queries."""
from __future__ import annotations

import argparse
import json
from decimal import Decimal

import psycopg
from psycopg import sql


CONNECTION = {
    "host": "rsshub.weixiewen.cn",
    "port": 5589,
    "dbname": "pg",
    "user": "dwzq",
    "sslmode": "prefer",
    "options": "-c default_transaction_read_only=on -c statement_timeout=60000",
}
TABLE_FIELDS = {
    "asharebalancesheet": [
        "monetary_cap", "acct_rcv", "inventories", "tot_assets", "tot_liab",
        "tot_shrhldr_eqy_excl_min_int",
    ],
    "asharecashflow": [
        "net_cash_flows_oper_act", "cash_pay_acq_const_fiolta", "free_cash_flow",
    ],
    "ashareincome": [
        "tot_oper_rev", "oper_profit", "net_profit_excl_min_int_inc", "ebit", "ebitda",
    ],
}


def json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def connect_read_only():
    conn = psycopg.connect(**CONNECTION)
    conn.execute("SET TRANSACTION READ ONLY")
    read_only = conn.execute("SHOW transaction_read_only").fetchone()[0]
    if read_only != "on":
        conn.close()
        raise RuntimeError("READ_ONLY_GUARD_FAILED")
    return conn


def fetch_statement(conn, table, code, report_period, cutoff, statement_type="408001000"):
    if table not in TABLE_FIELDS:
        raise ValueError("TABLE_NOT_ALLOWED")
    fields = TABLE_FIELDS[table]
    query = sql.SQL(
        """
        SELECT s_info_windcode, report_period,
               COALESCE(NULLIF(actual_ann_dt, ''), ann_dt) AS visible_date,
               opdate, statement_type, {fields}
          FROM public.{table}
         WHERE s_info_windcode = %(code)s
           AND report_period = %(report_period)s
           AND statement_type = %(statement_type)s
           AND COALESCE(NULLIF(actual_ann_dt, ''), ann_dt) <= %(cutoff)s
           AND opdate <= to_date(%(cutoff)s, 'YYYYMMDD')
         ORDER BY COALESCE(NULLIF(actual_ann_dt, ''), ann_dt) DESC,
                  opdate DESC
         LIMIT 1
        """
    ).format(
        table=sql.Identifier(table),
        fields=sql.SQL(", ").join(map(sql.Identifier, fields)),
    )
    row = conn.execute(query, {
        "code": code,
        "report_period": report_period,
        "statement_type": statement_type,
        "cutoff": cutoff,
    }).fetchone()
    if row is None:
        return {
            "status": "DATA_MISSING",
            "table": table,
            "code": code,
            "report_period": report_period,
            "cutoff": cutoff,
            "statement_type": statement_type,
        }
    names = ["code", "report_period", "visible_date", "opdate", "statement_type", *fields]
    return {"status": "CALCULATED_LINEAGE", "table": table, **dict(zip(names, row))}


def coverage(conn):
    result = []
    for table in TABLE_FIELDS:
        query = sql.SQL(
            """
            SELECT count(*), count(DISTINCT s_info_windcode),
                   min(report_period), max(report_period),
                   min(COALESCE(NULLIF(actual_ann_dt, ''), ann_dt)),
                   max(COALESCE(NULLIF(actual_ann_dt, ''), ann_dt)),
                   count(*) FILTER (WHERE statement_type = '408001000')
              FROM public.{table}
            """
        ).format(table=sql.Identifier(table))
        row = conn.execute(query).fetchone()
        result.append(dict(zip([
            "rows", "securities", "report_period_min", "report_period_max",
            "visible_date_min", "visible_date_max", "preferred_statement_rows",
        ], row)) | {"table": table})
    return result


def main():
    parser = argparse.ArgumentParser(description="Read-only point-in-time financial query")
    parser.add_argument("--coverage", action="store_true")
    parser.add_argument("--table", choices=sorted(TABLE_FIELDS))
    parser.add_argument("--code")
    parser.add_argument("--report-period")
    parser.add_argument("--cutoff")
    parser.add_argument("--statement-type", default="408001000")
    args = parser.parse_args()
    conn = connect_read_only()
    try:
        if args.coverage:
            payload = {"transaction_read_only": "on", "coverage": coverage(conn)}
        elif all([args.table, args.code, args.report_period, args.cutoff]):
            payload = fetch_statement(
                conn, args.table, args.code, args.report_period, args.cutoff, args.statement_type
            )
        else:
            parser.error("use --coverage or provide --table, --code, --report-period and --cutoff")
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=json_default))
    finally:
        conn.rollback()
        conn.close()


if __name__ == "__main__":
    main()
