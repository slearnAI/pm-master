# 阶段门评审 · {{ project.name }}

> 阶段门评审（Stage-Gate Review）在每个阶段结束时依检查清单逐项核验，并给出通过 / 有条件通过 / 不通过的决策结论，控制阶段间的投决风险。

- **评审门**：{{ gate.name }}
- **所处阶段**：{{ gate.phase }}

## 评审检查清单
| 检查项 | 状态 | 说明 |
|--------|------|------|
{{#each gate.checklist}}
| {{this.item}} | {{this.status}} | {{this.comment}} |
{{/each}}

## 决策结论
{{ gate.decision }}

_生成于 PM Master · 阶段门评审模板_
