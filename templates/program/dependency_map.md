# 依赖图 · {{ project.name }}

> 梳理组件/团队间的依赖关系与阻塞情况，提前识别交付风险。

## 依赖关系图

```mermaid
flowchart LR
{{#each dependencies}}
    {{ mid(this.from) }}["{{ mlabel(this.from) }}"] -->|{{ mlabel(this.type) }}| {{ mid(this.to) }}["{{ mlabel(this.to) }}"]
{{/each}}
```

## 依赖清单
| ID | 来源 | 目标 | 类型 | 状态 | 是否阻塞 |
|----|------|------|------|------|----------|
{{#each dependencies}}
| {{this.id}} | {{this.from}} | {{this.to}} | {{this.type}} | {{this.status}} | {{this.blocker}} |
{{/each}}

## 说明
- **类型**：接口 / 数据 / 资源 / 决策 等。
- **状态**：规划中 / 进行中 / 已完成 / 已失效。
- **是否阻塞**：是 / 否。

> 提示：存在阻塞的依赖须指定缓解措施与责任人，纳入风险跟踪。
