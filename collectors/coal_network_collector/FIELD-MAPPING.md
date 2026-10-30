# 首批字段映射

| 来源 | 页面内容 | `metric_code` | 目标表 |
|---|---|---|---|
| 国家统计局 | 原煤产量 | `RAW_COAL_OUTPUT` | `metric_values` |
| 国家统计局 | 火力发电量 | `POWER_GENERATION` | `metric_values` |
| 国家能源局 | 全社会用电量 | `POWER_CONSUMPTION` | `metric_values` |
| 国家能源局 | 火电累计平均利用小时 | `UTILIZATION_HOURS_THERMAL` | `metric_values` |
| 国家能源局 | 火电装机容量 | `THERMAL_CAPACITY` | `metric_values` |
| 全国煤炭交易中心 | 动力煤 5500K 价格 | `COAL_PRICE_5500` | `metric_values` |
| 全国煤炭交易中心 | 动力煤 5000K 价格 | `COAL_PRICE_5000` | `metric_values` |

每条指标必须同时建立 `evidence` 记录，保留发布者、发布日期、抓取时间、原文、文本定位、URL、快照路径和 SHA256。无法识别发布日期的页面进入 `review_queue`，不写入正式指标表。
