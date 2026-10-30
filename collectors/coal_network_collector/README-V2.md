# 煤炭—火电网络采集系统

当前权威交接说明见 `HANDOFF-V2.md`。唯一推荐入口是：

```powershell
python auto_collect_v2.py
```

离线刷新：

```powershell
python auto_collect_v2.py --offline
```

本项目将 `AI_APPROVED` 视为可用候选，但不把它等同于人工确认或因果识别。当前候选网络可以展示和导出；公式未校准，因此正式模拟仍保持关闭。
