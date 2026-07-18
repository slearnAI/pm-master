# 风险登记册 · {{ project.name }}

> 记录项目全生命周期已识别风险。每条风险须有责任人(owner)、应对措施(mitigation)，
> 并按 **5×5 校准矩阵**（references/risk-matrix.md）填写 likelihood(1-5) / impact(1-5) /
> score(=likelihood×impact) / severity(🟢绿·🟡黄·🟠橙·🔴红)，一致性校验将强制核对色带。

## 5×5 矩阵速查（行=影响 Impact，列=可能性 Likelihood）

| 影响\可能 | 1 | 2 | 3 | 4 | 5 |
|-----------|---|---|---|---|---|
| **5** | 5 🟢绿 | 10 🟠橙 | 15 🟠橙 | 20 🔴红 | 25 🔴红 |
| **4** | 4 🟢绿 | 8 🟡黄 | 12 🟠橙 | 16 🔴红 | 20 🔴红 |
| **3** | 3 🟢绿 | 6 🟡黄 | 9 🟡黄 | 12 🟠橙 | 15 🟠橙 |
| **2** | 2 🟢绿 | 4 🟢绿 | 6 🟡黄 | 8 🟡黄 | 10 🟠橙 |
| **1** | 1 🟢绿 | 2 🟢绿 | 3 🟢绿 | 4 🟢绿 | 5 🟢绿 |

_色带：🟢 绿 1–4 ｜ 🟡 黄 5–9 ｜ 🟠 橙 10–15 ｜ 🔴 红 16–25_

## 风险清单

| ID | 描述 | 类别 | 可能性 | 影响 | 评分 | 严重度 | 责任人 | 应对措施 | 状态 |
|----|------|------|--------|------|------|--------|--------|----------|------|
{{#each risks}}
| {{this.id}} | {{this.description}} | {{this.category}} | {{this.likelihood}} | {{this.impact}} | {{this.score}} | {{ sev_icon(this.severity) }} {{this.severity}} | {{this.owner}} | {{this.mitigation}} | {{this.status}} |
{{/each}}

_生成于 PM Master · 风险登记册模板（5×5 校准）_
