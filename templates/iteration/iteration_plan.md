# 迭代计划 · {{ project.name }}

> 定义本次迭代的目标、范围、里程碑与资源投入，作为迭代执行基线。

## 基本信息
- **迭代编号**：{{ iteration.num }}
- **迭代目标**：{{ iteration.goal }}

## 范围（Scope）
> 本次迭代纳入交付的需求与事项。

{{#each iteration.scope}}
- {{this}}
{{/each}}

## 里程碑（Milestones）
> 迭代内关键时间节点与可验收产出。

{{#each iteration.milestones}}
- {{this}}
{{/each}}

## 资源（Resources）
> 投入的人员、环境与其他必要资源。

{{#each iteration.resources}}
- {{this}}
{{/each}}

> 提示：范围与资源不匹配时，应优先裁剪范围以守住里程碑。
