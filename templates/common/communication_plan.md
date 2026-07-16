# 沟通计划 · {{ project.name }}

> 沟通计划（Communication Plan）定义向各干系人传递哪些信息、通过何种渠道、以何种频率、由谁负责，确保信息及时、准确、对称。
> 其中 **相关方联络簿** 是正式邮件沟通的「收件人数据库」：定稿后由 `stakeholder-agent` 同步进 `project.yaml` 的 `communication.contacts[]`，供 `communication-agent` / `comm_send.py` 按角色解析收件人（详见 `references/agents.md §8` 与 `references/project-schema.md`）。

## 1. 沟通矩阵（信息→渠道→频率）

| 受众 | 信息内容 | 渠道 | 频率 | 负责人 |
|------|----------|------|------|--------|
| {{audience}} | {{info}} | {{channel}} | {{frequency}} | {{owner}} |
{{#each comms}}
| {{this.audience}} | {{this.info}} | {{this.channel}} | {{this.frequency}} | {{this.owner}} |
{{/each}}

## 2. 相关方联络簿（Stakeholder Contacts）

> 登记项目主要相关方的关键联络方式，是正式邮件沟通的收件人来源。姓名/角色/邮箱为必填；电话/时区/备注可选。
> `stakeholder-agent` 在定稿时把本表逐行同步进 `project.yaml` 的 `communication.contacts[]`（机读，单一事实源）。

| 姓名 | 角色 | 组织 | 邮箱 | 电话 | 时区 | 备注 |
|------|------|------|------|------|------|------|
| {{name}} | {{role}} | {{org}} | {{email}} | {{phone}} | {{tz}} | {{note}} |
{{#each contacts}}
| {{this.name}} | {{this.role}} | {{this.org}} | {{this.email}} | {{this.phone}} | {{this.tz}} | {{this.note}} |
{{/each}}

_生成于 PM Master · 沟通计划模板_
