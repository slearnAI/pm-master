# 项目群章程 · {{ project.name }}

> 确立项目群的愿景、目标、范围、治理、收益与财务边界，作为群级治理的基线契约。

## 基本信息
- **项目/项目群类型**：{{ project.type }}
- **方法论**：{{ project.methodology }}

## 愿景（Vision）
{{ program.vision }}

## 目标（Goals）
{{#each program.goals}}
- {{this}}
{{/each}}

## 成功标准（Success Criteria）
{{#each program.success_criteria}}
- {{this}}
{{/each}}

## 范围（Scope）
{{ program.scope }}

## 财务边界（Financial Envelope）
| 项目 | 内容 |
|------|------|
| 总预算（BAC） | {{ program.budget.total }} |
| 资金来源 | {{ program.budget.funding }} |
| 成本基线 | {{ program.budget.baseline }} |
|  funding 约束/封顶 | {{ program.budget.constraint }} |

## 治理（Governance）
- **治理模式**：{{ program.governance.model }}
- **治理节奏**：{{ program.governance.cadence }}
- **变更控制**：{{ program.governance.change_control }}（CCB 见 change_log）

## 里程碑摘要（Milestones）
| ID | 里程碑 | 计划日期 | 责任人 |
|----|--------|----------|--------|
| {{#each program.milestones}}
| {{this.id}} | {{this.name}} | {{this.date}} | {{this.owner}} |
{{/each}}

## 收益目标（Benefits Target）
{{#each program.benefits_target}}
- {{this}}
{{/each}}

## 签署（Sign-off）
| 角色 | 姓名 | 日期 | 签字 |
|------|------|------|------|
| 项目群发起人(Sponsor) |  |  |  |
| 项目群经理(Program Manager) |  |  |  |
| 治理委员会主席 |  |  |  |

> 提示：章程一经批准即作为群级决策依据；变更须走治理流程（change_log / CCB）。
