# 项目看板 · {{ project.name }}

> 项目看板（Project Board）以可视化方式汇总所有工作项及其负责人、状态与优先级，便于每日站会与迭代规划时快速掌握全局。

| ID | 标题 | 负责人 | 状态 | 优先级 |
|----|------|--------|------|--------|
{{#each board}}
| {{this.id}} | {{this.title}} | {{this.owner}} | {{this.status}} | {{this.priority}} |
{{/each}}

_生成于 PM Master · 项目看板模板_
