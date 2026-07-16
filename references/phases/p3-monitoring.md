# 阶段模块 · P3 监控（Monitoring & Control）

> 监控阶段在执行推进的同时**持续进行**：跟踪偏差、控风险、保基线，确保项目按基线预期运行。
> 它与 **P2 执行**同在 `operational` 状态内并发（进入执行 ⟺ `lifecycle_state=operational`，监控是期间持续活动）。
> 状态机落位：`监控` ⊆ `operational`。离开本阶段经 **G3→4 收尾门** 翻 `closed`。

## 1. 目标

持续对照基线衡量进度/成本/风险偏差；在偏差越界前预警与纠偏；维护变更控制纪律。

## 2. 关键活动（方法论适配）

| 方法论 | 监控活动 | 频率 |
|------|----------|------|
| 通用 | 周期状态报告、风险/问题滚动更新、里程碑跟踪、变更控制 | 按 `control.cadence` |
| waterfall | EVM 跟踪、关键路径偏差、阶段门中期评审（Gate3） | 周/双周 + 阶段门 |
| agile | 燃尽/速率跟踪、Sprint 评审反馈、回顾行动闭环 | 每 Sprint |
| iteration | 迭代燃尽、迭代完成率、迭代评审偏差 | 每迭代 |
| hybrid | 宏层 EVM + 微层速率/燃尽合并看板；跨层依赖阻塞跟踪 | 宏低频/微高频 |
| 项目群 | 组合健康度看板、组件 CPI/SPI、依赖阻塞、收益进度 | 组合节奏 |

## 3. 必产出交付物（模板）

- `common/status_report`（执行/监控期必出，含 CPI/SPI/PV/EV/AC）
- `agile/burndown` / `iteration/iteration_review`（增量与偏差）
- `common/control_report`（`control_engine.py` 输出：控制项状态 + 升级项）
- 滚动更新：`common/risk_register`、`common/raid_log`、`common/milestone_list`、`common/change_log`

## 4. 入口准则（Entry · G2→3 软门）

- `lifecycle_state == operational`（即已通过 G1→2 控制门进入执行）。
- `control_register` 已建立、`control.cadence` 已配置（运营控制循环可启动）。
- 软门（PM 审批即可，见 `p2-execution.md §6`），不改状态机。

## 5. 出口准则（Exit · 可进入收尾）

硬门（G3→4，自动化校验，缺一不可）：

- **运营控制无 RED**：`control_engine.py --project` **exit 0**（无升级项）。
- **无未决变更**：变更请求均已关闭（控制引擎的"变更"控制项未超 `open_change_high`）。
- **验收交付物**：`artifacts.closure_report` 已产出/登记（交付物验收签字）。
- **经验教训沉淀**：`artifacts.lessons_learned` 已产出/登记。
- 项目群额外：全部收益已实现/闭环（`program.benefits[].status` ∈ realized/实现/closed）。

## 6. 阶段门审批（Gate · G3→4 收尾门）

- **门**：G3→4 监控→收尾（收尾门，强制串行，不可跳过）。
- **审批人**：sponsor（必要时 + PM）。
- **检查清单**：上述出口准则逐项核验；验收结论；收益核实（项目群）。
- **命令**（先评估缺口，再审批）：

```bash
SKILL_DIR=<本技能目录>
# 评估能否收尾（列出未满足项，不改动状态）
python3 $SKILL_DIR/scripts/gate_engine.py --project /workspace/<slug>/project.yaml --to 收尾
# 审批通过：翻转 lifecycle_state → closed，phase → 收尾，记录阶段门，产出评审报告
python3 $SKILL_DIR/scripts/gate_engine.py --project /workspace/<slug>/project.yaml --to 收尾 --approve "张三(sponsor)"
```

## 7. 推荐脚本

- `control_engine.py`：**核心**。运营期周期巡检，RED 升级 exit 1，可挂定时任务/自动化。
- `evm.py`：滚动 EVM（actuals 填报 ev/ac）。
- `schedule_health.py`：waterfall/hybrid 进度偏差。
- `consistency_check.py`：收尾前最终一致性核验。
- `gate_engine.py --to 收尾`：收尾门评估/审批。

## 8. 衔接

- 与 P2 执行并发于 `operational`；纠偏动作回流到执行。
- 满足出口准则后翻 `closed` 进入 **P4 收尾**；状态机不可跳步。
