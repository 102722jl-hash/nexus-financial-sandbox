from __future__ import annotations

import argparse
import json
from pathlib import Path

from crawler_network_compiler import compile_crawler_network


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile a validated crawler batch into a NEXUS network plan.")
    parser.add_argument("payload", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.payload.read_text(encoding="utf-8"))
    plan = compile_crawler_network(payload)
    output = args.output or Path("runs") / "networks" / f"{plan['networkPlanId']}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "COMPILED", "output": str(output), "networkPlanId": plan["networkPlanId"], "readiness": plan["readiness"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
