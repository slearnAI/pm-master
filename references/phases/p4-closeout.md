# 阶段模块 · P4 收尾（Closeout）

> 收尾阶段做验收、复盘、移交与收益核实，标志项目正式关闭。
> 状态机落位：经 **G3→4 收尾门** 从 `operational` 翻 `closed`（见 `references/lifecycle.md §5.3` 的 5 条出口条件）。
> 入口硬门即 G3→4（见 `p3-monitoring.md §5/§6` 与 `scripts/gate_engine.py`）。

## 1. 目标

确认交付物被验收、 knowledge 沉淀、资产移交、收益核实（项目群），干净关闭项目。

## 2. 关键活动（方法论适配）

| 方法论 | 收尾活动 |
|------|----------|
| 通用 | 验收签字、移交清单、经验教训、归档 |
| waterfall | 阶段门终验（Gate4 验收）、正式移交、资产归档 |
| agile/iteration | 最终增量验收、发布说明、回顾终章、Backlog 残余处置 |
| hybrid | 宏层终验 + 微层收口；跨层依赖关闭 |
| 项目群 | 各组件 closure_report + 组合收尾；收益核实报告；组合复盘 |

## 3. 必产出交付物（模板）

- `common/closure_report`：范围完成情况、验收结论、移交清单、指标、经验引用。
- `common/lessons_learned`：做得好/待改进/行动项（行动项进 RAID 的 issues 跟踪）。
- 项目群额外：`program/benefits_realization` 的**收益核实**（realized/实现日/status 闭环）。
- 移交物：按 `closure_report.handover[]` 列出的资产/文档清单。

## 4. 入口准则（Entry · G3→4 收尾门）

- `lifecycle_state == operational`（须先经 G1→2 进入执行/监控）。
- 硬门（自动化校验，缺一不可）：
  - `control_engine.py --project` **exit 0**（无 RED 升级）。
  - `artifacts.closure_report` 已产出/登记（验收交付物）。
  - `artifacts.lessons_learned` 已产出/登记（经验沉淀）。
  - 项目群：全部收益已实现/闭环。

## 5. 出口准则（Exit · 正式关闭）

满足 `references/lifecycle.md §5.3` 的 5 条出口条件后即视为关闭：

1. 全部交付物已验收签字（项目：`closure_report`；项目群：各组件 `closure_report` + 组合收尾）。
2. `lessons_learned` 已沉淀。
3. 项目群：收益已核实/实现（`program.benefits[].realized` 与 `status` 闭环）。
4. 无未决 RED 升级（`control_engine.py` exit 0）且无 open 变更请求（`change_log` 全关闭）。
5. 由主控将 `lifecycle_state` 置 `closed`（经 `gate_engine.py --to 收尾 --approve`）。

> 仍未基线化（缺 `baseline`）的 waterfall/hybrid 不得进入 operational；已 operational 但未满足
> 上述出口条件**不得**置 closed——状态机不可跳步。

## 6. 阶段门审批（Gate · G3→4）

- **门**：G3→4 监控→收尾（收尾门，强制串行）。
- **审批人**：sponsor（必要时 + PM）。
- **命令**：

```bash
SKILL_DIR=<本技能目录>
# 评估能否收尾（列出缺口）
python3 $SKILL_DIR/scripts/gate_engine.py --project /workspace/<slug>/project.yaml --to 收尾
# 审批通过：lifecycle_state → closed，phase → 收尾，记录阶段门，产出评审报告
python3 $SKILL_DIR/scripts/gate_engine.py --project /workspace/<slug>/project.yaml --to 收尾 --approve "张三(sponsor)"
```

## 7. 推荐脚本

- `gate_engine.py --to 收尾`：收尾门评估/审批（翻 `closed`）。
- `consistency_check.py`：收尾前最终一致性核验（exit 1 = 阻断）。
- `control_engine.py`：收尾前最终巡检（exit 0 = 无 RED）。
- `render_docx.py`：closure_report / lessons_learned 正式文档。

## 8. 衔接

- 进入本阶段即代表运营期结束；翻 `closed` 后项目只读归档。
- 若收尾评估不通过（仍有 RED/未决变更/缺验收），退回 `operational` 补齐后再走 G3→4。
