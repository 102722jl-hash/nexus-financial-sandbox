# 公司公告采集

从上交所或巨潮资讯取得公告 PDF 的最终公开 URL 后运行：

```powershell
python company_announcements.py download --code 600027.SH --url "公告PDF地址"
python company_announcements.py import
```

支持华能国际 `600011.SH`、华电国际 `600027.SH`、国电电力 `600795.SH`。当前提取发电量、上网电量、上网电价和装机容量。扫描件、缺少发布日期或无法识别公司的公告会进入 `review_queue`。
