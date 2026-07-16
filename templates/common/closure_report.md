# 项目收尾报告 · {{ project.name }}

> 项目收尾报告（Closure Report）确认交付范围完成、获得正式验收、完成知识移交，并沉淀最终指标与经验教训索引，标志项目正式关闭。

## 1. 范围完成情况
{{ closure.scope_done }}

## 2. 验收结论
{{ closure.acceptance }}

## 3. 移交清单
{{#each closure.handover}}
- {{this}}
{{/each}}

## 4. 最终指标
| 指标 | 数值 |
|------|------|
| 总预算 | {{ closure.metrics.budget }} |
| 实际花费 | {{ closure.metrics.spent }} |
| 进度偏差 | {{ closure.metrics.schedule_variance }} |
| 成本偏差 | {{ closure.metrics.cost_variance }} |

## 5. 经验沉淀索引
{{ closure.lessons_ref }}

_生成于 PM Master · 项目收尾报告模板_
