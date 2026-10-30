PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS network_registry (
  network_id TEXT PRIMARY KEY, network_name TEXT NOT NULL, network_version TEXT NOT NULL,
  network_status TEXT NOT NULL CHECK(network_status IN ('DRAFT','CONFIRMED','ACTIVE','ARCHIVED')),
  network_kind TEXT NOT NULL, data_cutoff TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS network_layers (
  network_id TEXT NOT NULL, layer_no INTEGER NOT NULL CHECK(layer_no BETWEEN 1 AND 6),
  layer_code TEXT NOT NULL, layer_name_cn TEXT NOT NULL, layer_subtitle_cn TEXT,
  semantic_role TEXT, path_role TEXT, description TEXT, sort_order INTEGER,
  status TEXT NOT NULL, confidence REAL, reason TEXT, PRIMARY KEY(network_id, layer_no),
  UNIQUE(network_id, layer_code), FOREIGN KEY(network_id) REFERENCES network_registry(network_id)
);
CREATE TABLE IF NOT EXISTS entities (
  network_id TEXT NOT NULL, entity_code TEXT NOT NULL, entity_name_cn TEXT NOT NULL,
  entity_type TEXT NOT NULL, industry_code TEXT, exchange_code TEXT, country TEXT,
  company_model_family TEXT, valuation_method TEXT, status TEXT NOT NULL,
  PRIMARY KEY(network_id, entity_code), FOREIGN KEY(network_id) REFERENCES network_registry(network_id)
);
CREATE TABLE IF NOT EXISTS evidence (
  evidence_id TEXT PRIMARY KEY, source_type TEXT NOT NULL, source_name TEXT NOT NULL,
  publisher TEXT NOT NULL, published_at TEXT NOT NULL, retrieved_at TEXT NOT NULL,
  original_quote TEXT NOT NULL, locator TEXT NOT NULL, source_url TEXT NOT NULL,
  data_cutoff TEXT NOT NULL, source_tier TEXT NOT NULL CHECK(source_tier IN ('T1','T2','T3','T4')),
  temporal_role TEXT NOT NULL, snapshot_path TEXT, snapshot_sha256 TEXT,
  supports_node_ids TEXT NOT NULL DEFAULT '[]', acceptance_status TEXT NOT NULL,
  acceptance_reason TEXT
);
CREATE TABLE IF NOT EXISTS metric_values (
  network_id TEXT NOT NULL, metric_value_id TEXT PRIMARY KEY, metric_code TEXT NOT NULL,
  node_id TEXT, entity_code TEXT, value REAL, unit TEXT NOT NULL, currency TEXT,
  report_period TEXT, announcement_date TEXT, opdate TEXT, as_of_date TEXT,
  data_cutoff TEXT NOT NULL, value_status TEXT NOT NULL, evidence_id TEXT,
  source_table TEXT, source_column TEXT, source_row_key TEXT,
  FOREIGN KEY(network_id) REFERENCES network_registry(network_id), FOREIGN KEY(evidence_id) REFERENCES evidence(evidence_id)
);
CREATE TABLE IF NOT EXISTS network_nodes (
  network_id TEXT NOT NULL, node_id TEXT NOT NULL, layer_no INTEGER NOT NULL,
  node_name_cn TEXT NOT NULL, node_description TEXT, node_type TEXT NOT NULL,
  metric_code TEXT, metric_name TEXT, metric_type TEXT, unit TEXT, currency TEXT,
  baseline_value TEXT, editable INTEGER NOT NULL DEFAULT 0, value_status TEXT NOT NULL,
  entity_code TEXT, evidence_id TEXT, data_cutoff TEXT NOT NULL, status TEXT NOT NULL,
  PRIMARY KEY(network_id, node_id), FOREIGN KEY(network_id, layer_no) REFERENCES network_layers(network_id, layer_no),
  FOREIGN KEY(entity_code) REFERENCES entities(entity_code), FOREIGN KEY(evidence_id) REFERENCES evidence(evidence_id)
);
CREATE TABLE IF NOT EXISTS formulas (
  network_id TEXT NOT NULL, formula_id TEXT PRIMARY KEY, formula_type TEXT NOT NULL,
  formula_expression TEXT NOT NULL, parameters_json TEXT NOT NULL, formula_version TEXT NOT NULL,
  parameter_status TEXT NOT NULL, unit_in TEXT, unit_out TEXT, lag_days INTEGER,
  impact_cap_pct REAL, invalidation_condition TEXT, evidence_id TEXT, status TEXT NOT NULL,
  FOREIGN KEY(network_id) REFERENCES network_registry(network_id), FOREIGN KEY(evidence_id) REFERENCES evidence(evidence_id)
);
CREATE TABLE IF NOT EXISTS network_edges (
  network_id TEXT NOT NULL, edge_id TEXT NOT NULL, source_node_id TEXT NOT NULL,
  target_node_id TEXT NOT NULL, direction TEXT NOT NULL, relation_type TEXT NOT NULL,
  formula_id TEXT, formula_type TEXT, weight REAL, lag_days INTEGER, impact_cap_pct REAL,
  confidence REAL, mechanism TEXT, parameter_status TEXT, evidence_id TEXT,
  evidence_source TEXT, status TEXT NOT NULL, PRIMARY KEY(network_id, edge_id),
  FOREIGN KEY(formula_id) REFERENCES formulas(formula_id), FOREIGN KEY(evidence_id) REFERENCES evidence(evidence_id)
);
CREATE TABLE IF NOT EXISTS valuation (
  network_id TEXT NOT NULL, entity_code TEXT NOT NULL, valuation_date TEXT NOT NULL,
  price_asof TEXT, close_price REAL, diluted_shares REAL, current_market_cap REAL,
  net_debt REAL, non_operating_assets REAL, valuation_method TEXT, valuation_multiple REAL,
  discount_rate REAL, terminal_growth REAL, baseline_equity_value REAL, scenario_equity_value REAL,
  value_change_amount REAL, value_change_pct REAL, upside_downside_pct REAL,
  data_cutoff TEXT NOT NULL, valuation_status TEXT NOT NULL, evidence_id TEXT,
  PRIMARY KEY(network_id, entity_code, valuation_date)
);
CREATE TABLE IF NOT EXISTS raw_documents (
  document_id TEXT PRIMARY KEY, source_url TEXT NOT NULL, source_name TEXT NOT NULL,
  retrieved_at TEXT NOT NULL, content_type TEXT, http_status INTEGER, content_sha256 TEXT NOT NULL,
  snapshot_path TEXT, parse_status TEXT NOT NULL, error_message TEXT
);
CREATE TABLE IF NOT EXISTS review_queue (
  review_id INTEGER PRIMARY KEY AUTOINCREMENT, object_type TEXT NOT NULL, object_id TEXT NOT NULL,
  candidate_value TEXT, confidence REAL, reason TEXT, evidence_ids TEXT NOT NULL DEFAULT '[]',
  required_action TEXT NOT NULL, review_status TEXT NOT NULL DEFAULT 'PENDING', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS collection_runs (
  run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL,
  source_count INTEGER DEFAULT 0, inserted_count INTEGER DEFAULT 0, skipped_count INTEGER DEFAULT 0,
  error_count INTEGER DEFAULT 0, error_message TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_metric_dedupe ON metric_values(network_id, metric_code, entity_code, report_period, as_of_date, evidence_id);
