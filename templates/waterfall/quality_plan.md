# 质量管理计划 · {{ project.name }}

> 质量管理计划（Quality Plan）定义项目质量目标、关键质量检查点（含准入/准出标准）以及所遵循的标准与规范，确保交付物满足既定质量要求。

## 1. 质量目标
{{#each quality.objectives}}
- {{this}}
{{/each}}

## 2. 质量检查点
| 检查点 | 准则 | 准入条件 | 准出条件 |
|--------|------|----------|----------|
{{#each quality.checkpoints}}
| {{this.name}} | {{this.criteria}} | {{this.entry}} | {{this.exit}} |
{{/each}}

## 3. 标准与规范
{{ quality.std }}

_生成于 PM Master · 质量计划模板_
