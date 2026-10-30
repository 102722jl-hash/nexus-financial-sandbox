# 侧面对话任务总结

更新日期：2026-09-16

## 一、版本管理

### 冻结版本

```text
版本：V2.19.13-frozen
目录：D:\桌面\workspace\study\financial-world-sandbox-v2.19.13-frozen
端口：4184
```

冻结版本不再继续修改，用于恢复升级前状态。

### 当前复合版本

```text
版本：V2.20.0-composite
目录：D:\桌面\workspace\study\financial-world-sandbox-v2.20-composite-network
端口：4186
```

统一版本登记文件：`NEXUS-VERSION-REGISTRY.md`。

## 二、网络生成问题治理

本轮主要治理了以下问题：

- 字段识别完成后没有生成关系；
- 节点数量过少、节点分类错误或总标题错误；
- 节点之间有连线但不能传播；
- 变量可以调整但下游数值不变化；
- `AI_APPROVED` 关系没有进入候选传播；
- 网络文件已经生成，但网页列表无法正确打开；
- 负权重导致候选关系被网页判断为不可传播；
- 新数据进入数据库后网络结构残缺。

V2.20 增加三道独立门禁：

```text
DATA_READY
GRAPH_READY
SCENARIO_READY
```

分别用于检查：

- 数据、证据和字段是否合格；
- 节点、层级、公式和关系是否完整；
- 是否存在“可调节点 → 中间节点 → 结果节点”的完整传播路径。

局部问题进入隔离区；关系端点缺失、非法层级、主键冲突等结构问题会阻止网络发布。

## 三、统一爬虫数据规范

建立了行业无关的数据契约：

```text
nexus-crawler-batch-1.0.0
```

每个采集批次统一包含：

```text
network
batch
sources
documents
evidence
layers
entities
metric_definitions
observations
formulas
relations
```

标准流程：

```text
网页 / API / CSV / PDF
→ 原始快照
→ 可定位证据
→ 标准指标
→ 实体与层级
→ 公式和关系
→ PostgreSQL
→ 网络编译
```

主要文件：

- `financial-world-sandbox-v2.20-composite-network/V2.20-CRAWLER-DATA-CONTRACT.md`
- `financial-world-sandbox-v2.20-composite-network/v220_crawler_payload.schema.json`
- `financial-world-sandbox-v2.20-composite-network/v220_crawler_payload.example.json`
- `financial-world-sandbox-v2.20-composite-network/v220_reference_schema_postgresql.sql`
- `financial-world-sandbox-v2.20-composite-network/crawler_contract.py`
- `financial-world-sandbox-v2.20-composite-network/validate_crawler_payload.py`

## 四、数据库到网络的自动编译

实现了确定性网络编译器：

```text
financial-world-sandbox-v2.20-composite-network/crawler_network_compiler.py
```

编译规则：

```text
network_name        → 网络总标题
default_layer_code  → 节点分类
metric + entity     → 稳定节点
relations           → 上下游连线
formulas            → 传播公式
observations        → 节点基准值
editable_default    → 可调变量
```

缺少当前数值的指标仍可生成结构节点，但标记为：

```text
DATA_MISSING
```

这样可以保留完整的网络结构，不会因为暂时缺少某条数据而丢失节点或路径。

## 五、候选关系传播规则

统一规则：

```text
AI_APPROVED
→ 候选可传播关系
→ candidate_weight
→ AI_ASSUMPTION
→ ABSTAIN
```

同时规定：

- `weight` 和 `candidate_weight` 必须填写正数幅度；
- 正向或负向影响只由 `direction` 表示；
- 候选关系可以用于条件情景试算；
- 候选试算结果不能被解释为正式因果结论。

## 六、PostgreSQL 增量入库

实现了：

```text
financial-world-sandbox-v2.20-composite-network/crawler_postgres_ingest.py
```

入库特点：

- 使用稳定主键；
- 使用 `ON CONFLICT` 增量写入；
- 同一批次重复执行不会重复生成记录；
- 不执行 `TRUNCATE`；
- 保留历史批次和网络版本；
- 局部问题写入隔离表；
- 数据库密码只从环境变量或密钥引用读取。

参考数据库结构已经准备完成，但尚未直接应用到正式 PostgreSQL，避免未经确认改变现有数据库。

## 七、新增接口

新增接口：

```text
GET  /api/contracts/crawler
POST /api/contracts/crawler/validate
POST /api/contracts/crawler/compile
```

分别用于：

- 获取机器可读的数据契约；
- 在入库前校验采集批次；
- 自动生成并保存浏览器网络。

4186 当前运行进程启动时间早于接口更新，因此新接口需要重启服务后才能加载。已经生成的网络文件不受影响，目前可以直接读取。

## 八、新能源汽车采集器接入

新能源汽车采集器已经接入统一批次出口：

```text
new_energy_vehicle_collector/export_nexus_batch_v1.py
```

每日采集入口已经更新：

```text
new_energy_vehicle_collector/auto_collect_v1.py
```

当前每日流程：

```text
每日采集
→ 原有质量门禁
→ 生成统一标准批次
→ 契约校验
→ 自动编译网络
→ 发布到浏览器网络列表
```

质量门禁失败时：

```text
保存批次和错误报告
但不发布新网络
```

当前完整转换结果：

```text
来源：4
原始文档：15
证据：127
指标观测：127
指标定义：31
公式：24
指标级关系：24
网络节点：77
实例化关系：66
```

当前网络：

```text
网络方案：PLAN-8B61DA1F5482AB281477EC40
总标题：新能源汽车多链路传导网络
门禁：DATA_READY / GRAPH_READY / SCENARIO_READY
```

传播验证：

```text
新能源汽车渗透率 +20%
→ 影响 15 个节点
→ 产生 17 步计算记录
→ CANDIDATE_SCENARIO
→ ABSTAIN
```

接入说明：

```text
new_energy_vehicle_collector/NEXUS-BATCH-INTEGRATION.md
```

## 九、自动发布策略

确定的发布策略：

```text
质量门禁通过
→ 自动发布到网络列表
→ 保留旧版本
→ 不强制切换当前页面
```

用户刷新网络列表后可以选择新版本，不会自动覆盖当前正在查看的网络。

## 十、数据库与 readonly 权限

最终采用：

```text
一个 PostgreSQL 数据库
+ 每个行业一个独立 Schema
+ 每个行业独立 writer
+ readonly 只读取网络发布视图
```

`readonly` 默认只允许访问：

```text
published_networks
published_layers
published_nodes
published_edges
published_metric_values
published_evidence
```

`readonly` 不能访问：

```text
raw_documents
quarantine
ingestion_runs
采集日志
密码和凭据
未审核数据
未发布公式和关系
```

因此，符合规范的行业 Schema 接入网络时，不需要再手工选择表和字段，只需要选择要打开的网络版本。

## 十一、个人 Skill

已创建并安装个人 Skill：

```text
$build-industry-network-collector
```

安装位置：

```text
C:\Users\LL\.codex\skills\build-industry-network-collector
```

调用示例：

```text
使用 $build-industry-network-collector
帮我创建一个储能行业的数据采集数据库和传导网络。
```

Skill 会依次完成：

1. 确认行业、地区、公司和最终结果；
2. 推荐应采集的指标；
3. 让用户选择指标；
4. 推荐数据来源和备用来源；
5. 确认采集周期、时间和历史回填；
6. 确认数据库 Schema 和密码管理方式；
7. 生成采集项目和数据库发布视图；
8. 验证节点、层级、公式和传播路径；
9. 门禁通过后发布到网络列表。

Skill 不会要求用户在聊天中发送明文密码，而是让用户选择：

```text
AUTO_GENERATE_LOCAL
USER_ENV
SECRET_MANAGER
```

Skill 文档：

- `C:\Users\LL\.codex\skills\build-industry-network-collector\SKILL.md`
- `references/interview-and-decisions.md`
- `references/database-publishing-contract.md`
- `references/source-and-network-gates.md`
- `assets/domain-spec.template.json`
- `assets/published_views.template.sql`

## 十二、验证结果

已经通过：

```text
JSON Schema 校验
爬虫数据契约：22/22
网络编译与变量传播：22/22
PostgreSQL 幂等入库：13/13
复合网络门禁：24/24
通用公式回归：25/25
预编译网络回归：30/30
契约接口：6/6
编译接口：7/7
新能源汽车原网络：7 项测试通过
个人 Skill 官方结构校验：通过
```

## 十三、后续待办

1. 重启 4186 服务，加载新增契约和编译接口；
2. 确认后将参考表结构应用到正式 PostgreSQL；
3. 为正式数据库创建每行业独立 Schema、writer 和 network readonly；
4. 验证 readonly 只能访问六个发布视图；
5. 使用 `$build-industry-network-collector` 创建下一个行业板块；
6. 对新行业完成一次真实采集、入库、网络生成和变量传播验收。
