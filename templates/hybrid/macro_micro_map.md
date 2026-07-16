# 宏微映射 · {{ project.name }}

> 将宏观里程碑与微观迭代对齐，确保短期交付持续支撑长期目标。

## 宏微对齐图

```mermaid
flowchart LR
{{#each map}}
    {{slug(this.macro_milestone)}}["{{this.macro_milestone}}"] -->|{{this.alignment_status}}| {{slug(this.micro_iteration)}}["{{this.micro_iteration}}"]
{{/each}}
```

## 映射表（Macro ↔ Micro）
| 宏观里程碑 | 微观迭代 | 对齐状态 |
|-----------|---------|----------|
{{#each map}}
| {{this.macro_milestone}} | {{this.micro_iteration}} | {{this.alignment_status}} |
{{/each}}

> 提示：对齐状态建议取值——已对齐 / 有偏差 / 已脱节；出现偏差需触发治理评审。
