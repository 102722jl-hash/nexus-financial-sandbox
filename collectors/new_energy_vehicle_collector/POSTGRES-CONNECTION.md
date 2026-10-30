# 新能源汽车模型数据库连接

新能源汽车网络与煤炭网络完全分离。

- Host：`127.0.0.1`
- Port：`5432`
- Database：`new_energy_vehicle`
- Schema：`new_energy_vehicle`
- 只读用户：`new_energy_vehicle_readonly`
- 网络 ID：`new_energy_vehicle_v1`

密码保存在本机当前 Windows 用户可解密的
`.postgres-secrets.dpapi.json` 中。模型只使用只读账号连接。

浏览器只读账号仅可读取以下六个发布视图：

- `published_networks`
- `published_layers`
- `published_nodes`
- `published_edges`
- `published_metric_values`
- `published_evidence`

原始文档、采集运行、隔离、凭据、日志和未发布关系不授予只读账号。
同步采用稳定主键增量更新，不清空行业 schema，历史观测和修订继续保留。

`published_nodes.value_status='DATA_MISSING'` 表示蓝图节点存在但尚无合格数据，
不能把它当成数值 0。`published_edges.parameter_status='AI_ASSUMPTION'` 表示可用于
候选情景试算，但 `formulas.causal_conclusion` 仍为 `ABSTAIN`。
