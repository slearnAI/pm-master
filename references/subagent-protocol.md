# Sub-Agent 通信协议 v2.0

本文件定义 PM Master 中主控与子Agent之间的**通信契约**。所有子Agent必须遵守此协议，
主控通过此协议校验子Agent产出。

---

## 1. 子Agent输出契约（JSON Schema）

每个子Agent完成任务后，必须向主控回报一个结构化JSON：

```json
{
  "agent_role": "planner-agent",
  "status": "success|partial|failed",
  "artifacts": [
    {
      "key": "wbs",
      "path": "/workspace/<slug>/plans/wbs.md",
      "rendered": true
    }
  ],
  "data_files": ["/workspace/<slug>/plans/wbs_data.yaml"],
  "project_yaml_updates": {
    "artifacts.wbs": "plans/wbs.md",
    "project.scope": "..."
  },
  "key_findings": [
    "WBS共包含23个工作包，其中SOW级5个，叶子包18个",
    "关键路径为SOW1→SOW3→SOW5，总工期约12周",
    "识别出3个跨域依赖需要协调"
  ],
  "warnings": [
    "SOW4缺少明确的责任人，标记为（待定）"
  ],
  "errors": []
}
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `agent_role` | 是 | 子Agent角色名（对齐agents.md） |
| `status` | 是 | success=全部完成, partial=部分完成, failed=失败 |
| `artifacts` | 是 | 产出的文件清单，每项含key(artifacts键名)和path |
| `data_files` | 否 | 产出的数据YAML文件路径 |
| `project_yaml_updates` | 否 | 需要主控写入project.yaml的更新（主控汇总后统一写） |
| `key_findings` | 是 | 3-5条关键发现 |
| `warnings` | 否 | 需要注意但未阻塞的问题 |
| `errors` | 否 | 阻塞性问题（有此项时status应为failed） |

---

## 2. 子Agent行为规范

### 2.1 必须做的事

1. **先读project.yaml**：用 `project_state.py show` 或直接Read文件
2. **用render.py渲染**：不可手写Markdown，必须 `render.py --template ... --data ... --out ...`
3. **回写数据**：产出物路径必须回报给主控，由主控统一写入project.yaml
4. **估算数值化**：所有estimate字段必须>0的数值
5. **未知填"（待定）"**：不可留空或编造数据

### 2.2 禁止做的事

1. **禁止直接回复用户**：所有产出只回报给主控
2. **禁止修改其他Agent的文件**：只写自己负责的目录
3. **禁止编造数据**：不确定的填"（待定）"并标注
4. **禁止跳过render.py**：模板渲染必须用render.py
5. **禁止修改project.yaml**：由主控汇总后统一写入

### 2.3 异常处理

当遇到问题时：
- 数据缺失 → 填"（待定）"，在warnings中说明
- 模板不存在 → 在errors中报告，status=partial
- 依赖文件不存在 → 在errors中报告，status=failed
- 不确定如何执行 → 在warnings中说明，按最佳判断继续

---

## 3. 主控聚合流程

```
1. 等待所有子Agent回报（或超时）
2. 对每个子Agent回报：
   a. 校验JSON格式完整性
   b. 验证产物文件确实存在
   c. 汇总 project_yaml_updates
3. 统一写入 project.yaml（避免并发冲突）
4. 运行 consistency_check.py
5. 如有问题，把问题清单交给对应子Agent修复
6. 通过后交付
```

---

## 4. 子Agent角色→产物映射

| 角色 | 产出文件 | artifacts key |
|------|---------|--------------|
| planner-agent | plans/wbs.md 或 plans/product_backlog.md | wbs / backlog |
| scheduler-agent | plans/schedule_gantt.md | schedule_gantt |
| risk-agent | risks/risk_register.md, risks/raid_log.md | risk_register, raid_log |
| stakeholder-agent | docs/stakeholder_register.md, docs/raci.md, docs/communication_plan.md | stakeholder, raci, communication_plan |
| reporter-agent | reports/status_report.md | status_report |
| program-agent | docs/program_charter.md, reports/portfolio_dashboard.md, risks/dependency_map.md, reports/benefits_realization.md | program_charter, portfolio_dashboard, dependency_map, benefits_realization |
| communication-agent | 邮件草稿 (不直接发) | email_draft |
| monitoring-agent | reports/status_report.md, artifacts/control_report.md | status_report, control_report |

---

## 5. Brief模板（主控发给子Agent）

```markdown
你是 PM Master 的【<角色>】子Agent。你的任务是独立产出以下文件，完成后回报主控。

## 输入
- 项目事实源：<绝对路径>/project.yaml（用 project_state.py 或 Read 工具读取）
- 模板：<SKILL_DIR>/templates/<路径>/<模板>.md
- 渲染引擎：<SKILL_DIR>/scripts/render.py

## 任务
1. 读取 project.yaml 了解项目背景
2. 整理本产物所需数据，写成 <slug>_data.yaml
3. 运行：python3 <SKILL_DIR>/scripts/render.py --template <模板路径> --data <slug>_data.yaml --out <输出路径>
4. 验证产物文件已生成

## 回报格式（必须严格遵守）
完成后，以以下JSON格式回报：
{
  "agent_role": "<你的角色>",
  "status": "success|partial|failed",
  "artifacts": [{"key": "<artifacts键名>", "path": "<产物绝对路径>"}],
  "data_files": ["<数据文件路径>"],
  "project_yaml_updates": {"<key>": "<value>"},
  "key_findings": ["发现1", "发现2", "发现3"],
  "warnings": [],
  "errors": []
}

## 约束
- 只产出你负责的文件，不碰其他角色的文件
- 必须用 render.py 渲染，不可手写Markdown
- 估算必须数值化(>0)，未知字段填"（待定）"
- 不直接回复用户，只回报主控
```
