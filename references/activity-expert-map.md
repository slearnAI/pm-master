# Activity → Expert Dispatch Map · Activity-to-Expert Map

This file is the "routing table" for PM Master's second-layer dispatch: given the **domain, product, and task keywords** of a WBS activity/deliverable,
it determines which **expert role** should produce it. Works together with `references/expert-roles.md` (role definitions and prompts)
and `scripts/dispatch.py` (auto-generates the dispatch plan).

> **Single source of truth = `scripts/role_catalog.py`.** The domain catalogue, keyword maps, and
> specialization naming all live there. `dispatch.py` and `consistency_check.py` import it; this document
> is the human-readable mirror. **The pack is domain-agnostic** — it ships no data-domain bias and applies
> to any tech project (software / cloud / data / AI / security / product / QA / integration / ERP / BI).

## 1. Tech Domains (inferred from contract/SOW extract)

`infer_domain(text)` scans the SOW/contract objective+scope+assumptions and picks the best-matching domain.
When no signal is found, domain = `generic` and roles fall back to cross-cutting / neutral defaults.

| domain key | covers |
|------------|--------|
| `data-platform` | data lake / warehouse / ETL / modeling / governance |
| `software-dev` | application / backend / frontend / microservice / mobile |
| `cloud-infra` | cloud / k8s / terraform / SRE / platform / DevOps / network |
| `ai-ml` | LLM / GenAI / ML / model training / MLOps |
| `cybersecurity` | security / privacy / AppSec / SecOps |
| `product` | product management / ownership / UX |
| `qa` | test engineering / automation / performance |
| `integration` | ESB / middleware / API gateway |
| `erp` | ERP implementation / finance-HR modules |
| `biz-analytics` | BI / reporting / metrics layer |

> `project.domain` may also be set explicitly (e.g. via `init_project.py --domain <domain>`); an explicit
> domain overrides inference. Legacy project domains (`insurance-data-lake` / `payments` / `ecommerce` /
> `fintech-core`) still resolve via a backward-compat map in `role_catalog.py` so existing programs keep
> their specialization labels.

## 2. Activity Type → Role (keyword routing, by domain)

Routing is **two-tier**: (1) if a domain is known, its domain-specific role keywords win; (2) otherwise
cross-cutting keywords apply; (3) ambiguous words fall back to a neutral role (e.g. "model/设计" → `solution-architect`).
Representative mappings (full set in `role_catalog.py`):

| Activity / deliverable keywords (CN/EN) | domain | dispatch role role_id |
|------------------------------|--------|------------------|
| 建模 / model / schema / ERD / 主题域 | data-platform | `data-architect` |
| 迁移 / ETL / load / 数据管道 | data-platform | `etl-engineer` |
| 治理 / 元数据 / 血缘 / 审计 | data-platform | `data-governance-lead` |
| 脱敏 / 隐私 / PII / 加密 / 合规 | data-platform / cybersecurity | `data-security-engineer` / `privacy-engineer` |
| 架构设计 / 模块 / 系统设计 | software-dev | `software-architect` |
| 后端 / 服务端 / API 实现 | software-dev | `backend-engineer` |
| 前端 / 界面 / UI | software-dev | `frontend-engineer` |
| 全栈 / fullstack | software-dev | `fullstack-engineer` |
| 移动端 / iOS / Android | software-dev | `mobile-engineer` |
| 云架构 / landing zone | cloud-infra | `cloud-architect` |
| 可靠性 / SRE / 容灾 | cloud-infra | `sre-engineer` |
| 平台工程 / DevOps / CI-CD | cloud-infra | `platform-engineer` / `devops-engineer` |
| 网络 / VPC / DNS | cloud-infra | `network-engineer` |
| 大模型 / LLM / RAG / 微调 | ai-ml | `llm-engineer` |
| 模型训练 / 特征工程 / ML | ai-ml | `ml-engineer` |
| 模型部署 / 监控 / MLOps | ai-ml | `mlops-engineer` |
| 渗透 / 零信任 / 安全加固 | cybersecurity | `security-engineer` |
| 应用安全 / SAST / DAST | cybersecurity | `appsec-engineer` |
| 安全运营 / SOC / 威胁检测 | cybersecurity | `secops-engineer` |
| 产品规划 / roadmap / 需求管理 | product | `product-manager` |
| backlog / 产品负责人 | product | `product-owner` |
| 用户体验 / UX / 原型 | product | `ux-designer` |
| 测试 / UAT / 质量 | qa (or cross-cutting `qa-lead`) | `qa-engineer` |
| 自动化测试 / 测试框架 | qa | `test-automation-engineer` |
| 性能测试 / 压测 | qa | `performance-engineer` |
| 集成 / ESB / 中间件 / 对接 | integration | `integration-engineer` |
| API 设计 / 网关 | integration | `api-engineer` |
| ERP 实施 / 业务流程 / blueprint | erp | `erp-consultant` |
| ERP 开发 / 二次开发 | erp | `erp-developer` |
| 报表 / dashboard / BI | biz-analytics | `bi-engineer` |
| 指标 / 指标体系 / marts | biz-analytics | `analytics-engineer` |
| 培训 / 赋能 / 课程 | cross-cutting | `enablement-lead` |
| 基础设施 / 安装 / 环境 / 部署 | cross-cutting | `infra-engineer` |
| SME / 业务知识 / 源系统 | cross-cutting | `domain-sme` |
| 测试 / UAT / 质量 (generic) | cross-cutting | `qa-lead` |
| 需求 / 用户故事 / 规格 | cross-cutting | `ba` |
| 变更 / CCB | cross-cutting | `change-manager` |
| 蓝图 / 集成 / 方案 (program) | cross-cutting | `solution-architect` |
| charter / RACI / 沟通 / 状态 / 风险 / 排期骨架 | PM-generalist | existing (planner/risk/stakeholder/…) |

> The matching engine lives in `role_catalog.py` (`infer_role`). `dispatch.py` and `consistency_check.py`
> share it (single source of truth). To add a domain or role, edit `role_catalog.py` only.

## 3. Granularity Standard —— preventing "SOW-level coarse-grained WBS"

An experienced team's WBS is not 10 SOW packages but **hundreds of leaf work packages**. Decision rules:

- **Leaf work package (leaf)**: `estimate` (person-days) ≤ `granularity_threshold` (default **10 person-days**;
  can be overridden via `control.granularity_threshold` in `project.yaml`).
- Any package with `estimate > threshold` is treated as a **summary package**, and its domain expert must be dispatched to further decompose it into
  leaf packages beneath it, **until all leaves ≤ threshold**.
- Required fields for a leaf package: `id` / `name` / `deliverable` / `role` (producing role) / `owner` / `estimate`
  / `acceptance` (DoD) / `dependsOn` / `domain`.
- **ID convention**: leaf packages decomposed by an expert inherit the parent package prefix, e.g. under `SOW1` there are `SOW1.1`, `SOW1.2`…;
  levels are separated by `.` to keep dependencies pointable.

## 4. Dispatch Flow (executed by the master controller, see orchestration.md §3.2)

```
1. Draft WBS (SOW-level summary packages, tagged with domain)
2. Tag each package's role (if absent, infer via §2 keywords, write to wbs[].role / wbs[].domain)
3. For each summary package (estimate > threshold) dispatch the corresponding expert sub-Agent:
   - Use that role's system_prompt from expert-roles.md (substituting DOMAIN/PRODUCT)
   - brief: decompose "<package name>" into leaf packages (≤ threshold person-days), write back to project.yaml.wbs (ID prefix <package ID>.x)
4. Expert writes back leaf packages → master re-renders wbs.md → runs consistency_check (new gate validates role tags + granularity)
5. If not passed, return to the corresponding expert to keep decomposing, until all leaves ≤ threshold and all domain activities have role tags
```

## 5. Consistency Gate Integration (consistency_check.py)

- **Domain activity missing a `role` tag → fatal by default (exit 1 blocks delivery)**; under `--strict`, other warnings are also escalated to fatal.
- Domain activities with `estimate > granularity_threshold` that are not decomposed → **fatal by default**; non-domain activities exceeding the threshold are only warnings (generic granularity hint).
- Program-level `summary` rollup packages (SOW/P0 parent packages) are skipped; the component-layer leaf packages carry them instead.

These two gates keep "coarse-grained SOW-level WBS not decomposed by experts / self-decomposed by master" out the door—you must go through `dispatch.py` → domain expert sub-Agent decomposition,
otherwise `consistency_check.py` will rule it fatal before delivery and it cannot be released (see SKILL.md Step 2.5 / §6).
