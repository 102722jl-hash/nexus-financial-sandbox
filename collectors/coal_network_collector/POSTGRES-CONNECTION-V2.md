# 模型直接连接 PostgreSQL

你截图中的模型入口不能连接 SQLite 文件，也不读取 JSONL 网络包。正确架构是：

```text
互联网采集 → coal_network.db（SQLite工作库）
          → PostgreSQL coal_network schema（模型只读主入口）
          → package_versions（审计和回滚备份）
```

模型界面填写：

```text
数据库类型：PostgreSQL
Host：127.0.0.1
Port：5432
Database：coal_network
只读用户：coal_network_readonly
Schema：coal_network
SSL：prefer
```

本机目前没有运行 PostgreSQL。已有 Docker Desktop 程序，但 Docker 引擎未启动。启动后，在当前 PowerShell 会话设置三个密码环境变量，然后运行：

```powershell
$env:COAL_PG_ADMIN_PASSWORD = Read-Host '管理员密码'
$env:COAL_PG_WRITER_PASSWORD = Read-Host '同步账号密码'
$env:COAL_PG_READONLY_PASSWORD = Read-Host '模型只读账号密码'

docker compose -f docker-compose.postgres.yml up -d
python setup_postgres_roles.py
python sync_postgres_v2.py --database coal_network --user coal_network_writer --password-env COAL_PG_WRITER_PASSWORD
python grant_postgres_after_sync.py
python verify_postgres_readonly.py
```

最后将 `COAL_PG_READONLY_PASSWORD` 对应的密码填入模型连接界面的“密码”框。每日定时任务应执行 `publish_database.ps1`；它先更新本地工作库，再事务同步 PostgreSQL，模型读取的就是最新数据库表。

不要使用旧的 `postgres_network_schema.sql` 或 `sync_postgres.py`；推荐 `sync_postgres_v2.py`，它会根据 SQLite 元数据自动创建 PostgreSQL 表。
