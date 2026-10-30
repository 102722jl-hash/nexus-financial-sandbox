# PostgreSQL 模型接入

当前 `coal_network.db` 是本地 SQLite 工作库，不能填入 PostgreSQL 连接界面。模型应连接同步后的 PostgreSQL schema：`coal_network`。

## 发布数据

1. 在 PostgreSQL 管理员会话中执行 `postgres_network_schema.sql`。如果目标数据库已有标准表，按实际表结构调整 `CREATE TABLE ... LIKE public...` 的来源表。
2. 安装 `psycopg[binary]`。
3. 用管理员或目标 schema 写入账号执行同步。密码建议放在临时环境变量：

```powershell
$env:COAL_PG_PASSWORD = '只在当前进程使用'
python sync_postgres.py --database your_database --user coal_network_writer --password-env COAL_PG_PASSWORD
```

同步成功后，SQLite 不会被修改；PostgreSQL 的 `coal_network` schema 会在一个事务中替换为当前 `coal_power_v1` 快照。

## 模型界面填写

```text
数据库类型：PostgreSQL
Host：PostgreSQL服务器地址
Port：5432
Database：目标数据库名
只读用户：coal_network_readonly
Schema：coal_network
SSL：按服务器要求，默认 prefer
```

选择“发现只读”后，应看到 `network_registry`、`network_layers`、`network_nodes`、`network_edges`、`entities`、`metric_values`、`formulas`、`evidence`、`valuation` 等表。

`package_export` 和 `package_versions` 仍是文件快照/备份，不是模型主连接目标。每日流程应先更新 SQLite，再运行 PostgreSQL 同步，模型直接读取 PostgreSQL schema。
