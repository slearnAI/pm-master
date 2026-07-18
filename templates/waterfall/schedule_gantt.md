# {{ view_label }}排期与甘特视图 · {{ project.name }}

> 排期计划（Schedule / Gantt）基于 WBS 编排任务顺序与依赖关系，标注工期、起止日期与里程碑，形成可供跟踪的项目时间基线。

| ID | 任务 | 工期(天) | 前置依赖 | 开始 | 结束 | 里程碑 |
|----|------|----------|----------|------|------|--------|
{{#each tasks}}
| {{this.id}} | {{this.name}} | {{this.duration}} | {{this.deps}} | {{this.start}} | {{this.end}} | {{#if this.milestone}}是{{else}}否{{/if}} |
{{/each}}

## 甘特图

```mermaid
gantt
    title {{ project.name }} · {{ view_label }}排期甘特图
    dateFormat YYYY-MM-DD
    axisFormat %m-%d
{{#each tasks}}
{{#if this.milestone}}
    {{ gname(this.name) }} :milestone, {{this.start}}
{{else}}
    {{ gname(this.name) }} :{{ mid(this.id) }}, {{this.start}}, {{this.end}}
{{/if}}
{{/each}}
```

_生成于 PM Master · 排期甘特模板_
