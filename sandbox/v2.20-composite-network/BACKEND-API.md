# NEXUS V2.20 后端 API

## 爬虫数据契约（V2.20.0）

- `GET /api/contracts/crawler`：返回 `nexus-crawler-batch-1.0.0` 的机器可读 JSON Schema、示例文件名和校验入口。
- `POST /api/contracts/crawler/validate`：在任何数据库写入之前检查网络身份、批次、来源、原始快照、证据、实体、指标、观测、层级、公式和关系。
- `POST /api/contracts/crawler/compile`：通过门禁后确定性生成节点、层级、候选关系和公式，并保存为可在浏览器切换的独立网络。
- 校验响应分别返回 `ingestionAllowed`、`networkCompilationAllowed` 和 `DATA_READY / GRAPH_READY / SCENARIO_READY`。
- `AI_APPROVED` 自动映射为候选可传播关系，使用 `candidate_weight`，并保持 `AI_ASSUMPTION / ABSTAIN`。
- 未来数据、单位冲突、未知公式和局部证据问题进入 `quarantine`；非法哈希、主键冲突、关系端点缺失和非法层级进入 `blockingIssues`。
- 编译后的浏览器方案使用 `networkPlanId` 作为查找 ID，原数据库网络 ID 保存在 `sourceNetworkId`，避免文件存在但网页无法打开。
- 传播方向只写入 `direction`；`weight / candidate_weight` 必须为正数幅度，防止负权重被网页判断为不可传播。

## 复合门禁（V2.20.0）

- `GET /api/version`：返回权威版本号、父版本、默认端口和契约版本。
- `GET /api/sources/:sourceId/diagnostics`：返回画像、映射和表角色的 `DATA_READY` 诊断。
- `GET /api/networks/:networkId/diagnostics`：返回 `DATA_READY / GRAPH_READY / SCENARIO_READY`、传播覆盖、孤立节点、循环、单位和公式告警。
- `POST /api/sources/:sourceId/analyze`：响应增加 `importDiagnostics`。
- `POST /api/sources/:sourceId/sync`：检测到网络定义时响应增加 `networkDiagnostics`。
- `POST /api/network-plans`：网络方案增加 `readiness / qualityReport / compositeContractVersion`。

结构问题只在确实破坏图一致性时阻断激活；未知字段、未知公式和孤立节点局部隔离并保留告警。

## 预编译网络表适配器（V2.19.12）

当选中表包含节点与连线 JSON，或单列完整网络 JSON 时，画像返回 `adapterMode=PRECOMPILED_NETWORK_JSON`。支持 `nodes_json + edges_json`、`network_json / graph_json` 及中文别名；自定义列名还可通过有限样例的 JSON 结构识别，也可在映射页手工指定网络字段角色。

结构签名匹配后，控制字段和标准财务字段自动确认，数值型计算字段自动注册为来源自定义指标；未识别文本才保留审核。同步仍使用只读、转义后的白名单查询，完整 JSON 只在同步阶段读取，并校验节点、六层、端点、方向、权重、滞后、置信度、机制和证据。无效结构以 `PRECOMPILED_NETWORK_INVALID:*` 失败关闭。

通过校验的结构写入 `precompiledNetwork`，创建网络方案时直接生成 `PRECOMPILED_NETWORK`，保留节点、边、六层和显式审核状态。缺少机制或证据的情景边会降级为 `CANDIDATE`，不会自动进入确定性传播。

## AI 语义识别调度（V2.19.10）

- 新网络语义识别固定为 4 字段/批、最多 3 路并发，降低兼容中转站同时拒绝或超时的概率。
- 单批超时限制为 20 至 120 秒，默认 60 秒；较慢的中转站不再被 45 秒硬截断。
- 已命中标准指标或本地财务字段词典的字段不提交 AI；画像样例全空的字段本地标记为 `LOCAL_EMPTY_PROFILE / 建议忽略`。
- 后台任务保留并返回本地候选，`totalFields`、`processedFields`、`localResolvedFields`、`localSuggestedIgnore` 和 `aiQueuedFields` 分别显示路由结果。
- AI 请求使用紧凑 JSON 协议及更小的输出预算；响应仍兼容此前的完整字段格式。
- 批量响应格式错误或遗漏字段时，仅把缺失字段拆成单字段补跑，已成功候选继续保留。
- `GET /api/ai/mapping-jobs/:id` 返回 `batchSize`、`maxWorkers`、`timeoutSeconds`，前端据此显示真实执行策略。
- `TIMEOUT` 不在同一轮自动无限重试；任务以 `PARTIAL` 返回后，用户可执行“重试剩余字段”。

## 生成网络关系审核（V2.19.9）

- `POST /api/network-plans/:id/ai-edge-candidates` 只生成 `CANDIDATE` 关系，写入独立网络图和差异清单。
- `POST /api/network-plans/:id/confirm` 通过 `confirmedEdgeIds` 明确确认关系；未勾选关系不参与传播。
- 已确认、`weight > 0` 且不是 `DATA_LINEAGE`、`ENTITY_METRIC`、`ACCOUNTING_STRUCTURE` 的边构成确定性情景网络。
- 数据谱系与会计结构永远不因为“已确认”而自动成为因果边。
- 数据库列注释可作为待确认中文语义；没有列注释时先查金融字段词典，再交给 AI 候选识别。

The browser talks only to the local connector. It never opens a PostgreSQL/MySQL socket and never calls an AI provider directly.

All `/api/*` routes except `/api/health` require the browser-issued `X-Client-Id` header. This is a local-client gate, not a replacement for deployment-grade user authentication; a hosted deployment must place the connector behind its own identity provider and authorization layer.

## Workspace recovery

GET  /api/workspace

Returns only the current client session's sanitized connection summary, selected tables, mappings, metric-value page and current network plan. It never returns database credentials or AI keys. It restores a browser refresh while the backend process remains running; activated networks are separately persisted.

## Connection and source lifecycle

POST /api/connections/test
POST /api/connections
GET  /api/connections/:id/tables
POST /api/sources/:id/analyze
POST /api/mappings/:id/confirm
POST /api/sources/:id/sync
GET  /api/sources/:id/metric-values
POST /api/sources/:id/cancel

PostgreSQL and MySQL sessions are forced into read-only transactions. Only confirmed field mappings enter generated, parameterized, allowlisted reads. A-share financial tables apply statement-type, announcement-date, opdate, row-limit and pagination gates.

## AI candidate lifecycle

POST /api/ai/sessions/test
POST /api/sources/:id/ai-mapping-candidates
POST /api/sources/:id/ai-mapping-jobs
GET  /api/ai/mapping-jobs/:id
POST /api/network-plans/:id/ai-edge-candidates

OpenAI-compatible and Ollama requests are executed only by the backend. Keys are encrypted in process memory. AI outputs are schema-validated and remain `PENDING_REVIEW / CANDIDATE`; AI never receives database credentials or executes SQL.

For `CREATE_NEW_NETWORK`, the async mapping job performs semantic enrichment. The backend supplies only the structured locator, data type, null/distinct/numeric summary, numeric range and at most five truncated sample values. Password/token/secret-like columns have no sample values. The validated candidate can propose a Chinese display name, description, metric type, unit and one of the four metric layers. It enters the network only after `/api/mappings/:id/confirm`; confirmed nodes retain AI confidence, reason and profile evidence.

## Network plan lifecycle

POST /api/network-plans
GET  /api/network-plans/:id
POST /api/network-plans/:id/confirm
POST /api/network-plans/:id/activate

Passwords are accepted only for the current request or through an environment-variable reference. They are not returned, logged, hashed into task IDs, persisted to disk, or stored in browser state. Connection records contain only sanitized metadata and an in-memory session reference.

## Deterministic sandbox lifecycle

GET  /api/sandbox/nodes
GET  /api/sandbox/edges
POST /api/scenarios
POST /api/scenarios/:id/run
GET  /api/scenarios/:id/results
POST /api/scenarios/:id/explain

Scenario values come from standardized metric values plus the active confirmed network. The explanation endpoint can only describe an existing result and returns `CANDIDATE_EXPLANATION`; it cannot change values, relationships, permissions, or evidence. Without an AI session it returns `AI_NOT_CONNECTED` while deterministic calculations remain available.

## Mock mode

Append ?api=mock to the page URL. mock-adapter.js exposes the same service methods and response envelope as the HTTP client, so the UI can switch to a production API without changing components.
