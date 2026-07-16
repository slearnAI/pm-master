# 项目 / 项目群生命周期与阶段-交付物矩阵

## 1. 项目生命周期（通用五阶段，方法论决定节奏）

| 阶段 | 目标 | 关键交付物（模板） | 出口准则 |
|------|------|--------------------|----------|
| **启动** | 立项、定目标与边界 | project_charter, stakeholder_register, raci | 章程获批、sponsor/pm 到位 |
| **规划** | 拆范围、排期、识风险 | wbs / product_backlog / iteration_plan, schedule_gantt, risk_register, raid_log, communication_plan | 计划基线确立 |
| **执行** | 交付增量/成果 | 迭代/冲刺产出、变更记录 | 按计划推进 |
| **监控** | 跟踪偏差、控风险 | status_report, burndown, 更新 risk/raid | 偏差可控、风险受管 |
| **收尾** | 验收、复盘、移交 | closure_report, lessons_learned | 验收签字、经验沉淀 |

> 各方法论对"阶段"的切分不同：waterfall 是串行阶段门；agile 是持续增量 + Sprint 循环；
> iteration 是时间盒迭代循环；hybrid 是宏阶段（门）+ 微迭代。详见对应 methodology 文件。

## 2. 项目群（Program）生命周期

| 阶段 | 目标 | 关键交付物（模板） |
|------|------|--------------------|
| **组合定义** | 定义愿景、收益、组件边界 | program_charter, benefits_realization |
| **组合交付** | 治理组件、管依赖、促协同 | portfolio_dashboard, dependency_map, 组合 risk/raid |
| **组合收尾** | 收益核实、组合复盘 | benefits 核实报告, 组合 lessons_learned |

## 3. 阶段-交付物速查（按 intent）

| intent | 必产出 | 推荐脚本 |
|--------|--------|----------|
| 规划/启动 | charter + stakeholder + raci + (wbs/backlog) | init_project, render |
| 构建计划 | wbs/backlog + schedule + risk + raid | render, schedule_health |
| 风险 | risk_register + raid_log | render, consistency_check |
| 汇报 | status_report (+ burndown) | render, evm |
| 分析 | —— | evm, schedule_health, consistency_check |
| 治理(群) | program_charter + portfolio_dashboard + dependency_map + benefits_realization | render |

## 4. 单一事实源联动

所有阶段产物最终都回写 `project.yaml`：
- `project.*`：元数据、阶段、范围
- `artifacts.*`：各产物文件路径索引
- `raid.*`：风险/假设/问题/依赖（持续更新）
- `metrics.*`：EVM、燃尽数据
- `program.*`：仅项目群，含组件/依赖/收益

## 5. 项目状态机：规划 → 基线 → 运营控制（核心纪律）

**规划（Planning）与运营化（Operationalization）不是二选一，而是强制串行的两个阶段，二者必须同时存在：**
先完成规划，经评审批准成为**已基线化的项目计划**，再通过**控制门**把项目推进到**运营/控制阶段**，
之后由 **PM 控制引擎**周期性运行既定检查，确保项目按基线预期运行。

| 状态 (project.lifecycle_state) | 含义 | 入口条件 | 关键动作 / 产物 | 出口 |
|------|------|----------|----------------|------|
| `planning` | 规划中（默认） | 项目立项 | 产出 draft 计划：charter / WBS / 排期 / 风险 / 估算 / RAID | 计划完成、评审通过 |
| `review` | 评审/批准中 | 计划就绪 | 阶段门评审（stage_gate_review）：范围/估算/风险/治理逐条核对 | 批准（或退回 planning） |
| `baselined` | 已基线化 | 评审批准且一致性门禁 exit 0 | `baseline.py --freeze`：冻结 wbs/风险/里程碑/metrics 为基线快照 → `baselines/<date>.yaml`；产出 `baseline_record` + `control_register` | 控制门放行 |
| `operational` | 运营/控制中 | 控制门通过（进入 执行/监控 阶段） | **PM 控制引擎**周期性运行（见下）；持续更新 `actuals` + `raid` + `change_log` | 阶段收尾 |
| `closed` | 已收尾 | 验收签字、收益核实 | closure_report / lessons_learned | —— |

> **纪律（不可跳过）**：未基线化（无 `baseline` 指针）的 waterfall / hybrid 项目**不得**进入 执行/监控 阶段；
> 一致性门禁会在 `phase ∈ {执行, 监控, 收尾}` 且 `methodology ∈ {waterfall, hybrid}` 且无 `baseline` 时**直接阻断**。

### 5.1 运营控制循环（PM 控制引擎做什么）

进入 `operational` 后，`control_engine.py` 按 `control.cadence` 周期性对照**基线**运行以下**常规控制项**
（即"确保项目按预期运行的必要定期任务与检查"），任一项突破阈值即升级告警：

| 控制项 | 对照基线计算 | 默认升级阈值 |
|--------|--------------|--------------|
| 进度控制 (Schedule) | 各 WBS 包"按计划% vs 实际%"偏差；逾期天数 | 实际落后计划 ≥ `schedule_slip_pct`(默认15%) 或已逾期未完成 |
| 成本/挣值 (EVM) | SPI = EV/PV、CPI = EV/AC、EAC/ETC/VAC | SPI<`spi_warn`(0.95) 或 CPI<`cpi_warn`(0.95) |
| 风险漂移 (Risk Drift) | 当前风险评分 vs 基线评分；新增红/严重风险 | 任一风险评分升级 或 出现新增红/严重风险 |
| 里程碑 (Milestone) | 里程碑日期已过且未完成 | 逾期未完成 |
| 问题 (RAID Issues) | 问题 due 已过且未关闭 | 逾期未关闭 |
| 变更 (Change) | 未决变更请求数量 | 未决数 ≥ `open_change_high`(默认2) |
| 数据完整性 (Integrity) | 重跑 consistency_check | 门禁失败 |

引擎输出 `control_report.md` + 结构化 JSON，并带**退出码**（任一 RED 升级 → exit 1），
可直接挂到定时任务 / 自动化（automation）做周期性巡检与告警。

### 5.2 控制登记册（Control Register）

`control_register.md` 是运营期开局必须产出的"常规控制清单"：定义**检查什么、频次、责任人、触发条件、上一次结果**。
它把 5.1 的七项控制固化为可审计的运营纪律，缺项时一致性门禁会告警。

### 5.3 项目群阶段 ↔ 状态机映射，与退出 operational

**方法论阶段 ≠ 生命周期状态机，二者是正交的两层。** 状态机（`lifecycle_state`：planning→review→baselined→operational→closed）是**方法论无关**的强制纪律，覆盖所有类型与所有方法论；方法论阶段（五阶段 / 迭代循环 / Sprint 循环 / 宏微双层）是**节奏层**，落在状态机之内。

| 类型 | 方法论阶段（节奏层） | 在状态机中的落位 |
|------|----------------------|------------------|
| 项目 | 启动 → 规划 → 执行 → 监控 → 收尾 | 启动/规划 ⊆ planning；评审 ⊆ review；**执行+监控 ⊆ operational**（须先 baselined 过控制门）；收尾 ⊆ closed |
| 项目群 | 组合定义 → 组合交付 → 组合收尾 | 组合定义 ⊆ planning；**组合交付 ⊆ baselined→operational**（组件各自仍走自身状态机，组合层只治理依赖/协同/收益）；组合收尾 ⊆ closed |

> **operational 与"监控"阶段的关系**：`operational` 是**受控执行的机制状态**（已冻结基线、`control_engine.py` 周期巡检）；"监控"是 operational 期间持续进行的**活动**。即：进入执行/监控阶段 ⟺ `lifecycle_state=operational`，二者同时发生，并非先 operational 后 monitor。

**退出 operational（→ closed）的出口条件**（任一类型都满足后方可关闭）：

1. 全部交付物已验收签字（项目：`closure_report`；项目群：各组件 `closure_report` + 组合收尾）；
2. `lessons_learned` 已沉淀；
3. 项目群：收益已核实/实现（`program.benefits[].realized` 与 `status` 闭环）；
4. 无未决 RED 升级（`control_engine.py` 退出码 0）且无 open 变更请求（`change_log` 全关闭）；
5. 由主控将 `project.lifecycle_state` 置为 `closed`（可经 `project_state.py set`）。

> 仍未基线化（缺 `baseline` 指针）的 waterfall / hybrid 项目**不得**进入 operational；已 operational 但未满足上述出口条件**不得**置 closed——状态机不可跳步。

---

## 6. 阶段模块与阶段门（Phase Modules & Gates）

方法论阶段（P0–P4）与状态机（`lifecycle_state`）是正交两层：阶段模块定义"该阶段做什么/交什么/怎么进门"，
状态机是"强制串行的纪律"。二者通过**阶段门（Gate）**衔接——每个硬门在 `gate_engine.py` 中复用既有引擎做自动化校验。

### 6.1 阶段模块 ↔ 门 ↔ 状态机 映射

| 阶段模块 | 覆盖 phase | 阶段门 | 门类型 | 前置状态 | 审批后翻转 | 审批人 | 模块文档 |
|----------|-----------|--------|--------|----------|------------|--------|----------|
| **P0+P1** 启动与规划 | 启动/规划（组合定义） | G0→1 | 软门 | planning | planning（仅置 phase） | PM | `references/phases/p0-p1-initiation-planning.md` |
| **P2** 执行 | 执行（组合交付） | **G1→2** | **硬门** | planning/review/baselined | → `operational` | sponsor | `references/phases/p2-execution.md` |
| **P3** 监控 | 监控（组合交付内并发） | G2→3 | 软门 | operational | operational（置 phase=监控） | PM | `references/phases/p3-monitoring.md` |
| **P4** 收尾 | 收尾（组合收尾） | **G3→4** | **硬门** | operational | → `closed` | sponsor | `references/phases/p4-closeout.md` |

> **执行与监控并发（operational 双轨）**：P2 与 P3 同处 `operational`，并非先执行后监控；G1→2 进入 operational 即同时启动执行与监控，
> G2→3 只是 PM 标记监控节奏（软门，不改状态机）。两轨以**多 Agent 并行**落地——执行轨（领域专家 Agent）持续交付，监控轨（`monitoring-agent`）
> 周期跑 `control_engine.py` 并回流升级项，共享 `project.yaml`+`baselines/` 且字段零冲突。详见 `p2-execution.md` / `p3-monitoring.md` 与
> `references/orchestration.md §3.4`。

### 6.2 硬门的自动化准则（gate_engine.py 强制）

- **G1→2（进执行）**：`consistency_check.py` **exit 0**；waterfall/hybrid 另须已 `baseline.py --freeze`（`baseline.file` 存在）。
- **G3→4（进收尾）**：`control_engine.py` **exit 0**（无 RED 升级）；`closure_report` 与 `lessons_learned` 已登记；项目群须全部收益已实现/闭环。

### 6.3 阶段门引擎用法

```bash
SKILL_DIR=<本技能目录>
python3 $SKILL_DIR/scripts/gate_engine.py --project /workspace/<slug>/project.yaml --status            # 当前状态 + 可走的门
python3 $SKILL_DIR/scripts/gate_engine.py --project /workspace/<slug>/project.yaml --to 执行            # 评估（dry-run，不改动）
python3 $SKILL_DIR/scripts/gate_engine.py --project /workspace/<slug>/project.yaml --to 执行 --approve "张三(sponsor)"  # 审批翻转
```

审批通过后会：① 翻转 `project.phase` 与 `lifecycle_state`；② 向 `governance.stage_gates` 追加一条门记录
（门名/前后 phase/前后状态/审批人/日期/准则快照）；③ 在 `docs/gate_reports/` 产出阶段门评审报告并登记到 `artifacts`。
硬门未通过则 **exit 1 拒绝推进**，不可跳过。
