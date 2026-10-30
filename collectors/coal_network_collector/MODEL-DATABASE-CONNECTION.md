# 模型数据库连接参数

模型现在直接连接 PostgreSQL，不读取 `package_export`。

```text
数据库类型：PostgreSQL
Host：127.0.0.1
Port：5432
Database：coal_network
只读用户：coal_network_readonly
Schema：coal_network
SSL：prefer
```

密码使用本机 DPAPI 加密保存。需要填入模型界面时运行：

```powershell
.\show_model_connection.ps1
```

该命令会临时显示只读账号密码。密码不写入说明文档、日志或网络数据包。

每日计划任务先更新本地 SQLite 工作库，再把完整标准表事务同步到 PostgreSQL。模型只读用户已经设置 `default_transaction_read_only=on`。
