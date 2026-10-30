# 多行业金融世界沙盒设计修订 V1.1

> 本文是 `financial-world-sandbox-multi-industry-design.md` 的修订补充，不覆盖 V1.0。
>
> 修订重点：估值定义、通用估值模板、已确认产品决策和下一阶段设计边界。

## 1. 已确认决策

以下三项作为第一阶段约束：

```text
部署：静态沙盒 + 本地数据连接器
AI：用户自带 API，可选本地模型
数据源：MySQL、PostgreSQL、CSV、Excel、SQLite
```

第四项“首批多行业范围”仍处于讨论状态，不在本版本中冻结。当前建议继续使用：

```text
已完成示范：焦煤—钢铁
第一候选扩展：AI 基础设施
跨行业验证候选：新能源汽车
后续规范化：银行、医药
```

第五项先完成设计文档，不立即实现完整在线平台或本地连接器。

## 2. 估值术语修订

原设计中的“估值贡献”不能作为公司估值使用。它只能表示模型中不同因素对结果的归因分数。正式展示必须拆分为市场事实、模型估值和情景差异。

### 2.1 四类核心结果

```text
当前市值
→ 基准情景股权价值
→ 冲击后情景股权价值
→ 情景价值变化
→ 相对当前市值空间
```

示例：

```text
当前市值：8,000 亿元
基准情景股权价值：8,300 亿元
冲击后股权价值：7,600 亿元
情景价值变化：-700 亿元 / -8.4%
相对当前市值空间：-5.0%
```

### 2.2 定义和数据等级

| 字段 | 定义 | 数据性质 |
|---|---|---|
| `current_market_cap` | 当前股价 × 稀释后股数 | 市场事实，必须有日期 |
| `baseline_equity_value` | 无冲击或基准情景下的模型股权价值 | 计算结果 |
| `scenario_equity_value` | 冲击情景下的模型股权价值 | 计算结果 |
| `scenario_value_change` | 情景股权价值 − 基准股权价值 | 计算结果 |
| `scenario_value_change_pct` | 情景价值变化 / 基准股权价值 | 计算结果 |
| `upside_downside_vs_market` | 情景股权价值 / 当前市值 − 1 | 计算结果 |
| `valuation_method` | DCF、P/E、EV/EBITDA 等 | 模型配置 |
| `valuation_currency` | 估值金额币种 | 数据契约 |
| `valuation_as_of` | 当前市值和模型估值的日期或截止日 | 时间契约 |

“当前市值”不能由模型推断，必须来自可核验的股价、稀释后股数和交易日期。缺少其中任一项时，不得输出相对市值空间。

### 2.3 企业价值到股权价值

适用于以 EBITDA 或 EV/EBITDA 为基础的公司：

```text
情景企业价值
= 情景 EBITDA × 情景 EV / EBITDA

情景股权价值
= 情景企业价值
− 净负债
+ 非经营性资产
− 少数股东权益
```

其中：

```text
净负债 = 有息负债 − 现金及现金等价物
```

每一项都必须声明币种、期间、来源和是否为合并口径。

### 2.4 DCF 模板

对现金流相对稳定、CapEx 和营运资本可以取得的公司，允许使用 DCF：

```text
企业价值
= 预测期 FCF 现值 + 终值现值

终值
= 终期 FCF × (1 + g) / (WACC − g)

股权价值
= 企业价值 − 净负债 + 非经营性资产 − 少数股东权益
```

DCF 必须记录：

- 预测期长度；
- 每期收入、EBITDA、税、CapEx、营运资本和 FCF；
- WACC；
- 永续增长率 `g`；
- 终值占企业价值比例；
- 净负债和非经营性资产；
- 各项数据截止时间和证据 ID。

### 2.5 P/E 模板

适用于净利润口径稳定、资本结构差异较小的公司：

```text
情景股权价值
= 情景净利润 × 情景 P / E
```

必须说明：

- 使用历史、行业还是可比公司倍数；
- 倍数的日期和样本；
- 是否使用前瞻或静态净利润；
- 是否包含周期高点或低点调整；
- 净利润是否为归母口径。

### 2.6 EV / EBITDA 模板

适用于资本结构、折旧和税制差异较大的公司：

```text
情景企业价值
= 情景 EBITDA × 情景 EV / EBITDA
情景股权价值
= 情景企业价值 − 净负债 + 非经营性资产 − 少数股东权益
```

煤炭、钢铁、化工、制造等周期行业优先考虑 EV/EBITDA 或区间 DCF，不应只用单一 P/E。

## 3. 通用估值模板建议

不要为每个行业写一套完全不同的页面。使用同一个估值接口，由公司适配器选择方法：

```json
{
  "valuation_method": "EV_EBITDA",
  "market_fact": {
    "price": 0,
    "price_date": "YYYY-MM-DD",
    "diluted_shares": 0,
    "market_cap": 0,
    "currency": "CNY"
  },
  "baseline": {
    "revenue": 0,
    "ebitda": 0,
    "fcf": 0,
    "net_debt": 0,
    "non_operating_assets": 0,
    "minority_interest": 0,
    "multiple": 0
  },
  "scenario": {
    "revenue": 0,
    "ebitda": 0,
    "fcf": 0,
    "net_debt": 0,
    "non_operating_assets": 0,
    "minority_interest": 0,
    "multiple": 0
  },
  "output": {
    "baseline_equity_value": 0,
    "scenario_equity_value": 0,
    "scenario_value_change": 0,
    "scenario_value_change_pct": 0,
    "upside_downside_vs_market": 0
  }
}
```

### 3.1 方法选择规则

```text
FCF、WACC、CapEx 和营运资本数据完整
    → DCF 或 DCF 区间

EBITDA 和净负债完整，但 FCF 不稳定
    → EV / EBITDA

归母净利润稳定，可比倍数有可靠样本
    → P / E

关键财务数据缺失
    → L1 / L2 / EXPOSURE_ONLY / ABSTAIN
```

公司可以同时运行两种方法，但必须并列展示，不得把不同方法悄悄混成一个综合分数：

```text
DCF：7,600 亿元
EV / EBITDA：7,850 亿元
P / E：7,420 亿元
方法区间：7,420–7,850 亿元
```

### 3.2 估值桥接必须可回加

公司页面固定展示：

```text
当前市值
基准情景企业价值
基准情景股权价值
冲击后企业价值
冲击后股权价值
情景价值变化
相对当前市值空间
```

同时保留驱动归因，但名称改为：

```text
收入变化归因
利润率变化归因
CapEx / FCF 归因
净负债归因
估值倍数归因
```

“估值贡献”只作为内部计算字段或归因分解标签，不能单独作为公司估值展示。

## 4. 多行业通用模板修订建议

通用模板应固定“语义位置”，不固定“业务名称”：

```text
固定：宏观、需求、生产 / 业务路线、约束、价值池、公司
可变：每层具体节点、边、指标、模型和估值方法
```

每个行业包必须声明：

```json
{
  "domain_id": "coal-steel",
  "layers": [],
  "required_nodes": [],
  "optional_nodes": [],
  "model_families": [],
  "valuation_methods": ["DCF", "EV_EBITDA", "PE"],
  "fallback_policy": {
    "missing_required_node": "DOWNGRADE_OUTPUT",
    "missing_market_cap": "ABSTAIN_UPSIDE_DOWNside",
    "missing_evidence": "NEEDS_HUMAN_REVIEW"
  }
}
```

公司适配器不要求每家公司拥有所有节点，只要求声明：

```text
MATCHED：进入完整公式
PARTIAL：进入区间或方向判断
UNAVAILABLE：从公式删除并降级
CONFLICTED：隔离
```

这样一个行业包可以容纳纯煤企、综合煤企、钢铁、特钢和焦化企业，而不用人为补齐不适用节点。

## 5. 页面和交互修订

顶部摘要不再使用“行业估值指数”作为公司价值替代。建议显示：

```text
当前市值覆盖率
可计算内在价值公司数
情景价值上升公司数
情景价值下降公司数
最大价值变化金额
最大相对市值空间
```

公司排序默认提供两种模式：

```text
按情景价值变化金额排序
按相对当前市值空间排序
```

二者不能混为一个排名，因为大市值公司和小市值公司的金额变化不可直接比较。

每个估值数字旁边显示：

```text
数值类型：MARKET_FACT / CALCULATED_RESULT
估值方法：DCF / EV_EBITDA / PE
日期：YYYY-MM-DD
币种：CNY / USD
数据状态：REPORTED_ACTUAL / ANALYST_ASSUMPTION
```

## 6. 估值数据门禁

### 当前市值门禁

必须同时具备：

- 股价；
- 股价日期；
- 稀释后股数；
- 股数日期；
- 币种；
- 股票代码；
- 来源和原文或稳定行情定位。

缺少股价或稀释后股数时：

```text
允许展示财务模型结果
禁止展示相对当前市值空间
状态：MARKET_CAP_DATA_MISSING
```

### 内在价值门禁

必须具备：

- 至少一种可解释估值方法；
- 基准和情景的关键输入；
- 净负债或明确说明不适用；
- 倍数、WACC 或终值假设；
- 输入、公式、参数和证据 lineage。

缺少关键输入时不输出精确金额，可降级为区间、方向或 `ABSTAIN`。

### 因果边界

即使情景价值下降，也只能表述为：

```text
在当前情景和参数下，模型股权价值较基准下降。
```

不能表述为：

```text
焦煤价格下降导致公司市值下降。
```

除非严格因果门禁达到 `IDENTIFIED`，否则继续显示 `ABSTAIN`。

## 7. 实施边界

本修订只冻结设计，不立即实现在线 API 平台或完整本地连接器。后续实现顺序：

```text
1. 修改通用结果契约，替换“估值贡献指数”字段
2. 在焦煤—钢铁领域包中加入当前市值和估值快照结构
3. 为五家公司选择可用的 DCF / EV_EBITDA / PE 方法
4. 增加估值门禁和缺失状态
5. 修改公司视图、排序和导出结构
6. 用 AI 基础设施领域包验证同一估值接口
7. 再实现本地数据连接器
```

## 8. 验收标准修订

- 当前市值与模型股权价值在 UI 中明确区分；
- 当前市值必须带股价日期和稀释后股数来源；
- 基准股权价值与情景股权价值均可复算；
- 情景价值变化可以用金额和百分比表示；
- 相对当前市值空间不在缺少市场事实时显示；
- 每家公司可以使用不同估值方法；
- 估值方法、倍数、WACC、净负债和非经营性资产可追溯；
- “估值贡献”仅作为归因字段，不作为公司估值标题；
- 资产、负债、币种、期间和股本口径不混用；
- 数据不足时降级，不伪造精确金额；
- 因果状态非 `IDENTIFIED` 时结论仍为 `ABSTAIN`；
- 该设计不改变 V2.8 基线和既有独立实验版本。

## 9. 第一阶段推荐输出格式

```json
{
  "company_id": "601088.SH",
  "company_name": "中国神华",
  "market_fact": {
    "market_cap": null,
    "price_date": null,
    "status": "MARKET_CAP_DATA_MISSING"
  },
  "valuation": {
    "method": "EV_EBITDA",
    "baseline_equity_value": null,
    "scenario_equity_value": null,
    "scenario_value_change": null,
    "upside_downside_vs_market": null,
    "status": "NEEDS_HUMAN_REVIEW"
  },
  "attribution": {
    "revenue": null,
    "margin": null,
    "fcf": null,
    "multiple": null
  },
  "causal": {
    "status": "NOT_IDENTIFIED",
    "conclusion": "ABSTAIN"
  }
}
```

这份结构允许先完成模型设计，再逐步补入真实市值、股数、倍数和估值输入，不会因为当前数据库缺少行情字段而强行生成“目标价”。
