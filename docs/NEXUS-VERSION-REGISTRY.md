# NEXUS 本地版本登记

## 冻结版本

| 项目 | 内容 |
|---|---|
| 版本 | `V2.19.13-frozen` |
| 状态 | 冻结，不再修改 |
| 目录 | `D:\桌面\workspace\study\financial-world-sandbox-v2.19.13-frozen` |
| ZIP | `D:\桌面\workspace\study\financial-world-sandbox-v2.19.13-frozen.zip` |
| ZIP SHA-256 | `7a5e950005ac3661f996574f81fa0708b56f567847183515629c47fe456ca74e` |
| 默认端口 | 4184 |
| 地址 | `http://127.0.0.1:4184` |
| 身份文件 | `VERSION.json` |
| 校验文件 | `SHA256SUMS.txt` |

## 当前复合版本

| 项目 | 内容 |
|---|---|
| 版本 | `V2.20.0-composite` |
| 状态 | 当前开发与运行版本 |
| 目录 | `D:\桌面\workspace\study\financial-world-sandbox-v2.20-composite-network` |
| 默认端口 | 4186 |
| 地址 | `http://127.0.0.1:4186` |
| 启动脚本 | `start-v220.ps1` |
| 验收报告 | `V2.20-REPORT.md` |
| 爬虫数据契约 | `nexus-crawler-batch-1.0.0` |
| 参考数据库结构 | `v220_reference_schema_postgresql.sql` |
| 幂等入库器 | `crawler_postgres_ingest.py` |
| 自动网络编译器 | `crawler_network_compiler.py` |

## 调用规则

- 需要恢复修改前状态：使用 `V2.19.13-frozen`。
- 需要三道门禁和复合网络诊断：使用 `V2.20.0-composite`。
- 新行业采集器必须先通过 `nexus-crawler-batch-1.0.0`；总标题、节点层级、公式和关系均从契约字段确定性生成。
- 新能源汽车采集器已接入统一批次出口；当前浏览器方案仍为 `PLAN-8B61DA1F5482AB281477EC40`（未自动切换），最新五公司预览版本为 `PLAN-85C5F615C180898B23F5343B`，原方案可作为回滚目标。
- 判断版本时读取各目录的 `VERSION.json`，不要根据文件夹修改时间推断。
