# 新浪公开行情

运行：

```powershell
python sina_market.py
python complete_contract.py
python manifest.py
```

它通过新浪公开 JSONP 日线接口获取三家公司的近一年日收盘价，写入 `metric_values` 和 `evidence`。数据标记为 `MARKET_PROXY/T3`，仅用于估值原型和事后行情验证；正式发布需替换为交易所或授权行情。
