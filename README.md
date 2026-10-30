# NEXUS Financial World Sandbox · 金融沙盘

> 把「行业数据」编译成「可调节、可复算、可追溯的金融传导网络」的沙盘。

当前版本基线：**V2.20.0-composite**（`ACTIVE_DEVELOPMENT`）｜冻结父版本：**V2.19.13-frozen**
网络契约：`composite-network-contract-1.0.0`｜采集批次契约：`nexus-crawler-batch-1.0.0`｜门禁契约：`data-graph-scenario-readiness-1.0.0`

---

## 一、这个项目解决什么问题

传统行业研究 / 财务模型有三个绕不开的痛点：

| 痛点 | 本项目的做法 |
|---|---|
| 模型是黑盒，改了参数不知道为什么变 | 每条边都挂公式与证据，可复算血缘（CALCULATED LINEAGE） |
| 数据来源说不清，无法审计 | 每个观测点回指原始快照，且哈希必须自洽 |
| 换一个行业就要重写一套系统 | 六层网络语义完全动态，同一引擎套所有行业 |

一句话：**这不是一个"看图"工具，而是一条"数据 → 网络 → 情景"的确定性流水线**，界面上看到每一个数字，都能倒推回原始快照。

---

## 二、仓库结构

```text
nexus-financial-sandbox/
├─ sandbox/
│  ├─ v2.20-composite-network/     ← 当前主版本（默认端口 4186）
│  └─ v2.19.13-frozen/             ← 冻结基线（端口 4184，含 127 条 SHA256SUMS）
├─ collectors/
│  ├─ coal_network_collector/      ← 焦煤 / 火电 采集器
│  └─ new_energy_vehicle_collector/← 新能源汽车 采集器
├─ template/
│  └─ multi-industry-sandbox-template/  ← 纯前端静态沙盒（对外演示用）
├─ docs/                           ← 设计、契约、指令与使用指南
└─ scripts/                        ← 独立打包脚本
```

> 仓库只包含**源码与文档**。数据库文件、原始快照、公开 PDF、加密凭据与运行产物均被 [.gitignore](.gitignore) 排除，不会进入版本库。

---

## 三、10 分钟上手

### 3.1 启动沙盒

```powershell
cd sandbox/v2.20-composite-network
python server.py --port 4186
```

或使用封装脚本（自动探测 venv、自动回退系统 python）：

```powershell
.\start-v220.ps1              # 默认 4186
.\start-v220.ps1 -Port 4187   # 自定义端口
```

依赖只有四个包，见 [requirements.txt](sandbox/v2.20-composite-network/requirements.txt)：`pandas`、`psycopg`、`pymysql`、`cryptography`。

服务只绑定 `127.0.0.1`（回环），不对外暴露，日志直接打到 stdout。

### 3.2 打开界面

```text
http://127.0.0.1:4186/?domain=coal-steel&view=data&v=2.20.0
```

用 Mock 数据快速体验（不连数据库）：

```text
http://127.0.0.1:4186/?domain=coal-steel&view=data&v=2.20.0&api=mock
```

### 3.3 界面导览

**顶部四个视图页签**

| 页签 | 用途 |
|---|---|
| 世界网络 `world` | 传导网络的图形化推演主场 |
| 公司模型 `company` | 单公司模型与 SCENARIO EQUITY VALUE 账页 |
| 数据接入 `data` | 连接只读数据库、发现表、画像、同步字段 |
| 任务治理 `governance` | 运行状态、门禁状态、审核队列 |

**世界网络里的主要操作**：领域切换、`播放传播` / `前进一步` / `从头重播` / `速度` / `重置` / `全部高亮`、`显示完整系统` / `仅显示解析图`、缩放与 `适应视图`，侧栏提供 `可复算血缘`、`追溯`、`证据门禁候选数据状态`。

---

## 四、核心概念（看懂 8 个词就够了）

| 概念 | 含义 |
|---|---|
| **网络 Network** | 一个行业的传导图，如 `coal_power_v1`（煤炭价格 → 火电企业盈利） |
| **层 Layer** | 网络的纵向阶段，默认六层：外部驱动 → 供需 → 价格 → 经营 → 财务 → 估值 |
| **节点 Node** | 层里的一个可观测/可调节量，带 `baseline`、`editable`、`valueStatus` |
| **边 Edge** | 节点之间的传导关系，带 `weight`、`formulaType`、`formulaParameters`、`impact_cap_pct` |
| **证据 Evidence** | 支撑某条边的原始材料，含 `source_url`、`original_quote`、`locator`、`snapshot_path`、`snapshot_sha256` |
| **批次 Batch** | 采集端交付给沙盒的标准数据包，契约版本 `nexus-crawler-batch-1.0.0` |
| **三道门禁** | `DATA_READY` / `GRAPH_READY` / `SCENARIO_READY`，把"能看"和"能算"严格分开 |
| **状态三态** | `CONFIRMED` 进计算、`CANDIDATE` 只展示、`ABSTAIN` 不输出 |

传导计算的基本式：

```text
target_change = source_change × direction × weight × time_factor
```

---

## 五、三种使用姿势

### 路径 A：只想推演（最快）

不需要数据库、不需要采集器、不需要写代码。

1. 启动服务，打开带 `api=mock` 的 URL
2. `domainSelect` 选领域
3. 在"传导网络"里拖动 / 修改可调节点（`editable=true`）
4. 点 `播放传播` 看逐层扩散，或 `前进一步` 单步观察
5. 切到"公司模型"看 SCENARIO EQUITY VALUE 账页
6. 想核对某条变化从哪来 → 打开 `可复算血缘` 与 `追溯`

### 路径 B：接入自己的数据库

适用于已有行业库、想直接变成沙盘网络、不想写采集器的场景。源库必须是**只读账号**（本项目全程遵守"不写回源库、不补零、不推断缺失值"）。

数据包指令有两版：`DATABASE-TO-NETWORK-PACK-PROMPT.md`（V1，给了示例层标题，容易被写死）与 `DATABASE-TO-NETWORK-PACK-PROMPT-V2.md`（V2，要求**六层语义完全动态**）——**建议直接用 V2**。

### 路径 C：新增一个行业板块（完整工程链路）

```text
① Skill 交互设计   ② 数据库与权限设计
        ↓
③ 契约批次幂等入库   ④ 编译并发布网络
```

1. **用 Skill 做设计与数据库设计**：个人 Skill `$build-industry-network-collector` 按 9 步逐步提问并落地（网络目的 → 指标矩阵 → 数据源比较 → 自动化策略 → 数据库与凭据 → 规范校验 → 脚手架实现 → 全链路验证 → 发布排程）。它会生成独立 schema 与 `<schema>_writer` / `<schema>_network_readonly` 两个角色，凭据走 `AUTO_GENERATE_LOCAL / USER_ENV / SECRET_MANAGER`，**不要求提供明文密码**。
2. **采集器落地**：参考 `collectors/` 下的两个现成范例（见第六节）。
3. **校验 → 编译 → 入库**：

```powershell
python validate_crawler_payload.py <批次.json> --report
python compile_crawler_network.py <批次.json>
python crawler_postgres_ingest.py <批次.json> `
  --host 127.0.0.1 --port 5432 --database <库> --schema nexus `
  --user <用户> --password-env <环境变量名>
```

入库前置条件：`nexus.contract_meta` 中必须存在 **ACTIVE** 的契约记录，否则报 `CRAWLER_CONTRACT_NOT_INSTALLED`。

4. **门禁与发布**：编译与入库都要过 `composite_quality.py` 的三道门禁；通过后输出网络 JSON（`outputLevel` 为 `CANDIDATE_SCENARIO` 或 `GRAPH_ONLY`）。发布规则：**只追加新网络，不自动切换当前页面**，旧版本保留可回滚。

> 快速原型：`template/multi-industry-sandbox-template` 是纯浏览器端静态沙盒（NEXUS DOMAIN LAB），无数据库、无 AI。扩展新行业 = 在 `domains.js` 的 `window.DOMAIN_PACKAGES.packages` 里追加一个领域包对象即可，适合做对外演示与方案评审。

---

## 六、现成采集器范例

| 采集器 | 工作库 | 只读库（PostgreSQL） | 数据源 |
|---|---|---|---|
| `coal_network_collector` | SQLite `coal_network.db` | schema `coal_network` / 用户 `coal_network_readonly` | 国家统计局能源生产(T1)、国家能源局电力统计(T1)、全国煤炭交易中心(T1)、上交所公告(T2)、巨潮资讯公告(T2)，另有场外行情代理(T3) |
| `new_energy_vehicle_collector` | SQLite `new_energy_vehicle.db` | schema `new_energy_vehicle` / 用户 `new_energy_vehicle_readonly` | 新浪公司日线、广期所碳酸锂日行情、中国汽车流通协会月报、公司法定公告/PDF |

```powershell
# 焦煤 / 火电
python auto_collect_v4.py
python auto_update_network_package.py

# 新能源汽车
python auto_collect_v1.py --market-days 30
python export_nexus_batch_v1.py     # 导出标准批次到 standard_batches\BATCH-*.json
```

---

## 七、设计想法与演进：从"事后找关系"到"采集端分类"

这一节记录的是**为什么项目会长成现在这样**。

**最初设想**：把每天采集到的金融数据，用网络沙盘的形式把各表、各字段之间的关系标出来，让"煤炭价格涨了 → 火电经营承压 → 公司盈利变化 → 估值重估"一眼可见。原始文档的假设是：**关系本来就藏在数据里，只是需要被读出来。**

**撞上的墙**：字段语义冲突、同一证据 ID 关键字段冲突、映射歧义、币种/单位/期间口径冲突、节点分类错误、跨表关联失败。结论是——**问题不在识别算法，而在数据源头就没有统一语义。**

**三次转向**：

1. **分类前移到采集端**：不再指望事后对齐，而是采集入库时按类别写进规范字段。给每张表定角色（`REGISTRY / LAYERS / NODES / EDGES / ENTITIES / METRICS / FORMULAS / EVIDENCE / VALUATION`，外加 V2 新增的 `UNKNOWN`），并立下硬规则「同一字段不能因为名称相似就重复写入多个角色」。
2. **契约锁死规范**：三层分工 RAW → STANDARD → NETWORK；`weight / candidate_weight` 始终填正数幅度，正负只能由 `direction` 表示；所有 ID 用规范化字段生成 SHA-256；Schema 设 `additionalProperties: false`，不合法直接 `CRAWLER_BATCH_BLOCKED`。
3. **位置与语义解耦**：`layer_no` 只表示从左到右的位置，六层业务含义**不能写死**，语义由当前网络的 `network_layers.semantic_role` / `path_role`（`SOURCE / INTERMEDIATE / SINK / EVIDENCE_ONLY`）决定。这一步之后，"六层"从业务假设降级为版式约定，同一套引擎才能通吃焦煤、新能源汽车以及之后的任何行业。
4. **与不确定性共处**：三态隔离（AI 判断最高只到 `CANDIDATE`）、显式 `review_queue`、**不补零**。

**一句话主线**：最初想"事后在多表之间找关系"，发现源头语义不统一救不回来；于是把分类、映射、稳定 ID 全部前移到采集端，再用契约锁死；接着把位置与语义解耦；最后用三道门禁 + 三态审核 + 不补零，让"能看"和"能算"彻底分离。

完整演进时间线与原文出处见 [docs/使用指南与加分点.md](docs/使用指南与加分点.md) 第四节。

---

## 八、加分点（这个项目真正值钱的地方）

1. **可复算血缘，而不是"看起来对"**——每条被采纳的边都必须带公式参数与证据，界面上可把结果倒推回原始快照。同类产品通常只给一个数字，这里给的是一条可以自己验算的算式。
2. **证据哈希自洽校验**——证据的 `snapshot_sha256` 必须等于其文档的 `content_sha256`，"引用了一张图但图被换过"在结构上不可能发生。
3. **三道门禁把"能看"和"能算"彻底分开**——覆盖率 ≥ 80% 才 `DATA_READY`；结构无阻断才 `GRAPH_READY`；必须存在至少一条"可调节点 → 可达结果终点"的路径才 `SCENARIO_READY`。从机制上排除"图很漂亮但点一下没反应"。
4. **确定性编译，同输入必同输出**——全程 `sorted` 排序，ID 由 `stable_id(prefix, *parts)` 生成（规范化 JSON 的 SHA-256 前 24 位大写十六进制），并记录 `graph_sha256 = sha256(canonical fullGraph)`。可复现，可对账。
5. **幂等入库，永不 TRUNCATE**——全部 `INSERT ... ON CONFLICT DO UPDATE/DO NOTHING`，重复跑同一批次不产生脏数据，也不清空历史。
6. **候选 / 确认 / 弃权三态，AI 不许越权**——策略常量写死在版本身份文件里：`AI_APPROVED_IS_CANDIDATE_AND_ABSTAIN`。把"AI 猜测"和"已确认事实"在数据结构层面分开，而不是靠文案提醒。
7. **凭据策略：密码以"引用"形式存在**——`credentialPolicy = EPHEMERAL_OR_ENV_REFERENCE_ONLY`，`--password-env` 传的是环境变量名；数据包明令禁止携带凭据；本地存储用 DPAPI 加密。审计时可直接证明密码没有落盘到交付物里。
8. **六层语义完全动态，一套引擎通吃全行业**——新增行业的边际成本接近线性。
9. **冻结版 + 哈希清单 + 版本注册表 = 可交付存档**——v2.19.13 冻结版带 `VERSION.json` 身份文件与 127 条 `SHA256SUMS.txt`，"这个结果到底是哪个版本跑出来的"有确定答案。
10. **只读与不补零的克制**——不改动源库、不填充缺失值、不臆测数据，把不确定性显式暴露。
11. **契约机器可校验，而非口头约定**——顶层 12 个必需键 + `additionalProperties: false` + 跨对象引用逐条校验。
12. **数据源按 Tier 分级**——T1 官方统计、T2 交易所与指定披露媒体公告、T3 行情代理，分级随数据源一起记录。

---

## 九、版本管理

判版本**只读各目录的 `VERSION.json`**，不要按文件夹时间推断。

| 版本 | 生命周期 | 端口 | 说明 |
|---|---|---|---|
| V2.19.13-frozen | `FROZEN` | 4184 | 不再接受功能修改，用于基线与回滚 |
| V2.20.0-composite | `ACTIVE_DEVELOPMENT` | 4186 | 当前开发 / 运行版本 |

冻结版完整性校验（127 条哈希）：

```powershell
$bad = @()
Get-Content SHA256SUMS.txt | ForEach-Object {
  $h, $f = $_ -split '\s+', 2
  if ((Get-FileHash -Algorithm SHA256 -LiteralPath $f).Hash.ToLower() -ne $h) { $bad += $f }
}
if ($bad) { "失败: $($bad -join ', ')" } else { "全部通过" }
```

---

## 十、注意事项与已知不一致

1. **端口不一致**：`start.ps1` 不带参数（默认 4179），README / `VERSION.json` 约定 4186。请统一用 `start-v220.ps1` 或显式 `--port 4186`。
2. **注册表路径过期**：`docs/NEXUS-VERSION-REGISTRY.md` 中记录的路径前缀仍为历史的 `D:\桌面\workspace\study\...`，需按本仓库结构自行替换。
3. **焦煤采集器入口版本混乱**：README 指向 v2，实际最新为 v4（`manifest.json` `packageVersion=4.0`）。**以 v4 为准。**
4. **两处"焦煤—钢铁"不是同一份数据**：`template/.../domains.js` 里的 `coal-steel` 是纯前端演示包（含神华 / 宝钢），与 `coal_network_collector` 产出的 `coal_power_v1`（华能 / 华电 / 国电电力）无关，不要混用。
5. **无独立日志文件**：服务日志走 stdout。
6. **冻结版不可改**：任何功能修改只能在 v2.20 进行，改动后需重新走编译与门禁。
7. **PostgreSQL 参考表结构尚未正式应用**：`v220_reference_schema_postgresql.sql` 是参考定义，每行业独立 schema 与 writer / readonly 角色仍需按流程正式创建后才能入库。

---

## 十一、文档索引

| 文档 | 说明 |
|---|---|
| [docs/使用指南与加分点.md](docs/使用指南与加分点.md) | 完整使用指南（10 分钟上手、三条路径、设计演进、加分点） |
| [docs/NEXUS-VERSION-REGISTRY.md](docs/NEXUS-VERSION-REGISTRY.md) | 版本注册表（权威版本清单） |
| [docs/DATABASE-TO-NETWORK-PACK-PROMPT-V2.md](docs/DATABASE-TO-NETWORK-PACK-PROMPT-V2.md) | 数据包指令 V2（推荐） |
| [docs/NETWORK-DATA-PACK-AI-GUIDE.md](docs/NETWORK-DATA-PACK-AI-GUIDE.md) | 数据包制作指南 |
| [docs/financial-world-sandbox-multi-industry-design.md](docs/financial-world-sandbox-multi-industry-design.md) | 多行业设计 |
| [docs/SIDE-CONVERSATION-TASK-SUMMARY.md](docs/SIDE-CONVERSATION-TASK-SUMMARY.md) | 关键决策与待办汇总 |
| [sandbox/v2.20-composite-network/README.md](sandbox/v2.20-composite-network/README.md) | 沙盒端详细说明 |
| [sandbox/v2.20-composite-network/V2.20-CRAWLER-DATA-CONTRACT.md](sandbox/v2.20-composite-network/V2.20-CRAWLER-DATA-CONTRACT.md) | 采集批次契约说明 |

---

## 十二、一句话总结

> 结果可复算（公式 + 血缘）、证据可验证（快照哈希自洽）、过程可复现（确定性编译 + `graph_sha256`）、写入可重放（幂等入库）。在此基础上，用动态六层语义 + Skill 驱动设计，把"新增一个行业"从一次重写工程压缩成一次对话。

---

## License

[MIT](LICENSE)
