"""Daily fail-closed NEV collection pipeline."""
from __future__ import annotations

import argparse
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path

from announcement_discovery_v1 import collect as collect_announcements
from company_pdf_parser_v1 import import_pending as import_monthly
from financial_pdf_parser_v1 import import_financial_reports
from derived_metrics_v1 import build_derived_metrics
from gfex_market_v1 import collect as collect_gfex
from industry_public_v1 import collect as collect_industry
from export_nexus_batch_v1 import export_batch
from initialize import DEFAULT_DB, ROOT, initialize
from quality_gate_v1 import run_quality_gate
from sina_market_v1 import collect as collect_market

REPORT_PATH = ROOT / "auto_collect_v1_report.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run(db_path: Path = DEFAULT_DB, market_days: int = 30) -> dict:
    report = {
        "pipeline": "new-energy-vehicle-auto-collect-v1",
        "started_at": utc_now(),
        "database": str(db_path),
        "stages": {},
        "status": "RUNNING",
    }
    failed = False

    def stage(name: str, function):
        nonlocal failed
        try:
            result = function()
            report["stages"][name] = {"status": "OK", "result": result}
            return result
        except Exception as exc:
            failed = True
            report["stages"][name] = {
                "status": "ERROR",
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            }
            return None

    stage("initialize_fixed_blueprint", lambda: initialize(db_path))
    market = stage("market_proxy_collection", lambda: collect_market(db_path, market_days))
    if market and any(item.get("status") != "OK" for item in market):
        failed = True
        report["stages"]["market_proxy_collection"]["status"] = "PARTIAL_ERROR"
    stage("official_lithium_market_collection", lambda: collect_gfex(db_path, 14, 1))
    stage("industry_public_collection", lambda: collect_industry(db_path))
    announcements = stage("official_announcement_collection", lambda: collect_announcements(db_path, True))
    if announcements and (
        announcements.get("discovery_errors") or announcements.get("download", {}).get("errors")
    ):
        failed = True
        report["stages"]["official_announcement_collection"]["status"] = "PARTIAL_ERROR"
    monthly = stage("monthly_disclosure_parse", lambda: import_monthly(db_path))
    if monthly and monthly.get("errors"):
        failed = True
        report["stages"]["monthly_disclosure_parse"]["status"] = "PARTIAL_ERROR"
    financial = stage("financial_report_parse", lambda: import_financial_reports(db_path))
    if financial and financial.get("errors"):
        failed = True
        report["stages"]["financial_report_parse"]["status"] = "PARTIAL_ERROR"
    stage("auditable_derived_baselines", lambda: build_derived_metrics(db_path))
    gate = stage("network_quality_gate", lambda: run_quality_gate(db_path))
    if not gate or gate.get("status") != "PASS":
        failed = True
        report["stages"]["network_quality_gate"]["status"] = "ERROR"

    standard_status = "PARTIAL" if failed else "SUCCEEDED"
    stage(
        "nexus_standard_batch_and_network",
        lambda: export_batch(
            db_path,
            run_status=standard_status,
            compile_network=bool(gate and gate.get("status") == "PASS"),
        ),
    )

    report["finished_at"] = utc_now()
    report["status"] = "FAILED" if failed else "SUCCESS"
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--market-days", type=int, default=30)
    args = parser.parse_args()
    result = run(args.db, args.market_days)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "SUCCESS" else 1)
