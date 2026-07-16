# 项目状态报告 · {{ project.name }}

> 项目状态报告（Status Report）定期向干系人同步项目健康度：本期进展、已完成与下期计划、关键指标、风险与求助项。

- **项目阶段**：{{ project.phase }}
- **报告周期**：{{ period }}

## 1. 本期概览
{{ progress.summary }}

## 2. 已完成事项
{{#each progress.completed}}
- {{this}}
{{/each}}

## 3. 下期计划
{{#each progress.next}}
- {{this}}
{{/each}}

## 4. 关键指标
| 指标 | 数值 |
|------|------|
| CPI（成本绩效指数） | {{ metrics.cpi }} |
| SPI（进度绩效指数） | {{ metrics.spi }} |
| PV（计划价值） | {{ metrics.pv }} |
| EV（挣值） | {{ metrics.ev }} |
| AC（实际成本） | {{ metrics.ac }} |

## 5. 风险与阻塞
{{#each risks}}
- {{this}}
{{/each}}

## 6. 求助项（需上升支持）
{{#each help}}
- {{this}}
{{/each}}

_生成于 PM Master · 项目状态报告模板_
