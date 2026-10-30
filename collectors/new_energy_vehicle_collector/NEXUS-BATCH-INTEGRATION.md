# 新能源汽车采集器统一批次接入

## 自动流程

`auto_collect_v1.py` 完成每日采集和原有质量门禁后，会自动执行：

```text
新浪公司日线 + 公司法定公告/PDF
+ 中国汽车流通协会月报
+ 广期所碳酸锂官方日行情
→ 来源事实 / 市场代理
→ 同公司、同期间的可审计公式计算
→ 基准覆盖率门禁
```

```text
新能源汽车 SQLite
→ export_nexus_batch_v1.py
→ nexus-crawler-batch-1.0.0
→ V2.20 数据契约校验
→ 确定性生成节点、层级、公式和关系
→ financial-world-sandbox-v2.20-composite-network/runs/networks
→ 浏览器网络列表
```

质量门禁没有通过时仍会保存标准批次，但不会生成新的浏览器网络。

## 当前完整验证

```text
来源：9
原始文档：80
证据：318
层级：6
实体：5（比亚迪、赛力斯、北汽蓝谷、长安汽车、长城汽车）
指标定义：31
指标观测：296
公式：24
指标关系：24
编译节点：128（含5个公司实体节点）
编译关系：113（含5条实体归集关系）
基准覆盖：79/123，64.23%
必需基准覆盖：54/84，64.29%
门禁：DATA_PARTIAL / GRAPH_READY / SCENARIO_NOT_READY
```

基准分为 `SOURCE_FACT`、`MARKET_PROXY`、`CALCULATED_LINEAGE` 和
`DATA_MISSING`。公式计算必须保留输入证据，不会用统一指数填充真实缺失。

标准批次保存在 `standard_batches`，网络方案保存在 V2.20 的 `runs/networks`。
当前五公司预览版本为 `PLAN-85C5F615C180898B23F5343B`；旧版本继续保留，浏览器不会自动切换。

PostgreSQL 已增量同步并通过只读验收：`published_nodes=123`、
`published_edges=108`、`published_metric_values=296`、`published_evidence=296`；
只读账号无法读取原始表，也无法执行写操作。

## 手工执行

```powershell
python export_nexus_batch_v1.py
```

只导出标准批次、不生成网络：

```powershell
python export_nexus_batch_v1.py --no-compile
```

## PostgreSQL 增量入库

先由数据库管理员执行一次 V2.20 的 `v220_reference_schema_postgresql.sql`，然后使用：

```powershell
python crawler_postgres_ingest.py <批次文件> `
  --database <数据库名> `
  --schema nexus `
  --user <写入账户> `
  --password-env <密码环境变量名>
```

入库使用稳定主键和 `ON CONFLICT`，不会执行 `TRUNCATE` 或整库覆盖。数据库密码只从环境变量读取。
