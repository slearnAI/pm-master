# 基线记录 · Baseline Record

> 本文档记录项目计划被**冻结为基线**的时点与范围，是后续运营控制（PM 控制引擎）的对照基准。
> 基线一旦确立，任何范围 / 排期 / 预算变更须经变更控制（CCB）。

| 项 | 内容 |
|----|------|
| 项目名称 | {{ project.name }}（{{ project.id }}） |
| 方法论 | {{ project.methodology }} |
| 基线日期 | {{ baseline.on }} |
| 基线人 | {{ baseline.by }} |
| 生命周期状态 | {{ project.lifecycle_state }} |
| 基线快照文件 | {{ baseline.file }} |
| 计划基线确立日 | {{ project.baselined_on }} |

## 基线范围（冻结内容）

基线快照（`{{ baseline.file }}`）固化了以下计划元素，作为控制对照：

- **WBS / 工作包**：范围、估算、依赖网络、交付物与 DoD
- **里程碑**：目标日期与责任人
- **风险登记册**：可能性 / 影响 / 评分 / 严重度（5×5 校准）
- **EVM 基线**：完工预算（BAC / PV）与初始度量

## 控制纪律

1. 未基线化（无 `baseline` 指针）的 waterfall / hybrid 项目**不得**进入执行/监控阶段。
2. 进入 `operational` 后，由 `control_engine.py` 按 `control.cadence` 周期性对照本基线巡检。
3. 任一控制项突破阈值 → 升级告警（exit 1），并触发 `change_request` 评估是否需重基线。

## 关联产物

- 控制登记册：`control_register.md`（定义巡检什么 / 频次 / 责任人）
- 控制报告：`control_report.md`（每次巡检输出）
