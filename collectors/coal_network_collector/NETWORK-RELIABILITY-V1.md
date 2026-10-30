# 网络采集与传导可靠性 V1

## 目标

每次更新经过采集、字段校验、证据固化、节点编译、关系编译、场景计算、质量门禁、数据库发布八个阶段。结构错误不覆盖上一版。

## 入口

~~~text
auto_collect_v4.py
  → contract_registry_v1.py
  → deep_report_metrics_v3.py
  → calculated_metrics_v3.py
  → build_nodes_v3.py
  → build_edges_v4.py
  → ai_judge_v3.py
  → network_quality_gate_v1.py
  → validate_v3.py
  → package_export
~~~

`metric_definitions` 保存指标名称、层级、单位、可编辑性和必需性；`network_edge_templates` 保存允许的上下游关系和公式族。新增字段先登记契约，再允许生成节点。

每日任务入口是 `scheduled_publish_database_v2.ps1`，已切换到 V4，并在 PostgreSQL 同步前执行校验。

## 状态边界

- `SOURCE_FACT`：有来源、原文、定位和 T1/T2 证据的事实。
- `MARKET_PROXY`：行情代理，不能替代财报事实。
- `CALCULATED`：由已有指标计算，并保留 `calculated_metric_lineage`。
- `AI_ASSUMPTION`：候选关系参数；允许进入候选网络，但因果结论保持 `ABSTAIN`。

缺失值保持缺失，不以 0 填充。

## 场景计算

`scenario_engine_v1.py` 只执行受控公式族，并按依赖顺序重算。输入缺失、公式不支持、循环或单位不匹配时返回 `BLOCKED_*`，不会沿用旧下游值。

~~~powershell
python scenario_engine_v1.py `
  --entity 600795.SH `
  --override STANDARD_COAL_PRICE=900 `
  --override PLANT_USE_RATE=5
~~~

结果写入 `scenario_result.json`，可持久化到 `scenario_runs`、`scenario_values`，并记录输入、基线、公式编号和计算轨迹。

## 质量门禁

~~~powershell
python network_quality_gate_v1.py
python validate_v3.py
~~~

门禁检查必要表、外键、证据、单位、重复冲突、节点层级、悬空关系、公式血缘，以及改变变量后下游是否真的重算。

只有 `errors=[]` 才允许同步 PostgreSQL。警告表示候选参数仍需校准，不代表正式因果结论。

## 当前边界

- 部分关系仍是 `AI_ASSUMPTION`，尚未历史校准。
- 旧季度记录保留用于审计，当前节点基线优先使用深度页级解析和正确报告期。
- 公司缺少火电分部输入时，相关燃料成本链路会阻断，不强行补值。
