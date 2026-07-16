# 完成定义（DoD）· {{ project.name }}

> 每个区域定义"完成"的验收清单；工作项须勾选所在区域全部条目，方可视为 Done。

{{#each dod}}
## {{this.area}}

> 本区域完成标准（全部勾选方视为该维度完成）：

{{#each this.checklist}}
- [ ] {{this}}
{{/each}}

{{/each}}

> 说明：DoD 是质量门槛而非工作量指标；未达标不得计入 Sprint 交付。
