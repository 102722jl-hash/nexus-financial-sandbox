from __future__ import annotations

import copy
import json
from pathlib import Path

from crawler_contract import CONTRACT_VERSION, stable_id, validate_crawler_payload


ROOT = Path(__file__).resolve().parent
EXAMPLE = json.loads((ROOT / "v220_crawler_payload.example.json").read_text(encoding="utf-8"))
passed = 0


def check(condition: bool, label: str) -> None:
    global passed
    if not condition:
        raise AssertionError(label)
    passed += 1


report = validate_crawler_payload(EXAMPLE)
check(report["contractVersion"] == CONTRACT_VERSION, "contract version")
check(report["status"] == "ACCEPTED", "example accepted")
check(report["ingestionAllowed"] is True, "example ingestion")
check(report["networkCompilationAllowed"] is True, "example graph")
check(report["readiness"]["dataStatus"] == "DATA_READY", "data ready")
check(report["readiness"]["graphStatus"] == "GRAPH_READY", "graph ready")
check(report["readiness"]["scenarioStatus"] == "SCENARIO_READY", "scenario ready")
check(report["examplePropagationPath"] == ["INPUT_PRICE_INDEX", "OPERATING_COST_INDEX", "PROFIT_MARGIN"], "complete path")
check(all(item["candidateSimulation"] for item in report["normalizedRelations"]), "AI approved defaults to candidate propagation")
check(all(item["causalConclusion"] == "ABSTAIN" for item in report["normalizedRelations"]), "candidate stays abstain")
check(stable_id("DOC", "a", 1) == stable_id("DOC", "a", 1), "stable ID repeatable")
check(stable_id("DOC", "a", 1) != stable_id("DOC", "a", 2), "stable ID distinguishes content")

future = copy.deepcopy(EXAMPLE)
future["observations"][0]["available_at"] = "2026-09-17T00:00:00Z"
future_report = validate_crawler_payload(future)
check(future_report["ingestionAllowed"] is True, "future record is locally quarantined")
check(any(item["objectId"] == "OBS-DEMO-INPUT" for item in future_report["quarantine"]), "future record identified")

unknown_formula = copy.deepcopy(EXAMPLE)
unknown_formula["formulas"][0]["formula_type"] = "EXECUTE_PYTHON"
unknown_formula["formulas"][0]["formula_expression"] = "run arbitrary code"
unknown_formula_report = validate_crawler_payload(unknown_formula)
check(unknown_formula_report["ingestionAllowed"] is True, "unknown formula isolated")
check(any(item["code"] == "FORMULA_NEEDS_REVIEW" for item in unknown_formula_report["quarantine"]), "unknown formula flagged")

missing_endpoint = copy.deepcopy(EXAMPLE)
missing_endpoint["relations"][0]["target_metric_code"] = "NOT_REGISTERED"
missing_endpoint_report = validate_crawler_payload(missing_endpoint)
check(missing_endpoint_report["ingestionAllowed"] is False, "missing endpoint blocks batch")
check(any(item["code"] == "RELATION_ENDPOINT_NOT_FOUND" for item in missing_endpoint_report["blockingIssues"]), "missing endpoint reason")

bad_hash = copy.deepcopy(EXAMPLE)
bad_hash["documents"][0]["content_sha256"] = "bad"
bad_hash_report = validate_crawler_payload(bad_hash)
check(bad_hash_report["ingestionAllowed"] is False, "bad document hash blocks batch")
check(any(item["code"] == "DOCUMENT_SHA256_INVALID" for item in bad_hash_report["blockingIssues"]), "bad hash reason")

duplicate = copy.deepcopy(EXAMPLE)
conflict = copy.deepcopy(duplicate["metric_definitions"][0])
conflict["metric_name"] = "冲突名称"
duplicate["metric_definitions"].append(conflict)
duplicate_report = validate_crawler_payload(duplicate)
check(duplicate_report["ingestionAllowed"] is False, "conflicting duplicate blocks batch")
check(any(item["code"] == "DUPLICATE_ID_CONFLICT" for item in duplicate_report["blockingIssues"]), "duplicate conflict reason")

print(f"V2.20 crawler contract: {passed}/22 passed")
