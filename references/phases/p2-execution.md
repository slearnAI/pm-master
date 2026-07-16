# 阶段模块 · P2 执行（Execution）

> 执行阶段按**已基线化的计划**交付增量/成果。它与 **P3 监控**在 `operational` 状态内**并发**进行
> （执行是"做"，监控是"盯"），并非先执行后监控的串行。
> 状态机落位：`执行` ⊆ `operational`（须先经 G1→2 控制门，且 waterfall/hybrid 已 `baseline.py --freeze`）。
> 进入本阶段的硬门：G1→2（见 `p0-p1-initiation-planning.md §6` 与 `scripts/gate_engine.py`）。

## 1. 目标

按计划/承诺交付可验收的增量或成果；保持基线对照，控制范围/进度/成本偏差。

## 2. 关键活动（方法论适配）

| 方法论 | 执行活动 | 节奏 |
|------|----------|------|
| waterfall | 按 WBS 包推进；质量计划检查点准入/准出；变更走 CCB | 阶段内按依赖推进；周/双周状态 |
| agile (Scrum) | Sprint 计划→每日站会→Sprint 评审（可演示增量）→回顾；严守 DoD | 固定 Sprint（1–4 周） |
| agile (Kanban) | 看板流动；限制 WIP；度量 Lead Time / 流动效率 | 连续流动 |
| iteration | 迭代计划→迭代执行（时间盒）→迭代评审→迭代复盘；迭代内范围锁定 | 固定迭代（如 2 周） |
| hybrid | 微层按所落方法论执行；宏层在对齐评审点核对微层增量是否满足门准入 | 宏低频/微高频 + 对齐评审 |
| 项目群 | 各组件各自执行；组合层持续更新依赖图/组合看板，促协同 | 组合节奏 |

## 3. 必产出交付物（模板）

- **增量/成果**：迭代/冲刺产出、`agile/sprint_plan`、`iteration/iteration_plan`、`agile/retro`、`agile/burndown`、`iteration/iteration_review`
- **变更控制**：`common/change_request` + `common/change_log`（任何范围/排期/资源变更必走正式通道，回写 `project.yaml`）
- **运营开局**：`common/control_register`（baseline.py 生成，定义常规控制清单/频次/责任人）
- **演示/验收物**：按方法论产出可演示增量（评审/演示结论）

## 4. 入口准则（Entry · G1→2 控制门）

- `lifecycle_state` ∈ {planning, review, baselined} 且经审批进入。
- 硬门（自动化校验，缺一不可）：
  - `consistency_check.py --project` **exit 0**（计划基线无致命问题）。
  - waterfall/hybrid：**已 `baseline.py --freeze`**（`baseline.file` 存在）。
- 审批人：sponsor（见 `p0-p1-initiation-planning.md §6` 的 `gate_engine.py --to 执行 --approve`）。

## 5. 出口准则（Exit · 可进入监控/收尾）

- 按基线/承诺推进，偏差在阈值内（进度落后 < `schedule_slip_pct`、SPI/CPI ≥ 0.95）。
- `control_register` 已建立，运营控制循环已启动（`control_engine.py` 按 `control.cadence` 周期跑）。
- 重大偏差/变更已走 CCB 并回写。
- 注：监控与执行并发，无需"完成执行"才进监控；二者同处 `operational`。

## 6. 阶段门审批（Gate · G2→3 软门）

- **门**：G2→3 执行→监控（软门，operational 内标记监控节奏，不改状态机）。
- **审批人**：PM。
- **命令**：

```bash
SKILL_DIR=<本技能目录>
python3 $SKILL_DIR/scripts/gate_engine.py --project /workspace/<slug>/project.yaml --to 监控 --approve "李四(PM)"
```

## 7. 推荐脚本

- `control_engine.py`：运营期按 `control.cadence` 周期巡检（对照基线），RED 升级 exit 1。
- `evm.py`：执行期建立并滚动 EVM 基线（pv/ev/ac），算 CPI/SPI。
- `schedule_health.py`：waterfall/hybrid 跟踪关键路径/浮动。
- `render.py` / `render_docx.py`：产出增量、演示物、正式文档。
- `gate_engine.py --to 监控`：软门标记监控节奏。

## 8. 衔接

- 本阶段是 **operational 双轨**的「执行轨」：与 **P3 监控轨**（`monitoring-agent` 周期跑 `control_engine.py`）并发于 `operational`，
  二者共享 `project.yaml`+`baselines/`、字段零冲突（执行轨写 `actuals`/`wbs_progress`/交付物，监控轨写控制/状态报告）。
  偏差/风险由监控轨持续拉回基线，纠偏动作回流本轨。双轨编排见 `references/orchestration.md §3.4`。
- 满足收尾出口（见 `p4-closeout.md §5`）后，经 **G3→4 收尾门** 翻 `closed`。
