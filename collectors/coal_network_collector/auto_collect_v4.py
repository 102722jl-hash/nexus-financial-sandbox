"""Authoritative collection, calculation, multi-path graph and package refresh."""
import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ai_judge_v3 import run as ai_review
from announcement_discovery_fixed import COMPANIES, discover, download_pending
from build_edges_v4 import build as build_edges
from build_nodes_v3 import build as build_nodes
from calculated_metrics_v3 import run as calculate_metrics
from collector import seed
from company_announcements import import_pending
from contract_registry_v1 import ensure as ensure_contract
from complete_contract import build_baselines, build_valuation, install_evidence_defaults
from deep_report_metrics_v3 import run as extract_deep_reports
from enrich_financials import run as enrich_financials
from export_package_v2 import export
from import_snapshots import run as import_public
from manifest_v2 import build as build_manifest
from nce_public import run as collect_nce
from project_state_v2 import sync_cutoff
from network_quality_gate_v1 import run as quality_gate
from share_capital import run as complete_market_cap
from sina_market_fixed import run as collect_market
from source_adapters import acquire_all
from validate_v3 import validate

ROOT = Path(__file__).parent
DB = ROOT / "coal_network.db"


def stage(results, name, function):
    try:
        results[name] = function()
    except Exception as exc:
        results[name] = {"status": "ERROR", "error": str(exc)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--skip-market", action="store_true")
    parser.add_argument("--db", default=str(DB))
    args = parser.parse_args()
    path = Path(args.db)
    db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript((ROOT / "complete_schema.sql").read_text(encoding="utf-8"))
    seed(db)
    results_contract = ensure_contract(db)
    results = {
        "pipelineVersion": "4.0-multi-path-database",
        "mode": "offline" if args.offline else "online",
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "contract_registry": results_contract,
    }
    if not args.offline:
        stage(results, "public_acquisition", lambda: acquire_all(db))
        stage(results, "nce_public", lambda: collect_nce(db))
        stage(results, "announcement_discovery", lambda: {code: len(discover(db, code)) for code in COMPANIES})
        stage(results, "announcement_download", lambda: download_pending(db))
        if not args.skip_market:
            stage(results, "market_proxy", lambda: collect_market(db))
    stage(results, "public_parse", lambda: import_public(db))
    stage(results, "company_parse", lambda: import_pending(db))
    stage(results, "legacy_financial_enrichment", lambda: enrich_financials(db))
    stage(results, "deep_report_metrics", lambda: extract_deep_reports(db))
    install_evidence_defaults(db)
    db.execute(
        """UPDATE evidence SET
        page_or_locator=coalesce(nullif(page_or_locator,''),locator),
        anchor_at=coalesce(anchor_at,data_cutoff),
        declared_role=coalesce(declared_role,case when temporal_role='POST_EVENT_VALIDATION'
          then 'POST_EVENT_VALIDATION' else 'AS_OF_EVIDENCE' end),
        review_status=case when acceptance_status='ACCEPTED' then 'ACCEPTED' else review_status end"""
    )
    results["valuation_rows_added"] = build_valuation(db)
    stage(results, "market_cap", lambda: complete_market_cap(db))
    stage(results, "calculated_metrics", lambda: calculate_metrics(db))
    results["baseline_nodes_updated"] = build_baselines(db)
    stage(results, "nodes", lambda: build_nodes(db))
    stage(results, "edges", lambda: build_edges(db))
    stage(results, "ai_review", lambda: ai_review(db))
    stage(results, "quality_gate", lambda: quality_gate(db))
    results["data_cutoff"] = sync_cutoff(db)
    db.commit()
    db.close()
    results["manifest"] = build_manifest(path)
    results["validation"] = validate(path)
    results["export"] = export(path)
    results["finishedAt"] = datetime.now(timezone.utc).isoformat()
    report = ROOT / "auto_collect_v4_report.json"
    report.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    failed = [
        name for name, value in results.items()
        if isinstance(value, dict)
        and (value.get("status") == "ERROR" or value.get("errors"))
    ]
    raise SystemExit(1 if failed or results["validation"]["errors"] else 0)


if __name__ == "__main__":
    main()
