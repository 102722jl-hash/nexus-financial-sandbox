# 行情环境

当前机器已安装 AKShare，但如果出现“compiled using NumPy 1.x”警告，建议建立独立虚拟环境：

```powershell
python -m venv .venv-market
.\.venv-market\Scripts\Activate.ps1
python -m pip install -r requirements-market.txt
python akshare_market.py
```

AKShare 数据仅用于免费原型和市场表现验证。正式发布前应改用有授权的 Tushare/Wind/交易所数据，并保留原始来源与许可信息。
