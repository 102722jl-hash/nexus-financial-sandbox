# 煤价来源选择

## 首选：CCTD

CCTD 秦皇岛数据页明确列出 5500、5000、4500 大卡动力煤价格，并提供“下载数据”入口。建议在 CCTD 账户或授权数据服务中导出 CSV，再交给 `coal_price_import.py`。页面动态接口当前可能返回 SQL 错误，因此不应把网页 HTML 直接当作稳定 API。

```powershell
python coal_price_import.py cctd-price.csv
python build_nodes.py
python build_edges.py
```

## 付费/授权备选

- S&P Global Platts：适合国际煤价和高频基准，需授权。
- Argus/McCloskey：适合 API 指数，需授权。
- Wind：适合与股票、商品和宏观数据统一，需终端/API授权。
- 煤炭资源网（SXCOAL）：有标准数据产品 API，需商务授权。

不要绕过登录、验证码、付费墙或下载限制。CSV 中必须保留导出来源 URL 和数据日期，系统会将每个价格值写入 `evidence` 和 `metric_values`。
