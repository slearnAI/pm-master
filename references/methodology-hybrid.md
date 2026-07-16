# 方法论 · Hybrid（混合）

## 适用场景
单一纯方法论不够用时：大型系统里**硬件走瀑布、软件走敏捷**；或**对外阶段门合规、
对内敏捷交付**；或**组合层 waterfall 路线图 + 组件层 sprint**。混合不是"随便混"，而是
"在清晰的边界上分层"。

## 三种常见形态

| 形态 | 宏层（Macro） | 微层（Micro） | 治理重点 |
|------|---------------|---------------|----------|
| 宏瀑布 + 微敏捷 | 阶段门 / 路线图 | 组件内 Sprint | 门评审 + 增量演示 |
| 硬件瀑布 + 软件敏捷 | 硬件串行交付 | 软件持续迭代 | 接口/依赖对齐 |
| 组合瀑布 + 组件敏捷 | 组合路线图 | 各项目自选框架 | 依赖、收益、协同 |

## 核心工件（混合专属模板）
- `templates/hybrid/hybrid_governance.md`：治理地图——哪些部分用哪种方法论、门在哪、谁决策
- `templates/hybrid/macro_micro_map.md`：宏微映射——宏里程碑 ↔ 微迭代对应关系

> 其余工件按所落方法论取用：宏层用 waterfall/*，微层用 agile/* 或 iteration/*。

## 实操要求（强制，见 references/hybrid_playbook.md）
1. **每个宏工作流（Wave / 阶段）至少挂 1 个微层计划**：sprint_plan / product_backlog / iteration_plan。
   一致性校验（`consistency_check.py`）会因此阻断无微计划的混合项目。
2. **边界与门必须显式**：`hybrid_governance.md` 写清哪部分走宏、哪部分走微、门在哪、谁决策。
3. **对齐评审**：每个阶段门前设对齐评审，核对微层增量是否满足门准入（playbook §5）。
4. **变更控制**：混合项目须有 `change_log` + CCB（playbook §6），范围/排期/资源变更走正式通道。
5. **指标合并看板**：组合层 EVM（宏）+ 速率/燃尽（微）并入 `portfolio_dashboard`。

## 节奏（cadence）
- 宏层：阶段门 / 路线图评审（低频、强）
- 微层：Sprint / 迭代节奏（高频、轻）
- 对齐点：宏里程碑前设"对齐评审"，核对微层增量是否满足门准入。

## 关键指标
- 组合层：EVM（宏）+ 速率/燃尽（微）合并看板（program/portfolio_dashboard）
- 依赖阻塞数（hybrid_governance 中跨层依赖）

## 注意事项
- 必须在 `hybrid_governance.md` 里**显式写清边界与门**，否则混合会变混乱。
- `project.yaml.methodology = hybrid`，`framework` 可空；治理地图是必产出。
- 跨层依赖是最大风险源，进 `raid.dependencies` 并上依赖图（program/dependency_map 思路）。
