# 干系人登记册 · {{ project.name }}

> 干系人登记册（Stakeholder Register）识别所有受项目影响或能影响项目的个人与组织，记录其利益、影响力与参与度策略，为沟通与期望管理提供依据。

- **项目经理**：{{ project.pm }}

## 干系人清单

| 姓名 | 角色 | 利益诉求 | 影响力 | 参与度策略 |
|------|------|----------|--------|------------|
{{#each stakeholders}}
| {{this.name}} | {{this.role}} | {{this.interest}} | {{this.influence}} | {{this.engagement}} |
{{/each}}

_生成于 PM Master · 干系人登记册模板_
