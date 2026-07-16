# 迭代 Backlog · {{ project.name }}

> 本次迭代范围内的工作项清单，含负责人、估算与状态，用于日常跟踪。

- **迭代编号**：{{ iteration.num }}

## 工作项清单
| ID | 标题 | 负责人 | 估算 | 状态 |
|----|------|--------|------|------|
{{#each backlog}}
| {{this.id}} | {{this.title}} | {{this.owner}} | {{this.estimate}} | {{this.status}} |
{{/each}}

> 提示：状态建议：未开始 / 进行中 / 已阻塞 / 已完成。
