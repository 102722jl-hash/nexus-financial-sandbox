# 煤炭—火电网络采集系统交接文档

更新时间：2026-09-06

## 1. 项目目标

本项目根据 `DATABASE-TO-NETWORK-PACK-PROMPT-V2.md`，建立一个“煤炭价格 → 火电经营 → 公司财务 → 市场估值”的数据采集和网络数据包系统。

目标流程：

```text
公开网页/API/PDF
→ 原始快照
→ 字段解析与标准化
→ evidence 证据
→ metric_values 指标
→ network_nodes 节点
→ network_edges/formulas 关系与公式
→ valuation 估值
→ manifest/JSONL 网络包
```

项目目录：

```text
D:\桌面\workspace\study\coal_network_collector\
```

实际数据库：

```text
D:\桌面\workspace\study\coal_network_collector\coal_network.db
```

规范数据库结构：

```text
D:\桌面\workspace\study\coal_network_collector\complete_schema.sql
```

## 2. 已完成工作

### 数据库和契约

- 创建了 SQLite 数据库 `coal_network.db`。
- 按 MD 建立了标准表：`network_registry`、`network_layers`、`network_nodes`、`network_edges`、`entities`、`metric_values`、`formulas`、`evidence`、`valuation`。
- 建立了辅助表：`raw_documents`、`review_queue`、`collection_runs`、`announcement_catalogue`、`discovery_runs`、`document_processors`、`ai_judgements`。
- 修复了 SQLite 联合外键问题，当前 `pragma foreign_key_check` 为 0 错误。
- 生成了数据库迁移前备份：`coal_network.before_contract_20260906_192058.db`、`coal_network.pre_nodes_fk.db`。
- `complete_schema.sql` 是目前推荐的新库结构；旧的 `schema.sql` 仍保留，但不是最新规范文件。

### 网络定义

网络名称：

```text
煤炭价格到火电企业盈利传导
```

六层：

```text
1 宏观与政策
2 煤炭供需
3 动力煤价格
4 火电经营
5 公司财务
6 估值与市场表现
```

当前实体：

```text
600011.SH  华能国际
600027.SH  华电国际
600795.SH  国电电力
```

### 数据采集

已经实现的来源适配：

- 国家统计局：原煤产量、火力发电量等能源生产页面。
- 国家能源局：全社会用电量、火电利用小时、装机容量等页面。
- 全国煤炭交易中心：公开动力煤指数当前值。
- 巨潮资讯：公司公告目录和 PDF 下载。
- 公司半年度报告：发电量、上网电量、上网电价、装机容量、营收、成本、净利润、经营现金流、资产和负债。
- 新浪公开日线接口：三家公司近 400 个交易日收盘价。
- CCTD 合法导出 CSV：历史煤价导入接口已经实现，但尚未导入历史 CSV。

### 当前实际数据

截至本文档更新时间，数据库统计为：

```text
network_registry：1
network_layers：6
entities：3
raw_documents：14
evidence：1311
metric_values：1308
network_nodes：22
network_edges：14
formulas：14
valuation：3
review_queue：54
ai_judgements：50
```

行情和估值：

```text
CLOSE_PRICE：1200 条
估值记录：3 条
估值状态：PARTIAL_CALCULATED
```

当前估值记录：

```text
华能国际：收盘价 6.86，股本 15,698,093,359，当前市值约 1076.89 亿元
华电国际：收盘价 4.84，股本 11,611,774,184，当前市值约 562.01 亿元
国电电力：收盘价 5.37，股本 17,835,619,082，当前市值约 957.77 亿元
```

估值仍是 `PARTIAL_CALCULATED`，因为尚未补齐净债务、非经营性资产和完整估值参数。

## 3. 推荐脚本入口

### 免费公开来源每日采集

```powershell
cd D:\桌面\workspace\study\coal_network_collector
python auto_collect.py
```

只处理已有快照：

```powershell
python auto_collect.py --offline
```

Windows 任务计划程序可执行：

```text
D:\桌面\workspace\study\coal_network_collector\run_auto_collect.ps1
```

### 煤炭交易中心公开价格

```powershell
python nce_public.py
```

### 合法 CCTD CSV 历史价格

CSV 至少包含：

```text
date,price_5500,price_5000,price_4500,source_url
```

导入：

```powershell
python coal_price_import.py cctd-price.csv
```

### 新浪历史行情

推荐使用修正版：

```powershell
python sina_market_fixed.py
python share_capital.py
```

该数据是第三方市场代理，应保持 `MARKET_PROXY/T3` 标记。

### 自动判断和公式校准

```powershell
python ai_judge_calibrate.py
```

规则：

- 节点和关系可自动标记为 `AI_APPROVED`。
- 不再要求逐条人工确认，但 `AI_APPROVED` 不等同于人工 `CONFIRMED`。
- 只有至少 3 个同日期历史配对样本时，公式才可能标记 `AI_CALIBRATED`。
- 当前 14 条公式均为 `AI_ASSUMPTION`，原因是煤价历史和同口径经营指标重叠样本不足。

### 节点、校验和导出

```powershell
python complete_contract.py
python build_nodes.py
python build_edges.py
python manifest.py
python validate_contract.py
python confirmed_path_check.py
python export_package.py
```

导出目录：

```text
D:\桌面\workspace\study\coal_network_collector\package_export\
```

## 4. 当前状态和已知问题

当前 `manifest.json` 状态：

```text
packageStatus：IMPORT_READY
formalReady：false
```

原因：

1. 14 条边已经被自动判断为 `AI_APPROVED`，但不是 `CONFIRMED/ACTIVE/APPROVED`，旧版路径统计因此仍显示确认边为 0。
2. 14 条公式没有足够煤价历史和经营指标重叠样本，参数为 `DATA_MISSING/AI_ASSUMPTION`。
3. 估值只有收盘价、股本和当前市值，尚未补净债务、非经营资产及完整估值参数。
4. 当前存在 13 个孤立节点，其中包括不在现有候选关系路径上的公司经营节点。
5. 没有从煤价到公司财务再到估值的完整确认路径。
6. AKShare 的东方财富接口在当前网络环境中会断开，且全局 Python 有 NumPy 1.x/2.x 二进制兼容警告；已经创建 `.venv-market` 隔离环境，但东方财富端点仍可能拒绝连接。
7. 新浪行情接口目前可用，但它是第三方公开代理，不是交易所一手数据。
8. `test_coal_price_import.py` 在本机测试时受到临时目录权限影响失败，导入逻辑本身尚未被该测试完整验证。
9. `.write_test` 是权限测试遗留文件，内容为 `ok`，不参与程序运行。

旧入口注意：

- `daily_job.py` 曾存在公告目录占位符和运行 ID 问题，不建议使用。
- 使用 `daily_job_fixed.py` 或统一入口 `auto_collect.py`。
- `sina_market.py` 有列数错误，使用 `sina_market_fixed.py`。

## 5. 下一步优先级

### P0：稳定每日运行

1. 在本机任务计划程序中运行 `run_auto_collect.ps1`。
2. 确认网络代理允许新浪、国家统计局、能源局、巨潮资讯和全国煤炭交易中心访问。
3. 每日检查 `auto_collect_report.json`、`validation_report.json` 和 `database_status.py` 输出。

### P1：补齐估值

1. 保留新浪 400 日收盘价作为原型行情。
2. 从公司定期报告提取净债务：有息负债减货币资金，保留原文定位。
3. 录入估值方法和参数，例如 PE、EV/EBITDA 或 DCF；参数必须标记为 `CALIBRATED_PARAMETER` 或 `ANALYST_ASSUMPTION`。
4. 重新运行 `complete_contract.py`、`manifest.py` 和 `validate_contract.py`。

### P1：补齐历史权重

1. 获取至少 6–12 个月的 CCTD 合法 CSV，字段包含 5500K/5000K 价格。
2. 将煤价历史与公司经营指标按报告期或可解释的时间窗口对齐。
3. 至少形成 3 个以上可复核样本后运行 `ai_judge_calibrate.py`。
4. 检查斜率、方向、单位、滞后和影响上限，异常结果标记为 `DATA_MISSING` 或进入隔离。

### P2：完整网络路径

1. 为公司财务节点补充明确的源节点和证据。
2. 为估值节点生成节点记录并补齐基准值。
3. 依据真实证据生成经营→财务→估值候选边。
4. 自动判断后运行 `confirmed_path_check.py`，确认完整路径数量大于 0。

## 6. 安全和数据边界

- 不绕过登录、验证码、付费墙、robots 或访问限制。
- 不使用搜索摘要作为 `SOURCE_FACT`。
- T1/T2 才能直接支持来源事实；AKShare 和新浪行情标记为 T3/市场代理。
- 不用零值填补缺失数据。
- 不把相关性自动表述为现实因果。
- 不把 AI 自动判断改写为人工确认。
- 不把市场行情代理伪装成交易所一手行情。
- API 密钥、数据库密码和完整连接凭证不得写入日志或导出包。

## 7. 交接验证命令

```powershell
cd D:\桌面\workspace\study\coal_network_collector
python database_status.py
python validate_contract.py
python manifest.py
python export_package.py
```

预期重点检查：

```text
foreignKeyErrors = 0
evidence 缺失审计字段 = 0
valuation 有真实记录
formula 参数是否仍为 DATA_MISSING
AI_APPROVED 与 CONFIRMED 的区别
completePaths 是否大于 0
```

## 8. 结论

当前项目已经完成“公开数据采集、原始快照、证据、指标、公司节点、行情代理、当前市值、自动判断和网络包导出”的第一版闭环。

当前可用等级：

```text
可采集：是
可入库：是
可自动更新：是，但依赖本机网络和任务计划程序
可导入网络沙盒：是，状态 IMPORT_READY
历史权重已校准：否
完整估值已完成：否
完整确认路径：否
正式模拟推演：尚未达到
```

后续接手者应优先使用 `auto_collect.py`，先补 CCTD 合法历史煤价，再补净债务和估值参数，最后重新运行门禁和导出流程。
