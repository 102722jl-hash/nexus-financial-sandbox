"""Create a durable coal-power network from the last complete graph."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "runs" / "networks" / "PLAN-B04F7248D89D05F0.json"
TARGET = ROOT / "runs" / "networks" / "PLAN-COALPOWER-V1.json"
DB = ROOT.parent / "coal_network_collector" / "coal_network.db"
NETWORK_ID = "PLAN-COALPOWER-V1"


def latest_values(connection: sqlite3.Connection) -> dict[tuple[str | None, str], sqlite3.Row]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT * FROM (
          SELECT mv.*, ROW_NUMBER() OVER (
            PARTITION BY entity_code, metric_code
            ORDER BY COALESCE(as_of_date, '' ) DESC,
                     COALESCE(data_cutoff, '' ) DESC,
                     COALESCE(announcement_date, '' ) DESC,
                     COALESCE(metric_value_id, '' ) DESC
          ) AS rn
          FROM metric_values mv
          WHERE network_id = 'coal_power_v1'
            AND value IS NOT NULL
        ) ranked
        WHERE rn = 1
        """
    ).fetchall()
    return {(row["entity_code"], row["metric_code"]): row for row in rows}


def main() -> None:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    with sqlite3.connect(DB) as connection:
        values = latest_values(connection)

    graph = payload.get("fullGraph") or {}
    updated = 0
    cutoffs: list[str] = []
    for node in graph.get("nodes", []):
        baseline = dict(node.get("baseline") or {})
        metric_codes = list(node.get("metricCodes") or [])
        entity_code = node.get("entityCode")
        for code in metric_codes:
            row = values.get((entity_code, code))
            if row is None:
                continue
            value = row["value"]
            if value is None:
                continue
            baseline[code] = value
            if code == metric_codes[0] or "BASE" not in baseline:
                baseline["BASE"] = value
            if row["as_of_date"]:
                node["asOfDate"] = row["as_of_date"]
            if row["data_cutoff"]:
                node["dataCutoff"] = row["data_cutoff"]
                cutoffs.append(str(row["data_cutoff"]))
            if row["evidence_id"]:
                node["evidenceIds"] = [row["evidence_id"]]
            node["valueStatus"] = row["value_status"] or node.get("valueStatus") or "SOURCE_FACT"
            updated += 1
        node["baseline"] = baseline

    stamp = datetime.now(timezone.utc).isoformat()
    cutoff = max(cutoffs) if cutoffs else payload.get("dataCutoff")
    payload.update(
        {
            "ownerClientId": "LOCAL-COAL-NETWORK",
            "networkId": NETWORK_ID,
            "networkPlanId": NETWORK_ID,
            "networkName": "煤炭-电力经营-财务-现金流-估值多链路传导网络",
            "networkKind": "PRECOMPILED_NETWORK",
            "outputLevel": "SCENARIO_PATH_ONLY",
            "dataCutoff": cutoff,
            "nodes": graph.get("nodes", []),
            "edges": graph.get("edges", []),
            "fullGraph": graph,
            "createdAt": stamp,
            "activatedAt": stamp,
            "deletable": False,
            "recovery": {
                "sourceNetworkId": "PLAN-B04F7248D89D05F0",
                "sourceCreatedAt": payload.get("createdAt"),
                "updatedNodeMetricValues": updated,
                "database": "coal_power_v1",
                "preservesGraphStructure": True,
            },
        }
    )
    temporary = TARGET.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(TARGET)
    print(json.dumps({"target": str(TARGET), "nodes": len(graph.get("nodes", [])), "edges": len(graph.get("edges", [])), "updated": updated, "dataCutoff": cutoff}, ensure_ascii=False))


if __name__ == "__main__":
    main()
