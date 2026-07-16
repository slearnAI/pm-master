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
- **联络簿同步（关键）**：定稿 `communication_plan.md` 的「相关方联络簿」后，**必须把每一行同步进 `project.yaml` 的 `communication.contacts[]`**（用 `project_state.py set communication.contacts '<yaml>'`）。这是邮件沟通的机读收件人库——`communication-agent` / `comm_send.py` 只认 `project.yaml`，不解析 Markdown。字段：`{ name, role, org, email, phone, tz, note }`；`email` 必填。

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

## 8. communication-agent（沟通 / 邮件 Agent）

> 正式邮件是**对外、不可逆、安全敏感**动作。本角色只负责起草与编排，**绝不自行外发**——
> 任何发送都必须经显式审批（见 `scripts/comm_send.py` 的硬审批门与技能根 `config.yaml` 的 `requires_send_approval`）。

- **职责**：基于沟通计划与联络簿，起草正式邮件（状态通知、里程碑提醒、风险升级、变更通知等），经审批后外发，并登记审计。
- **输入**：`project.yaml` 的 `communication.contacts[]`（收件人库）、`config.yaml` 的 `email.*`（后端/发件人/审批护栏）、`templates/` 中可复用的通知模板（如 `status_report` / `closure_report` 摘要）。
- **输出**：起草的邮件草稿（呈现给用户确认）；经审批后调用邮件技能/ `comm_send.py` 实际发送；发送记录写入 `governance.communications[]`（审计：`to / subject / on / approved_by / backend / status`）。
- **标准流程（强制）**：
  1. **起草**：按角色解析收件人（如 `sponsor,pm` → 查 `communication.contacts[]` 得邮箱），写正文。
  2. **呈现待批**：把「收件人 + 主题 + 正文摘要」交给用户/PM，**等待显式 approve**。
  3. **审批后发送**：`python3 $SKILL_DIR/scripts/comm_send.py --project <项目>/project.yaml --to <角色或邮箱> --subject "..." --body-file <草稿.md> --approve "张三(PM)"`。未带 `--approve` 或被安装护栏要求 sponsor 会签而 approver 不含 sponsor → 脚本直接 `exit 1`，**不发**。
  4. **审计**：发送成功/ dry-run 后，`comm_send.py` 自动追加一条 `governance.communications` 记录，供追溯。
- **brief 要点**：邮件正文必须含项目名与明确的行动项/截止；外部邮件（收件人不在 `contacts` 内或 `approval_override.require_sponsor_cosign=true`）须升级到 sponsor 会签；任何情况下不得绕过审批门。

## 9. monitoring-agent（监控 / 控制 Agent）

> operational 双轨的「监控轨」（见 `references/orchestration.md §3.4`）。与执行轨并行，只负责"盯"，不产交付物本身。

- **职责**：按 `control.cadence` 周期跑 `control_engine.py` 对照基线巡检；产出 `status_report` / `control_report`；滚动更新 `risk_register` / `raid_log` / `milestone_list`；对 RED 升级项回报主控。
- **输入**：`project.yaml`（须已 `operational` 且 `baseline.file` 存在）、`baselines/`、各产物。
- **输出**：`reports/status_report.md`、`artifacts/control_report.md`、`risks/raid_log.md`（滚动）；回写 `raid.risks[]` / `raid.issues[]` 状态。
- **brief 要点**：只读基线、写控制/状态报告与 RAID 更新，**不碰**执行轨的交付物；发现 RED 升级立即回流主控，由主控路由纠偏回执行轨。
