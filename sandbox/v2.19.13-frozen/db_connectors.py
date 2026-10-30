"""Portable, metadata-only database connectors with enforced read-only sessions."""
from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from typing import Any

import psycopg
from psycopg import sql
import pymysql


MAX_TABLES = 50
MAX_COLUMNS = 3000
PROFILE_SAMPLE_ROWS = 50
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
POSTGRES_SSL = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}
MYSQL_SSL = {"disabled", "preferred", "required"}
YEAR_IN_NAME = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
PRECOMPILED_NODE_FIELDS = {"nodes", "nodes_json", "node_json", "network_nodes", "network_nodes_json", "节点", "节点_json", "节点json", "网络节点", "网络节点_json", "网络节点json"}
PRECOMPILED_EDGE_FIELDS = {"edges", "edges_json", "edge_json", "network_edges", "network_edges_json", "关系", "连线", "连线_json", "连线json", "网络关系", "网络关系_json", "网络关系json"}
PRECOMPILED_BUNDLE_FIELDS = {"network_json", "graph_json", "network_definition", "network_definition_json", "网络_json", "网络json", "网络定义", "网络定义_json", "网络定义json"}
COLUMNAR_PRECOMPILED_FIELDS = {
    "editable_metric_name", "editable_metric_type", "editable_metric_unit",
    "editable_baseline_value", "driver_sensitivity", "lag_days", "impact_cap_pct",
    "network_status", "network_kind", "network_state", "network_position", "source_node_id", "target_node_id", "edge_weight", "edge_direction", "edge_mechanism", "edge_lag_days", "edge_confidence",
}
COLUMNAR_CONTROL_ROLES = {
    "record_id": "ROW_KEY",
    "network_status": "NETWORK_STATUS",
    "network_kind": "NETWORK_KIND",
    "network_state": "NETWORK_STATE",
    "network_position": "NETWORK_CHAIN_POSITION",
    "chain_layer_no": "NETWORK_CHAIN_LAYER_NO",
    "chain_layer_name": "NETWORK_CHAIN_LAYER_NAME",
    "chain_position": "NETWORK_CHAIN_POSITION",
    "editable_metric_code": "NETWORK_EDITABLE_METRIC_CODE",
    "editable_metric_name": "NETWORK_EDITABLE_METRIC_NAME",
    "editable_metric_type": "NETWORK_EDITABLE_METRIC_TYPE",
    "editable_metric_unit": "NETWORK_EDITABLE_METRIC_UNIT",
    "editable_baseline_value": "NETWORK_EDITABLE_BASELINE_VALUE",
    "driver_sensitivity": "NETWORK_DRIVER_SENSITIVITY",
    "driver_direction": "NETWORK_DRIVER_DIRECTION",
    "impact_direction": "NETWORK_DRIVER_DIRECTION",
    "driver_mechanism": "NETWORK_DRIVER_MECHANISM",
    "impact_mechanism": "NETWORK_DRIVER_MECHANISM",
    "lag_days": "NETWORK_LAG_DAYS",
    "impact_cap_pct": "NETWORK_IMPACT_CAP_PCT",
}


def require_text(config: dict[str, Any], key: str, limit: int = 255) -> str:
    value = str(config.get(key) or "").strip()
    if not value or len(value) > limit:
        raise ValueError(f"DB_CONFIG_INVALID:{key}")
    return value


def identifier(value: Any, key: str, default: str | None = None) -> str:
    text = str(value or default or "").strip()
    if not text or len(text) > 128 or any(char == "\x00" or unicodedata.category(char).startswith("C") for char in text):
        raise ValueError(f"DB_IDENTIFIER_INVALID:{key}")
    return text


def port_value(config: dict[str, Any], default: int) -> int:
    port = int(config.get("port") or default)
    if not 1 <= port <= 65535:
        raise ValueError("DB_CONFIG_INVALID:port")
    return port


def password_value(config: dict[str, Any]) -> tuple[str | None, str]:
    reference = str(config.get("credentialRef") or "").strip()
    if reference:
        if not ENV_NAME.fullmatch(reference):
            raise ValueError("CREDENTIAL_REFERENCE_INVALID")
        if reference not in os.environ:
            raise ValueError("CREDENTIAL_REFERENCE_NOT_FOUND")
        return os.environ[reference], f"ENV:{reference}"
    password = config.get("password")
    return (str(password) if password not in (None, "") else None), "REQUEST_EPHEMERAL"


def table_names(config: dict[str, Any]) -> list[str]:
    raw = config.get("tables") or []
    if isinstance(raw, str):
        raw = raw.split(",")
    names = []
    for value in raw:
        text = str(value).strip()
        if not text:
            continue
        names.append(identifier(text, "table"))
    names = list(dict.fromkeys(names))
    if len(names) > MAX_TABLES:
        raise ValueError("TABLE_LIMIT_EXCEEDED")
    return names


def fingerprint(kind: str, host: str, port: int, database: str, schema: str, user: str) -> str:
    payload = json.dumps(
        {"type": kind, "host": host, "port": port, "database": database, "schema": schema, "user": user},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def profile_rows(rows: list[tuple[Any, ...]], database: str) -> list[dict[str, Any]]:
    if len(rows) > MAX_COLUMNS:
        raise ValueError("COLUMN_LIMIT_EXCEEDED")
    return [{
        "column": f"{database}.{row[0]}.{row[1]}.{row[2]}",
        "columnName": str(row[2]),
        "tableName": str(row[1]),
        "schemaName": str(row[0]),
        "databaseName": database,
        "sourceLocator": {"database": database, "schema": str(row[0]), "table": str(row[1]), "column": str(row[2])},
        "dtype": str(row[3]),
        "columnComment": str(row[4]).strip() if len(row) > 4 and row[4] not in (None, "") else None,
        "nullRate": None,
        "candidateValue": None,
        "candidateStatus": "SCHEMA_ONLY",
    } for row in rows]


def _as_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


SENSITIVE_COLUMN_TOKENS = ("password", "passwd", "secret", "token", "api_key", "apikey", "密钥", "密码")


def _safe_sample_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    number = _as_number(value)
    if number is not None:
        return number
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text[:80] if text else None


def apply_sample_profile(columns: list[dict[str, Any]], table: str, rows: list[tuple[Any, ...]]) -> None:
    fields = [item for item in columns if item.get("tableName") == table]
    total_rows = len(rows)
    for index, field in enumerate(fields):
        values = [row[index] for row in rows if index < len(row) and row[index] not in (None, "")]
        numeric = [_as_number(value) for value in values]
        numeric_values = [value for value in numeric if value is not None]
        column_name = str(field.get("columnName") or "").lower()
        examples: list[Any] = []
        if not any(token in column_name for token in SENSITIVE_COLUMN_TOKENS):
            seen: set[str] = set()
            for value in values:
                safe = _safe_sample_value(value)
                marker = json.dumps(safe, ensure_ascii=False, sort_keys=True)
                if safe is None or marker in seen:
                    continue
                seen.add(marker)
                examples.append(safe)
                if len(examples) >= 5:
                    break
        field["sampleNonNull"] = len(values)
        field["sampleValues"] = examples
        field["distinctSampleCount"] = len({str(value) for value in values})
        field["nullRate"] = round((total_rows - len(values)) / total_rows, 4) if total_rows else None
        field["numericSampleRate"] = round(len(numeric_values) / len(values), 4) if values else 0.0
        field["numericMin"] = min(numeric_values) if numeric_values else None
        field["numericMax"] = max(numeric_values) if numeric_values else None
        field["profileMethod"] = "TYPE_VALUE_SHAPE_AND_LIMITED_EXAMPLES"


def _mysql_identifier(value: Any, key: str) -> str:
    return "`" + identifier(value, key).replace("`", "``").replace("%", "%%") + "`"


def infer_network_table_role(names: set[str]) -> str:
    node_id = bool(names.intersection({"node_id", "nodeid", "node_code", "node_key"}))
    layer = bool(names.intersection({"layer", "node_layer", "layer_id", "layer_no", "chain_layer_no", "chain_layer_name"}))
    label = bool(names.intersection({"label", "name", "node_name", "node_name_cn", "node_label", "node_title", "node_description", "title"}))
    source = bool(names.intersection({"source_node_id", "source", "source_id", "from", "from_node", "source_node"}))
    target = bool(names.intersection({"target_node_id", "target", "target_id", "to", "to_node", "target_node"}))
    if "network_id" in names and names.intersection({"layer_no", "layer_code"}) and names.intersection({"layer_name_cn", "layer_name", "layer_label"}): return "LAYERS"
    if node_id and layer and label: return "NODES"
    if source and target and bool(names.intersection({"weight", "edge_weight", "direction", "relation_type", "mechanism"})): return "EDGES"
    if "formula_id" in names and names.intersection({"formula_type", "formula_code"}): return "FORMULAS"
    if "evidence_id" in names and bool(names.intersection({"original_quote", "source_url", "evidence_source", "locator"})): return "EVIDENCE"
    if "network_id" in names and names.intersection({"metric_code", "metric_id"}) and names.intersection({"value", "metric_value", "baseline_value"}): return "METRIC_VALUES"
    if {"metric_value_id", "component_metric_value_id", "input_role"}.issubset(names): return "CALCULATED_LINEAGE"
    entity = bool(names.intersection({"entity_code", "company_code", "security_code", "exchange_code"}))
    if entity and names.intersection({"valuation_date", "current_market_cap", "baseline_equity_value", "scenario_equity_value"}): return "VALUATION"
    if entity and names.intersection({"report_period", "announcement_date", "ann_dt", "actual_ann_dt"}): return "FINANCIALS"
    if "network_id" in names and names.intersection({"network_name", "network_version", "network_status"}) and not names.intersection({"entity_code", "node_id", "source_node_id"}): return "REGISTRY"
    if entity: return "METRICS"
    return "UNKNOWN"

def table_adapters(database: str, schema: str, selected: list[str], columns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for table in selected:
        fields = [item for item in columns if item.get("tableName") == table and item.get("schemaName") == schema]
        lower_names = {str(item.get("columnName") or "").strip().lower().replace("-", "_").replace(" ", "_") for item in fields}
        has_report_period = bool(lower_names.intersection({"report_period", "报告期", "报告日期", "财报日期"}))
        has_available_date = bool(lower_names.intersection({"actual_ann_dt", "ann_dt", "announcement_date", "公告日期", "实际公告日期", "披露日期", "发布日期", "opdate", "更新时间", "数据更新时间", "版本时间", "入库时间"}))
        year_match = YEAR_IN_NAME.search(table)
        node_fields: list[str] = []
        edge_fields: list[str] = []
        bundle_fields: list[str] = []
        columnar_controls: list[str] = []
        network_role = infer_network_table_role(lower_names)
        network_control_names = lower_names.intersection(COLUMNAR_PRECOMPILED_FIELDS)
        columnar_signature = network_role == "UNKNOWN" and bool(network_control_names) and (
            "network_status" in lower_names or "network_kind" in lower_names or "network_state" in lower_names or
            "chain_layer_no" in lower_names or "editable_metric_name" in lower_names or "network" in table.lower()
        )
        # Columnar network contracts take precedence over content-based JSON guesses.
        for field in fields:
            name = str(field.get("columnName") or "").strip()
            normalized_name = name.lower().replace("-", "_").replace(" ", "_")
            sample = json.dumps(field.get("sampleValues") or [], ensure_ascii=False).lower()
            comment = str(field.get("columnComment") or "").lower().replace(" ", "")
            node_like = (not columnar_signature) and (normalized_name in PRECOMPILED_NODE_FIELDS or ("nodeid" in sample and "layer" in sample) or ("节点" in comment and "json" in comment))
            edge_like = (not columnar_signature) and (normalized_name in PRECOMPILED_EDGE_FIELDS or (("sourcenodeid" in sample or '"from"' in sample) and ("targetnodeid" in sample or '"to"' in sample)) or (("连线" in comment or "关系" in comment) and "json" in comment))
            bundle_like = (not columnar_signature) and (normalized_name in PRECOMPILED_BUNDLE_FIELDS or ((("nodes" in sample and "edges" in sample) or ("节点" in comment and ("连线" in comment or "关系" in comment))) and "json" in (normalized_name + comment + sample)))
            if node_like:
                field["precompiledRole"] = "NETWORK_NODES_JSON"
                node_fields.append(name)
            if edge_like:
                field["precompiledRole"] = "NETWORK_EDGES_JSON"
                edge_fields.append(name)
            if bundle_like:
                field["precompiledRole"] = "NETWORK_METADATA_JSON"
                bundle_fields.append(name)
            if normalized_name in COLUMNAR_CONTROL_ROLES:
                field["precompiledRole"] = COLUMNAR_CONTROL_ROLES[normalized_name]
                columnar_controls.append(name)
        node_fields.sort()
        edge_fields.sort()
        bundle_fields.sort()
        columnar_controls.sort()
        json_precompiled = bool((node_fields and edge_fields) or bundle_fields) and not columnar_signature
        columnar_precompiled = columnar_signature and len(lower_names.intersection(COLUMNAR_PRECOMPILED_FIELDS)) >= 3
        network_role = "" if (columnar_precompiled or json_precompiled) else network_role
        for field in fields:
            field["tableRole"] = network_role
        multi_table_role = network_role in {"REGISTRY", "LAYERS", "NODES", "EDGES", "FORMULAS", "EVIDENCE", "METRIC_VALUES", "CALCULATED_LINEAGE", "FINANCIALS", "VALUATION"}
        if multi_table_role:
            precompiled = True
            adapter_mode = f"MULTI_TABLE_{network_role}"
        else:
            precompiled = json_precompiled or columnar_precompiled
            adapter_mode = "PRECOMPILED_NETWORK_JSON" if json_precompiled else ("PRECOMPILED_NETWORK_COLUMNS" if columnar_precompiled else "MAPPED_POINT_IN_TIME")
        report_period_hint = None if has_report_period else (year_match.group(1) + "1231" if year_match else None)
        output.append({
            "adapterId": hashlib.sha256(json.dumps({"database": database, "schema": schema, "table": table}, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16],
            "databaseName": database, "schemaName": schema, "tableName": table,
            "qualifiedDisplay": f"{database}.{schema}.{table}", "identifierMode": "DRIVER_ESCAPED",
            "sourceFieldMode": "STRUCTURED_LOCATOR", "profileStatus": "READY",
            "columnCount": len(fields), "syncMode": adapter_mode,
            "reportPeriodHint": report_period_hint,
            "reportPeriodSource": "SOURCE_COLUMN" if has_report_period else ("INFERRED_FROM_TABLE_NAME" if report_period_hint else "MISSING"),
            "availableDateMode": "SOURCE_COLUMN" if has_available_date else "SYNC_CUTOFF",
            "temporalStatus": "SOURCE_CONTROL_FIELDS" if has_report_period and has_available_date else "PENDING_REVIEW",
            "adapterMode": adapter_mode,
            "networkRole": network_role,
            "precompiledStatus": "STRUCTURE_SIGNATURE_MATCHED" if precompiled else "NOT_DETECTED",
            "nodeJsonFields": node_fields, "edgeJsonFields": edge_fields,
            "bundleJsonFields": bundle_fields,
            "columnarControlFields": columnar_controls,
        })
    return output


def result(
    *,
    kind: str,
    host: str,
    port: int,
    database: str,
    schema: str,
    user: str,
    credential_source: str,
    read_only: str,
    discovered: list[str],
    selected: list[str],
    columns: list[dict[str, Any]],
    server_version: str,
) -> dict[str, Any]:
    return {
        "status": "PROFILED_READ_ONLY",
        "summary": {
            "source_type": kind.upper(),
            "current_user": user,
            "current_database": database,
            "server": f"{host}:{port}",
            "server_version": server_version,
            "schema": schema,
            "transaction_read_only": read_only,
            "discovered_tables": len(discovered),
            "selected_tables": len(selected),
            "columns_profiled": len(columns),
            "credential_source": credential_source,
            "credential_persisted": False,
            "query_mode": "SCHEMA_AND_VALUE_SHAPE_SAMPLE",
            "sample_row_limit_per_table": PROFILE_SAMPLE_ROWS,
        },
        "tables": discovered,
        "selectedTables": selected,
        "profile": columns,
        "tableAdapters": table_adapters(database, schema, selected, columns),
        "entityHints": [],
        "sourceHash": fingerprint(kind, host, port, database, schema, user),
    }


def profile_postgresql(config: dict[str, Any]) -> dict[str, Any]:
    host = require_text(config, "host")
    database = require_text(config, "database")
    user = require_text(config, "user")
    port = port_value(config, 5432)
    schema = identifier(config.get("schema"), "schema", "public")
    selected = table_names(config)
    sslmode = str(config.get("sslmode") or "prefer").lower()
    if sslmode not in POSTGRES_SSL:
        raise ValueError("DB_CONFIG_INVALID:sslmode")
    password, credential_source = password_value(config)
    params = {
        "host": host,
        "port": port,
        "dbname": database,
        "user": user,
        "password": password,
        "sslmode": sslmode,
        "connect_timeout": 8,
        "options": "-c default_transaction_read_only=on -c statement_timeout=30000 -c lock_timeout=5000",
    }
    with psycopg.connect(**params) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        read_only = str(conn.execute("SHOW transaction_read_only").fetchone()[0]).lower()
        if read_only != "on":
            raise RuntimeError("READ_ONLY_GUARD_FAILED")
        identity = conn.execute(
            "SELECT current_user, current_database(), version()"
        ).fetchone()
        discovered_rows = conn.execute(
            """
            SELECT table_name
              FROM information_schema.tables
             WHERE table_schema = %s AND table_type IN ('BASE TABLE', 'VIEW')
             ORDER BY table_name
             LIMIT %s
            """,
            (schema, MAX_TABLES),
        ).fetchall()
        discovered = [str(row[0]) for row in discovered_rows]
        missing = [name for name in selected if name not in discovered]
        if missing:
            raise ValueError("TABLE_NOT_FOUND:" + ",".join(missing))
        columns: list[dict[str, Any]] = []
        if selected:
            rows = conn.execute(
                """
                SELECT table_schema, table_name, column_name, data_type,
                       pg_catalog.col_description(
                           (format('%%I.%%I', table_schema, table_name))::regclass::oid,
                           ordinal_position
                       )
                  FROM information_schema.columns
                 WHERE table_schema = %s AND table_name = ANY(%s)
                 ORDER BY table_name, ordinal_position
                """,
                (schema, selected),
            ).fetchall()
            columns = profile_rows(rows, database)
            for table in selected:
                fields = [item for item in columns if item.get("tableName") == table]
                if not fields:
                    continue
                selected_columns = sql.SQL(", ").join(sql.Identifier(item["columnName"]) for item in fields)
                sample_query = sql.SQL("SELECT {columns} FROM {schema}.{table} LIMIT %s").format(
                    columns=selected_columns, schema=sql.Identifier(schema), table=sql.Identifier(table)
                )
                samples = conn.execute(sample_query, (PROFILE_SAMPLE_ROWS,)).fetchall()
                apply_sample_profile(columns, table, samples)
        conn.rollback()
    return result(
        kind="postgresql", host=host, port=port, database=database, schema=schema,
        user=str(identity[0]), credential_source=credential_source, read_only=read_only,
        discovered=discovered, selected=selected, columns=columns, server_version=str(identity[2]),
    )


def mysql_read_only(cursor: Any) -> str:
    for variable in ("transaction_read_only", "tx_read_only"):
        try:
            cursor.execute(f"SELECT @@session.{variable}")
            value = cursor.fetchone()[0]
            return "on" if str(value).lower() in {"1", "on", "true"} else "off"
        except Exception:
            continue
    raise RuntimeError("READ_ONLY_STATUS_UNAVAILABLE")


def profile_mysql(config: dict[str, Any]) -> dict[str, Any]:
    host = require_text(config, "host")
    database = require_text(config, "database")
    user = require_text(config, "user")
    port = port_value(config, 3306)
    schema = identifier(config.get("schema"), "schema", database)
    selected = table_names(config)
    sslmode = str(config.get("sslmode") or "preferred").lower()
    if sslmode not in MYSQL_SSL:
        raise ValueError("DB_CONFIG_INVALID:sslmode")
    password, credential_source = password_value(config)
    ssl = None if sslmode == "disabled" else {"check_hostname": sslmode == "required"}
    conn = pymysql.connect(
        host=host, port=port, database=database, user=user, password=password,
        connect_timeout=8, read_timeout=30, write_timeout=5, autocommit=False,
        charset="utf8mb4", ssl=ssl,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET SESSION TRANSACTION READ ONLY")
            cursor.execute("START TRANSACTION READ ONLY")
            read_only = mysql_read_only(cursor)
            if read_only != "on":
                raise RuntimeError("READ_ONLY_GUARD_FAILED")
            cursor.execute("SELECT CURRENT_USER(), DATABASE(), VERSION()")
            identity = cursor.fetchone()
            if selected:
                table_placeholders = ",".join(["%s"] * len(selected))
                cursor.execute(
                    f"""
                    SELECT table_name
                      FROM information_schema.tables
                     WHERE table_schema = %s
                       AND table_type IN ('BASE TABLE', 'VIEW')
                       AND table_name IN ({table_placeholders})
                     ORDER BY table_name
                    """,
                    (schema, *selected),
                )
            else:
                cursor.execute(
                    """
                    SELECT table_name
                      FROM information_schema.tables
                     WHERE table_schema = %s AND table_type IN ('BASE TABLE', 'VIEW')
                     ORDER BY table_name
                     LIMIT %s
                    """,
                    (schema, MAX_TABLES),
                )
            discovered = [str(row[0]) for row in cursor.fetchall()]
            missing = [name for name in selected if name not in discovered]
            if missing:
                raise ValueError("TABLE_NOT_FOUND:" + ",".join(missing))
            columns: list[dict[str, Any]] = []
            if selected:
                placeholders = ",".join(["%s"] * len(selected))
                cursor.execute(
                    f"""
                    SELECT table_schema, table_name, column_name, data_type, column_comment
                      FROM information_schema.columns
                     WHERE table_schema = %s AND table_name IN ({placeholders})
                     ORDER BY table_name, ordinal_position
                    """,
                    (schema, *selected),
                )
                columns = profile_rows(list(cursor.fetchall()), database)
                for table in selected:
                    fields = [item for item in columns if item.get("tableName") == table]
                    if not fields:
                        continue
                    selected_columns = ", ".join(_mysql_identifier(item["columnName"], "column") for item in fields)
                    sample_query = "SELECT " + selected_columns + " FROM " + _mysql_identifier(schema, "schema") + "." + _mysql_identifier(table, "table") + " LIMIT %s"
                    cursor.execute(sample_query, (PROFILE_SAMPLE_ROWS,))
                    apply_sample_profile(columns, table, list(cursor.fetchall()))
        conn.rollback()
    finally:
        conn.close()
    return result(
        kind="mysql", host=host, port=port, database=database, schema=schema,
        user=str(identity[0]), credential_source=credential_source, read_only=read_only,
        discovered=discovered, selected=selected, columns=columns, server_version=str(identity[2]),
    )


def profile_database(config: dict[str, Any]) -> dict[str, Any]:
    kind = str(config.get("type") or "").lower()
    if kind == "postgresql":
        return profile_postgresql(config)
    if kind == "mysql":
        return profile_mysql(config)
    raise ValueError("DATABASE_TYPE_NOT_ALLOWED")


def public_config(config: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in config.items()
        if key not in {"password", "apiKey", "token", "secret"}
    }
