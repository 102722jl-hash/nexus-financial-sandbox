export type ApiState = 'loading' | 'ready' | 'empty' | 'error' | 'permission_denied' | 'partial';
export type MappingStatus = 'UNRESOLVED' | 'PENDING_REVIEW' | 'CONFIRMED' | 'IGNORED' | 'REJECTED';
export type SourceStatus = 'CONNECTED' | 'PROFILED' | 'SYNCED' | 'QUARANTINED';

export interface ApiEnvelope<T> {
  state: ApiState;
  data?: T;
  error?: { code: string; message: string; retryable?: boolean };
  requestId: string;
}

export interface DatabaseConnectionInput {
  type: 'postgresql' | 'mysql';
  host: string;
  port: number;
  database: string;
  user: string;
  password?: string;
  credentialRef?: string;
  schema: string;
  sslmode: string;
  tables?: string[];
}

export interface Connection {
  id: string;
  type: DatabaseConnectionInput['type'];
  host: string;
  port: number;
  database: string;
  schema: string;
  user: string;
  readOnly: boolean;
  credentialPersisted: false;
}

export interface TableInfo {
  name: string;
  schema: string;
  selected?: boolean;
}

export interface ConnectionTestResult {
  status: 'CONNECTION_TESTED';
  readOnly: true;
  credentialPersisted: false;
  connection: Connection;
  tables: TableInfo[];
  summary: Record<string, string | number | boolean | null>;
}

export interface MetricMapping {
  mappingId: string;
  sourceField: string;
  sourceColumn: string;
  metricCode: string;
  status: MappingStatus;
  confidence: number;
  reason: string;
  evidence: string[];
  candidateSource: 'RULE' | 'RULE_UNRESOLVED' | 'CUSTOM_NUMERIC' | 'TABLE_ADAPTER' | 'LOCAL_PREFILTER' | 'AI' | 'AI_CACHE' | 'AI_SEMANTIC' | 'AI_SEMANTIC_CACHE' | 'MANUAL';
  sourceLocator?: { database: string; schema: string; table: string; column: string | null };
  databaseName?: string; schemaName?: string; tableName?: string; columnName?: string;
  valueMode?: 'CONSTANT' | 'SYNC_CUTOFF' | 'ROW_HASH';
  constantValue?: string | null;
  metricDefinition?: MetricDefinition;
  semanticStatus?: 'CANDIDATE' | 'CONFIRMED';
  semanticConfidence?: number;
  semanticDescription?: string;
  sampleSummary?: { sampleNonNull: number; numericSampleRate: number; distinctSampleCount: number; numericMin: number | null; numericMax: number | null; sampleValues: Array<string | number | boolean> };
}

export interface MetricDefinition { metricCode: string; metricName: string; metricType: string; unit?: string | null; networkLayer?: 'demand' | 'route' | 'constraint' | 'chain'; description?: string; sourceDefined?: boolean; semanticSource?: 'AI_CANDIDATE' | 'AI_CONFIRMED_BY_USER' }

export interface MetricValue {
  metricValueId: string; metricCode: string; metricName: string; entityCode: string; value: number;
  unit: string | null; currency: string | null; reportPeriod: string; announcementDate: string | null;
  dataCutoff: string; sourceId: string; sourceTable: string; sourceColumn: string; sourceRowKey: string;
  valueStatus: 'REPORTED_ACTUAL' | 'MANAGEMENT_GUIDANCE' | 'CONSENSUS_EXPECTATION' | 'CALIBRATED_PARAMETER' | 'ANALYST_ASSUMPTION' | 'CALCULATED_RESULT';
  evidenceId: string; version: string; opdate: string | null;
}

export interface SyncResult {
  sourceId: string; status: 'SYNCED' | 'PARTIAL'; rowsRead: number; acceptedRows: number; rejectedRows: number;
  rejectionReasons: Record<string, number>; metricValuesCreated: number; cutoffStatus: string;
  sourceSnapshotId: string; evidenceIds: string[]; formalReady: false;
  tableRoles?: Array<{ table: string; role: string; rowsRead: number; status: "READY" | "INCOMPLETE" | "SKIPPED" | "NEEDS_MAPPING" | "ERROR"; missing: string[] }>;
}

export interface NetworkPlan {
  networkPlanId: string; sourceId: string; domainId: string; status: 'PENDING_REVIEW' | 'CONFIRMED' | 'ACTIVE';
  mode: 'EXTEND_EXISTING' | 'REPLACE_EXISTING' | 'CREATE_NEW_NETWORK';
  networkKind: 'DOMAIN_OVERLAY' | 'FINANCIAL_DISCLOSURE_NETWORK' | 'SOURCE_DEFINED_NETWORK';
  networkName: string;
  outputLevel?: 'L1' | 'L2' | 'L3' | 'EXPOSURE_ONLY' | 'ABSTAIN';
  causalStatus: 'ABSTAIN';
  layerLabels?: Array<{ id: string; label: string; subtitle: string }>;
  graph?: { nodes: SandboxNode[]; edges: SandboxEdge[] };
  diff: { addedNodes: SandboxNode[]; updatedNodes: SandboxNode[]; removedNodes: SandboxNode[]; sharedNodes: string[];
    unavailableNodes: SandboxNode[]; addedEdges: SandboxEdge[]; removedEdges: SandboxEdge[]; evidenceGaps: string[]; companyAdapterGaps: unknown[] };
}

export interface AiSessionInput { provider: 'openai-compatible' | 'ollama'; baseUrl: string; model: string; apiKey?: string; timeoutSeconds: number }
export interface AiSessionResult { status: 'CONNECTED' | 'AUTH_FAILED' | 'MODEL_NOT_FOUND' | 'RATE_LIMITED' | 'NETWORK_ERROR' | 'TIMEOUT' | 'INVALID_RESPONSE'; modelsVisible?: number; detail?: string }

export interface SourceAnalysisResult {
  sourceId: string;
  status: 'PROFILED';
  summary: Record<string, string | number | boolean | null>;
  mappings: MetricMapping[];
  profile: Array<Record<string, string | number | boolean | null>>;
  selectedTables?: string[];
  tableAdapters?: TableAdapter[];
  profileProgress?: { completed: number; total: number };
}

export interface WorkspaceRestore {
  status: 'READY' | 'EMPTY';
  source: null | { sourceId: string; connectionId?: string; sourceType: string; status: SourceStatus; networkIntent?: NetworkPlan['mode']; selectedTables?: string[]; tableAdapters?: TableAdapter[]; dataCutoff?: string; snapshotId?: string };
  connection: Connection | null;
  mappings: MetricMapping[];
  metricCatalog: MetricDefinition[];
  metricValues: MetricValue[];
  metricValueTotal: number;
  plan: NetworkPlan | null;
  activePlanId?: string | null;
  aiSessionConnected: boolean;
  credentialPersisted: false;
}
export interface TableAdapter {
  adapterId: string; databaseName: string; schemaName: string; tableName: string;
  qualifiedDisplay: string; identifierMode: 'DRIVER_ESCAPED'; sourceFieldMode: 'STRUCTURED_LOCATOR';
  profileStatus: 'READY'; columnCount: number; syncMode: 'MAPPED_POINT_IN_TIME';
  reportPeriodHint: string | null; reportPeriodSource: 'SOURCE_COLUMN' | 'INFERRED_FROM_TABLE_NAME' | 'MISSING';
  availableDateMode: 'SOURCE_COLUMN' | 'SYNC_CUTOFF'; temporalStatus: 'SOURCE_CONTROL_FIELDS' | 'PENDING_REVIEW';
}

export interface SandboxNode {
  nodeId: string;
  layer: string;
  label: string;
  value?: number | null;
  unit?: string;
  source?: string;
  status?: 'CONFIRMED' | 'CONFIRMED_DATA' | 'EXPOSURE_ONLY' | 'COMPANY_ADAPTER_REQUIRED';
  sub?: string;
  entityCode?: string;
  metricCodes?: string[];
  baseline?: Record<string, number>;
  evidenceIds?: string[];
  description?: string;
  semanticSource?: string;
  semanticConfidence?: number;
  semanticReason?: string;
}

export interface SandboxEdge {
  sourceNodeId: string;
  targetNodeId: string;
  direction: 'positive' | 'negative' | 'mixed';
  weight: number;
  lagDays: number;
  confidence: number;
  mechanism: string;
  evidenceSource: string | null;
  status: 'CONFIRMED' | 'CONFIRMED_LINEAGE' | 'CONFIRMED_STRUCTURE' | 'CANDIDATE' | 'UNAVAILABLE';
  relationType?: 'DATA_LINEAGE' | 'ACCOUNTING_STRUCTURE' | 'ENTITY_METRIC' | 'CAUSAL';
}

export interface ScenarioChange {
  metricCode: string;
  changePercent: number;
  durationMonths: number;
}

export interface ScenarioResult {
  affectedNodes: Array<{
    nodeId: string;
    changePercent: number;
    confidence: number;
    reason: string;
  }>;
  affectedEdges: string[];
  summary: string;
  status: 'CALCULATED' | 'PARTIAL' | 'ABSTAIN';
}

export interface ScenarioExplanationResult {
  scenarioId: string;
  status: 'CANDIDATE_EXPLANATION';
  explanation: string;
  confidence: number;
  reason: string;
  evidence: string[];
  formalReady: false;
}
