# 活动 → 专家调度映射 · Activity-to-Expert Map

本文件是 PM Master 第二层调度的"路由表"：给定 WBS 活动/交付物的**领域、产品、任务关键词**，
决定应调度哪个**专家角色**产出它。配合 `references/expert-roles.md`（角色定义与 prompt）
与 `scripts/dispatch.py`（自动生成调度计划）。

## 1. 领域特化（按 project.domain / project.product）

调度时把通用 `role_id` 特化为带领域味儿的专家名，让子 Agent / 专家更聚焦。

| domain | product 示例 | 关键角色特化 |
|--------|--------------|--------------|
| `insurance-data-lake` | 客户A 数据湖（代号 ALPHA，MPP 数仓） | 保险主题域数据架构师 · MPP 数仓 TPT/ETL 工程师 · 个保法/PII 合规工程师 · 保险精算/分析建模工程师 · 保险数据治理与审计负责人 |
| `payments` | 支付清算平台 | 支付领域架构师 · 支付 ETL 工程师 · PCI-DSS 安全工程师 · 反欺诈建模工程师 |
| `ecommerce` | 电商中台 | 电商域建模师 · 订单/商品/用户工程师 · 推荐/搜索 ML 工程师 |
| `fintech-core` | 核心银行系统 | 核心银行领域架构师 · 账务/清算工程师 · 监管报送工程师 |
| `default` | — | 通用 `<role_id>`（不特化） |

> 特化命名由 `dispatch.py` 依据上表生成；未命中 domain 时回退到 `role_id` + product 名。

## 2. 活动类型 → 角色（关键词路由）

| 活动 / 交付物关键词（中/英） | 调度角色 role_id | 说明 |
|------------------------------|------------------|------|
| 数据建模 / 模型 / 主题域 / schema / ERD / 数据模型 / model | `data-architect` | 含概念-逻辑-物理模型 |
| 迁移 / 历史加载 / 抽取 / ETL / 加载 / 接入 / migration / load | `etl-engineer` | |
| 脱敏 / 掩码 / 隐私 / PII / 令牌 / 加密 / mask / privacy | `data-security-engineer` | |
| 分析 / 建模 / 特征 / ML / ModelOps / 用例 / analytic | `data-scientist` | |
| 容灾 / 业务连续 / BCM / DR / RPO / RTO / 故障切换 | `dr-bcp-engineer` | |
| 治理 / 元数据 / 血缘 / 审计 / 加固 / governance / meta / audit / hardening | `governance-lead` | |
| 培训 / 赋能 / 课程 / training / enable | `enablement-lead` | |
| 基础设施 / 安装 / 环境 / infra / install / env / 部署 | `infra-engineer` | |
| SME / 业务知识 / 源系统 / 领域支持 | `domain-sme` | |
| 测试 / UAT / 质量 / test / quality | `qa-lead` | 横切 |
| 需求 / 用户故事 / 规格 / requirement / story | `ba` | 横切 |
| 变更 / CCB / change | `change-manager` | 横切 |
| 蓝图 / 集成 / 方案 / blueprint / integration / solution | `solution-architect` | 项目群级 |
| 章程 / RACI / 沟通 / 状态 / 风险 / 排期骨架 | PM-generalist | 已有（planner/risk/stakeholder/…） |

> 关键词匹配顺序即上表自上而下；命中第一个即定角色。`dispatch.py` 与 `consistency_check.py`
> 共用此路由（保持单一事实源，避免漂移）。

## 3. 颗粒度标准（Granularity Standard）—— 防止"SOW 级粗粒度 WBS"

经验团队的 WBS 不是 10 个 SOW 包，而是**数百个叶子工作包**。判定规则：

- **叶子工作包（leaf）**：`estimate`（人天）≤ `granularity_threshold`（默认 **10 人天**；
  可在 `project.yaml` 的 `control.granularity_threshold` 覆盖）。
- 任何 `estimate > 阈值` 的包视为**汇总包（summary）**，必须调度其领域专家进一步拆解为其下
  叶子包，**直到全部叶子 ≤ 阈值**。
- 叶子包必备字段：`id` / `name` / `deliverable` / `role`（产出角色）/ `owner` / `estimate`
  / `acceptance`(DoD) / `dependsOn` / `domain`。
- **ID 规范**：专家拆出的叶子包沿用父包前缀，如 `SOW1` 下为 `SOW1.1`、`SOW1.2`…；
  跨层用 `.` 分隔，保证依赖可指向。

## 4. 调度流程（主控执行，见 orchestration.md §3.2）

```
1. 初稿 WBS（SOW 级 summary 包，标 domain）
2. 标注每个包的 role（无则按 §2 关键词推断，写入 wbs[].role / wbs[].domain）
3. 对每个 summary 包（estimate>阈值）调度对应专家子 Agent：
   - 用 expert-roles.md 中该角色的 system_prompt（代入 DOMAIN/PRODUCT）
   - brief：把『<包名>』拆成叶子包(≤阈值人天)，写回 project.yaml.wbs（ID 前缀 <包ID>.x）
4. 专家回写叶子包 → 主控重新渲染 wbs.md → 跑 consistency_check（新门禁校验 role 标签 + 颗粒度）
5. 未通过则退回对应专家继续拆，直到叶子全 ≤ 阈值、领域活动均有 role 标签
```

## 5. 一致性门禁联动（consistency_check.py 新增）

- 领域活动缺 `role` 标签 → **告警**（默认）；`--strict` 下**致命**。
- `estimate > granularity_threshold` 且未拆解 → **告警**（默认）；`--strict` 下**致命**。

这两条门禁直接把"粗粒度 WBS 未经专家拆解就当交付"挡在门外。
