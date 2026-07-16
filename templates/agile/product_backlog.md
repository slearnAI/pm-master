# 产品 Backlog · {{ project.name }}

> 需求池按优先级排序；估算单位可为故事点（Story Point）。本文档是产品的单一需求来源（Single Source of Truth）。

## 使用说明
- 优先级建议：P0（必须）> P1（重要）> P2（一般）> P3（待定）。
- 状态建议：待梳理 / 已就绪 / 开发中 / 已完成。
- 史诗（Epic）用于横向归类，便于路线规划。

## Backlog 清单
| ID | 标题 | 史诗 | 优先级 | 估算 | 状态 |
|----|------|------|--------|------|------|
{{#each backlog}}
| {{this.id}} | {{this.title}} | {{this.epic}} | {{this.priority}} | {{this.estimate}} | {{this.status}} |
{{/each}}

> 提示：配合 `sprint_plan.md` 将高优先级条目纳入 Sprint 承诺范围。
