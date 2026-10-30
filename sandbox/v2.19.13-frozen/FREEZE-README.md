# V2.19.13 冻结基线

这是当前已验证网络浏览器的冻结基线。冻结版本号为 `V2.19.13-frozen`，冻结日期为 2026-09-16。

## 能力范围

- PostgreSQL、MySQL、SQLite、CSV、Excel、JSON 只读画像与同步。
- 多表网络契约：层级、实体、指标、节点、关系、公式和证据。
- 通用公式归一化与未知公式局部隔离。
- `AI_APPROVED` 默认进入候选传播，使用 `candidateWeight`，因果状态保持 `ABSTAIN`。
- 数据库生成网络中的可调节点、候选情景传播和动态黄/绿/红虚线。
- 网络持久化、刷新恢复、版本化网络文件和旧网络保留。

## 当前已验证网络

- 新能源汽车产业传导网络：77 个节点、66 条候选关系。
- 新能源汽车渗透率 +20% 的验证结果：行业销量 +3.5%，动力电池装车量 +0.6125%，比亚迪销量 +0.6125%，17 步计算记录。

## 启动方式

```powershell
cd D:\桌面\workspace\study\financial-world-sandbox-v2.19.13-frozen
.\.venv-ui\Scripts\python.exe server.py --port 4184
```

冻结包默认不包含虚拟环境。若 `.venv-ui` 不存在：

```powershell
python -m venv .venv-ui
.\.venv-ui\Scripts\pip.exe install -r requirements.txt
.\.venv-ui\Scripts\python.exe server.py --port 4184
```

## 恢复规则

- 冻结目录不再承接功能修改。
- 后续功能开发只在 `financial-world-sandbox-v2.20-composite-network` 进行。
- `VERSION.json` 是判断版本身份的权威文件。
- `SHA256SUMS.txt` 用于检查冻结文件是否被修改。
