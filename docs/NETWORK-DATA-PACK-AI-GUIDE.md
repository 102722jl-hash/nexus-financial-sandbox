# 网络数据包生成指南

## 用途

本文件用于指导 AI 后台在连接用户数据库后，自动发现、校验并生成可导入金融世界沙盒的多表网络数据包。行业不限定为 AI、煤炭或钢铁，也可以是能源、半导体、汽车、银行、医药、产品、地区、项目等系统。

目标流程：

```text
用户数据库
→ 识别表和字段角色
→ 读取网络层定义或生成六层候选
→ 解析节点、指标、实体、关系、公式和证据
→ 校验跨表关联
→ 生成因果网络和完整证据网络
→ 只有已确认关系进入确定性推演
```

## 安全边界

1. 数据库连接必须使用只读事务。
2. 只允许执行元数据查询、样例查询和用户授权范围内的 SELECT。
3. 不执行 INSERT、UPDATE、DELETE、DDL、权限变更或存储过程。
4. 数据库密码不得写入前端状态、LocalStorage、日志、导出文件或模型提示词。
5. 表名、schema 名和列名必须使用数据库驱动提供的标识符转义，不能直接拼接未校验 SQL。
6. 必须使用数据截止时间，禁止用截止时间之后的信息解释此前情景。
7. 不用零值填补缺失数据。
8. AI 只能提出候选映射和候选关系，不能自行确认关系或执行计算。
9. 证据不足时输出 CANDIDATE、NEEDS_HUMAN_REVIEW 或 ABSTAIN，不得伪造精确参数。

## 用户意图优先级

先判断用户选择：

```text
CREATE_NEW_NETWORK    创建独立新网络，不继承当前行业节点
EXTEND_EXISTING       在现有网络中增加已确认节点和关系
REPLACE_EXISTING      用新网络替换当前网络，但保留版本历史
```

网络意图优先于当前页面行业。选择 CREATE_NEW_NETWORK 时，不得把来源数据强行映射为当前行业指标。

## 表角色

优先根据字段签名、注释、样例值和表名识别以下角色：

| 角色 | 推荐表 | 作用 |
|---|---|---|
| REGISTRY | network_registry | 网络名称、版本、状态、截止日 |
| LAYERS | network_layers | 六层标题、顺序和副标题 |
| NODES | network_nodes | 节点定义、基准值、可编辑状态 |
| EDGES | network_edges | 节点之间的传导关系和参数 |
| ENTITIES | entities | 公司、银行、产品、地区或项目 |
| METRICS | metric_values | 实际指标、行业数据和财务数据 |
| FORMULAS | formulas | 确定性公式和参数 |
| EVIDENCE | evidence | 数值和关系的来源 |
| VALUATION | valuation | 当前市值、基准价值和情景价值 |

用户不必提供全部表。缺少某张表时继续处理其他角色，并返回具体缺口。

## 表结构契约

### REGISTRY

```text
network_id
network_name
network_version
network_status          DRAFT / ACTIVE / ARCHIVED
network_kind
data_cutoff
created_at
```

注册表不要求 entity_code 或 report_period。如果同时存在实体或财务字段，不要误判为纯注册表。

### LAYERS

通常每个网络 6 行：

```text
network_id
layer_no                 1～6
layer_code               macro / demand / route / constraint / outcome / entity
layer_name_cn
layer_subtitle_cn
sort_order
```

没有 LAYERS 表时，根据节点名称、描述、指标类型和关系拓扑生成六层候选，并返回 confidence、reason、evidence 和 AI_CANDIDATE 状态。用户确认后保存为网络正式版本。

### NODES

```text
network_id
node_id
layer_no
node_name_cn
node_description
node_type                 DRIVER / METRIC / ROUTE / ENTITY / VALUATION
metric_code
metric_name
metric_type               price / quantity / flow / stock / margin / ratio
unit
currency
baseline_value            数值或 JSON
editable                  true / false
value_status
entity_code
evidence_id
data_cutoff
status
```

兼容别名：

```text
node_id / nodeid / node_code / node_key
node_name_cn / node_name / node_label / label / title
node_description / description
layer_no / layer / node_layer / chain_layer_no
baseline_value / baseline / value
editable
metric_code / metric_name / unit
```

只有 editable=true 且 baseline_value 是有限数值或数值 JSON 的节点才可调整。推荐：

```json
{"BASE": 100, "LOW": 90, "HIGH": 115}
```

### EDGES

```text
network_id
edge_id
source_node_id
target_node_id
direction                 POSITIVE / NEGATIVE / MIXED
relation_type
formula_id
formula_type
weight
lag_days
impact_cap_pct
confidence
mechanism
parameter_status
evidence_id
evidence_source
status
```

兼容别名：

```text
source_node_id / source_node / source_id / from_node / source
target_node_id / target_node / target_id / to_node / target
direction / edge_direction
weight / edge_weight
lag_days / edge_lag_days
confidence / edge_confidence
mechanism / edge_mechanism
status / parameter_status
evidence_source
```

正式传导关系必须满足：

```text
source_node_id 和 target_node_id 均存在
direction 明确
formula_type 或 weight 至少一个可用
mechanism 非空
evidence_id、evidence_source 或已确认的分析师假设至少一个
status = CONFIRMED / ACTIVE / APPROVED
```

DATA_LINEAGE、ENTITY_METRIC、ACCOUNTING_STRUCTURE、CANDIDATE 关系只能进入完整证据图，不能进入确定性传播。

### ENTITIES

```text
network_id
entity_code
entity_name_cn
entity_type                COMPANY / BANK / PRODUCT / REGION / PROJECT / DRUG
industry_code
exchange_code
country
company_model_family
valuation_method
status
```

非公司实体不得强行套用上市公司估值模型。

### METRICS

```text
network_id
metric_value_id
metric_code
node_id
entity_code
value
unit
currency
report_period
announcement_date
opdate
as_of_date
data_cutoff
value_status
evidence_id
```

财务数据必须使用 entity_code + report_period + announcement_date 或 opdate。行业价格、库存、利率和产能可以使用 as_of_date，不强制要求财务报告期。

### FORMULAS

```text
formula_id
formula_type
formula_expression
parameters_json
parameter_status
unit_in
unit_out
lag_days
impact_cap_pct
evidence_id
status
```

推荐公式族：

```text
LINEAR_WEIGHT
PRICE_VOLUME
REVENUE_BRIDGE
MARGIN_BRIDGE
CAPACITY_UTILIZATION
INVENTORY_FLOW
WORKING_CAPITAL
DCF
PE_MULTIPLE
EV_EBITDA
```

没有校准依据的参数标记为 ANALYST_ASSUMPTION。

### EVIDENCE

```text
evidence_id
source_type
source_name
publisher
published_at
original_quote
page_or_locator
source_url
data_cutoff
review_status
```

缺少原文、页码、表格定位或稳定 URL 时，状态为 NEEDS_HUMAN_REVIEW。

### VALUATION

```text
network_id
entity_code
valuation_date
price_asof
close_price
diluted_shares
current_market_cap
net_debt
non_operating_assets
valuation_method
valuation_multiple
discount_rate
terminal_growth
baseline_equity_value
scenario_equity_value
value_change_amount
value_change_pct
upside_downside_pct
data_cutoff
valuation_status
evidence_id
```

没有当前市值、股数、财务桥接或估值参数时输出 DATA_MISSING，不能把归因分数称为公司估值。

## 自动识别和生成流程

### 1. 发现表和字段

读取表名、schema、列名、类型、注释和少量样例。使用结构化字段定位和标识符转义。

### 2. 判断角色

```text
node_id + layer_no/layer + node_name → NODES
source_node_id + target_node_id + weight/direction → EDGES
evidence_id + source_url/original_quote → EVIDENCE
network_id/network_name/status 且无实体财务字段 → REGISTRY
entity_code + value/metric_code → METRICS
formula_id + formula_type/parameters_json → FORMULAS
current_market_cap/valuation_method → VALUATION
```

角色判断返回 confidence 和 reason；不确定时标记 UNKNOWN，不强行归类。

### 3. 按角色校验

每张表只校验本角色字段：

```text
REGISTRY 不要求 report_period
NODES 不要求 announcement_date
EDGES 不要求 entity_code
METRICS 只有财务行才要求 report_period 和公告日期
```

一张表不完整只能将该表标为 INCOMPLETE，不得让其他合格表全部失败。

### 4. 建立关联

优先级：

```text
network_id 关联网络
node_id 关联节点和关系
entity_code 关联实体和指标
metric_code 关联指标和节点
formula_id 关联关系和公式
evidence_id 关联关系、节点、指标和证据
```

必须检查节点 ID 重复、关系引用不存在节点、network_id 混用、单位/币种不一致和数据截止日越界。

### 5. 生成六层

优先级：

```text
1. 使用来源 LAYERS 表
2. 使用节点已有 layer_no 和中文名称
3. AI 根据节点语义和关系拓扑生成六层候选
4. 只有无法判断的层级进入人工确认
```

每层返回 layer_no、layer_code、layer_name_cn、layer_subtitle_cn、node_count、status、confidence 和 reason。标题不得写死为某个行业。

### 6. 生成两个网络视图

```text
causalGraph
→ 已确认、权重有效、处于有效传播路径的节点和边

fullGraph
→ 所有节点、指标、实体、会计结构、数据谱系和候选关系
```

完整图用于审计，因果图用于情景推演，结构连接不能冒充因果传导。

### 7. 确认传播资格

```text
CONFIRMED / ACTIVE / APPROVED
→ 进入确定性计算

CANDIDATE
→ 可以展示和解释，但不能改变下游数值

ABSTAIN
→ 不输出方向或精确数值
```

## 计算规则

简单关系：

```text
target_change
= source_change × direction × weight × time_factor
```

复杂关系调用 formula_id 对应公式，不能由 AI 自由生成结果。每一步记录 edge_id、formula_id、formula_type、inputs、parameters、direction、lag_days、output 和 evidence_ids。

## 缺口和错误处理

以下情况允许降级继续：

```text
缺少 LAYERS 表
缺少部分证据字段
未知字段无法映射
公司没有经营模型
估值数据不足
部分表字段不完整
```

对应状态：

```text
PARTIAL
NEEDS_HUMAN_REVIEW
EXPOSURE_ONLY
COMPANY_ADAPTER_REQUIRED
DATA_MISSING
ABSTAIN
```

只有以下情况阻止网络生成：

```text
没有任何可识别的节点表或节点 JSON
节点 ID 全部为空或重复
所有关系都引用不存在节点
layer_no 无法解析且无法生成候选
公式声明存在但参数完全缺失，且没有可替代的权重
数据源不是只读或无法确认读取权限
```

阻止时返回具体表名、字段名和原因，不能只显示“数据库连接失败”。

## 标准输出

```json
{
  "networkIntent": "CREATE_NEW_NETWORK",
  "networkStatus": "READY|PARTIAL|NEEDS_HUMAN_REVIEW|ABSTAIN",
  "network": {
    "networkId": "N-001",
    "networkName": "自动生成的中文网络名称",
    "networkVersion": "1.0.0",
    "dataCutoff": "2026-09-04"
  },
  "tableRoles": [
    {
      "table": "schema.network_nodes",
      "role": "NODES",
      "status": "READY",
      "rowsRead": 20,
      "missing": []
    }
  ],
  "layers": [],
  "nodes": [],
  "edges": [],
  "entities": [],
  "metricValues": [],
  "formulas": [],
  "evidence": [],
  "causalGraph": {"nodes": [], "edges": []},
  "fullGraph": {"nodes": [], "edges": []},
  "gates": {
    "nodeGate": "PASS|FAIL",
    "edgeGate": "PASS|PARTIAL|ABSTAIN",
    "evidenceGate": "PASS|PARTIAL|NEEDS_HUMAN_REVIEW",
    "valuationGate": "PASS|DATA_MISSING|ABSTAIN"
  },
  "missing": [],
  "warnings": []
}
```

## 前端行为

1. 使用 layers 自动生成六列标题和顺序。
2. 使用 layer_no 对节点重新布局，缩放后保持标题、节点和连线对应。
3. 默认显示 causalGraph，并可切换 fullGraph。
4. 只有 editable=true 且有数值基线的节点显示调节控件。
5. 只有确认边交给确定性引擎。
6. 正向、负向和候选关系使用不同颜色和线型。
7. 点击节点查看输入、单位、期间、来源、公式、证据、置信度和失效条件。
8. 某张表失败时显示具体表名和字段原因，其他成功表仍可生成部分结果。
9. 新网络独立保存，不能覆盖当前网络。

## 最终原则

```text
网络结构可以由 AI 发现
六层标题可以由 AI 生成
字段映射可以由 AI 推荐
关系可以由 AI 提出候选
数值计算必须由确定性引擎执行
正式关系必须经过来源证明或用户确认
```

如果用户只提供普通业务数据，没有明确节点、关系或公式，系统可以生成结构候选网络，但必须标记 EXPOSURE_ONLY 或 ABSTAIN，不能伪装成完成金融因果推演的正式网络。

