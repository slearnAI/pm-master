# 项目群（Program）管理

## 是什么
项目群 = 为达成共同战略收益而**集中管理**的一组相互关联的项目/组件。与"项目组合(Portfolio)"
（按优先级投资）不同，项目群强调**依赖协同与收益实现**。

> 触发：用户说"项目群/组合/多个关联项目一起管/跨部门大计划" → `init_project.py ... --type program`。

## 治理模型
- **治理委员会**：sponsor + 各组件 PM + PMO，定期组合评审。
- **三层视角**：战略收益层（program_charter / benefits_realization）→ 协同层（dependency_map / portfolio_dashboard）→ 组件层（各项目自管）。
- **决策**：新增/终止组件、资源再分配、跨组件依赖仲裁。

## 核心工件（项目群专属模板）
- `templates/program/program_charter.md`：组合愿景、目标、范围、治理、收益目标
- `templates/program/portfolio_dashboard.md`：各组件健康度红黄绿汇总看板
- `templates/program/dependency_map.md`：跨组件依赖与阻塞
- `templates/program/benefits_realization.md`：收益登记、衡量口径、实现跟踪

## 与单项目的区别（主控要记住）
| 维度 | 项目 | 项目群 |
|------|------|--------|
| 目标 | 交付具体成果 | 实现战略收益 |
| 管理重心 | 范围/进度/成本 | 依赖/协同/收益 |
| 产物重点 | 章程/WBS/排期/风险 | 组合章程/看板/依赖图/收益 |
| 风险 | 项目级 | 跨组件依赖阻塞、收益落空 |

## 关键指标
- 组件健康度汇总（CPI/SPI 红黄绿）
- 依赖阻塞数
- 收益实现率（已核实 / 计划）

## WBS 两层颗粒度约定（Two-Tier WBS）

> 触发：用户要求"项目群层级 WBS 只到各 SOW 里程碑级，最细叶子包在组件层级"。

- **项目群（program）WBS** = SOW 汇总包（id 无 `.` 或 `summary: true`）
  **+ 每个 SOW / P0 的「阶段(phase) 里程碑汇总包」**（`milestone: true`, `tier: program`）。
  **不展开叶子工作包**——项目群报告只看里程碑级颗粒度。
- **组件（project）WBS** = 最细颗粒度的**叶子工作包**（`tier: component`, `component: <slug>`），
  含领域专家拆解包。

单一事实源实现（`project.yaml`）：
- `scripts/rollup_program_wbs.py` 把叶子按阶段聚合为里程碑汇总包并打 `tier` 标签；
  加 `--derive-actuals` 可把叶子实际% 按 `estimate` 加权汇总为里程碑实际%，写入 `actuals.wbs_progress`。
- `build_wbs.py --view program|component` 据此过滤：program 视图只渲染 `tier != component`，
  component 视图只渲染 `tier == component`（可 `--component <slug>` 进一步过滤）。
- 模板 `templates/waterfall/wbs.md` 单输出同时支持两种视图（表格 + mermaid 甘特）。

聚合规则（里程碑汇总包）：`estimate` = 叶子之和；`start/end` = 叶子极值；`dependsOn` = 上一阶段里程碑；
`owner` 继承 SOW 汇总；领域专家拆解产出叶子包、归属对应组件。

## 控制报告 · 进度明细列化

`control_engine.py` 的进度控制**不再**把"计划/实际/偏差/逾期"挤进同一长串，
而是输出结构化 `schedule_table`：每个工作包 / 里程碑单列一行，分列 **计划% | 实际% | 偏差% | 状态**。
项目群层级因 baseline.wbs 仅含里程碑汇总包，自然聚合为里程碑级明细；组件层级明细到叶子。
偏差落后超阈值（`control.thresholds.schedule_slip_pct`，默认 15%）标黄/红，一眼定位滞后项。

## 主控调度提示
- 项目群启动用 **team** 模式派 `program-agent`（组合章程+看板）、`risk-agent`（组合风险）、
  `dependency-agent`（依赖图）并行。
- 组件层可各自用本技能独立管理，`program.projects[]` 记录组件清单与各自 methodology。
- 详见 `references/agents.md` 与 `references/metrics.md`。
