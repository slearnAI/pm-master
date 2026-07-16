# 项目章程 · {{ project.name }}

> 项目章程（Project Charter）由项目发起方批准，正式授权项目经理动用资源，并明确项目目标、范围、关键角色与时间窗。

## 1. 项目概述
- **项目名称**：{{ project.name }}
- **项目类型**：{{ project.type }}
- **方法论**：{{ project.methodology }}

## 2. 项目目标
{{#each project.objectives}}
- {{this}}
{{/each}}

## 3. 范围
- **范围内（In Scope）**：{{ project.scope }}
- **范围外（Out of Scope）**：{{ project.out_of_scope }}

## 4. 关键角色
- **项目发起方（Sponsor）**：{{ project.sponsor }}
- **项目经理（PM）**：{{ project.pm }}
- **核心团队**：
{{#each project.team}}
  - {{this}}
{{/each}}

## 5. 时间窗
- **启动日期**：{{ project.start_date }}
- **目标完成日期**：{{ project.target_end }}

## 6. 方法论说明
{{#if project.methodology == "scrum"}}
本项目采用 Scrum 敏捷框架，以固定时长的 Sprint 迭代交付，通过每日站会、评审会与回顾会持续对齐需求并改进。
{{else}}
本项目采用 {{ project.methodology }} 方法论推进，按既定阶段与里程碑进行计划、执行与监控。
{{/if}}

_生成于 PM Master · 项目章程模板_
