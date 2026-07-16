# 工作分解结构（WBS）· {{ project.name }}

> **视图：{{ view_label }}** — {{ view_note }}
> 两层颗粒度约定（pm-master）：**项目群层级仅呈现里程碑级**（各 SOW 汇总包 + 各阶段里程碑汇总包）；
> **组件层级呈现最细叶子工作包级**（含领域专家拆解包）。两者共用单一事实源（`project.yaml`），
> 由 `build_wbs.py --view` 切换。`slug(this.id)` 生成甘特任务 id，依赖网络由 `wbs[].dependsOn` 定义。

## WBS 总表（{{ view_label }}）

| ID | 名称 | 层级 | 领域 | 交付物 | 责任人 | 角色/专家 | 估算(人天) | 工期 | 开始时间 | 结束时间 | 依赖 | 验收准则(DoD) |
|----|------|------|------|--------|--------|-----------|------------|------|----------|----------|------|---------------|
{{#each wbs}}
| {{this.id}} | {{this.name}} | {{this.level}} | {{this.domain}} | {{this.deliverable}} | {{this.owner}} | {{this.role}}{{#if this.expert}}（{{this.expert}}）{{/if}} | {{this.estimate}} | {{this.duration}} | {{this.start}} | {{this.end}} | {{this.dependsOn}} | {{this.acceptance}} |
{{/each}}

## WBS 甘特图（mermaid · {{ view_label }}）

> 按 **{{ view_group_note }}** 分组；每包以起止日期绝对定位（不混用 `after` 依赖链，保证语法合法、可读）。

```mermaid
gantt
    title {{ project.name }} · WBS 甘特图（{{ view_label }}）
    dateFormat YYYY-MM-DD
    axisFormat %Y-%m
    todayMarker stroke-width:2px,stroke:#e3000b
{{#each wbs_groups}}
    section {{this.name}}
{{#each this.items}}
    {{this.gantt_name}} :{{slug(this.id)}}, {{this.start}}, {{this.end}}
{{/each}}
{{/each}}
```

> **依赖说明**：依赖网络由 `wbs[].dependsOn` 定义（一致性校验强制联网）。甘特图以绝对起止日期呈现各包位置；
> 如需在图中绘制依赖箭头，可在 `wbs_groups` 任务行追加 `after <id>`（须保证被引用 id 已作为任务渲染）。
>
> **角色 / 领域 / 颗粒度**：每个**领域活动**工作包须标注 `role`（产出角色，见 `references/expert-roles.md`）
> 与 `domain`（子领域）；叶子包 `estimate` 不得超过颗粒度阈值（默认 10 人天，见 `control.granularity_threshold`），
> 超过者须由对应领域专家拆解为其下叶子包（ID 前缀如 `SOW1.1`）。粗粒度 SOW 级包未经专家拆解不得作为交付。
>
> **两层颗粒度**：项目群 `project.type: program` 的 WBS 工件仅含里程碑级行（`tier: program`）；
> 各组件 `project.type: project` 持有最细叶子包（`tier: component`）。`build_wbs.py --view` 据此过滤。

_生成于 PM Master · WBS 模板（两层颗粒度 · 表格 + mermaid 甘特双视图）_
