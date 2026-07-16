# 运营控制报告 · Control Report

> 由 PM 控制引擎（`control_engine.py`）对照基线生成。整体状态：
**{{ overall_status }}** · 巡检基准日：{{ as_of }} · 基线日期：{{ baseline_on }}

## 指标卡

| 指标 | 值 |
|------|----|
| 进度（计划→实际） | {{ metrics.planned_pct }}% → {{ metrics.actual_pct }}% |
| SPI（进度绩效） | {{ metrics.spi }} |
| CPI（成本绩效） | {{ metrics.cpi }} |
| PV / EV / AC | {{ metrics.pv }} / {{ metrics.ev }} / {{ metrics.ac }} |
| EAC / ETC / VAC | {{ metrics.eac }} / {{ metrics.etc }} / {{ metrics.vac }} |
| BAC（完工预算） | {{ metrics.bac }} |

## 控制项明细

| 状态 | 控制项 | 说明 |
|------|--------|------|
{{#each controls}}| {{ this.status }} | {{ this.name }} | {{ this.detail }} |
{{/each}}

## 进度明细（Schedule）

> 每个工作包 / 里程碑单列一行，**计划% / 实际% / 偏差% 分列呈现**（偏差 = 实际 − 计划）。
> 落后超过阈值即标黄/红，便于一眼定位滞后项，而非挤在一列长串中。

| ID | 工作包 / 里程碑 | 计划% | 实际% | 偏差% | 状态 |
|----|----------------|-------|-------|-------|------|
{{#each schedule_table}}| {{this.id}} | {{this.name}} | {{this.planned}} | {{this.actual}} | {{this.variance}} | {{this.status}} |
{{/each}}

{{schedule_note}}

## 升级项（Escalations）

{{#if escalations}}
{{#each escalations}}- {{ this }}
{{/each}}{{#else}}
无升级项。项目按基线预期运行。
{{/if}}

---
*本报告由 `control_engine.py` 自动生成；状态 RED 时退出码为 1，可挂定时任务 / 自动化进行周期巡检与告警。*
