from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from validate_domain_spec import PUBLIC_VIEWS, validate_spec


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def quoted_identifier(value: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,62}", value):
        raise ValueError(f"UNSAFE_POSTGRES_IDENTIFIER:{value}")
    return '"' + value + '"'


def write_new_or_force(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"FILE_EXISTS:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def scaffold(spec_path: Path, output: Path, force: bool = False) -> dict:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    report = validate_spec(spec)
    if not report["valid"]:
        codes = ",".join(item["code"] for item in report["blockingIssues"])
        raise ValueError(f"SPEC_BLOCKED:{codes}")

    database = spec["database"]
    schema = database["schema_name"]
    readonly_role = database["readonly_role"]
    created: list[str] = []

    domain_spec = output / "config" / "domain_spec.json"
    write_new_or_force(domain_spec, json.dumps(spec, ensure_ascii=False, indent=2) + "\n", force)
    created.append(str(domain_spec))

    runtime_env = output / "config" / "runtime.example.env"
    env_text = "\n".join([
        f"NEXUS_DATABASE={database['database_name']}",
        f"NEXUS_SCHEMA={schema}",
        f"NEXUS_WRITER_ROLE={database['writer_role']}",
        f"NEXUS_READONLY_ROLE={readonly_role}",
        f"NEXUS_WRITER_PASSWORD_REF={database['writer_password_ref']}",
        f"NEXUS_READONLY_PASSWORD_REF={database['readonly_password_ref']}",
        "# Store actual secrets in local environment or a secret manager, never here.",
        "",
    ])
    write_new_or_force(runtime_env, env_text, force)
    created.append(str(runtime_env))

    sql_template = (ASSETS / "published_views.template.sql").read_text(encoding="utf-8")
    sql_body = sql_template.replace("{{schema}}", quoted_identifier(schema)).replace("{{readonly_role}}", quoted_identifier(readonly_role))
    view_sql = output / "database" / "published_views.sql"
    write_new_or_force(view_sql, sql_body, force)
    created.append(str(view_sql))

    blueprint = output / "network" / "network_blueprint.json"
    write_new_or_force(blueprint, json.dumps(spec["network"], ensure_ascii=False, indent=2) + "\n", force)
    created.append(str(blueprint))

    schedule = output / "scheduler" / "schedule.json"
    write_new_or_force(schedule, json.dumps(spec["schedule"], ensure_ascii=False, indent=2) + "\n", force)
    created.append(str(schedule))

    source_rows = json.dumps(spec["sources"], ensure_ascii=False, indent=2)
    adapter_body = f'''"""Source adapter registry generated from the confirmed domain specification.

Implement one fetch/snapshot/extract adapter per entry. Do not put credentials here.
"""
from __future__ import annotations

import json

SOURCES = json.loads(r\'''{source_rows}\''')


def fetch_source(source_code: str):
    source = next((item for item in SOURCES if item["source_code"] == source_code), None)
    if not source:
        raise KeyError(f"SOURCE_NOT_REGISTERED:{{source_code}}")
    raise NotImplementedError(f"SOURCE_ADAPTER_REQUIRED:{{source_code}}")
'''
    adapters = output / "collector" / "source_adapters.py"
    write_new_or_force(adapters, adapter_body, force)
    created.append(str(adapters))

    for directory in ("standard_batches", "snapshots", "tests", "reports"):
        (output / directory).mkdir(parents=True, exist_ok=True)

    result = {
        "status": "SCAFFOLDED",
        "domainCode": spec["domain"]["domain_code"],
        "database": database["database_name"],
        "schema": schema,
        "readonlyObjects": sorted(PUBLIC_VIEWS),
        "createdFiles": created,
        "nextRequiredAction": "IMPLEMENT_AND_DRY_RUN_SOURCE_ADAPTERS",
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    report_path = output / "reports" / "scaffold_report.json"
    write_new_or_force(report_path, json.dumps(result, ensure_ascii=False, indent=2) + "\n", force)
    result["createdFiles"].append(str(report_path))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold an industry collector and network project from a validated specification.")
    parser.add_argument("spec", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        result = scaffold(args.spec, args.output, args.force)
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": type(exc).__name__, "detail": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

