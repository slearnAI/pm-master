# PM Master v2.0 · 项目与项目群管理

> 面向科技行业 PM 的**项目 + 项目群**管理技能。强制执行手册、Builder 理念、内置模板库、
> 多 Agent 调度，适配 **waterfall / agile / iteration / hybrid** 四种方法论。

- **版本**：2.0.0
- **许可**：MIT
- **定位**：任何请求必须产出真实文件，禁止只给建议

---

## v2.0 相比 v1.x 的核心改进

| 改进 | v1.3.6 | v2.0.0 |
|------|--------|--------|
| SKILL.md | 201行，含大量参考资料 | ~90行，纯强制执行指令 |
| 输出稳定性 | 依赖Agent自行理解执行 | 强制工作流+checkpoint机制 |
| 子Agent通信 | 无协议，行为不可预测 | JSON Schema协议+subagent_check校验 |
| 执行期支撑 | 只有control_engine巡检 | +execution_driver驱动执行 |
| 状态机 | 脚本层定义，Agent可跳过 | Agent层_checkpoint锁 |
| 专家调度 | 两层19个角色 | 简化为主控fork模式逐域拆解 |

---

## 快速开始

```bash
SKILL_DIR=/root/.codebuddy/skills/pm-master-v2

# 1) 建工作区
python3 $SKILL_DIR/scripts/init_project.py "支付重构" --type project --methodology agile --framework scrum

# 2) 渲染产物
python3 $SKILL_DIR/scripts/render.py \
  --template $SKILL_DIR/templates/common/risk_register.md \
  --data risks.yaml --out /workspace/支付重构/risks/risk_register.md

# 3) 导出Word
python3 $SKILL_DIR/scripts/render_docx.py /workspace/支付重构/risks/risk_register.md
```

自然语言触发更简单："用敏捷帮我启动支付重构项目"。

---

## 核心铁律（8条不可违反规则）

1. 任何请求必须产出文件
2. 先定位/创建 project.yaml
3. 交付前必过质量门
4. 阶段流转必须过阶段门
5. 估算必须数值化(>0)
6. 方法论模板不混用
7. 正式邮件必须审批
8. 项目群与子项目分层

---

## 脚本清单

| 脚本 | 用途 |
|------|------|
| `init_project.py` | 项目脚手架 |
| `render.py` | 模板→Markdown |
| `render_docx.py` | Markdown→DOCX |
| `consistency_check.py` | 质量门 |
| `build_wbs.py` | WBS视图 |
| `build_schedule.py` | WBS→排期+甘特 |
| `build_sow_kickoff.py` | per-SOW启动会 |
| `schedule_health.py` | 关键路径分析 |
| `evm.py` | 挣值分析 |
| `baseline.py` | 基线化 |
| `control_engine.py` | 运营巡检 |
| `gate_engine.py` | 阶段门 |
| `dispatch.py` | 专家调度审计 |
| `comm_send.py` | 邮件审批发送 |
| `project_state.py` | 事实源读写 |
| `execution_driver.py` | **v2新增** 执行驱动 |
| `subagent_check.py` | **v2新增** 子Agent产出校验 |

---

## 参考文档索引

| 文件 | 何时读 |
|------|--------|
| `references/orchestration.md` | 多Agent调度 |
| `references/agents.md` | 子Agent角色 |
| `references/subagent-protocol.md` | **v2新增** 子Agent通信协议 |
| `references/project-schema.md` | project.yaml结构 |
| `references/lifecycle.md` | 生命周期状态机 |
| `references/methodology-*.md` | 各方法论 |
| `references/phases/*.md` | 阶段模块 |
| `references/templates-index.md` | 模板库索引 |

---

_PM Master v2 · 让项目管理真正"强制执行"。_
