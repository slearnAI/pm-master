# 专职子 Agent 角色定义

主控在 team 模式下派出的专职子 Agent。每个角色职责单一、输入/输出清晰，便于并行且无冲突。
子 Agent **不直接触达用户**，只产出文件并向主控回报。

> 通用约束：所有角色都用 `project_state.py` 读写 `<项目>/project.yaml`，用 `render.py` 产出文件；
> 未知字段填"（待定）"并标注，避免一致性校验失败。

## 1. planner-agent（规划 Agent）
- **职责**：拆解范围 → WBS / 产品 Backlog / 迭代计划；产出里程碑与排期。
- **输入**：`project.yaml`；方法论专属计划模板（waterfall/wbs、agile/product_backlog、iteration/iteration_plan）。
- **输出**：`plans/wbs.md` 或 `plans/product_backlog.md` 等；回写 `artifacts.wbs` / `artifacts.backlog`；`project.yaml` 的 `project.scope` / `metrics.burndown`（如适用）。
- **brief 要点**：WBS 须覆盖全部 scope，每项有唯一 ID、交付物、责任人、工期估算。

## 2. scheduler-agent（排期 Agent）
- **职责**：把 WBS/Backlog 转成带依赖的排期，标注关键路径与里程碑日期。
- **输入**：planner 产物；`templates/waterfall/schedule_gantt.md`。
- **输出**：排期数据 `plans/schedule.yaml`（供 `schedule_health.py` 校验）+ 渲染后的甘特说明。
- **brief 要点**：任务含 id/name/duration/deps；依赖必须指向已有任务 ID。

## 3. risk-agent（风险 Agent）
- **职责**：识别风险/假设/问题/依赖（RAID），给每条风险评概率×影响、定责任人、写应对措施。
- **输入**：`project.yaml`；`templates/common/risk_register.md`、`templates/common/raid_log.md`。
- **输出**：`risks/risk_register.md`、`risks/raid_log.md`；回写 `raid.risks[]`（含 owner、mitigation）、`artifacts.risk`。
- **brief 要点**：每条风险必须有 owner 与 mitigation，否则一致性校验失败。

## 4. stakeholder-agent（干系人 Agent）
- **职责**：梳理干系人、建 RACI、定沟通计划。
- **输入**：`project.yaml`；`templates/common/stakeholder_register.md`、`templates/common/raci.md`、`templates/common/communication_plan.md`。
- **输出**：`docs/stakeholder_register.md`、`docs/raci.md`、`docs/communication_plan.md`；回写 `project.sponsor` / `project.pm` / `project.team[]`。
- **brief 要点**：sponsor 与 pm 必须明确（质量门强制项）。

## 5. reporter-agent（汇报 Agent）
- **职责**：汇总进展，产出状态报告/复盘/收尾报告，计算健康度指标卡。
- **输入**：`project.yaml` + 各产物；`templates/common/status_report.md`、`templates/common/closure_report.md`、`templates/common/lessons_learned.md`。
- **输出**：`reports/status_report.md` 等；如提供 evm 数据则运行 `evm.py` 附指标卡。
- **brief 要点**：状态报告须含 本期进展 / 偏差 / 风险 / 下期计划 / 求助项。

## 6. program-agent（项目群 Agent）
- **职责**：组合层面的治理——组合章程、组合看板、跨项目依赖图、收益实现计划。
- **输入**：`project.yaml`（type=program）；`templates/program/*`。
- **输出**：`docs/program_charter.md`、`reports/portfolio_dashboard.md`、`risks/dependency_map.md`、`reports/benefits_realization.md`；回写 `program.projects[]` / `program.dependencies[]` / `program.benefits[]`。
- **brief 要点**：聚焦"依赖、协同、收益"，而非单项目细节。

## 7. 主控聚合校验清单
- [ ] 各角色产物文件均已生成
- [ ] `consistency_check.py` 通过（风险有 owner/mitigation、pm/sponsor 已填、依赖完整）
- [ ] `artifacts` 索引已回写
- [ ] 必要时 `render_docx.py` 渲染正式文档
