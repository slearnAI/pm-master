# 控制登记册 · Control Register

> 运营期开局必须确立的**常规控制清单**：定义"巡检什么 / 频次 / 责任人 / 触发条件 / 上一次结果"。
> 这是 PM 控制引擎运行的纪律基础；缺项时一致性门禁会告警。

| 项 | 内容 |
|----|------|
| 项目名称 | {{ project.name }}（{{ project.id }}） |
| 控制责任人 | {{ project.pm }} |
| 巡检频次 (cadence) | {{#if control}}{{ control.cadence }}{{#else}}（未配置：请在 project.yaml 设置 control.cadence）{{/if}} |
| 升级阈值 | {{#if control}}{{#if control.thresholds}}SPI<{{control.thresholds.spi_warn}} / CPI<{{control.thresholds.cpi_warn}} / 进度落后≥{{control.thresholds.schedule_slip_pct}}% / 未决变更≥{{control.thresholds.open_change_high}}{{#else}}（默认）{{/if}}{{#else}}（默认）{{/if}} |

## 常规控制项（Recurring Controls）

| # | 控制项 | 对照基线计算 | 默认升级阈值 | 频次 | 上一次结果 |
|---|--------|--------------|--------------|------|------------|
| 1 | 进度 Schedule | 各 WBS 包 计划% vs 实际% 偏差 / 逾期天数 | 落后≥15% 或逾期未完成 | {{#if control}}{{control.cadence}}{{#else}}—{{/if}} | 待首次巡检 |
| 2 | 成本 EVM | SPI=EV/PV, CPI=EV/AC, EAC/ETC/VAC | SPI<0.95 或 CPI<0.95 | {{#if control}}{{control.cadence}}{{#else}}—{{/if}} | 待首次巡检 |
| 3 | 风险漂移 Risk | 当前评分 vs 基线评分；新增红/严重风险 | 评分升级或新增高/严重风险 | 每评审周期 | 待首次巡检 |
| 4 | 里程碑 Milestone | 里程碑日期已过且未完成 | 逾期未完成 | 每里程碑前 | 待首次巡检 |
| 5 | 问题 RAID | 问题 due 已过且未关闭 | 逾期未关闭 | 每周 | 待首次巡检 |
| 6 | 变更 Change | 未决变更请求数量 | 未决数≥2 | 每 CCB | 待首次巡检 |
| 7 | 数据完整性 | 重跑 consistency_check | 门禁失败 | 每次巡检 | 待首次巡检 |

## 运行方式

```
python3 control_engine.py --project <project.yaml> [--as-of YYYY-MM-DD]
```

- 输出 `control_report.md` + 结构化 JSON；整体状态 **RED 时退出码 1**，可挂定时任务 / 自动化周期巡检与告警。
- 收件人：{{#if control}}{{#if control.recipients}}{{#each control.recipients}}{{this}} {{/each}}{{#else}}（未配置）{{/if}}{{#else}}（未配置）{{/if}}
