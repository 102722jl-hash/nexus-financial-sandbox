BEGIN;

CREATE SCHEMA IF NOT EXISTS nexus;
SET search_path TO nexus, public;

CREATE TABLE IF NOT EXISTS contract_meta (
  contract_version       text PRIMARY KEY,
  product_version        text NOT NULL,
  installed_at           timestamptz NOT NULL DEFAULT now(),
  status                 text NOT NULL CHECK (status IN ('ACTIVE','DEPRECATED','DISABLED'))
);

INSERT INTO contract_meta(contract_version,product_version,status)
VALUES ('nexus-crawler-batch-1.0.0','V2.20.0-composite','ACTIVE')
ON CONFLICT (contract_version) DO UPDATE
SET product_version=excluded.product_version,status=excluded.status;

CREATE TABLE IF NOT EXISTS source_registry (
  source_code            text PRIMARY KEY,
  source_name            text NOT NULL,
  source_type            text NOT NULL CHECK (source_type IN ('WEB','API','CSV','PDF','DATABASE')),
  publisher              text NOT NULL,
  base_url               text NOT NULL,
  source_tier            text NOT NULL CHECK (source_tier IN ('T1','T2','T3','MARKET_PROXY')),
  license_status         text NOT NULL CHECK (license_status IN ('ALLOWED','RESTRICTED','UNKNOWN')),
  robots_policy          text,
  rate_limit_per_minute  integer CHECK (rate_limit_per_minute IS NULL OR rate_limit_per_minute > 0),
  status                 text NOT NULL CHECK (status IN ('ACTIVE','PAUSED','DISABLED')),
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
  batch_id               text PRIMARY KEY,
  contract_version       text NOT NULL REFERENCES contract_meta(contract_version),
  domain_code            text NOT NULL,
  collector_code         text NOT NULL,
  collector_version      text NOT NULL,
  run_type               text NOT NULL CHECK (run_type IN ('DAILY','BACKFILL','MANUAL','REPAIR')),
  started_at             timestamptz NOT NULL,
  completed_at           timestamptz NOT NULL,
  data_cutoff            date NOT NULL,
  status                 text NOT NULL CHECK (status IN ('SUCCEEDED','PARTIAL','FAILED')),
  document_count         integer NOT NULL DEFAULT 0 CHECK (document_count >= 0),
  evidence_count         integer NOT NULL DEFAULT 0 CHECK (evidence_count >= 0),
  observation_count      integer NOT NULL DEFAULT 0 CHECK (observation_count >= 0),
  quarantine_count       integer NOT NULL DEFAULT 0 CHECK (quarantine_count >= 0),
  manifest_sha256        char(64),
  error_summary          jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at             timestamptz NOT NULL DEFAULT now(),
  CHECK (completed_at >= started_at),
  CHECK (manifest_sha256 IS NULL OR manifest_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE IF NOT EXISTS raw_documents (
  document_id            text PRIMARY KEY,
  batch_id               text NOT NULL REFERENCES ingestion_runs(batch_id),
  source_code            text NOT NULL REFERENCES source_registry(source_code),
  source_url             text NOT NULL,
  canonical_url          text NOT NULL,
  title                  text,
  published_at           timestamptz,
  retrieved_at           timestamptz NOT NULL,
  content_type           text NOT NULL,
  http_status            integer NOT NULL CHECK (http_status BETWEEN 100 AND 599),
  content_sha256         char(64) NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
  snapshot_path          text,
  raw_payload            bytea,
  language               text,
  encoding               text,
  etag                   text,
  last_modified          text,
  parser_version         text,
  parse_status           text NOT NULL CHECK (parse_status IN ('FETCHED','PARSED','NEEDS_REVIEW','QUARANTINED','ERROR')),
  error_code             text,
  error_message          text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  CHECK (snapshot_path IS NOT NULL OR raw_payload IS NOT NULL),
  UNIQUE(source_code,canonical_url,published_at,content_sha256)
);

CREATE INDEX IF NOT EXISTS ix_raw_documents_batch ON raw_documents(batch_id);
CREATE INDEX IF NOT EXISTS ix_raw_documents_source_time ON raw_documents(source_code,retrieved_at DESC);

CREATE TABLE IF NOT EXISTS evidence (
  evidence_id            text PRIMARY KEY,
  document_id            text NOT NULL REFERENCES raw_documents(document_id),
  source_type            text NOT NULL,
  source_tier            text NOT NULL CHECK (source_tier IN ('T1','T2','T3','MARKET_PROXY')),
  published_at           timestamptz,
  retrieved_at           timestamptz NOT NULL,
  original_quote         text NOT NULL,
  locator                text NOT NULL,
  page_number            integer CHECK (page_number IS NULL OR page_number > 0),
  table_name             text,
  row_label              text,
  column_label           text,
  json_pointer           text,
  anchor_at              timestamptz NOT NULL,
  temporal_role          text NOT NULL CHECK (temporal_role IN ('SOURCE_FACT','PRE_EVENT','AT_EVENT','POST_EVENT_VALIDATION','UNDATED')),
  snapshot_sha256        char(64) NOT NULL CHECK (snapshot_sha256 ~ '^[0-9a-f]{64}$'),
  acceptance_status      text NOT NULL CHECK (acceptance_status IN ('ACCEPTED','AI_APPROVED','PENDING_REVIEW','REJECTED')),
  acceptance_reason      text NOT NULL,
  reviewed_by            text,
  reviewed_at            timestamptz,
  created_at             timestamptz NOT NULL DEFAULT now(),
  UNIQUE(document_id,locator,snapshot_sha256)
);

CREATE INDEX IF NOT EXISTS ix_evidence_document ON evidence(document_id);
CREATE INDEX IF NOT EXISTS ix_evidence_acceptance ON evidence(acceptance_status);

CREATE TABLE IF NOT EXISTS network_registry (
  network_id             text PRIMARY KEY,
  domain_code            text NOT NULL,
  network_name           text NOT NULL,
  network_version        text NOT NULL,
  schema_version         text NOT NULL DEFAULT 'composite-network-1.0.0',
  network_status         text NOT NULL CHECK (network_status IN ('DRAFT','CANDIDATE','ACTIVE','FROZEN','DISABLED')),
  network_kind           text NOT NULL,
  data_cutoff            date NOT NULL,
  causal_status          text NOT NULL DEFAULT 'ABSTAIN' CHECK (causal_status IN ('ABSTAIN','CONDITIONAL','IDENTIFIED')),
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  UNIQUE(domain_code,network_version)
);

CREATE TABLE IF NOT EXISTS network_layers (
  network_id             text NOT NULL REFERENCES network_registry(network_id),
  layer_no               integer NOT NULL CHECK (layer_no > 0),
  layer_code             text NOT NULL,
  layer_name             text NOT NULL,
  layer_subtitle         text,
  path_role              text NOT NULL CHECK (path_role IN ('SOURCE','INTERMEDIATE','SINK','EVIDENCE_ONLY')),
  sort_order             integer NOT NULL,
  status                 text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','DISABLED')),
  PRIMARY KEY(network_id,layer_no),
  UNIQUE(network_id,layer_code)
);

CREATE TABLE IF NOT EXISTS entities (
  network_id             text NOT NULL REFERENCES network_registry(network_id),
  entity_code            text NOT NULL,
  entity_name            text NOT NULL,
  entity_type            text NOT NULL CHECK (entity_type IN ('COMPANY','INDUSTRY','COMMODITY','REGION','MACRO','POLICY','MARKET')),
  parent_entity_code     text,
  stock_code             text,
  exchange_code          text,
  industry_code          text,
  country                text,
  currency               char(3),
  aliases                jsonb NOT NULL DEFAULT '[]'::jsonb,
  valid_from             date,
  valid_to               date,
  status                 text NOT NULL CHECK (status IN ('ACTIVE','INACTIVE','MERGED','DELISTED')),
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(network_id,entity_code),
  FOREIGN KEY(network_id,parent_entity_code) REFERENCES entities(network_id,entity_code),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);

CREATE TABLE IF NOT EXISTS metric_definitions (
  network_id             text NOT NULL REFERENCES network_registry(network_id),
  metric_code            text NOT NULL,
  metric_name            text NOT NULL,
  aliases                jsonb NOT NULL DEFAULT '[]'::jsonb,
  description            text NOT NULL DEFAULT '',
  metric_type            text NOT NULL CHECK (metric_type IN ('FLOW','STOCK','PRICE','RATIO','AMOUNT','COUNT','INDEX','TEXT_SIGNAL')),
  canonical_unit         text NOT NULL,
  unit_family            text NOT NULL CHECK (unit_family IN ('CURRENCY','COUNT','MASS','ENERGY','POWER','PERCENT','PRICE','INDEX','TEXT','OTHER')),
  frequency              text NOT NULL CHECK (frequency IN ('REALTIME','DAILY','WEEKLY','MONTHLY','QUARTERLY','ANNUAL','EVENT')),
  entity_scope           text NOT NULL CHECK (entity_scope IN ('GLOBAL','INDUSTRY','ENTITY','COMPANY','REGION','COMMODITY')),
  default_layer_code     text NOT NULL,
  editable_default       boolean NOT NULL DEFAULT false,
  aggregation_method     text,
  value_min              numeric,
  value_max              numeric,
  currency_policy        text,
  required_for_network   boolean NOT NULL DEFAULT false,
  contract_version       text NOT NULL DEFAULT 'nexus-crawler-batch-1.0.0' REFERENCES contract_meta(contract_version),
  status                 text NOT NULL CHECK (status IN ('ACTIVE','DEPRECATED','DISABLED')),
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(network_id,metric_code),
  FOREIGN KEY(network_id,default_layer_code) REFERENCES network_layers(network_id,layer_code),
  CHECK (value_max IS NULL OR value_min IS NULL OR value_max >= value_min)
);

CREATE TABLE IF NOT EXISTS metric_values (
  network_id             text NOT NULL REFERENCES network_registry(network_id),
  observation_id         text PRIMARY KEY,
  batch_id               text NOT NULL REFERENCES ingestion_runs(batch_id),
  metric_code            text NOT NULL,
  entity_code            text,
  value                  numeric,
  text_value             text,
  unit                   text NOT NULL,
  currency               char(3),
  frequency              text NOT NULL,
  report_period          text,
  as_of_date             date NOT NULL,
  published_at           timestamptz,
  available_at           timestamptz NOT NULL,
  data_cutoff            date NOT NULL,
  dimensions             jsonb NOT NULL DEFAULT '{}'::jsonb,
  revision               integer NOT NULL DEFAULT 1 CHECK (revision > 0),
  quality_status         text NOT NULL CHECK (quality_status IN ('SOURCE_FACT','REPORTED_ACTUAL','MARKET_PROXY','AI_EXTRACTED','CALCULATED_LINEAGE','PENDING_REVIEW','REJECTED')),
  evidence_id            text NOT NULL REFERENCES evidence(evidence_id),
  source_table           text,
  source_column          text,
  source_row_key         text NOT NULL,
  created_at             timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY(network_id,metric_code) REFERENCES metric_definitions(network_id,metric_code),
  FOREIGN KEY(network_id,entity_code) REFERENCES entities(network_id,entity_code),
  CHECK ((value IS NOT NULL) <> (text_value IS NOT NULL)),
  CHECK (available_at < (data_cutoff + 1)::timestamp AT TIME ZONE 'UTC')
);

CREATE INDEX IF NOT EXISTS ix_metric_values_lookup
  ON metric_values(network_id,metric_code,entity_code,as_of_date DESC,available_at DESC);
CREATE INDEX IF NOT EXISTS ix_metric_values_batch ON metric_values(batch_id);

CREATE TABLE IF NOT EXISTS formulas (
  network_id             text NOT NULL REFERENCES network_registry(network_id),
  formula_id             text NOT NULL,
  formula_name           text,
  formula_type           text NOT NULL,
  formula_expression     text NOT NULL,
  parameters             jsonb NOT NULL DEFAULT '{}'::jsonb,
  input_unit_family      text,
  output_unit_family     text,
  formula_version        text NOT NULL DEFAULT '1.0.0',
  parameter_status       text NOT NULL CHECK (parameter_status IN ('CALIBRATED','HUMAN_CONFIRMED','CALCULATED_LINEAGE','AI_ASSUMPTION','MISSING')),
  causal_conclusion      text NOT NULL CHECK (causal_conclusion IN ('ABSTAIN','CONDITIONAL','IDENTIFIED')),
  evidence_ids           jsonb NOT NULL DEFAULT '[]'::jsonb,
  invalidation           text,
  status                 text NOT NULL CHECK (status IN ('ACTIVE','NEEDS_REVIEW','DISABLED')),
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(network_id,formula_id)
);

CREATE TABLE IF NOT EXISTS network_nodes (
  network_id             text NOT NULL REFERENCES network_registry(network_id),
  node_id                text NOT NULL,
  layer_no               integer NOT NULL,
  node_name_cn           text NOT NULL,
  node_type              text NOT NULL,
  metric_code            text NOT NULL,
  metric_name            text NOT NULL,
  metric_type            text NOT NULL,
  unit                   text NOT NULL,
  baseline_value         numeric,
  editable               boolean NOT NULL DEFAULT false,
  quality_status         text NOT NULL,
  entity_code            text,
  evidence_id            text REFERENCES evidence(evidence_id),
  source_observation_id  text REFERENCES metric_values(observation_id),
  data_cutoff            date NOT NULL,
  description            text,
  sort_order             integer NOT NULL DEFAULT 0,
  status                 text NOT NULL CHECK (status IN ('CONFIRMED_DATA','CANDIDATE','DATA_MISSING','DISABLED')),
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(network_id,node_id),
  FOREIGN KEY(network_id,layer_no) REFERENCES network_layers(network_id,layer_no),
  FOREIGN KEY(network_id,metric_code) REFERENCES metric_definitions(network_id,metric_code),
  FOREIGN KEY(network_id,entity_code) REFERENCES entities(network_id,entity_code)
);

CREATE TABLE IF NOT EXISTS network_edges (
  network_id             text NOT NULL REFERENCES network_registry(network_id),
  edge_id                text NOT NULL,
  source_node_id         text NOT NULL,
  target_node_id         text NOT NULL,
  direction              text NOT NULL CHECK (direction IN ('positive','negative','mixed')),
  relation_type          text NOT NULL,
  formula_id             text NOT NULL,
  formula_type           text NOT NULL,
  parameter_status       text NOT NULL CHECK (parameter_status IN ('CALIBRATED','HUMAN_CONFIRMED','CALCULATED_LINEAGE','AI_ASSUMPTION','MISSING')),
  weight                 numeric,
  candidate_weight       numeric,
  lag_days               integer NOT NULL DEFAULT 0 CHECK (lag_days >= 0),
  confidence             numeric NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  impact_cap_pct         numeric,
  mechanism              text NOT NULL,
  parameters             jsonb NOT NULL DEFAULT '{}'::jsonb,
  evidence_ids           jsonb NOT NULL DEFAULT '[]'::jsonb,
  invalidation           text,
  status                 text NOT NULL CHECK (status IN ('CONFIRMED','AI_APPROVED','CANDIDATE','NEEDS_HUMAN_REVIEW','DISABLED')),
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(network_id,edge_id),
  FOREIGN KEY(network_id,source_node_id) REFERENCES network_nodes(network_id,node_id),
  FOREIGN KEY(network_id,target_node_id) REFERENCES network_nodes(network_id,node_id),
  FOREIGN KEY(network_id,formula_id) REFERENCES formulas(network_id,formula_id),
  CHECK (
    (status='CONFIRMED' AND weight > 0)
    OR (status IN ('AI_APPROVED','CANDIDATE','NEEDS_HUMAN_REVIEW') AND candidate_weight > 0)
    OR status='DISABLED'
  )
);

CREATE INDEX IF NOT EXISTS ix_network_edges_source ON network_edges(network_id,source_node_id);
CREATE INDEX IF NOT EXISTS ix_network_edges_target ON network_edges(network_id,target_node_id);

CREATE TABLE IF NOT EXISTS quarantine (
  quarantine_id          bigserial PRIMARY KEY,
  batch_id               text REFERENCES ingestion_runs(batch_id),
  object_type            text NOT NULL,
  object_id              text NOT NULL,
  reason_code            text NOT NULL,
  severity               text NOT NULL CHECK (severity IN ('WARNING','BLOCKING')),
  payload_json           jsonb NOT NULL,
  created_at             timestamptz NOT NULL DEFAULT now(),
  resolved_at            timestamptz,
  resolution             text,
  status                 text NOT NULL CHECK (status IN ('OPEN','RESOLVED','IGNORED')),
  UNIQUE(batch_id,object_type,object_id,reason_code)
);

CREATE TABLE IF NOT EXISTS network_versions (
  network_id             text NOT NULL REFERENCES network_registry(network_id),
  version_id             text NOT NULL,
  parent_version_id      text,
  source_batch_ids_json  jsonb NOT NULL,
  mapping_version        text NOT NULL,
  formula_registry_version text NOT NULL,
  graph_sha256           char(64) NOT NULL CHECK (graph_sha256 ~ '^[0-9a-f]{64}$'),
  readiness_json         jsonb NOT NULL,
  quality_report_json    jsonb NOT NULL,
  activation_status      text NOT NULL CHECK (activation_status IN ('CANDIDATE','ACTIVE','REJECTED','ROLLED_BACK')),
  created_at             timestamptz NOT NULL DEFAULT now(),
  activated_at           timestamptz,
  PRIMARY KEY(network_id,version_id)
);

CREATE OR REPLACE VIEW latest_metric_values AS
SELECT DISTINCT ON (network_id,metric_code,entity_code,dimensions)
  *
FROM metric_values
WHERE quality_status NOT IN ('REJECTED','PENDING_REVIEW')
ORDER BY network_id,metric_code,entity_code,dimensions,as_of_date DESC,available_at DESC,revision DESC;

COMMIT;
