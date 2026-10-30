# 日常运行说明 V2

## 每日自动任务

Windows 任务计划程序建议每天 `18:30` 执行：

```text
程序：powershell.exe
参数：-ExecutionPolicy Bypass -File "D:\桌面\workspace\study\coal_network_collector\run_auto_collect_v2.ps1"
起始位置：D:\桌面\workspace\study\coal_network_collector
```

如果当天只想处理已有数据：

```powershell
.\run_offline_refresh_v2.ps1
```

## 每日检查

查看以下文件：

```text
auto_collect_report.json
validation_report.json
manifest.json
```

正常候选状态应为：

```text
operationalStatus = AI_CANDIDATE_READY
candidateReady = true
errors = []
```

`formalReady=false` 在公式未校准阶段是预期状态。

## 历史煤价导入

只使用新版导入器：

```powershell
python coal_price_import_v2.py cctd-price.csv
python auto_collect_v2.py --offline
```

旧 `coal_price_import.py` 不兼容完整证据契约，不再使用。

## 验证

```powershell
.\run_tests_v2_fixed.ps1
python validate_v3.py
python path_check_v2.py
```

## 失败处理

- 网站访问失败：查看 `auto_collect_report.json` 对应阶段，不删除旧数据。
- PDF无法解析：保持 `review_queue=PENDING`，不要自动补值。
- 页面改版：保留 `raw_documents` 快照后更新对应解析器。
- 公式未校准：补充合法历史煤价，不把 `DATA_MISSING` 改成零。
- 数据异常：先复制 `coal_network.db`，再做修复或离线刷新。
