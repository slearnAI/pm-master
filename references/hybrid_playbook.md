# 混合交付实操手册（Hybrid Playbook）

把"混合"从一句口号落成可执行的节奏。适用 `methodology=hybrid`：宏层用阶段门/路线图
（waterfall 风格）控投决与合规，微层用 Sprint / 迭代（agile / iteration 风格）做增量交付。

## 1. 两个图层（Layers）

| 图层 | 目的 | 主要工件 | 节奏 |
|------|------|----------|------|
| **宏层 Macro** | 阶段门投决、组合对齐、对外合规 | wbs（阶段/波次）、stage_gate_review、hybrid_governance | 低频、强（阶段末） |
| **微层 Micro** | 增量交付、快速反馈、内部敏捷 | sprint_plan / product_backlog / iteration_plan、burndown、definition_of_done | 高频、轻（1–4 周） |

> 边界必须显式写在 `hybrid_governance.md`：哪部分走宏、哪部分走微、门在哪、谁决策。

## 2. 节奏（Cadence）

- **宏节奏**：每个阶段末开阶段门评审（stage_gate_review），checklist 全绿才放行下一阶段。
- **微节奏**：Sprint / 迭代固定时长（建议 2 周），含计划会、每日站会、评审会、回顾会。
- **对齐点（Alignment Review）**：在每个宏里程碑（阶段门）之前设一次对齐评审，核对微层
  增量是否满足该门的准入准则（exit criteria）。未过对齐评审，不得进阶段门。

## 3. 微层计划解剖（Wave / Sprint Anatomy）

以"波次(Wave) + Sprint"为例：

```
阶段门 G0 ── Wave 1 (宏: 范围/目标)
              ├─ Sprint 1  (微: 增量a)
              ├─ Sprint 2  (微: 增量b)
              └─ 波次出口评审 (Wave Exit Gate) ── 满足 G1 准入
阶段门 G1 ── Wave 2 ...
```

- **每个 Wave = 一个宏工作包（WBS 行）**；其下至少挂 **1 个 Sprint / 迭代计划**（微层）。
- 微层计划必须含：目标(goal)、承诺(commitment)、任务清单(带估算)、DoD。
- **强制**：每个混合项目/组件至少具备一个微层计划；否则一致性校验阻断交付。

## 4. 出口准则（Exit Criteria）与 准入准则（Entry Criteria）

- **波次/阶段出口**：交付物齐备 + DoD 满足 + 关键风险已缓解 + 指标达标（如 SPI≥0.95）。
- **下一阶段准入**：上游依赖就绪（如真实数据/资源到位）+ 上游门结论为"通过/有条件通过"。
- 出口/准入清单写入对应 `stage_gate_review.checklist` 与 `wbs` 的 `acceptance`(DoD) 列。

## 5. 对齐评审（Alignment Review）检查单

- [ ] 微层已完成增量是否覆盖本阶段门要求的范围？
- [ ] 增量质量是否达 DoD？是否通过波次出口评审？
- [ ] 跨层依赖（宏↔微、组件↔组件）是否阻塞？阻塞项是否升级？
- [ ] EVM / 速率指标是否健康（CPI/SPI≥0.95）？偏差是否在容差内？
- [ ] 重大变更是否走 change_log / CCB？

## 6. 变更控制（Change Control）

混合项目变化快，必须有正式变更通道：
- 任何范围/排期/资源变更 → 提 `change_request`，记录影响（范围/进度/成本/风险）。
- CCB（变更控制委员会）评审 → 结论写入 `change_log`。
- 阶段门结论、波次出口评审结论一并纳入 `change_log` 追溯。

## 7. 一致性校验要点（hybrid）

- 必须存在微层计划（sprint / backlog / iteration）→ 否则阻断。
- 建议具备 `change_log`（CCB）→ 告警。
- 宏层 wbs 须形成依赖网络（dependsOn）→ 否则阻断。
- 进入执行/监控阶段须建 EVM 基线并跑 `evm.py` → 否则阻断。

> 参见 `methodology-hybrid.md`（形态与工件）与 `templates-index.md`（模板清单）。
