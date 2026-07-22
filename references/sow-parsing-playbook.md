# SOW / Contract Parsing Playbook（基础布局加固）

> **定位**：解析任何「合同 / 意向书 / SOW / 工作说明书」是项目群的基础布局。
> 此步骤若粗放（套用泛化阶段、漏掉商业结构），后续排期、计费、风险全部失准。
> 本 Playbook 把「专家级理解」固化为**可重复、可校验的流水线**，适配所有合同类型与所有方法论。

---

## 0. 适用范围

- **合同类型**：固定费率 SOW、T&M（工时上限）合同、混合（固定+里程碑+T&M）、意向书(LOI)、框架协议、分包合同。
- **方法论**：waterfall（阶段/Wave）、agile（Epic/Sprint/Release）、T&M（工时上限包）、hybrid。
- **层级**：单项目（project）与项目群（program，含多 SOW 子项目）均适用。

本 Playbook 不依赖任何具体客户/项目；所有项目专属信息都来自输入的**理解记录(spec)**。

---

## 1. 可靠性循环（a + c）

为「确保可靠」，解析走两条输入通道，二者互补：

- **(a) 文本抽取**：把 SOW PDF 文本 dump 为 `.txt`（或粘贴原文）喂给解析者。逐字读取**计费/交付、范围边界、进入条件、假设**四节——禁止凭印象推断。
- **(c) 引导式 Q&A**：当文本含糊（金额币种、Wave 数量、进入条件、角色归属）时，解析者用 `render_ui`/直问向用户澄清，**不臆测**。

产物是结构化的**理解记录（spec，JSON）**，再交给 `parse_sow.py` 生成 WBS。**WBS 自动写入 `project.yaml`，无需人工审批**——因为理解记录已通过 (a)+(c) 双重确认，人为审批只是重复。

---

## 2. 专家级理解链路（CoT + Critic）

解析者拿到文本后，**必须**执行以下思维链，禁止跳步：

1. **商业结构优先**：逐字提取「<交付物> post sign-off / 完工证书 / 验收」类事件及其费用。每一个都是**计费里程碑**候选。
2. **范围边界**：明确 in-scope / out-of-scope、逻辑 vs 物理、是否含 ETL 转换规则、语义层比例、归档/培训等特殊项。
3. **进入条件 / 数据就绪门**：SME 可用性、真实数据、接口文档、基础设施就绪——这些是最大的返工风险，必须成为关键路径上的**显式前置包**。
4. **假设即变更触发**：把「≤N 源表 / M 核心表 / 角色上限」写为 `raid.assumptions`，超界即走 CCB 变更单。
5. **Wave / 工作流分解**：把每个计费里程碑映射到一个工作流（Wave / Phase / Epic），工作流内自含「分析→设计→构建→映射→签字」活动。
6. **Critic 自审**（写完 spec 前必做，且落盘后须运行 `scripts/critic_review.py --strict` 通过）：
   - 是否漏了某个计费事件？（缺里程碑 = 计划不可测）
   - 排期是否只铺了前几周，没覆盖全部 Wave？（= 初级水平）
   - 叶子包是否都 ≤10 人天（**双周 fortnight 颗粒度**，见 control.leaf_granularity）？（否则控制门硬失败）
   - 进入条件是否显式成了前置包（entry_gate）？
   - **6 因素拆解纪律**（scope / milestone / payment / assumptions / constraints / dependencies）必须全部可追溯：
     每叶子须有 deliverable/scope 且归属某 milestone（milestone_ref）；每固定费率 SOW 有计费里程碑并挂在 sow_map 支付行；
     raid.assumptions 须含可量化边界（≤N 源表/M 核心表）以便 CCB 触发；外部前置约束须有 entry_gate 叶子；依赖网络连通无孤立包。
   - 落盘后须置 `decomposition.critic_passed: true`（consistency_check 在规划期会校验此标志，缺则致命）。

---

## 3. 理解记录（spec）Schema

`parse_sow.py --spec sow1.spec.json` 接受的 JSON：

```json
{
  "sow": "SOW1",
  "name": "Data Modelling & Engineering",
  "methodology": "waterfall",            // waterfall | agile | tm | hybrid
  "objective": "...",
  "scope": "...",
  "out_of_scope": "...",
  "assumptions": ["≤1600 源表...", "..."],
  "roles": ["ba", "solution-architect", "etl-engineer", "domain-sme"],
  "entry_gates": [
    {"id": "SOW1.0", "name": "源就绪门", "acceptance": "...", "role": "ba",
     "duration_days": 10, "estimate": 8, "dependsOn": ["SOW9"]}
  ],
  "waves": [
    {
      "id": "SOW1.W1", "name": "Wave 1 — 源集1",
      "billing": {"event": "Wave 1 Design Document post sign-off", "fee": 11645092,
                  "currency": "INR", "fee_type": "fixed"},
      "leaves": [
        {"id": "SOW1.W1.1", "name": "源系统识别与需求剖析", "role": "ba",
         "duration_days": 8, "estimate": 6, "acceptance": "..."},
        {"id": "SOW1.W1.2a", "name": "逻辑模型 FSDM", "role": "solution-architect",
         "duration_days": 8, "estimate": 6, "acceptance": "..."}
      ]
    }
  ],
  "deliverables_non_billing": [
    {"id": "SOW1.AR", "name": "冷数据归档设计",
     "billing": {"event": "Data Archival Design Document sign-off", "fee": 0, "fee_type": "none"},
     "leaves": [ {"id": "SOW1.AR.1a", "name": "...", "role": "nos-architect",
                  "duration_days": 9, "estimate": 7, "acceptance": "..."} ]}
  ]
}
```

字段规则：
- `fee_type`：`fixed`（固定费率，fee>0 → 计费里程碑）| `tm`（工时上限，包带 `billing.cap`，里程碑为交付签字非固定费）| `none`（纯交付物，fee=0）。
- `waves[].leaves[].estimate` 必填且 **>0 且 ≤10 人天**（控制门硬阈值）。`duration_days` 可选（用于排期；缺省=estimate）。
- 未显式给 `dependsOn` 时，脚本按默认链生成：entry_gate → Wave1 → Wave1 叶链 → W1 里程碑 → Wave2 …；非计费交付物依赖首个 entry_gate，其内部叶链到交付里程碑。
- summary / milestone 包的 `estimate` 由脚本**自底向上累计**子项，无需手写。

---

## 4. 方法论变体

| 方法论 | 工作流命名 | 计费里程碑来源 | 叶子包含义 |
|--------|-----------|---------------|-----------|
| waterfall | Wave / Phase | 设计文档/完工证书签字 | ≤10人天领域活动 |
| agile | Epic / Release | Sprint/Release 目标达成 | ≤10人天 Story/Sprint 任务 |
| tm | 工时上限包 | 阶段验收（非固定费） | ≤10人天工时桶，estimate=cap 内 |
| hybrid | Wave + 迭代 | 固定里程碑 + 迭代验收 | 混合 |

`parse_sow.py` 只忠实渲染 spec；方法论决定**解析者如何切分 waves/leaves**，不改变脚本逻辑。

---

## 5. 生成与校验

```bash
# 1) 导出空白 spec 模板
python3 parse_sow.py --emit-spec-template > sow1.spec.json

# 2) （解析者填 spec：来自文本抽取 + Q&A）

# 3) 生成并自动写入 project.yaml
python3 parse_sow.py --project program/project.yaml --spec sow1.spec.json

# 4) 干跑（只打印将要写入的包，不落盘）
python3 parse_sow.py --project program/project.yaml --spec sow1.spec.json --dry-run
```

脚本行为：
- 删除 `project.yaml` 中该 SOW 的旧子树（`id == SOWn` 或 `id 以 "SOWn." 开头`），再追加新包 → **幂等可重跑**。
- 累计 summary/milestone 估算；默认依赖链保证可正向排程。
- 在 `sow_map` 写入/更新该 SOW 的 `fee` / `fee_type` / `methodology` / `status`。
- 末尾自动跑 `consistency_check.py`；若固定费率 SOW 却无计费里程碑，一致性门**致命失败**（见下）。

---

## 6. 基础布局一致性门（consistency_check 加固）

新增规则（控制级，致命）：
- **计费里程碑完整性**：`sow_map` 中任一 SOW 若 `fee_type: fixed` 或任一子包 `billing.fee_type=='fixed' 且 fee>0`，则该 SOW 子树内**必须存在 ≥1 个 `milestone: true` 且 `billing.fee_type=='fixed'` 的包**，否则阻断。
- **方法论一致性**：SOW summary 包的 `methodology`（若在 spec 提供）须与 `project.methodology` 兼容（program=waterfall 时子项目可为 waterfall/agile/hybrid；不允许凭空调换）。
- 既有规则（叶子包 ≤10 人天、估算强制、依赖完整）继续生效。

> 这些门禁保证：任何「基础布局」只要写入，就**必然**含计费里程碑、细粒度叶子、完整依赖——从机制上杜绝初级计划。

## 7. 排期联动（Pillar 2 + 4）

基础布局解析后，排期阶段须保证「收款节奏 = 交付节奏」，杜绝“铺了任务却没把收费事件连到排期”。

- **Pillar 2 · 里程碑↔活动归集**：`parse_sow.py` 在生成每片 Wave 时，自动给其下所有叶子置 `milestone_ref: <WAVE>.M`（每叶子显式归属其结账里程碑）。`build_schedule.py` 据此渲染「Milestone Coverage」段，列出每个里程碑下直接归属的活动；一个支付里程碑可对应多个活动。
- **Pillar 4 · 支付里程碑↔排期联动**：`parse_sow.py` 自动给每计费里程碑置 `billing.payment_id: {SOW}-P{n}`（n=该片在 spec.waves 中的 1-based 序号）。`build_schedule.py` 渲染「Payment Linkage」段，把每条固定费率支付行 → 其里程碑 → 排期日 vs 合同 `due_date` 对齐，状态：
  - `linked`：排期日 ≤ 合同 due_date（一致）
  - `drift`：排期日晚于合同 due（须纠偏或走变更单）
  - `no-due`：合同未填 due_date（须补合同日期）
- **一致性门禁（6d，仅规划期致命）**：
  - **6d-1 里程碑覆盖缺口**：任一叶子既无 `milestone_ref`、其依赖末端也不落在任何里程碑 → 致命。
  - **6d-2 支付↔里程碑缺失**：`sow_map`/`program.sows` 中任一固定费率支付行（fee>0），其 SOW 子树内却无 `milestone + billing.fee_type=fixed` 包 → 致命。
  - **6d-3 支付顺序非单调**：同一 SOW 的计费里程碑排期日须升序（付款节奏与交付节奏同向）→ 否则致命。
- 运营期（已冻结，如示例客户）自动跳过 6d，避免击穿已基线化项目。
