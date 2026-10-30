# 审核与导出

查看待审核对象：

```powershell
python review_cli.py list
python review_cli.py list --kind EDGE
```

人工确认后升级对象：

```powershell
python review_cli.py approve --review-id 1
```

检查正式路径并导出网络包：

```powershell
python confirmed_path_check.py
python export_package.py
```

导出只读取标准表，不会修改原数据库；候选边和候选公式不会自动升级。
