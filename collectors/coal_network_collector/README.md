# 煤炭网络采集库

这是一个独立的、规则驱动的 SQLite 起始项目，对应 `DATABASE-TO-NETWORK-PACK-PROMPT-V2.md` 的标准表。它先建立煤炭—火电传导网络的空库和种子元数据；网站采集器应将内容先保存为 `raw_documents`，解析出带 `evidence_id` 的标准记录后，再写入 `metric_values`。

初始化并写入网络、六层和三家公司：

```powershell
python collector.py seed
```

正式接入网站时，为每个来源实现一个适配器，返回统一字段：`metric_code`、`value`、`unit`、`report_period/as_of_date`、`evidence_id`、`data_cutoff`。缺少原文、定位或 URL 的记录必须进入 `review_queue`，不能直接当作事实入库。
