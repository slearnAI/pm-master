# RAID 日志 · {{ project.name }}

> RAID 日志（Risks / Assumptions / Issues / Dependencies）是项目日常管理的一页纸看板，集中跟踪风险、假设、问题与依赖，便于站会与周会快速过堂。

## R · 风险（Risks）
| ID | 描述 | 责任人 | 应对措施 |
|----|------|--------|----------|
{{#each raid.risks}}
| {{this.id}} | {{this.description}} | {{this.owner}} | {{this.mitigation}} |
{{/each}}

## A · 假设（Assumptions）
{{#each raid.assumptions}}
- {{this}}
{{/each}}

## I · 问题（Issues）
| ID | 描述 | 责任人 | 解决期限 |
|----|------|--------|----------|
{{#each raid.issues}}
| {{this.id}} | {{this.description}} | {{this.owner}} | {{this.due}} |
{{/each}}

## D · 依赖（Dependencies）
| ID | 来源 | 依赖对象 |
|----|------|----------|
{{#each raid.dependencies}}
| {{this.id}} | {{this.from}} | {{this.to}} |
{{/each}}

_生成于 PM Master · RAID 日志模板_
