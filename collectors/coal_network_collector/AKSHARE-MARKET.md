# AKShare 行情接入

运行：

```powershell
python akshare_market.py
python complete_contract.py
python build_nodes.py
python manifest.py
```

适配器获取三家公司的最新日线收盘价和总股本，计算当前市值并写入 `valuation`。AKShare 底层数据属于第三方公开行情，记录为 `source_tier=T3`、`value_status=MARKET_PROXY`、`temporal_role=POST_EVENT_VALIDATION`，不能替代交易所或授权行情。生产环境应替换为 Tushare/Wind 或其他获得许可的接口。
