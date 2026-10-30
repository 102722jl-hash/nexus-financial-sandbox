# 契约补齐

运行：

```powershell
python complete_contract.py
python validate_contract.py
```

脚本会为新证据记录自动补齐 `page_or_locator`、`anchor_at`、`declared_role`、`review_status` 和 `raw_storage_status`；根据最新真实指标写入节点 `baseline_value`。有收盘价但缺少股本、净债务或估值参数时，`valuation` 仅写入真实收盘价并标记 `DATA_MISSING`，不计算市值或估值。
