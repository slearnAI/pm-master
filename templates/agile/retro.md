# Sprint 回顾 · {{ project.name }}

> 周期性复盘：沉淀经验、暴露问题、落实改进行动项。

- **Sprint 编号**：{{ sprint.num }}

## 做得好（Keep）
> 本周期值得保持的做法。

{{#each retro.good}}
- {{this}}
{{/each}}

## 待改进（Improve）
> 本周期暴露的问题与改进机会。

{{#each retro.improve}}
- {{this}}
{{/each}}

## 行动项（Action Items）
| 行动 | 负责人 | 截止 |
|------|--------|------|
{{#each retro.actions}}
| {{this.item}} | {{this.owner}} | {{this.due}} |
{{/each}}

> 提示：行动项须在下个 Sprint 计划会上跟踪闭环。
