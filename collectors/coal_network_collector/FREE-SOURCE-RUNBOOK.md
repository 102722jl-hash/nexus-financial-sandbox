# 免费来源运行方式

每天执行：

```powershell
python nce_public.py
```

它只读取全国煤炭交易中心公开页面，保存 HTML 快照、SHA256、发布日期和原文定位。页面结构变化、价格缺失或访问受限时不会填零，而是写入 `review_queue`。

历史价格可从 CCTD 合法导出 CSV 后导入：

```powershell
python coal_price_import.py cctd-price.csv
```
