# 方法论 · Waterfall（瀑布 / 阶段门）

## 适用场景
需求明确、变更成本高、强合规/强集成的交付（如基础设施迁移、硬件+固件、监管系统、ERP 上线）。
重文档、重计划基线、阶段间强依赖。

## 生命周期（串行阶段 + 阶段门）

```
启动 ──[Gate1 立项]──▶ 规划 ──[Gate2 计划基线]──▶ 执行 ──[Gate3 中期]──▶ 监控 ──[Gate4 验收]──▶ 收尾
```

| 阶段 | 阶段门评审要点 | 主要模板 |
|------|----------------|----------|
| 启动 | 业务必要性、预算、sponsor | common/project_charter |
| 规划 | WBS/排期/风险/质量基线完整 | waterfall/wbs, waterfall/schedule_gantt, waterfall/requirements_spec, common/risk_register |
| 执行 | 范围/进度/成本在基线内 | 变更记录、质量检查 |
| 监控 | 偏差可控、风险受管 | common/status_report, references/metrics（EVM） |
| 收尾 | 验收签字、移交、复盘 | common/closure_report, common/lessons_learned |

## 核心工件（瀑布专属模板）
- `templates/waterfall/requirements_spec.md`：功能/非功能需求、验收标准
- `templates/waterfall/wbs.md`：工作分解结构（唯一 ID、层级、交付物、责任人、工期、开始时间、结束时间、依赖），并附 Mermaid 甘特图
- `templates/waterfall/schedule_gantt.md`：带依赖的排期与甘特说明
- `templates/waterfall/stage_gate_review.md`：阶段门评审清单
- `templates/waterfall/quality_plan.md`：质量目标、检查点、准入准出

## 节奏（cadence）
- 阶段门评审：每阶段结束一次（强制）
- 状态报告：周/双周（监控期）
- 变更控制委员会（CCB）：按需，重大变更必过

## 关键指标
- EVM：CPI / SPI / EAC（见 `references/metrics.md`）
- 里程碑达成率、阶段门一次通过率、变更率

## 注意事项
- 范围在规划期冻结；执行期变更必须走 CCB，并回写 `project.yaml` 与排期。
- 阶段门是"继续/整改/终止"的决策点，不是走形式。
