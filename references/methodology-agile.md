# 方法论 · Agile（敏捷：Scrum / Kanban）

## 适用场景
需求不确定、需快速反馈、软件产品持续演进。框架二选一：**Scrum**（时间盒 Sprint）或 **Kanban**（流动优先）。

## A. Scrum 框架

### 仪式（ ceremonies ）
| 仪式 | 频率 | 产出 |
|------|------|------|
| Sprint Planning 冲刺计划 | 每 Sprint 初 | sprint_plan（承诺 backlog + 目标） |
| Daily Standup 站会 | 每日 | 阻塞同步 |
| Sprint Review 评审 | 每 Sprint 末 | 可演示增量、反馈 |
| Sprint Retro 回顾 | 每 Sprint 末 | 改进项（retro 模板） |

### 核心工件（敏捷专属模板）
- `templates/agile/product_backlog.md`：史诗/特性/用户故事、优先级、估算
- `templates/agile/sprint_plan.md`：本 Sprint 目标 + 承诺项 + 任务拆解
- `templates/agile/definition_of_done.md`：完成定义（DoD）检查清单
- `templates/agile/burndown.md`：燃尽图数据 + 说明
- `templates/agile/retro.md`：回顾模板（做得好/待改进/行动）

### 节奏
- Sprint 长度 1–4 周（默认 2 周）；固定节奏，不随意拉长。
- 看板流动：WIP 受限，Lead Time 度量。

## B. Kanban 框架
- 无固定迭代；聚焦**流动**：限制 WIP、度量 Lead Time / 流动效率、按类服务（CoS）。
- 工件：看板板（可用 `templates/agile/product_backlog.md` 当需求池）+ `burndown.md` 改作累积流图。

## 关键指标
- Velocity 速率、Burn-down 燃尽、Lead Time、WIP、流动效率（见 `references/metrics.md`）

## 注意事项
- `project.yaml` 的 `framework` 必须为 `scrum` 或 `kanban`，影响模板与仪式选择。
- DoD 是质量红线，回顾行动项要跟踪闭环（进 RAID 的 issues）。
- 敏捷不等于无文档：章程、RACI、风险仍按 common/ 维护。
