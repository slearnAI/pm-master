# SOW 启动会 · {{ sow.id }} · {{ sow.name }}

> 每个 SOW（Statement of Work，工作说明书）级包在规划期须单独召开**启动会（Kick-off）**，
> 对齐范围、交付物、责任人与首批行动，并产出本工件（由 `scripts/build_sow_kickoff.py`
> 从 `project.yaml` 的 WBS 自动生成）。本启动会应在对应领域专家完成叶子包拆解后、进入执行前召开。

## 1. 基本信息

| 项 | 内容 |
|----|------|
| 所属项目 | {{ project.name }} |
| SOW ID | {{ sow.id }} |
| SOW 名称 | {{ sow.name }} |
| 领域(domain) | {{ sow.domain }} |
| SOW 责任人(owner) | {{ sow.owner }} |
| 启动会日期 | {{ kickoff_date }} |
| 状态 | {{ status }} |

## 2. 目标与范围

- **目标**：{{ sow.objective }}
- **范围**：{{ sow.scope }}

## 3. 关键交付物（叶子工作包）

| 叶子包 ID | 名称 |
|-----------|------|
{{#each deliverables}}
| {{this.id}} | {{this.name}} |
{{/each}}

## 4. 参与人

| 姓名/角色 | 职责 |
|-----------|------|
{{#each participants}}
| {{this.name}} | {{this.role}} |
{{/each}}

> 领域专家（role）：{{ join(experts, "、") }}

## 5. 启动会决议

| # | 决议事项 | 结论 |
|---|----------|------|
{{#each decisions}}
| {{this.id}} | {{this.item}} | {{this.conclusion}} |
{{/each}}

## 6. 假设与约束

{{#each assumptions}}
- {{this}}
{{/each}}

## 7. 首批行动项

| 行动 | 责任人 | 截止 |
|------|--------|------|
{{#each next_actions}}
| {{this.action}} | {{this.owner}} | {{this.due}} |
{{/each}}

## 8. 关联工件

{{#each artifacts}}
- {{this}}
{{/each}}

_生成于 PM Master · SOW 启动会模板（per-SOW Kick-off）_
