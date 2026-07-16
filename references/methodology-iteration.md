# 方法论 · Iteration（迭代 / 时间盒）

## 适用场景
需求中等确定、希望规律交付但不必严格 Scrum 仪式；或团队偏大、按固定时间盒出可验收增量
（常见于大型研发组织的"双周迭代""月度迭代"）。比 agile 更强调**迭代内范围相对固定**。

## 生命周期（迭代循环）
```
迭代规划 ──▶ 迭代执行(时间盒) ──▶ 迭代评审 ──▶ 迭代复盘 ──┐
   ▲                                                  │
   └──────────────── 下一迭代 ◀───────────────────────┘
```

| 活动 | 频率 | 主要模板 |
|------|------|----------|
| 迭代计划 | 每迭代初 | iteration/iteration_plan |
| 迭代执行 | 迭代期内 | iteration/iteration_backlog（任务看板） |
| 迭代评审 | 每迭代末 | iteration/iteration_review |
| 迭代复盘 | 每迭代末 | agile/retro（复用） |

## 核心工件（迭代专属模板）
- `templates/iteration/iteration_plan.md`：迭代目标、承诺范围、关键里程碑、资源
- `templates/iteration/iteration_backlog.md`：本迭代任务清单（ID/负责人/估时/状态）
- `templates/iteration/iteration_review.md`：完成项 / 偏差 / 演示结论 / 下迭代输入

## 节奏（cadence）
- 固定时间盒（如 2 周），迭代长度稳定。
- 评审 + 复盘在迭代末固定进行；状态报告按迭代出（可复用 common/status_report）。

## 关键指标
- 迭代燃尽、迭代完成率 = 完成项 / 承诺项、速率趋势（见 `references/metrics.md`）

## 与 Agile 的区别
- iteration：迭代内范围锁定、重承诺；agile(Scrum)：更强调价值拉动、DoD、角色化仪式。
- 模板可互通：iteration_backlog ≈ sprint_plan 的轻量版；复盘共用 retro。

## 注意事项
- 迭代评审要产出"是否达成承诺"的结论，偏差进 `raid.issues`。
- 跨迭代依赖在 `raid.dependencies` 登记，避免下迭代被阻塞。
