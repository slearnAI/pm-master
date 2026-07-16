# project.yaml 数据契约（单一事实源）

`project.yaml` 是 PM Master 的**单一事实源（Single Source of Truth）**：主控 Agent 与所有子 Agent
都通过它读写，保证状态一致、跨会话连续。本文件定义其**完整字段结构、必填约定、初始化行为**，
以及**子 Agent 拿到不完整 yaml 时如何处理**。

> 完整可运行样例见 `examples/sample_project.yaml`；字段键契约（渲染所需数据键）见 `references/templates-index.md`。

---

## 1. 顶层结构（全字段）

```yaml
schema_version: 1                       # int，固定 1
project:
  id: pay-refactor                      # slug，唯一
  name: 支付重构                         # 显示名
  type: project                         # project | program
  methodology: agile                    # waterfall | agile | iteration | hybrid
  framework: scrum                      # scrum | kanban | null（非 agile 为 null）
  phase: 启动                           # 项目: 启动/规划/执行/监控/收尾
                                        # 项目群: 组合定义/组合交付/组合收尾
  status: 规划中
  lifecycle_state: planning             # planning|review|baselined|operational|closed（状态机，见 lifecycle.md §5）
  baselined_on: null                    # 基线化日期（baseline.py 写入）
  domain: payments                      # 领域标签，用于专家调度特化（可选）
  product: 支付清结算                     # 产品名，专家调度特化兜底（可选）
  created: 2026-08-01
  start_date: null                      # ISO，规划阶段可空
  target_end: null                      # ISO
  objectives: []                        # 目标清单
  scope: ''                             # 范围描述
  out_of_scope: ''                      # 排除范围
  sponsor: ''                           # 发起人（质量门强制）
  pm: ''                                # 项目经理（质量门强制）
  team: []                              # 成员列表
governance:
  stage_gates: []                       # 阶段门清单
  cadence: ''                           # 评审/汇报节奏
artifacts: {}                           # key -> 相对项目根的文件路径（产物索引）
raid:
  risks: []                             # 风险（须 owner/mitigation/5×5）
  assumptions: []
  issues: []                            # 问题（须 owner/due）
  dependencies: []                      # 依赖（须 from/to）
metrics:
  evm: {}                               # { pv, bac, ev, ac }（执行期建立基线）
  burndown: []                          # 敏捷/迭代燃尽点
wbs: []                                 # 工作分解（每行须 estimate>0、role、domain；waterfall/hybrid 须依赖网络）
milestones: []                          # 里程碑（id/name/date/owner/status）
actuals: {}                             # 运营期实际进展：{ ev, ac, as_of, wbs_progress{} }
control: {}                             # 运营控制：{ cadence, thresholds{}, recipients[] }
baseline: null                          # 基线指针（baseline.py 写入）：{ file, on, by }
program: null                          # 仅 type=program：{ projects[], dependencies[], benefits[] }
```

---

## 2. 必填与质量门约束

`consistency_check.py`（控制级，exit 1 = 阻断交付）强制以下项：

| 字段 | 约束 | 阶段 |
|------|------|------|
| `project.pm` / `project.sponsor` | 非空 | 任意 |
| `raid.risks[].owner` / `.mitigation` | 每条风险须有 | 任意 |
| `raid.risks[].likelihood/impact` | 1–5 数值；`score=likelihood×impact`；`severity` 与色带一致 | 任意 |
| `raid.issues[].owner` / `.due` | 每条问题须有 | 任意 |
| `raid.dependencies[].from/to` | 每条依赖须有 | 任意 |
| `wbs[].estimate` | 数值且 >0（不允许 `—`/空/非数字） | 任意 |
| `wbs` 依赖网络 | waterfall/hybrid 多行须形成依赖（否则无法算关键路径） | 任意 |
| `metrics.evm.{pv,bac,ev,ac}` | 执行/监控/收尾阶段须建 EVM 基线 | 执行/监控/收尾 |
| `baseline.file` | waterfall/hybrid 进入执行前须基线化 | 执行/监控/收尾 |
| 微层计划 | hybrid 须至少 1 个 sprint/backlog/iteration | 任意 |
| `program.benefits[].owner` | 每条收益须有责任人 | 项目群 |

> 未知字段填 `（待定）` 并标注，避免一致性校验失败；交付前补全。

---

## 3. 初始化行为

- **首次**：`init_project.py "<名称>" --type <project|program> --methodology <...> [--framework scrum|kanban] [--domain <领域> --product <产品>]`
  生成完整骨架（含第 1 节全部键，默认值见上）+ 标准目录 `docs/ plans/ risks/ reports/ artifacts/`。
  若 `<slug>/project.yaml` 已存在则**跳过**（不覆盖）。
- **子 Agent / 续会话**：用 `project_state.py` 读写：
  `get <key>` / `set <key> <value>` / `exists` / `show` / `init <name> [--type --methodology --framework]`。
  所有读写都落在同一份 `project.yaml`，保证跨 Agent / 跨会话连续。

---

## 4. 子 Agent 拿到不完整 yaml 怎么办

1. **文件不存在** → 先 `init_project.py`（或 `project_state.py init`）建骨架，再继续。
2. **缺必填字段**（如 `pm`/`sponsor` 空）→ 暂填 `（待定）`，记入回报让主控补全；**不要**为了过校验而编造。
3. **缺 `wbs`/`artifacts` 等块** → 直接按第 1 节结构补写对应键（脚本对此有容错，如 `rollup_program_wbs.py` 会在缺 `wbs:` 块时自动创建）。
4. **字段类型不符**（如 estimate 写成 `"—"`）→ 按第 2 节约束修正为数值，或标 `（待定）` 并告警。
5. **只读不改**职责冲突 → 子 Agent 只写自己负责的产物与 `artifacts.<key>`，不碰他人文件；冲突由主控聚合时解决。

> 黄金法则：**任何产物都回写 `artifacts` 索引 + 更新 `project.yaml`**，绝不只在对话里给文字。
