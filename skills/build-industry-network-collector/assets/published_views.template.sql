BEGIN;

REVOKE ALL ON ALL TABLES IN SCHEMA {{schema}} FROM {{readonly_role}};
GRANT USAGE ON SCHEMA {{schema}} TO {{readonly_role}};

CREATE OR REPLACE VIEW {{schema}}.published_networks AS
SELECT network_id, domain_code, network_name, network_version, network_kind,
       data_cutoff, causal_status, network_status, created_at, updated_at
FROM {{schema}}.network_registry
WHERE network_status IN ('ACTIVE','CANDIDATE');

CREATE OR REPLACE VIEW {{schema}}.published_layers AS
SELECT layer.network_id, layer.layer_no, layer.layer_code, layer.layer_name,
       layer.layer_subtitle, layer.path_role, layer.sort_order
FROM {{schema}}.network_layers AS layer
JOIN {{schema}}.published_networks AS network USING (network_id)
WHERE layer.status='ACTIVE';

CREATE OR REPLACE VIEW {{schema}}.published_nodes AS
SELECT node.network_id, node.node_id, node.layer_no, node.node_name_cn,
       node.node_type, node.metric_code, node.metric_name, node.metric_type,
       node.unit, node.baseline_value, node.editable, node.quality_status,
       node.entity_code, node.evidence_id, node.source_observation_id,
       node.data_cutoff, node.description, node.sort_order, node.status
FROM {{schema}}.network_nodes AS node
JOIN {{schema}}.published_networks AS network USING (network_id)
WHERE node.status IN ('CONFIRMED_DATA','CANDIDATE','DATA_MISSING');

CREATE OR REPLACE VIEW {{schema}}.published_edges AS
SELECT edge.network_id, edge.edge_id, edge.source_node_id, edge.target_node_id,
       edge.direction, edge.relation_type, edge.formula_id, edge.formula_type,
       edge.parameter_status, edge.weight, edge.candidate_weight, edge.lag_days,
       edge.confidence, edge.impact_cap_pct, edge.mechanism, edge.parameters,
       edge.evidence_ids, edge.invalidation, edge.status
FROM {{schema}}.network_edges AS edge
JOIN {{schema}}.published_networks AS network USING (network_id)
WHERE (edge.status='CONFIRMED' AND edge.weight > 0)
   OR (edge.status IN ('AI_APPROVED','CANDIDATE') AND edge.candidate_weight > 0)
   OR (edge.status='CONFIRMED_LINEAGE' AND edge.relation_type IN ('DATA_LINEAGE','ENTITY_METRIC','ACCOUNTING_STRUCTURE'));

CREATE OR REPLACE VIEW {{schema}}.published_metric_values AS
SELECT value.network_id, value.observation_id, value.metric_code, value.entity_code,
       value.value, value.text_value, value.unit, value.currency, value.frequency,
       value.report_period, value.as_of_date, value.published_at, value.available_at,
       value.data_cutoff, value.dimensions, value.revision, value.quality_status,
       value.evidence_id, value.source_table, value.source_column, value.source_row_key
FROM {{schema}}.metric_values AS value
JOIN {{schema}}.published_networks AS network USING (network_id)
WHERE value.quality_status NOT IN ('PENDING_REVIEW','REJECTED');

CREATE OR REPLACE VIEW {{schema}}.published_evidence AS
SELECT DISTINCT evidence.evidence_id, evidence.source_type, evidence.source_tier,
       evidence.published_at, evidence.retrieved_at, evidence.original_quote,
       evidence.locator, evidence.page_number, evidence.table_name,
       evidence.row_label, evidence.column_label, evidence.json_pointer,
       evidence.anchor_at, evidence.temporal_role, evidence.snapshot_sha256,
       evidence.acceptance_status, evidence.acceptance_reason
FROM {{schema}}.evidence AS evidence
WHERE evidence.acceptance_status IN ('ACCEPTED','AI_APPROVED')
  AND (
    EXISTS (SELECT 1 FROM {{schema}}.published_nodes AS node WHERE node.evidence_id=evidence.evidence_id)
    OR EXISTS (SELECT 1 FROM {{schema}}.published_metric_values AS value WHERE value.evidence_id=evidence.evidence_id)
  );

GRANT SELECT ON
  {{schema}}.published_networks,
  {{schema}}.published_layers,
  {{schema}}.published_nodes,
  {{schema}}.published_edges,
  {{schema}}.published_metric_values,
  {{schema}}.published_evidence
TO {{readonly_role}};

COMMIT;
