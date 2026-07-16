# 变更请求 · {{ project.name }}

> 任何范围 / 排期 / 资源 / 成本的偏离基线变更，均须通过本表单提出，由 CCB 评审后方可实施。

## 变更概要
- **变更编号（CR）**：{{ cr.id }}
- **提出人**：{{ cr.requester }}
- **提出日期**：{{ cr.date }}
- **关联阶段/门**：{{ cr.gate }}

## 变更内容
| 项 | 现状（基线） | 拟变更后 |
|----|--------------|----------|
| 范围 | {{ cr.scope_before }} | {{ cr.scope_after }} |
| 进度 | {{ cr.schedule_before }} | {{ cr.schedule_after }} |
| 成本 | {{ cr.cost_before }} | {{ cr.cost_after }} |
| 资源 | {{ cr.resource_before }} | {{ cr.resource_after }} |

## 变更理由
{{ cr.rationale }}

## 影响评估
- **对关键路径/里程碑的影响**：{{ cr.impact_schedule }}
- **对预算/BAC 的影响**：{{ cr.impact_cost }}
- **对质量/风险的影响**：{{ cr.impact_risk }}
- **对依赖组件的影响**：{{ cr.impact_dependency }}

## CCB 评审结论
| 角色 | 决策（批准/有条件批准/驳回） | 意见 | 日期 |
|------|------------------------------|------|------|
| 发起人(Sponsor) |  |  |  |
| 项目经理(PM) |  |  |  |
| 治理委员会主席 |  |  |  |

> 结论须同步写入 `change_log` 形成追溯链；未经批准不得实施变更。
