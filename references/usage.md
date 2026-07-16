# PM Master · 完整使用文档

> 面向科技行业 PM 的「项目 + 项目群」管理技能。Builder 理念、可执行、内置模板库、支持多 Agent 调度，
> 适配 **waterfall / agile / iteration / hybrid** 四种方法论。本文档是技能的**完整使用手册**。

---

## 目录
1. [快速开始](#1-快速开始)
2. [能力地图](#2-能力地图)
3. [核心概念](#3-核心概念)
4. [端到端工作流（按场景）](#4-端到端工作流按场景)
5. [多 Agent 调度详解](#5-多-agent-调度详解)
6. [模板库总览](#6-模板库总览)
7. [脚本速查](#7-脚本速查)
8. [双轨产出（Markdown → DOCX）](#8-双轨产出markdown--docx)
9. [指标口径](#9-指标口径)
10. [扩展指南](#10-扩展指南)
11. [常见问题 FAQ](#11-常见问题-faq)
12. [完整示例：从 0 启动一个敏捷项目](#12-完整示例从-0-启动一个敏捷项目)
13. [提示词示例库](#13-提示词示例库)

---

## 1. 快速开始

**启用**：把技能目录放在 CodeBuddy 的 `skills/` 下（本环境已位于 `/root/.codebuddy/skills/pm-master/`），
技能随会话自动可用，无需额外安装。

**最小可用三步**：

```bash
# 1) 建工作区（单一事实源 project.yaml 在此生成）
python3 <SKILL_DIR>/scripts/init_project.py "支付重构" --type project --methodology agile --framework scrum

# 2) 用模板产出一份风险登记册（先准备数据 yaml，再渲染）
python3 <SKILL_DIR>/scripts/render.py \
  --template <SKILL_DIR>/templates/common/risk_register.md \
  --data risks.yaml --out /workspace/支付重构/risks/risk_register.md

# 3) 导出正式 Word 文档
python3 <SKILL_DIR>/scripts/render_docx.py /workspace/支付重构/risks/risk_register.md
```

> `<SKILL_DIR>` 指技能根目录，即包含 `SKILL.md` 的 `pm-master/`。
> 自然语言触发更简单：直接对 Agent 说"用敏捷帮我启动支付重构项目"即可，不必手敲命令。

---

## 2. 能力地图

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

---

## 3. 核心概念

### 3.1 单一事实源 `project.yaml`
每个项目一个 `project.yaml`，存在于项目工作区根目录（`/workspace/<slug>/project.yaml`）。
主控 Agent 与所有子 Agent 都通过它读写，保证**状态一致、跨会话连续**。关键字段：

```yaml
project:   { id, name, type(project|program), methodology, framework(scrum|kanban),
            phase, status, start_date, target_end, objectives[], scope, out_of_scope, sponsor, pm, team[] }
governance: { stage_gates[], cadence }
artifacts:  { charter: path, wbs: path, ... }   # 产物文件路径索引
raid:       { risks[], assumptions[], issues[], dependencies[] }
metrics:    { evm: {}, burndown[] }
program:    { projects[], dependencies[], benefits[] }   # 仅 type=program
```

读写可用 `scripts/project_state.py`：`get <key>` / `set <key> <value>` / `show` / `exists` / `init`。

### 3.2 四维度分类（每次请求先判定）
| 维度 | 取值 |
|------|------|
| `type` | project（项目） / program（项目群） |
| `methodology` | waterfall / agile / iteration / hybrid |
| `phase` | 启动 / 规划 / 执行 / 监控 / 收尾（项目群另有组合阶段） |
| `intent` | 规划 / 构建 / 汇报 / 分析 / 治理 |

### 3.3 三种执行模式
| 模式 | 何时用 | 做法 |
|------|--------|------|
| **direct** | 单产物 / 解释 / 微调 | 主控直接调脚本或模板完成 |
| **team** | 多独立产物（如启动需章程+WBS+风险+RACI） | 并行派出专职子 Agent，汇总后一致性校验 |
| **fork** | 需完整上下文接力（如"接着上次风险分析继续"） | 子 Agent 继承本会话全部上下文 |

---

## 4. 端到端工作流（按场景）

### 场景 A：敏捷项目启动（team 模式，组队并行）
**你说**："用敏捷（Scrum）帮我启动『支付重构』项目"

1. `init_project.py "支付重构" --type project --methodology agile --framework scrum`
2. 分类 → `{project, agile, 启动, 构建}` → 选 **team** 模式
3. 同一条消息并行派出三个子 Agent：
   - `planner-agent` → 渲染 `agile/product_backlog.md`
   - `risk-agent` → 渲染 `common/risk_register.md` + `common/raid_log.md`
   - `stakeholder-agent` → 渲染 `common/stakeholder_register.md` + `common/raci.md`
4. 主控汇总 → 跑 `consistency_check.py` → 通过 → `render_docx.py` 渲染
5. 交付：产物清单 + 关键指标卡

### 场景 B：瀑布项目规划
**你说**："按瀑布帮我规划『核心系统升级』，出 WBS、排期和阶段门"

1. `init_project.py "核心系统升级" --type project --methodology waterfall`
2. 路由到 `references/methodology-waterfall.md`
3. 渲染 `waterfall/wbs.md` → `waterfall/schedule_gantt.md` → `waterfall/stage_gate_review.md`
4. 用 `schedule_health.py` 校验关键路径与依赖
5. 更新 `project.yaml.artifacts`

### 场景 C：阶段评审 / 状态汇报
**你说**："生成本周状态报告，并算一下 EVM"

1. 准备 `metrics.yaml`（pv/ev/ac/bac）
2. `evm.py --data metrics.yaml` → 输出 CPI/SPI/EAC 与健康旗标
3. 渲染 `common/status_report.md`（填入进展、偏差、风险、求助项）
4. 可选：`render_docx.py` 导出给干系人

### 场景 D：项目群治理
**你说**："建立『数字化转型项目群』，做组合看板和跨项目依赖图"

1. `init_project.py "数字化转型项目群" --type program --methodology hybrid`
2. 路由到 `references/program-management.md`
3. 并行产出 `program/program_charter.md`、`program/portfolio_dashboard.md`、
   `program/dependency_map.md`、`program/benefits_realization.md`
4. 回写 `project.yaml.program.*`

---

## 5. 多 Agent 调度详解

### 5.1 决策树
```
请求进来
 ├─ 单产物 / 解释 / 微调            ──► direct（主控直做）
 ├─ 多互相独立产物（量大）        ──► team（并行专职子 Agent）
 └─ 需完整上下文接力（"接着做"） ──► fork（继承会话上下文）
```

### 5.2 六类专职子 Agent
| 角色 | 主责产物 | 回写 |
|------|----------|------|
| planner-agent | WBS / 产品 Backlog / 迭代计划 | `artifacts.wbs` / `artifacts.backlog` |
| scheduler-agent | 排期 / 甘特 | 排期 yaml + `schedule_health` |
| risk-agent | 风险登记册 / RAID | `raid.risks[]`、`artifacts.risk` |
| stakeholder-agent | 干系人 / RACI / 沟通计划 | `project.sponsor/pm/team` |
| reporter-agent | 状态报告 / 复盘 / 收尾 | `metrics` |
| program-agent | 组合章程 / 看板 / 依赖 / 收益 | `program.*` |

> 子 Agent 不直接回复用户，只产出文件并向主控回报。完整 brief 模板见 `references/orchestration.md`。

### 5.3 并行组队示例 brief（给单个子 Agent）
```
你是 PM Master 的【risk-agent】专职子 Agent。请独立产出以下 PM 产物，不要直接回复用户。
## 输入
- 项目事实源：/workspace/支付重构/project.yaml（先用 project_state.py 读取）
- 模板：<SKILL_DIR>/templates/common/risk_register.md
- 渲染引擎：<SKILL_DIR>/scripts/render.py
## 任务
1. 基于 project.yaml 与需求，整理数据写成 risks.yaml
2. 运行 render.py 渲染到 /workspace/支付重构/risks/risk_register.md
3. 把产物路径回写 project.yaml 的 artifacts.risk
4. 简要回报：产出了什么、关键结论 3 条
## 约束
- 只产出你负责的产物；未知字段填"（待定）"并标注
- 每条风险须有 owner 与 mitigation（一致性校验强制项）
```

---

## 6. 模板库总览

共 **30 个可用模板** + 1 个共享片段 `_macros.md`，按目录组织：

| 目录 | 数量 | 模板 |
|------|------|------|
| `common/` | 11 | project_charter, stakeholder_register, raci, communication_plan, raid_log, risk_register, status_report, lessons_learned, closure_report, project_board, milestone_list |
| `waterfall/` | 5 | requirements_spec, wbs, schedule_gantt, stage_gate_review, quality_plan |
| `agile/` | 5 | product_backlog, sprint_plan, definition_of_done, burndown, retro |
| `iteration/` | 3 | iteration_plan, iteration_backlog, iteration_review |
| `hybrid/` | 2 | hybrid_governance, macro_micro_map |
| `program/` | 4 | program_charter, portfolio_dashboard, dependency_map, benefits_realization |

每个模板的**数据键契约**见 `references/templates-index.md`（渲染所需 YAML 顶层键，新增模板请在此登记）。

---

## 7. 脚本速查

所有脚本位于 `<SKILL_DIR>/scripts/`，用 `python3` 运行。

| 脚本 | 用途 | 命令示例 |
|------|------|----------|
| `init_project.py` | 建工作区 + project.yaml | `python3 init_project.py "项目名" --type project --methodology agile --framework scrum` |
| `render.py` | 模板 + 数据 → Markdown | `python3 render.py --template T --data D.yaml --out O.md` |
| `render_docx.py` | Markdown → DOCX | `python3 render_docx.py O.md [--out O.docx]` |
| `evm.py` | 挣值分析 | `python3 evm.py --data metrics.yaml` |
| `schedule_health.py` | 关键路径 / 依赖 / 浮动 | `python3 schedule_health.py --data schedule.yaml [--start 2025-08-01]` |
| `consistency_check.py` | 交付前质量门 | `python3 consistency_check.py --project <项目>/project.yaml` |
| `project_state.py` | 单一事实源读写 | `python3 project_state.py get project.phase --file project.yaml` |

> 渲染引擎 `render.py` 支持的语法子集：`{{ project.name }}` 变量、`{{#each list}}…{{this.x}}…{{/each}}` 循环、
> `{{#if a == "b"}}…{{else}}…{{/if}}` 条件。不支持 Jinja 的 `{% %}`、过滤器、宏。

---

## 8. 双轨产出（Markdown → DOCX）

- **Markdown 是单一事实源**：所有模板渲染为 `.md`，便于版本管理、差异对比、二次处理。
- **DOCX 是正式交付件**：`render_docx.py` 优先用 `pandoc`；若环境无 pandoc，自动回退到 `python-docx`
  （支持标题、段落、有序/无序列表、表格、粗体）。已内置验证通过。

```bash
python3 <SKILL_DIR>/scripts/render_docx.py /workspace/支付重构/risks/risk_register.md
# 输出 /workspace/支付重构/risks/risk_register.docx
```

---

## 9. 指标口径

| 指标 | 公式 | 健康阈值 |
|------|------|----------|
| CPI 成本绩效 | EV/AC | <0.95 成本超支 |
| SPI 进度绩效 | EV/PV | <0.95 进度落后 |
| CV / SV | EV−AC / EV−PV | 负为超支/落后 |
| EAC / ETC | BAC/CPI / EAC−AC | — |
| VAC | BAC−EAC | 负为将超预算 |
| 速率 / 燃尽（敏捷） | 完成故事点 / 剩余工作量 | 趋势稳定为佳 |

完整定义与项目群/迭代指标见 `references/metrics.md`。

---

## 10. 扩展指南

本技能为**可扩展模板库**设计，新增能力无需改引擎或 SKILL.md：

1. **新增一个产物模板**：在对应目录（如 `agile/`）放 `my_template.md`，用 `render.py` 语法写占位符。
2. **登记数据键**：在 `references/templates-index.md` 加一行（模板文件 / 数据键 / 说明）。
3. **新增一个方法论**：建 `references/methodology-xxx.md` 说明阶段与仪式，建 `templates/xxx/` 放专属模板，在 SKILL.md 路由表与 templates-index 登记。
4. **新增分析脚本**：放 `scripts/`，在 SKILL.md「脚本速查」与对应 reference 引用即可。

---

## 11. 常见问题 FAQ

**Q1：为什么 `{{ sprint.num }}` 用了 `num` 而不是 `no`？**
PyYAML 遵循 YAML 1.1，会把键名 `no`/`yes`/`on`/`off` 强制转成布尔值，导致 `{{ sprint.no }}` 渲染为空。
技能统一用 `num`（如 `sprint.num` / `iteration.num`）规避，数据侧直接写数字即可。

**Q2：表格行之间为什么有时有空行？**
`render.py` 对循环体做了首尾换行归一，渲染产物行尾仅保留一个换行，Markdown 仍合法可用，不影响渲染与 DOCX 导出。

**Q3：依赖 `deps` 在甘特里显示成 `['t1','t2']` 这种格式？**
这是列表字面量直接输出。渲染引擎已对列表型变量做逗号拼接（`t1, t2`）。若需更精致格式，可在数据里预拼好字符串。

**Q4：没有 pandoc 能导出 Word 吗？**
能。`render_docx.py` 会自动回退到 `python-docx`（已验证）。

**Q5：一致性校验报"风险缺少 owner"怎么办？**
每条风险必须填 `owner` 与 `mitigation`；`project.sponsor` / `project.pm` 也必须明确，否则质量门不通过。未知时填"（待定）"并标注，交付前补全。

---

## 12. 完整示例：从 0 启动一个敏捷项目

```bash
SKILL_DIR=/root/.codebuddy/skills/pm-master

# ① 脚手架
python3 $SKILL_DIR/scripts/init_project.py "支付重构" --type project --methodology agile --framework scrum

# ② 准备数据（risks.yaml 节选）
cat > /tmp/risks.yaml <<'YAML'
project: { name: 支付重构, pm: 张三, sponsor: 李四 }
risks:
  - { id: R1, description: 第三方接口不稳, category: 技术, likelihood: 中, impact: 高,
      score: 12, owner: 王五, mitigation: 熔断+重试+压测, status: 监控中 }
YAML

# ③ 渲染产物
python3 $SKILL_DIR/scripts/render.py \
  --template $SKILL_DIR/templates/common/risk_register.md \
  --data /tmp/risks.yaml --out /workspace/支付重构/risks/risk_register.md

# ④ 导出 Word
python3 $SKILL_DIR/scripts/render_docx.py /workspace/支付重构/risks/risk_register.md

# ⑤ 质量门
python3 $SKILL_DIR/scripts/consistency_check.py --project /workspace/支付重构/project.yaml
```

> 自然语言方式等价："用敏捷帮我启动支付重构项目，识别主要风险并出一份风险登记册和 Word 版。"
> 在真实会话中，主控会自动完成 ①~⑤ 并视情况组队并行产出其余产物。

---

## 13. 提示词示例库

直接用自然语言即可触发，以下供参考：

- "用**瀑布**帮我规划『核心系统升级』，出 **WBS、排期和阶段门评审**。"
- "用**敏捷 Scrum** 启动『支付重构』，建 **产品 Backlog 和风险登记册**。"
- "按 **2 周迭代** 管理『数据平台』，生成**迭代计划和燃尽图**。"
- "『自动驾驶项目群』用 **hybrid**，硬件走瀑布、软件走敏捷，出**治理地图**。"
- "建立『数字化转型项目群』，做**组合看板、跨项目依赖图和收益实现计划**。"
- "算一下这个项目的 **EVM**，看 CPI/SPI 是否健康。"
- "检查排期，**找关键路径和缺失依赖**。"
- "基于我们刚定的范围，**接着**把 WBS 拆到三级**（fork 接力）**。"
- "把这些产物**导出成 Word** 发给干系人。"

---

_本文档由 PM Master 技能配套提供。技能路径：`<skills>/pm-master/`，入口 `SKILL.md`。_
