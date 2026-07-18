# PM Master · 项目与项目群管理技能

> 面向科技行业 PM 的**项目 + 项目群**管理技能。Builder 理念、可执行、内置模板库、支持多 Agent 调度，
> 适配 **waterfall / agile / iteration / hybrid** 四种实施方法论。

- **版本**：1.3.6
- **许可**：MIT
- **定位**：任何项目/项目群请求都必须落到真实产物（文件），禁止只给建议。

---

## 1. 它解决什么问题

科技行业的项目交付常常卡在三件事上：**方法论不统一**（瀑布/敏捷/迭代/混合混用）、
**交付物无标准**（章程/WBS/风险/状态报告各自为政）、**治理不可持续**（计划与执行脱节、缺基线、
缺周期巡检）。PM Master 把这三件事固化成一个**可执行工程系统**：

- 每个请求 → 一份真实文件（Markdown，可导出 DOCX）；
- 每个项目 → 一份 `project.yaml` 单一事实源，跨会话/跨 Agent 连续；
- 每条纪律 → 一道可校验的质量门（一致性门禁、基线化、运营控制）。

---

## 2. 核心能力

| 能力 | 说明 | 适用 |
|------|------|------|
| 项目启动 / 规划 | 章程、干系人、RACI、WBS、排期、风险、RAID | 任何方法论 |
| 敏捷交付 | 产品 Backlog、Sprint 计划、DoD、燃尽、回顾 | agile |
| 迭代交付 | 迭代计划 / Backlog / 评审 | iteration |
| 瀑布交付 | 需求规格、WBS、甘特、阶段门、质量计划 | waterfall |
| 混合治理 | 治理地图、宏微映射 | hybrid |
| 项目群治理 | 组合章程、组合看板、依赖图、收益实现 | program |
| 指标分析 | 挣值 EVM、排期关键路径、一致性校验 | 分析场景 |
| 多 Agent 并行 | 组队产出互相独立的产物 | 复杂启动 / 评审 |
| 双轨文档 | Markdown 源 → DOCX 正式件 | 交付 / 汇报 |
| 阶段化交付 | P0+P1 启动规划 / P2 执行 / P3 监控 / P4 收尾 阶段模块，每阶段定义活动/交付物/准则 | 全周期 |
| 阶段门审批 | gate_engine 评估入口准则 + 硬门（执行/收尾）强制审批，翻转状态机 | 阶段流转 |
| operational 双轨并行 | P2 执行轨（领域专家）+ P3 监控轨（monitoring-agent）多 Agent 并行，共享事实源、字段零冲突 | 执行/监控 |
| 对外沟通与邮件审批 | communication_plan 登记相关方联络簿；communication-agent 起草，comm_send.py 强制审批门 + 审计，分层配置（安装期护栏 / 项目期数据） | 沟通/邮件 |

---

## 3. 快速开始

### 3.1 安装
把技能目录放到 CodeBuddy 的 `skills/` 下：

```bash
# 例如
cp -r pm-master /root/.codebuddy/skills/pm-master
```

技能随会话自动可用，无需额外安装。也可直接解压分发的 `pm-master.zip` 到该目录。

> **安装期配置（策略/护栏）**：技能根 `config.yaml` 定义邮件能力与安全护栏——
> `email.enabled` / `email.backend`（agent-mail·himalaya·gog·smtp）/ `email.default_from` /
> `email.requires_send_approval`（硬护栏，项目不可关闭）。安装时按需填写；项目级数据（联络簿/节奏）
> 在 `project.yaml` 的 `communication:` 块。详见 `references/project-schema.md` 与 `scripts/comm_send.py`。

### 3.2 最小可用三步（命令行）

```bash
SKILL_DIR=/root/.codebuddy/skills/pm-master

# 1) 建工作区（单一事实源 project.yaml 在此生成）
python3 $SKILL_DIR/scripts/init_project.py "支付重构" --type project --methodology agile --framework scrum

# 2) 用模板产出一份风险登记册（先准备数据 yaml，再渲染）
python3 $SKILL_DIR/scripts/render.py \
  --template $SKILL_DIR/templates/common/risk_register.md \
  --data risks.yaml --out /workspace/支付重构/risks/risk_register.md

# 3) 导出正式 Word 文档
python3 $SKILL_DIR/scripts/render_docx.py /workspace/支付重构/risks/risk_register.md
```

> 自然语言触发更简单：直接对 Agent 说"用敏捷帮我启动支付重构项目"即可，不必手敲命令。

---

## 4. 核心概念

### 4.1 单一事实源 `project.yaml`
每个项目/项目群一个 `project.yaml`（位于工作区根 `/workspace/<slug>/project.yaml`）。
主控与所有子 Agent 都通过它读写，保证状态一致、跨会话连续。完整字段结构见
[`references/project-schema.md`](references/project-schema.md)；样例见 `examples/sample_project.yaml`。

### 4.2 四维度分类（每次请求先判定）
| 维度 | 取值 |
|------|------|
| `type` | project（项目） / program（项目群） |
| `methodology` | waterfall / agile / iteration / hybrid |
| `phase` | 启动 / 规划 / 执行 / 监控 / 收尾（项目群另有组合阶段） |
| `intent` | 规划 / 构建 / 汇报 / 分析 / 治理 |

### 4.3 三种执行模式（混合调度）
| 模式 | 何时用 | 做法 |
|------|--------|------|
| **direct（直做）** | 单产物 / 解释 / 微调 | 主控直接调脚本或模板完成 |
| **team（组队并行）** | 多独立产物（如启动需章程+WBS+风险+RACI） | 同消息并行派出专职子 Agent，聚合 + 一致性校验 |
| **fork（续上下文）** | 需完整上下文接力（如"接着上次风险分析继续"） | 子 Agent 继承本会话全部上下文 |

> **TeamCreate** 是本环境的多 Agent 并发派发机制（Agent 工具的 team 模式）。子 Agent 角色与 brief
> 模板见 [`references/agents.md`](references/agents.md)，调度决策树见
> [`references/orchestration.md`](references/orchestration.md)。

### 4.4 强制状态机：规划 → 基线 → 运营控制
`lifecycle_state` 的强制串行纪律（详见 [`references/lifecycle.md`](references/lifecycle.md) §5）：

```
planning → review → baselined → operational → closed
```

- **waterfall / hybrid** 进入执行/监控前**必须** `baseline.py --freeze`（冻结计划为基线）；
- 经控制门把 `lifecycle_state` 置为 `operational` 后，才能用 `control_engine.py` 周期巡检；
- 未基线化（缺 `baseline` 指针）的项目**不得**进入运营阶段，一致性门禁会直接阻断。

### 4.5 阶段模块与阶段门（Phase Modules & Gates）
启动→规划→执行→监控→收尾 拆成 4 个阶段模块（`references/phases/`），每模块定义该阶段的
**活动 / 必产出交付物 / 入口准则 / 出口准则 / 阶段门审批清单**，并适配各方法论。阶段间流转由
`gate_engine.py` 管控（硬门复用 `consistency_check` / `control_engine`，未过则 exit 1 拒绝推进）：

- G0→1 启动→规划（软门 / PM）
- **G1→2 规划→执行（硬门 / sponsor）**：须 `consistency_check.py` exit 0（waterfall/hybrid 另须 `baseline.py --freeze`）
- G2→3 执行→监控（软门 / PM，operational 内并发）
- **G3→4 监控→收尾（硬门 / sponsor）**：须 `control_engine.py` exit 0 + 验收/复盘交付物 +（项目群）收益闭环

详见 `lifecycle.md` §6 与 `references/phases/*`。

---

## 5. 标准工作流（每次都遵循）

- **Step 0 · 定位事实源**：找 `project.yaml`；若不存在 → `init_project.py` 建骨架。
- **Step 1 · 分类路由**：判定 type / methodology / phase / intent 四维度；判定 `phase` 后读取对应阶段模块（`references/phases/*`），按该模块的活动/交付物/准则推进，阶段间流转须过 `gate_engine.py` 阶段门。
- **Step 2 · 读方法论手册**：按 methodology 读 `references/methodology-*.md`（项目群读 `program-management.md`）。
- **Step 2.5 · 专家调度（WBS 拆到叶子包）**：`planner-agent` 出 SOW 级摘要包；`dispatch.py` 审计并生成调度计划；领域专家子 Agent 把包拆到叶子级（≤ `control.granularity_threshold` 人天，默认 10）。
- **Step 3 · 选执行模式**：direct / team / fork（见 §4.3）。
- **Step 4 · 构建产物**：脚手架 + `render.py` 渲染 + **强制跑分析脚本**（`schedule_health` / `evm`）+ 交付前**必过 `consistency_check.py`**。
- **Step 5 · 组队（仅 team 模式）**：TeamCreate 派专职子 Agent，主控聚合 + 一致性校验。
- **Step 6 · 交付**：更新 `artifacts` 索引；按需 `render_docx.py`；向用户汇总产物清单 + 指标卡。

---

## 6. 模板库（35 个 + `_macros.md`）

| 目录 | 数量 | 模板 |
|------|------|------|
| `common/` | 16 | project_charter, stakeholder_register, raci, communication_plan, raid_log, risk_register, status_report, lessons_learned, closure_report, project_board, milestone_list, change_request, change_log, baseline_record, control_register, control_report |
| `waterfall/` | 5 | requirements_spec, wbs, schedule_gantt, stage_gate_review, quality_plan |
| `agile/` | 5 | product_backlog, sprint_plan, definition_of_done, burndown, retro |
| `iteration/` | 3 | iteration_plan, iteration_backlog, iteration_review |
| `hybrid/` | 2 | hybrid_governance, macro_micro_map |
| `program/` | 4 | program_charter, portfolio_dashboard, dependency_map, benefits_realization |

每个模板的**数据键契约**见 [`references/templates-index.md`](references/templates-index.md)。

---

## 7. 脚本速查

所有脚本位于 `scripts/`，用 `python3` 运行。

| 脚本 | 用途 | 命令示例 |
|------|------|----------|
| `init_project.py` | 建工作区 + project.yaml | `python3 init_project.py "项目名" --type project --methodology agile --framework scrum [--domain <领域> --product <产品>]` |
| `render.py` | 模板 + 数据 → Markdown | `python3 render.py --template T --data D.yaml --out O.md` |
| `render_docx.py` | Markdown → DOCX | `python3 render_docx.py O.md [--out O.docx]` |
| `evm.py` | 挣值分析 | `python3 evm.py --data metrics.yaml` |
| `schedule_health.py` | 关键路径 / 依赖 / 浮动 | `python3 schedule_health.py --project <项目>/project.yaml`（或 `--data schedule.yaml [--start 2025-08-01]`） |
| `consistency_check.py` | 交付前质量门（控制级，exit 1=阻断） | `python3 consistency_check.py --project <项目>/project.yaml [--strict]` |
| `baseline.py` | 计划冻结为基线（前置质量门） | `python3 baseline.py --freeze --project <项目>/project.yaml`；`--status` 查看状态 |
| `control_engine.py` | 运营控制引擎（对照基线周期巡检，exit 1=有 RED 升级） | `python3 control_engine.py --project <项目>/project.yaml [--as-of 2026-08-12] [--json]` |
| `dispatch.py` | 专家调度计划（审计 WBS 缺 role / 超阈值） | `python3 dispatch.py --project <项目>/project.yaml [--threshold 10] [--out dispatch_plan.md] [--json]` |
| `rollup_program_wbs.py` | 项目群 WBS 两层化（里程碑级 / 组件级） | `python3 rollup_program_wbs.py <项目群>/project.yaml [--derive-actuals]` |
| `project_state.py` | 单一事实源读写 | `python3 project_state.py get project.phase --file project.yaml` |
| `gate_engine.py` | 阶段门引擎（评估/审批进入目标阶段，硬门复用 consistency/control） | `python3 gate_engine.py --project <项目>/project.yaml --to 执行 [--approve "张三(sponsor)"]`；`--status` 看当前状态与可走的门 |
| `test_gate_engine.py` | 阶段门引擎单测套件（CI 门禁，66 断言覆盖 4 方法论 × 软/硬门 / 被拒 / dry-run / --status） | `python3 test_gate_engine.py`（无参；退出码 0=全过，1=有失败，可挂 CI） |
| `comm_send.py` | 对外邮件审批门（按角色解析 `communication.contacts[]` 收件人，强制 `--approve` 后委派后端，写 `governance.communications` 审计；`--dry-run` 不真正外发） | `python3 comm_send.py --project <项目>/project.yaml --to "sponsor,pm" --subject "里程碑达成" --body-file draft.md --approve "张三(PM)"`；`--dry-run` 仅复核 |

> ⚠️ **脚本异常处理**：若脚本缺失/路径错误/参数非法，不要静默失败——给出具体报错，并降级为：
> ① 用 `project_state.py` 维护 `project.yaml`；② 用 `render.py` 直接渲染模板；③ 缺 PyYAML 时先 `pip install pyyaml`。

---

## 8. 关键规则（摘要）

- **绝不 advice-only**：任何请求都要产出文件或运行分析，至少更新 `project.yaml`。
- **先有事实源**：没有 `project.yaml` 就先 `init_project.py`。
- **方法论要对味**：agile 用 backlog/sprint/burndown，waterfall 用 WBS/甘特/阶段门。
- **估算强制**：WBS / backlog 每行必须有数值化估算(>0)，不允许占位。
- **专家调度 + 叶子包颗粒度**：技术领域工作包须由对应领域专家拆解，标 `role` 与 `domain`，叶子包 ≤ 阈值。
- **分析强制**：waterfall / hybrid 交付前跑 `schedule_health`；执行/监控阶段跑 `evm`。
- **交付前过质量门**：`consistency_check.py` exit 0 才放过；致命项（估算缺失 / 排期未联网 / 缺 EVM 基线 / 混合缺微计划 / 风险未校准 5×5 / 收益缺 owner / 未基线化）直接阻断。
- **规划 ≠ 运营化（强制串行）**：先规划→评审→`baseline.py --freeze`→控制门→才能进入执行/监控。
- **运营控制循环**：进入 `operational` 后按 `control.cadence` 周期跑 `control_engine.py`，对照基线巡检；RED 升级退出码 1，可挂定时任务告警。
- **阶段流转须过阶段门（强制）**：启动→规划→执行→监控→收尾 按状态机串行推进；进入 `执行`（G1→2）与 `收尾`（G3→4）为**硬门**，须经 `gate_engine.py` 评估且自动化准则全过、由 sponsor 审批后才翻转 `lifecycle_state`；`监控`（G2→3）为**软门**（PM 审批）。硬门不可跳过（见 `references/phases/*`、`lifecycle.md` §6）。

---

## 9. 扩展指南（无需改引擎）

1. **新增产物模板**：在对应目录放 `my_template.md`（用 `render.py` 语法写占位符）。
2. **登记数据键**：在 `references/templates-index.md` 加一行（模板文件 / 数据键 / 说明）。
3. **新增方法论**：建 `references/methodology-xxx.md` + `templates/xxx/`，在 SKILL.md 路由表与 templates-index 登记。
4. **新增分析脚本**：放 `scripts/`，在 SKILL.md 脚本速查与对应 reference 引用即可。

---

## 10. 项目群（Program）专项

- 用 `init_project.py --type program` 建组合级工作区。
- 组合章程 / 组合看板 / 跨项目依赖图 / 收益实现计划，均为项目群专属模板。
- `rollup_program_wbs.py` 把单源 `wbs` 两层化：项目群层级 = 里程碑级、组件层级 = 叶子工作包级；
  组件/阶段映射优先读 `project.yaml` 的 `program.components` / `governance.waves`，缺省回退内置示例。
- 项目群阶段（组合定义/交付/收尾）与生命周期状态机（planning→…→closed）是正交两层，详见 `lifecycle.md` §5.3。

---

## 11. 参考文档索引

| 文件 | 何时读 |
|------|--------|
| `references/orchestration.md` | 多 Agent 调度、判定执行模式 |
| `references/agents.md` | 派遣专职子 Agent、写 brief |
| `references/expert-roles.md` | 领域专家角色目录 + system prompt |
| `references/activity-expert-map.md` | 活动→角色路由、专家特化、叶子包颗粒度 |
| `references/lifecycle.md` | 阶段-交付物矩阵、生命周期与状态机 |
| `references/methodology-*.md` | 各方法论（waterfall/agile/iteration/hybrid） |
| `references/hybrid_playbook.md` | 混合实操：节奏/微计划/对齐评审/变更控制 |
| `references/risk-matrix.md` | 风险 5×5 校准刻度与色带 |
| `references/program-management.md` | 项目群（组合）管理 |
| `references/metrics.md` | EVM / 燃尽 / 健康度指标口径 |
| `references/project-schema.md` | `project.yaml` 完整字段结构与协同约定 |
| `references/templates-index.md` | 模板库全量清单与数据键契约 |
| `references/usage.md` | 完整使用手册（端到端示例、提示词库） |
| `references/phases/p0-p1-initiation-planning.md` | P0+P1 启动与规划阶段模块 |
| `references/phases/p2-execution.md` | P2 执行阶段模块 |
| `references/phases/p3-monitoring.md` | P3 监控阶段模块 |
| `references/phases/p4-closeout.md` | P4 收尾阶段模块 |

---

## 12. 版本与变更

变更历史见 [`CHANGELOG.md`](CHANGELOG.md)。当前版本 **1.3.5**（v1.2.0 引入阶段模块 P0–P4 与阶段门引擎 `gate_engine.py`；v1.2.1 同步本 README；v1.2.2 新增 `gate_engine.py` 单测套件；v1.3.0 新增 **operational 双轨并行** 与 **对外邮件审批门**；v1.3.1 **脱敏**：移除真实客户名 / 厂商名等敏感信息，统一改为代号（客户A / MPP 数仓 / 代号 ALPHA），消除法律风险；v1.3.2 进一步脱敏：`rollup_program_wbs.py` 示例映射去标识化（SOW slug 去后缀 / Wave→Stream / 移除 FSAS·NOS·金融与协议）；v1.3.3 新增英文版 `README.en.md` 并确立「中文与英文双语文档同步」规则；v1.3.4 **Mermaid 渲染稳定性 + SOW 级 WBS 强制专家拆解**；v1.3.5 **WBS→排期交付物（build_schedule/build_wbs）+ per-SOW 启动会（build_sow_kickoff）+ 风险登记册色标图标（sev_icon）**；v1.3.6 **项目群级排期（build_schedule --level program）+ SOW 子计划（--sow）+ Mermaid 里程碑语法修复 + 组合看板色标图标（sev_icon）；OpenClaw 英文包运行时输出英文化**）。

> **文档同步规则**：每次技能变更须同步更新 `README.md`（中文）与 `README.en.md`（英文）两份文档，并与 `SKILL.md` / `CHANGELOG.md` / 版本号保持一致；英文版与 OpenClaw 纯英文技能包同源生成。

---

_PM Master · 让项目管理真正"可执行"。_
