# PM Master v1.3.6 → v2.0.0 迁移指南

## 概述

v2.0.0 是一次**架构性重构**，目标是从"参考手册式SKILL"转变为"强制执行手册式SKILL"。
大部分脚本和模板保持不变，主要变化在 SKILL.md 结构、Sub-Agent 协议、和新增的执行驱动脚本。

---

## 变更清单

### 1. SKILL.md 重构（核心变更）

| 方面 | v1.3.6 | v2.0.0 |
|------|--------|--------|
| 行数 | ~201行 | ~90行 |
| 结构 | 编排+参考资料混合 | 纯强制执行指令 |
| 规则表述 | "建议/推荐/按需" | "必须/禁止/否则阻断" |
| 工作流 | 6步建议性流程 | 6步强制性流程+checkpoint |

**迁移动作**：替换 SKILL.md 为 v2 版本，旧版本备份为 SKILL.v1.md。

### 2. 新增文件

| 文件 | 用途 |
|------|------|
| `scripts/execution_driver.py` | 执行期驱动脚本，弥补规划→执行的断层 |
| `scripts/subagent_check.py` | 子Agent产出校验器 |
| `references/subagent-protocol.md` | 子Agent通信协议（JSON Schema） |

### 3. 修改文件

| 文件 | 变更 |
|------|------|
| `config.yaml` | 新增 execution/quality_gate/stage_gates/operational_control 配置块 |
| `references/project-schema.md` | 新增 _checkpoint 字段定义，schema_version升级为2 |

### 4. 保持不变的文件

以下文件可直接从 v1.3.6 复制使用，无需修改：
- 所有 `scripts/` 下脚本（除新增的2个外）
- 所有 `templates/` 下模板
- 所有 `references/methodology-*.md`
- 所有 `references/phases/*.md`
- `references/agents.md`, `references/expert-roles.md`, `references/activity-expert-map.md`
- `references/lifecycle.md`, `references/orchestration.md`
- `references/hybrid_playbook.md`, `references/program-management.md`
- `references/risk-matrix.md`, `references/metrics.md`, `references/templates-index.md`
- `examples/sample_project.yaml`

### 5. 可删除文件

| 文件 | 原因 |
|------|------|
| `references/usage.md` | 与 README.md 高度重叠，v2 中不再需要 |
| `README.en.md` | 可保留但不再强制同步 |
| `CHANGELOG.md` (v1.x) | 保留为历史记录，新建 v2 CHANGELOG |

---

## 向后兼容性

- **project.yaml 兼容**：v1.3.6 的 project.yaml 可在 v2.0.0 中使用，schema_version 自动升级
- **模板兼容**：所有 v1.3.6 模板在 v2.0.0 中完全兼容
- **脚本兼容**：所有 v1.3.6 脚本在 v2.0.0 中完全兼容

---

## 建议迁移步骤

1. 备份当前 pm-master 目录
2. 替换 SKILL.md 为 v2 版本
3. 复制新增文件到对应目录
4. 更新 config.yaml
5. 删除 usage.md
6. 更新 _user_meta.json 版本号为 2.0.0
7. 测试：用"启动一个敏捷项目"验证新流程
