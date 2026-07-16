# 里程碑清单 · {{ project.name }}

> 里程碑清单（Milestone List）列出项目关键节点及其计划日期、责任人与达成状态，用于高层进度跟踪与阶段验收。

| ID | 里程碑 | 计划日期 | 责任人 | 状态 |
|----|--------|----------|--------|------|
{{#each milestones}}
| {{this.id}} | {{this.name}} | {{this.date}} | {{this.owner}} | {{this.status}} |
{{/each}}

_生成于 PM Master · 里程碑清单模板_
