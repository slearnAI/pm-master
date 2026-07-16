# Sprint 燃尽图 · {{ project.name }}

> 对比实际剩余工作量与理想燃尽线，判断 Sprint 进度健康度。

- **Sprint 编号**：{{ sprint.num }}

## 燃尽数据
| 日期/天 | 剩余工作量 | 理想燃尽 |
|---------|-----------|----------|
{{#each burndown}}
| {{this.day}} | {{this.remaining}} | {{this.ideal}} |
{{/each}}

## 燃尽图

```mermaid
xychart-beta
    title "Sprint {{ sprint.num }} 燃尽图"
    x-axis "天" [{{ join(burndown, ", ", "day") }}]
    y-axis "剩余工作量" 0 --> {{ burndown.[0].remaining }}
    line [{{ join(burndown, ", ", "remaining") }}]
    line [{{ join(burndown, ", ", "ideal") }}]
```

> 判读：实际线持续高于理想线 → 进度滞后；贴近或低于 → 进度健康。

> 提示：估算单位需与 Sprint 计划保持一致（如故事点或人天）。
