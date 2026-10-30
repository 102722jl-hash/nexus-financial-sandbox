# Windows 定时运行

在任务计划程序中创建“每日”任务，操作选择：

```text
程序：python
参数：D:\桌面\workspace\study\coal_network_collector\source_adapters.py --source all
起始位置：D:\桌面\workspace\study\coal_network_collector
```

建议先设置为每天一次并保留运行历史。当前适配器只下载公开页面、保存原始响应和哈希，并写入 `raw_documents`；解析器必须从快照提取原文引用、定位、发布日期和字段后，才能写入正式指标表。
