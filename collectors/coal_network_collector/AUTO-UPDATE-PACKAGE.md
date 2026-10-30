# 网络包自动更新

推荐定时入口：

```powershell
.\run_auto_update_network_package.ps1
```

测试或无网络时：

```powershell
python auto_update_network_package.py --offline
```

每次运行会先更新 `coal_network.db`，校验候选网络，再在 `package_versions` 中生成不可变版本。校验和哈希复算通过后，才原子更新 `latest_candidate.json`。默认保留最近30个版本；失败时不会改变最新版本指针。

网络沙盒应读取 `latest_candidate.json`，再加载其中 `path` 指向的目录。`package_export` 仍作为当前覆盖式快照保留，但版本化目录是推荐的生产读取方式。
