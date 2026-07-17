# 混合治理地图 · {{ project.name }}

> 在混合交付模式下，明确各部分采用的方法论、关口（Gate）与决策人，避免权责模糊。

## 治理地图

```mermaid
flowchart TD
{{#each governance.parts}}
    {{ mid(this.name) }}["{{ mlabel(this.name) }}\n方法: {{ mlabel(this.methodology) }}\n关口: {{ mlabel(this.gate) }}\n决策: {{ mlabel(this.decision_owner) }}"]
{{/each}}
```

## 各部分方法论（Governance Map）
| 部分 | 方法论 | 关口/门禁 | 决策人 |
|------|--------|-----------|--------|
{{#each governance.parts}}
| {{this.name}} | {{this.methodology}} | {{this.gate}} | {{this.decision_owner}} |
{{/each}}

## 治理原则（Principles）
> 贯穿各部分的统一治理准则。

{{#each governance.principles}}
- {{this}}
{{/each}}

> 提示：关口（Gate）是阶段流转的强制评审点；未过门禁不得进入下一阶段。
