# Sprint 计划 · {{ project.name }}

> 声明本 Sprint 的目标、承诺范围与任务拆解，作为团队本周期的执行契约。

## 基本信息
- **Sprint 编号**：{{ sprint.num }}
- **Sprint 目标**：{{ sprint.goal }}

## 承诺范围（Commitment）
> 本 Sprint 承诺交付的范围要点，须可演示、可验证。

{{#each sprint.commitment}}
- {{this}}
{{/each}}

## 任务拆解（Task Breakdown）
| ID | 标题 | 负责人 | 估算 |
|----|------|--------|------|
{{#each sprint.tasks}}
| {{this.id}} | {{this.title}} | {{this.owner}} | {{this.estimate}} |
{{/each}}

> 提示：承诺范围应覆盖目标；任务估算之和即为本 Sprint 投入基线。
