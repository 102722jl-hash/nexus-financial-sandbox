from __future__ import annotations

import json
from pathlib import Path

from crawler_postgres_ingest import ingest_crawler_payload


class Context:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self.value

    def __exit__(self, exc_type, exc, trace):
        return False


class FakeCursor:
    def __init__(self):
        self.commands = []
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, trace):
        return False

    def execute(self, statement, values=None):
        self.commands.append((statement, values))

    def executemany(self, statement, rows):
        materialized = list(rows)
        self.commands.append((statement, materialized))
        self.rows.extend(materialized)

    def fetchone(self):
        return (1,)


class FakeConnection:
    def __init__(self):
        self.cursors = []
        self.transactions = 0

    def transaction(self):
        self.transactions += 1
        return Context(self)

    def cursor(self):
        cursor = FakeCursor()
        self.cursors.append(cursor)
        return cursor


root = Path(__file__).resolve().parent
payload = json.loads((root / "v220_crawler_payload.example.json").read_text(encoding="utf-8"))
connection = FakeConnection()
first = ingest_crawler_payload(connection, payload)
second = ingest_crawler_payload(connection, payload)

assert first["status"] == "INGESTED"
assert first["networkPlanId"] == second["networkPlanId"]
assert first["counts"] == second["counts"]
assert first["counts"]["network_nodes"] == 3
assert first["counts"]["network_edges"] == 2
assert first["counts"]["metric_values"] == 3
assert first["counts"]["raw_documents"] == 1
assert first["counts"]["network_versions"] == 1
assert first["quarantineCount"] == 0
assert connection.transactions == 2
assert len(connection.cursors) == 2
assert all("TRUNCATE" not in str(statement).upper() for cursor in connection.cursors for statement, _ in cursor.commands)
assert all("DELETE" not in str(statement).upper() for cursor in connection.cursors for statement, _ in cursor.commands)

print("V2.20 PostgreSQL idempotent ingest: 13/13 passed")
