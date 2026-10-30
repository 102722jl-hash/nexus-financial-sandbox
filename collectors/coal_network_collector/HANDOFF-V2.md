# 煤炭—火电网络采集系统交接文档 V2

更新时间：2026-09-08

## 当前结论

系统已经形成可自动更新、可审计、可导出的 AI 候选网络。`AI_APPROVED` 默认计入候选集合，不要求逐条人工确认；但它仍不等于现实因果已经确认，公式未校准时不标记为正式模拟就绪。

```text
运行状态：AI_CANDIDATE_READY
候选网络：可展示、可导入
正式模拟：尚未就绪
因果结论：ABSTAIN
```

## 唯一推荐入口

联网每日更新：

```powershell
cd D:\桌面\workspace\study\coal_network_collector
python auto_collect_v2.py
```

只处理已有快照和数据库：

```powershell
python auto_collect_v2.py --offline
```

Windows 任务计划程序使用：

```text
D:\桌面\workspace\study\coal_network_collector\run_auto_collect_v2.ps1
```

旧的 `auto_collect.py`、`daily_job.py`、`daily_job_fixed.py` 和 `run_auto_collect.ps1` 仅保留用于历史回溯，不再作为推荐入口。

## 当前数据库状态

```text
network_registry：1
network_layers：6
entities：3
raw_documents：14
evidence：1311
metric_values：1308
network_nodes：25
network_edges：39
formulas：39
valuation：3
review_queue：82
```

状态统计：

```text
AI候选边：39
完整AI候选路径：20
正式确认边：0
正式完整路径：0
已校准公式：0
孤立节点：1（国电电力 · 装机容量）
AI自动通过审核：78
仍待处理：4（无法可靠解析的公司PDF）
```

数据截止时间已经从占位值 `2099-12-31` 修正为数据库最新可见数据日期 `2026-09-05`。

## 状态规则

候选网络状态：`CANDIDATE`、`AI_CANDIDATE`、`AI_APPROVED`。

正式网络状态：`CONFIRMED`、`ACTIVE`、`APPROVED`。

`AI_APPROVED` 的节点、边和公式可以显示、导出并参与候选路径统计。公式为 `AI_ASSUMPTION` 或 `DATA_MISSING` 时，只能表达机制候选，不能输出正式确定性模拟结果。

## 当前候选链路

已经形成20条煤价到市场价格代理的完整候选路径，例如：

```text
动力煤5500K价格
→ 华电国际 · 发电量/上网电量/上网电价
→ 华电国际 · 营业收入
→ 华电国际 · 归母净利润
→ 华电国际 · 市场价格代理
```

另有煤价直接作用于营业成本，再连接净利润和市场价格代理的候选路径。所有关系均保留 `causal_conclusion=ABSTAIN`。

## 运行产物

```text
manifest.json                 当前状态与统计
validation_report.json        压缩后的错误和警告
auto_collect_report.json      最近一次完整运行报告
package_export/*.jsonl        标准网络数据包
```

检查命令：

```powershell
python path_check_v2.py
python validate_v3.py
python export_package_v2.py
```

预期结果：`errors=[]`、`candidateReady=true`、`formalReady=false`、`foreignKeyErrors=0`。

## 尚未完成

1. 39条候选边缺少逐边直接机制证据。
2. 39个公式缺少足够历史重叠样本，尚未校准。
3. 煤价历史只有少量当前值，需要合法的 CCTD CSV 或授权接口补充。
4. 估值仍缺净债务、非经营资产及完整估值参数。
5. 4份PDF仍需人工检查或OCR，不能自动当作可信字段来源。
6. 新浪行情是 `T3/MARKET_PROXY`，只作为市场观察。

## 数据边界

- 不绕过登录、验证码、付费墙或访问限制。
- 搜索摘要不作为来源事实。
- T3行情保持 `MARKET_PROXY`，不升级为 `SOURCE_FACT`。
- 不用零值填补缺失数据。
- AI通过代表进入候选集合，不代表正式因果识别。
- 非 `IDENTIFIED` 的关系保持 `causal_conclusion=ABSTAIN`。

## 恢复与备份

V2策略应用前备份：`coal_network.before_ai_candidate_policy_v2.db`。

如需回滚，先停止定时任务，复制备份为 `coal_network.db`，再运行 `python auto_collect_v2.py --offline` 重建报告和导出包。
