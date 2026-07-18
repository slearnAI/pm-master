# 阶段模块 · P0+P1 启动与规划（Initiation & Planning）

> 本模块覆盖生命周期最前端两个阶段的**活动、交付物、入口/出口准则与阶段门**。
> 启动与规划耦合紧密（立项即定边界，规划即拆范围），合并为一个子模块；对应的硬门是
> **G1→2 规划→执行控制门**（见 `references/lifecycle.md §5/§6` 与 `scripts/gate_engine.py`）。
> 状态机落位：`启动`/`规划` ⊆ `planning`（经 `review` 评审后 `baseline.py --freeze` 进入 `baselined`）。

## 1. 目标

- **启动**：明确业务必要性、目标与边界，落实 sponsor 与 PM，获得立项。
- **规划**：把目标拆成可交付的范围、排期、估算、风险与治理基线，形成可基线化的计划。

## 2. 关键活动（方法论适配）

| 方法论 | 启动活动 | 规划活动 |
|------|----------|----------|
| 通用 | 立项、干系人识别、RACI、沟通计划、范围/目标 | WBS/Backlog 拆解、排期、风险/RAID、里程碑 |
| waterfall | 业务必要性 + 预算 + sponsor 确认 | 需求规格、WBS（依赖网络+DoD）、甘特、质量计划、阶段门清单 |
| agile | 章程（轻量）、产品愿景 | 产品 Backlog、Sprint 计划框架、DoD、燃尽基线 |
| iteration | 章程、迭代节奏约定 | 迭代计划、迭代 Backlog、评审/复盘节奏 |
| hybrid | 治理地图（宏/微边界 + 门 + 决策人） | 宏层路线图 + 每宏波次≥1 个微层计划（sprint/backlog/iteration） |
| 项目群 | 组合章程、收益蓝图、组件边界 | 组合路线图、组件依赖图、收益实现计划、变更控制 CCB |

> 领域活动（技术领域工作包）必须由对应**领域专家**拆解到叶子包（≤ `control.granularity_threshold` 人天），
> 经 `scripts/dispatch.py` 调度；粗粒度 SOW 级 WBS 不得作为交付。详见 `references/expert-roles.md`。

## 3. 必产出交付物（模板）

- **标准启动套件（任何项目）**：`common/project_charter` + `common/stakeholder_register` + `common/raci` + `common/communication_plan`
- **范围/计划**：`common/wbs`（或 agile `product_backlog` / iteration `iteration_plan`）+ `common/risk_register` + `common/raid_log`
- **waterfall/hybrid 专属**：`waterfall/requirements_spec` + `waterfall/wbs`（由 `build_wbs.py` 渲染） + `waterfall/schedule_gantt`（由 `build_schedule.py` 从 WBS 正向排程生成，**P0/P1 主要排期交付物**） + `waterfall/quality_plan` + `waterfall/stage_gate_review`（计划基线门清单）
- **每 SOW 级包**：`common/sow_kickoff`（由 `build_sow_kickoff.py` 为**每个 SOW 级 summary 包**生成 per-SOW 启动会工件，对齐范围/交付物/责任人/首批行动，规划期必跑）
- **项目群专属**：`program/program_charter` + `program/portfolio_dashboard` + `program/dependency_map` + `program/benefits_realization` + `common/change_log`

## 4. 入口准则（Entry）

- `project.yaml` 已存在（`init_project.py` 初始化）；或本模块即触发初始化。
- 明确 `project.type` / `methodology` / `framework`（决定后续模板与节奏）。

## 5. 出口准则（Exit · 可进入执行）

- 计划完整、估算齐全（`wbs[].estimate > 0`、agile/iteration backlog 有估算）。
- 风险已按 5×5 校准（likelihood/impact/score/severity 一致）。
- **一致性门禁 `consistency_check.py --project` exit 0**（无致命问题）。
- waterfall/hybrid：**已 `baseline.py --freeze`** 冻结计划为基线（`baseline.file` 存在）。
- 阶段门评审 `stage_gate_review`（Gate2 计划基线）给出"通过/有条件通过"结论。

## 6. 阶段门审批（Gate · G1→2）

- **门**：G1→2 规划→执行（控制门，强制串行，不可跳过）。
- **审批人**：sponsor（必要时 + PM）。
- **检查清单**：范围/估算/风险/依赖/质量基线逐项核验；计划基线完整性；一致性门禁结论。
- **命令**（dry-run 先评估，再审批）：

```bash
SKILL_DIR=<本技能目录>
# 评估能否进入执行（不改动状态）
python3 $SKILL_DIR/scripts/gate_engine.py --project /workspace/<slug>/project.yaml --to 执行
# 审批通过：翻转 lifecycle_state → operational，phase → 执行，记录阶段门，产出评审报告
python3 $SKILL_DIR/scripts/gate_engine.py --project /workspace/<slug>/project.yaml --to 执行 --approve "张三(sponsor)"
```

## 7. 推荐脚本

- `init_project.py`：初始化 `project.yaml` 骨架。
- `dispatch.py`：审计 WBS、特化推荐领域专家（多 Agent 第二层）。
- `render.py`：渲染上述模板为 Markdown 交付物。
- `build_wbs.py`：渲染 `plans/wbs.md`（两层颗粒度 WBS 视图，修掉 `wbs.md` 对 `build_wbs.py` 的悬空依赖）。
- `build_schedule.py`：waterfall/hybrid 把 WBS 正向排程为 `plans/schedule_gantt.md` 排期计划（**P0/P1 主要交付物**，规划期必跑）。
- `build_sow_kickoff.py`：为每个 SOW 级包产出 `plans/kickoff/<sow>_kickoff.md` 启动会工件（规划期必跑）。
- `schedule_health.py`：waterfall/hybrid 算关键路径/浮动（规划期必跑）。
- `consistency_check.py`：交付前质量门（exit 1 = 阻断）。
- `baseline.py --freeze`：冻结计划为基线（waterfall/hybrid 进执行前必跑）。
- `gate_engine.py --to 执行`：控制门评估/审批。

## 8. 衔接

- 出口经 G1→2 进入 **P2 执行**（operational）；P3 监控在 operational 内并发启动。
- 若评审不通过，退回 `planning` 修订后重评（状态机 `review → planning` 允许回退）。
