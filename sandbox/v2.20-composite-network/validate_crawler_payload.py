from __future__ import annotations

import argparse
import json
from pathlib import Path

from crawler_contract import validate_crawler_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a NEXUS crawler batch before database ingestion.")
    parser.add_argument("payload", type=Path, help="Path to crawler batch JSON")
    parser.add_argument("--report", type=Path, help="Optional path for the validation report")
    args = parser.parse_args()

    payload = json.loads(args.payload.read_text(encoding="utf-8"))
    report = validate_crawler_payload(payload)
    body = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.write_text(body + "\n", encoding="utf-8")
    print(body)
    return 0 if report["ingestionAllowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
