from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any


SPEC_VERSION = "industry-network-spec-1.1.0"
SUPPORTED_SPEC_VERSIONS = {"industry-network-spec-1.0.0", SPEC_VERSION}
PUBLIC_VIEWS = {
    "published_networks",
    "published_layers",
    "published_nodes",
    "published_edges",
    "published_metric_values",
    "published_evidence",
}
SAFE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{1,62}$")
METRIC_CODE = re.compile(r"^[A-Z][A-Z0-9_]{1,95}$")
TIMEZONE_NAME = re.compile(r"^(?:UTC|[A-Za-z_]+(?:/[A-Za-z0-9_+.-]+)+)$")
DISPLAY_VERSION_FORMATS = {"YYYY-MM-DD", "YYYY-MM-DD HH:mm", "YYYY-MM-DD HH:mm:ss"}


def issue(code: str, path: str, message: str, severity: str = "BLOCKING") -> dict[str, str]:
    return {"code": code, "path": path, "message": message, "severity": severity}


def required(item: dict[str, Any], fields: tuple[str, ...], path: str, errors: list[dict[str, str]]) -> None:
    missing = [name for name in fields if item.get(name) is None or item.get(name) == ""]
    if missing:
        errors.append(issue("REQUIRED_FIELDS_MISSING", path, ", ".join(missing)))


def duplicate_values(items: list[dict[str, Any]], field: str) -> list[str]:
    counts = Counter(str(item.get(field) or "") for item in items)
    return sorted(key for key, count in counts.items() if key and count > 1)


def contains_plain_secret(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            normalized = str(key).lower()
            if normalized in {"password", "password_value", "api_key", "token", "secret", "client_secret"} and item not in (None, ""):
                found.append(child)
            found.extend(contains_plain_secret(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(contains_plain_secret(item, f"{path}[{index}]"))
    return found


def has_complete_path(metrics: dict[str, dict[str, Any]], relations: list[dict[str, Any]], layers: dict[str, dict[str, Any]]) -> bool:
    starts = {code for code, metric in metrics.items() if metric.get("editable_default") is True and metric.get("selection") != "EXCLUDE"}
    sinks = {code for code, metric in metrics.items() if (layers.get(str(metric.get("default_layer_code"))) or {}).get("path_role") == "SINK"}
    adjacency: dict[str, set[str]] = defaultdict(set)
    for relation in relations:
        if relation.get("status") != "DISABLED":
            adjacency[str(relation.get("source_metric_code"))].add(str(relation.get("target_metric_code")))
    queue = deque(starts)
    visited = set(starts)
    while queue:
        source = queue.popleft()
        for target in adjacency.get(source, set()):
            if target in sinks:
                return True
            if target not in visited:
                visited.add(target)
                queue.append(target)
    return False


def validate_spec(spec: Any) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if not isinstance(spec, dict):
        return {"status": "REJECTED", "valid": False, "blockingIssues": [issue("SPEC_NOT_OBJECT", "$", "Specification must be a JSON object.")], "warnings": []}
    spec_version = str(spec.get("spec_version") or "")
    if spec_version not in SUPPORTED_SPEC_VERSIONS:
        errors.append(issue("SPEC_VERSION_UNSUPPORTED", "$.spec_version", f"Expected one of {sorted(SUPPORTED_SPEC_VERSIONS)}."))
    is_v11 = spec_version == SPEC_VERSION
    sections = ["domain", "network", "data_requirements", "sources", "schedule", "database", "publication"]
    if is_v11:
        sections.append("history")
    for section in sections:
        expected = list if section == "sources" else dict
        if not isinstance(spec.get(section), expected):
            errors.append(issue("SECTION_INVALID", f"$.{section}", f"{section} must be {expected.__name__}."))

    secret_paths = contains_plain_secret(spec)
    if secret_paths:
        errors.append(issue("PLAINTEXT_SECRET_FORBIDDEN", "$", ", ".join(secret_paths)))

    domain = spec.get("domain") if isinstance(spec.get("domain"), dict) else {}
    required(domain, ("domain_code", "domain_name", "market_scope"), "$.domain", errors)

    network = spec.get("network") if isinstance(spec.get("network"), dict) else {}
    required(network, ("network_name", "network_kind", "outcomes", "layers", "relations"), "$.network", errors)
    if is_v11:
        required(network, ("entity_node_policy", "company_metric_instantiation", "missing_value_policy", "structural_relation_type"), "$.network", errors)
        expected_network_policies = {
            "entity_node_policy": "EXPLICIT_WHEN_IN_SCOPE",
            "company_metric_instantiation": "ALL_ACTIVE_ENTITIES",
            "missing_value_policy": "KEEP_NODE_AS_DATA_MISSING",
            "structural_relation_type": "ENTITY_METRIC",
        }
        for field, expected in expected_network_policies.items():
            if network.get(field) != expected:
                errors.append(issue("NETWORK_POLICY_INVALID", f"$.network.{field}", f"Expected {expected}."))
    layers_list = network.get("layers") if isinstance(network.get("layers"), list) else []
    relations = network.get("relations") if isinstance(network.get("relations"), list) else []
    if duplicate_values(layers_list, "layer_code"):
        errors.append(issue("DUPLICATE_LAYER_CODE", "$.network.layers", "Layer codes must be unique."))
    if duplicate_values(layers_list, "layer_no"):
        errors.append(issue("DUPLICATE_LAYER_NUMBER", "$.network.layers", "Layer numbers must be unique."))
    layers = {str(item.get("layer_code")): item for item in layers_list if item.get("layer_code")}
    roles = {item.get("path_role") for item in layers_list}
    if not {"SOURCE", "SINK"}.issubset(roles):
        errors.append(issue("SOURCE_AND_SINK_LAYERS_REQUIRED", "$.network.layers", "At least one SOURCE and one SINK layer are required."))

    requirements = spec.get("data_requirements") if isinstance(spec.get("data_requirements"), dict) else {}
    metrics_list = requirements.get("metrics") if isinstance(requirements.get("metrics"), list) else []
    if duplicate_values(metrics_list, "metric_code"):
        errors.append(issue("DUPLICATE_METRIC_CODE", "$.data_requirements.metrics", "Metric codes must be unique."))
    metrics = {str(item.get("metric_code")): item for item in metrics_list if item.get("metric_code")}
    for index, metric in enumerate(metrics_list):
        path = f"$.data_requirements.metrics[{index}]"
        required(metric, ("metric_code", "metric_name", "selection", "metric_type", "canonical_unit", "unit_family", "frequency", "entity_scope", "default_layer_code", "editable_default", "required_for_network"), path, errors)
        if metric.get("metric_code") and not METRIC_CODE.fullmatch(str(metric["metric_code"])):
            errors.append(issue("METRIC_CODE_INVALID", path + ".metric_code", "Use uppercase letters, digits, and underscores."))
        if metric.get("selection") not in {"REQUIRED", "OPTIONAL", "PROXY_ALLOWED", "EXCLUDE"}:
            errors.append(issue("METRIC_SELECTION_INVALID", path + ".selection", "Invalid selection."))
        if metric.get("default_layer_code") not in layers:
            errors.append(issue("METRIC_LAYER_NOT_FOUND", path + ".default_layer_code", "Metric layer is not declared."))

    for index, relation in enumerate(relations):
        path = f"$.network.relations[{index}]"
        required(relation, ("relation_code", "source_metric_code", "target_metric_code", "direction", "formula_type", "parameter_status", "status", "mechanism"), path, errors)
        if relation.get("source_metric_code") not in metrics or relation.get("target_metric_code") not in metrics:
            errors.append(issue("RELATION_ENDPOINT_NOT_FOUND", path, "Both endpoints must reference declared metrics."))
        if relation.get("direction") not in {"positive", "negative", "mixed"}:
            errors.append(issue("RELATION_DIRECTION_INVALID", path + ".direction", "Invalid direction."))
        status = relation.get("status")
        weight = relation.get("weight") if status == "CONFIRMED" else relation.get("candidate_weight")
        if status in {"CONFIRMED", "AI_APPROVED", "CANDIDATE"} and (not isinstance(weight, (int, float)) or isinstance(weight, bool) or weight <= 0):
            errors.append(issue("POSITIVE_WEIGHT_REQUIRED", path, "Weight must be a positive magnitude; use direction for sign."))

    sources = spec.get("sources") if isinstance(spec.get("sources"), list) else []
    if duplicate_values(sources, "source_code"):
        errors.append(issue("DUPLICATE_SOURCE_CODE", "$.sources", "Source codes must be unique."))
    mapped_metrics: set[str] = set()
    for index, source in enumerate(sources):
        path = f"$.sources[{index}]"
        required(source, ("source_code", "source_name", "publisher", "base_url", "source_type", "source_tier", "license_status", "metric_codes", "primary"), path, errors)
        for code in source.get("metric_codes") or []:
            if code not in metrics:
                errors.append(issue("SOURCE_METRIC_NOT_FOUND", path + ".metric_codes", str(code)))
            mapped_metrics.add(str(code))
        if source.get("license_status") == "UNKNOWN":
            warnings.append(issue("SOURCE_LICENSE_UNCONFIRMED", path + ".license_status", "Confirm usage rights before scheduling.", "WARNING"))
    derived_targets = {str(item.get("target_metric_code")) for item in relations}
    for code, metric in metrics.items():
        if metric.get("selection") == "REQUIRED" and code not in mapped_metrics and code not in derived_targets:
            errors.append(issue("REQUIRED_METRIC_WITHOUT_SOURCE_OR_FORMULA", f"$.data_requirements.metrics[{code}]", code))

    schedule = spec.get("schedule") if isinstance(spec.get("schedule"), dict) else {}
    required(schedule, ("frequency", "timezone", "workdays_only", "holiday_policy", "retry_count", "revision_policy", "notification_policy", "retention_days"), "$.schedule", errors)
    if schedule.get("frequency") in {"DAILY", "WEEKLY", "MONTHLY"} and not schedule.get("local_time"):
        errors.append(issue("SCHEDULE_TIME_REQUIRED", "$.schedule.local_time", "Scheduled collection needs a local time."))

    if is_v11:
        history = spec.get("history") if isinstance(spec.get("history"), dict) else {}
        required(history, ("append_observations", "preserve_revisions", "company_history_enabled", "company_history_windows_days", "change_comparison_key", "change_comparison_rule"), "$.history", errors)
        if history.get("append_observations") is not True or history.get("preserve_revisions") is not True:
            errors.append(issue("HISTORY_PRESERVATION_REQUIRED", "$.history", "Observations and revisions must be preserved."))
        windows = history.get("company_history_windows_days")
        if history.get("company_history_enabled") is True:
            if not isinstance(windows, list) or not windows or any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in windows) or len(windows) != len(set(windows)) or 0 not in windows:
                errors.append(issue("COMPANY_HISTORY_WINDOWS_INVALID", "$.history.company_history_windows_days", "Use unique non-negative day windows and include 0 for all history."))
        if set(history.get("change_comparison_key") or []) != {"entity_code", "metric_code"}:
            errors.append(issue("CHANGE_COMPARISON_KEY_INVALID", "$.history.change_comparison_key", "Changes must be partitioned by entity_code and metric_code."))
        if history.get("change_comparison_rule") != "PREVIOUS_VALID_OBSERVATION":
            errors.append(issue("CHANGE_COMPARISON_RULE_INVALID", "$.history.change_comparison_rule", "Use PREVIOUS_VALID_OBSERVATION."))

    database = spec.get("database") if isinstance(spec.get("database"), dict) else {}
    required(database, ("engine", "database_name", "schema_name", "writer_role", "readonly_role", "credential_policy", "writer_password_ref", "readonly_password_ref", "readonly_objects"), "$.database", errors)
    if database.get("engine") != "POSTGRESQL":
        errors.append(issue("POSTGRESQL_REQUIRED", "$.database.engine", "This skill's publication contract requires PostgreSQL."))
    for field in ("schema_name", "writer_role", "readonly_role"):
        value = str(database.get(field) or "")
        if value and not SAFE_IDENTIFIER.fullmatch(value):
            errors.append(issue("DATABASE_IDENTIFIER_INVALID", f"$.database.{field}", value))
    if database.get("writer_role") == database.get("readonly_role"):
        errors.append(issue("DATABASE_ROLES_MUST_DIFFER", "$.database", "Writer and readonly roles must differ."))
    if database.get("credential_policy") not in {"AUTO_GENERATE_LOCAL", "USER_ENV", "SECRET_MANAGER"}:
        errors.append(issue("CREDENTIAL_POLICY_INVALID", "$.database.credential_policy", "Invalid credential policy."))
    readonly = set(database.get("readonly_objects") or [])
    if readonly != PUBLIC_VIEWS:
        errors.append(issue("READONLY_OBJECTS_INVALID", "$.database.readonly_objects", "Readonly must expose exactly the six published views."))

    publication = spec.get("publication") if isinstance(spec.get("publication"), dict) else {}
    if is_v11:
        required(publication, ("publication_mode", "preview_required_gates", "scenario_required_gates", "required_baseline_coverage_threshold", "auto_publish_graph_preview", "auto_publish_to_network_list", "auto_switch_current_network", "preserve_old_versions", "candidate_causal_status", "display_version_timezone", "display_version_format"), "$.publication", errors)
        mode = publication.get("publication_mode")
        if mode not in {"TIERED_PREVIEW", "FULL_GATES_ONLY"}:
            errors.append(issue("PUBLICATION_MODE_INVALID", "$.publication.publication_mode", "Use TIERED_PREVIEW or FULL_GATES_ONLY."))
        preview_gates = set(publication.get("preview_required_gates") or [])
        scenario_gates = set(publication.get("scenario_required_gates") or [])
        if not {"DATA_READY", "GRAPH_READY", "SCENARIO_READY"}.issubset(scenario_gates):
            errors.append(issue("READINESS_GATES_INCOMPLETE", "$.publication.scenario_required_gates", "Scenario publication requires all three readiness gates."))
        if mode == "TIERED_PREVIEW" and ("GRAPH_READY" not in preview_gates or publication.get("auto_publish_graph_preview") is not True):
            errors.append(issue("GRAPH_PREVIEW_POLICY_INVALID", "$.publication", "Tiered preview requires GRAPH_READY and auto_publish_graph_preview=true."))
        if mode == "FULL_GATES_ONLY" and publication.get("auto_publish_graph_preview") is not False:
            errors.append(issue("GRAPH_PREVIEW_POLICY_INVALID", "$.publication.auto_publish_graph_preview", "FULL_GATES_ONLY must disable graph preview publication."))
        threshold = publication.get("required_baseline_coverage_threshold")
        if not isinstance(threshold, (int, float)) or isinstance(threshold, bool) or not 0 < threshold <= 1:
            errors.append(issue("BASELINE_COVERAGE_THRESHOLD_INVALID", "$.publication.required_baseline_coverage_threshold", "Use a ratio greater than 0 and at most 1."))
        timezone_name = str(publication.get("display_version_timezone") or "")
        if not TIMEZONE_NAME.fullmatch(timezone_name):
            errors.append(issue("DISPLAY_TIMEZONE_INVALID", "$.publication.display_version_timezone", "Use UTC or an IANA-style timezone such as Asia/Shanghai."))
        if publication.get("display_version_format") not in DISPLAY_VERSION_FORMATS:
            errors.append(issue("DISPLAY_VERSION_FORMAT_INVALID", "$.publication.display_version_format", f"Use one of {sorted(DISPLAY_VERSION_FORMATS)}."))
    else:
        required(publication, ("required_gates", "auto_publish_to_network_list", "auto_switch_current_network", "preserve_old_versions", "candidate_causal_status"), "$.publication", errors)
        if not {"DATA_READY", "GRAPH_READY", "SCENARIO_READY"}.issubset(set(publication.get("required_gates") or [])):
            errors.append(issue("READINESS_GATES_INCOMPLETE", "$.publication.required_gates", "All three readiness gates are required."))
    if publication.get("auto_publish_to_network_list") is not True or publication.get("auto_switch_current_network") is not False or publication.get("preserve_old_versions") is not True:
        errors.append(issue("PUBLICATION_POLICY_INVALID", "$.publication", "Publish to the list, preserve old versions, and never auto-switch."))
    if publication.get("candidate_causal_status") != "ABSTAIN":
        errors.append(issue("CANDIDATE_CAUSAL_STATUS_INVALID", "$.publication.candidate_causal_status", "Candidate relationships must remain ABSTAIN."))

    if metrics and relations and layers and not has_complete_path(metrics, relations, layers):
        errors.append(issue("NO_EDITABLE_TO_SINK_PATH", "$.network", "No complete adjustable-to-result path exists."))

    return {
        "specVersion": spec_version or SPEC_VERSION,
        "status": "REJECTED" if errors else ("READY_WITH_WARNINGS" if warnings else "READY"),
        "valid": not errors,
        "counts": {"layers": len(layers_list), "metrics": len(metrics_list), "sources": len(sources), "relations": len(relations)},
        "blockingIssues": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an industry network project specification.")
    parser.add_argument("spec", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    report = validate_spec(spec)
    body = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.write_text(body + "\n", encoding="utf-8")
    print(body)
    return 0 if report["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
