# Changelog · PM Master v2

## 2.0.0 (2026-07-19)

### 架构性重构：从"参考手册"到"强制执行手册"

**核心问题诊断**：v1.3.6 在多次迭代中积累了201行SKILL.md、14个脚本、12个references、35个模板——功能全面但输出不稳定。根因分析见审查报告。

### 重大变更

#### SKILL.md 重构
- 从201行压缩到~90行，移除所有参考资料到references
- 所有规则从"建议/推荐"改为"必须/禁止/否则阻断"
- 8条核心铁律前置，不可违反
- 工作流每步增加校验点
- 意图→产物路由表精简

#### Sub-Agent 通信协议（新增）
- `references/subagent-protocol.md`：定义JSON Schema回报格式
- `scripts/subagent_check.py`：子Agent产出自动校验
- 子Agent行为规范：必须做的事/禁止做的事/异常处理

#### 执行期脚本补齐（新增）
- `scripts/execution_driver.py`：执行驱动引擎
  - 读取WBS状态，生成可执行工作包清单
  - 追踪Sprint/迭代进度
  - 自动触发control_engine巡检
  - 支持JSON输出

#### Agent层状态机锁（新增）
- `project.yaml` 新增 `_checkpoint` 字段
- 追踪当前工作流步骤
- 非法跳步直接拒绝

#### 配置增强
- `config.yaml` 新增 execution/quality_gate/stage_gates/operational_control 配置块
- 分层配置更清晰

### 保持不变
- 所有 v1.3.6 脚本（render/render_docx/consistency_check/build_*/schedule_health/evm/baseline/control_engine/gate_engine/dispatch/comm_send/project_state）完全兼容
- 所有 35 个模板完全兼容
- 所有方法论 references 完全兼容
- project.yaml 核心结构兼容（新增字段可选）

### 移除
- `references/usage.md`（与README重叠，不再需要）
