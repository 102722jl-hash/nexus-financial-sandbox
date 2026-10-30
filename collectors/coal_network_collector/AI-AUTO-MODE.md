# 自动判断模式

执行：

```powershell
python ai_judge_calibrate.py
```

系统会自动判断节点和候选关系，但使用 `AI_APPROVED` 状态保留来源边界；不会把 AI 判断改写为人工 `CONFIRMED`。公式仅在至少 3 个同日期历史样本可配对时标记 `AI_CALIBRATED`，否则写入 `DATA_MISSING` 和 `AI_ASSUMPTION`，不虚构权重。
