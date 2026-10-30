PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS network_registry(
  network_id TEXT PRIMARY KEY, network_name TEXT NOT NULL, network_version TEXT NOT NULL,
  network_status TEXT NOT NULL, network_kind TEXT NOT NULL, data_cutoff TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS network_layers(
  network_id TEXT NOT NULL, layer_no INTEGER NOT NULL, layer_code TEXT NOT NULL,
  layer_name_cn TEXT NOT NULL, path_role TEXT NOT NULL, sort_order INTEGER NOT NULL,
  status TEXT NOT NULL, PRIMARY KEY(network_id,layer_no),
  UNIQUE(network_id,layer_code),
  FOREIGN KEY(network_id) REFERENCES network_registry(network_id)
);
CREATE TABLE IF NOT EXISTS entities(
  network_id TEXT NOT NULL, entity_code TEXT NOT NULL, entity_name_cn TEXT NOT NULL,
  entity_type TEXT NOT NULL, exchange_code TEXT, country TEXT NOT NULL,
  business_model TEXT NOT NULL, status TEXT NOT NULL,
  PRIMARY KEY(network_id,entity_code),
  FOREIGN KEY(network_id) REFERENCES network_registry(network_id)
);
CREATE TABLE IF NOT EXISTS metric_definitions(
  metric_code TEXT PRIMARY KEY, metric_name_cn TEXT NOT NULL, layer_no INTEGER NOT NULL,
  metric_type TEXT NOT NULL, canonical_unit TEXT NOT NULL, entity_scope TEXT NOT NULL,
  editable_default INTEGER NOT NULL, required_for_network INTEGER NOT NULL,
  description TEXT NOT NULL, contract_version TEXT NOT NULL, status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS edge_templates(
  template_id TEXT PRIMARY KEY, source_metric_code TEXT NOT NULL,
  target_metric_code TEXT NOT NULL, scope TEXT NOT NULL, formula_type TEXT NOT NULL,
  formula_expression TEXT NOT NULL, required_inputs_json TEXT NOT NULL,
  relation_type TEXT NOT NULL, parameter_status TEXT NOT NULL,
  mechanism TEXT NOT NULL, contract_version TEXT NOT NULL, status TEXT NOT NULL,
  FOREIGN KEY(source_metric_code) REFERENCES metric_definitions(metric_code),
  FOREIGN KEY(target_metric_code) REFERENCES metric_definitions(metric_code)
);
CREATE TABLE IF NOT EXISTS raw_documents(
  document_id TEXT PRIMARY KEY, source_url TEXT NOT NULL, source_name TEXT NOT NULL,
  retrieved_at TEXT NOT NULL, content_type TEXT, http_status INTEGER,
  content_sha256 TEXT NOT NULL, snapshot_path TEXT, parse_status TEXT NOT NULL,
  error_message TEXT
);
CREATE TABLE IF NOT EXISTS evidence(
  evidence_id TEXT PRIMARY KEY, source_type TEXT NOT NULL, source_name TEXT NOT NULL,
  publisher TEXT NOT NULL, published_at TEXT NOT NULL, retrieved_at TEXT NOT NULL,
  original_quote TEXT NOT NULL, locator TEXT NOT NULL, source_url TEXT NOT NULL,
  anchor_at TEXT NOT NULL, data_cutoff TEXT NOT NULL, source_tier TEXT NOT NULL,
  temporal_role TEXT NOT NULL, snapshot_path TEXT, snapshot_sha256 TEXT,
  supports_node_ids TEXT NOT NULL DEFAULT '[]', acceptance_status TEXT NOT NULL,
  acceptance_reason TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metric_values(
  network_id TEXT NOT NULL, metric_value_id TEXT PRIMARY KEY, metric_code TEXT NOT NULL,
  entity_code TEXT, value REAL, unit TEXT NOT NULL, currency TEXT,
  report_period TEXT, published_at TEXT, as_of_date TEXT, data_cutoff TEXT NOT NULL,
  value_status TEXT NOT NULL, evidence_id TEXT NOT NULL, source_table TEXT NOT NULL,
  source_row_key TEXT NOT NULL,
  FOREIGN KEY(network_id) REFERENCES network_registry(network_id),
  FOREIGN KEY(metric_code) REFERENCES metric_definitions(metric_code),
  FOREIGN KEY(evidence_id) REFERENCES evidence(evidence_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_nev_metric_dedupe
  ON metric_values(network_id,metric_code,entity_code,report_period,as_of_date,evidence_id);
CREATE TABLE IF NOT EXISTS formulas(
  network_id TEXT NOT NULL, formula_id TEXT PRIMARY KEY, template_id TEXT NOT NULL,
  formula_type TEXT NOT NULL, formula_expression TEXT NOT NULL,
  parameters_json TEXT NOT NULL, parameter_status TEXT NOT NULL,
  causal_conclusion TEXT NOT NULL, status TEXT NOT NULL,
  FOREIGN KEY(network_id) REFERENCES network_registry(network_id),
  FOREIGN KEY(template_id) REFERENCES edge_templates(template_id)
);
CREATE TABLE IF NOT EXISTS network_nodes(
  network_id TEXT NOT NULL, node_id TEXT NOT NULL, layer_no INTEGER NOT NULL,
  node_name_cn TEXT NOT NULL, node_type TEXT NOT NULL, metric_code TEXT NOT NULL,
  metric_name TEXT NOT NULL, metric_type TEXT NOT NULL, unit TEXT NOT NULL,
  baseline_value TEXT, editable INTEGER NOT NULL, value_status TEXT NOT NULL,
  entity_code TEXT, evidence_id TEXT, data_cutoff TEXT NOT NULL, status TEXT NOT NULL,
  PRIMARY KEY(network_id,node_id),
  FOREIGN KEY(network_id,layer_no) REFERENCES network_layers(network_id,layer_no),
  FOREIGN KEY(metric_code) REFERENCES metric_definitions(metric_code),
  FOREIGN KEY(network_id,entity_code) REFERENCES entities(network_id,entity_code),
  FOREIGN KEY(evidence_id) REFERENCES evidence(evidence_id)
);
CREATE TABLE IF NOT EXISTS network_edges(
  network_id TEXT NOT NULL, edge_id TEXT NOT NULL, template_id TEXT NOT NULL,
  source_node_id TEXT NOT NULL, target_node_id TEXT NOT NULL, direction TEXT NOT NULL,
  relation_type TEXT NOT NULL, formula_id TEXT NOT NULL, formula_type TEXT NOT NULL,
  parameter_status TEXT NOT NULL, confidence REAL NOT NULL, mechanism TEXT NOT NULL,
  parameters_json TEXT NOT NULL, status TEXT NOT NULL,
  PRIMARY KEY(network_id,edge_id),
  FOREIGN KEY(template_id) REFERENCES edge_templates(template_id),
  FOREIGN KEY(network_id,source_node_id) REFERENCES network_nodes(network_id,node_id),
  FOREIGN KEY(network_id,target_node_id) REFERENCES network_nodes(network_id,node_id),
  FOREIGN KEY(formula_id) REFERENCES formulas(formula_id)
);
CREATE TABLE IF NOT EXISTS quarantine(
  quarantine_id INTEGER PRIMARY KEY AUTOINCREMENT, object_type TEXT NOT NULL,
  object_id TEXT NOT NULL, reason_code TEXT NOT NULL, payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL, status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS announcement_catalogue(
  announcement_id TEXT PRIMARY KEY, network_id TEXT NOT NULL, entity_code TEXT NOT NULL, title TEXT NOT NULL,
  published_ms INTEGER, pdf_url TEXT NOT NULL, discovered_at TEXT NOT NULL,
  document_id TEXT, status TEXT NOT NULL, error_message TEXT,
  FOREIGN KEY(network_id,entity_code) REFERENCES entities(network_id,entity_code)
);
CREATE TABLE IF NOT EXISTS discovery_runs(
  discovery_id TEXT PRIMARY KEY, query_url TEXT NOT NULL, entity_code TEXT NOT NULL,
  queried_at TEXT NOT NULL, result_count INTEGER, status TEXT NOT NULL,
  error_message TEXT
);
CREATE TABLE IF NOT EXISTS scenario_runs(
  run_id TEXT PRIMARY KEY, network_id TEXT NOT NULL, entity_code TEXT NOT NULL,
  created_at TEXT NOT NULL, status TEXT NOT NULL, input_json TEXT NOT NULL,
  engine_version TEXT NOT NULL,
  FOREIGN KEY(network_id,entity_code) REFERENCES entities(network_id,entity_code)
);
CREATE TABLE IF NOT EXISTS scenario_values(
  run_id TEXT NOT NULL, network_id TEXT NOT NULL, node_id TEXT NOT NULL,
  metric_code TEXT NOT NULL, entity_code TEXT, value REAL, unit TEXT,
  calculation_status TEXT NOT NULL, formula_id TEXT, trace_json TEXT NOT NULL,
  PRIMARY KEY(run_id,node_id),
  FOREIGN KEY(run_id) REFERENCES scenario_runs(run_id),
  FOREIGN KEY(network_id,node_id) REFERENCES network_nodes(network_id,node_id)
);
