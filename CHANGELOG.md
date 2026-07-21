# Changelog · PM Master

## 2.2.9 (2026-07-21)

### 运营期交付物护栏（OAG, Operational Artifact Guardrail）— 新增可执行护栏
- **根因**：LIC 项目在 operational 阶段修改了 `project.yaml`（RAID/EVM）却未重渲染对应交付物，导致
  `raid_log` / `risk_register` / `portfolio_dashboard` 落后于事实源数周，违反「每次动作须刷新交付物」护栏。
- **新增 `scripts/artifact_guard.py`**：内容哈希漂移检测。
  - 每次渲染（`build_subproject.py` / `rerender_docs.py`）向 `project.yaml.artifacts_meta.<key>`
    写入 `source_hash`（依赖数据切片 content-hash）+ `rendered_at`；
  - 校验时重算当前数据哈希并与 `source_hash` 比对：一致=OK，不一致=数据漂移（违规，exit 1）；
  - 存量文档（无 `source_hash`）仅给 ADVISORY，不误杀；
  - `--stamp <key>` 为手工/外部渲染文档记录 `source_hash`（如 `portfolio_dashboard`）。
- **集成**：
  - `control_engine.py` 周期巡检内置 OAG 检查，漂移即 RED 升级并 `exit 1`（可挂定时任务）；
  - `gate_engine.py` 收尾门（G3→4）将「交付物与事实源一致 (OAG)」列为**硬准则**，漂移则禁止收尾；
  - 每次阶段门评估均打印 OAG 状态。
- **文档化**：SKILL.md 新增 Iron Rule #12；`references/operation-model.md` §4.6、`references/phases/p2-execution.md`
  §7.1、`references/project-schema.md`（artifacts_meta）同步。
- 验证：LIC 程序 `artifact_guard.py --project` 在重渲染后 exit 0；临时改动 `raid` 后运行立即报
  `[数据漂移] raid_log`，证明可抓到当初漏掉的环节。

### Bug fix · 程序级 RAID 渲染读取 `raid.*` 而非顶层 `risks`
- **根因**：`build_subproject.py` / `rerender_docs.py` 读取 RAID 时取顶层 `data['risks']`，但程序层 RAID 存于
  `data['raid']['risks']`，导致 `rerender_docs.py` 静默跳过风险文档（`if not data.get('risks'): skip`），
  且 `risk_register.md` 被喂空列表；`consistency_check.py` 读 `raid.risks` 故门禁仍过，造成「门过但文档陈旧」的静默漂移。
- **修复**：两脚本的 risk 渲染路径回退到 `data['raid']['risks']`；`rerender_docs.py` 去掉 `KeyError` 隐患。
- 验证：LIC 程序 `risks/raid_log.md` / `risks/risk_register.md` 正确反映 R1–R12 / I1–I6；`rerender_docs.py` 不再跳过。

## 2.2.7 (2026-07-20)

### Bug fix · 子项目状态报告「5. Risks & Blockers」渲染为 JSON 字符串
- **根因**：`templates/common/status_report.md` 的 §5 用 `{{#each risks}} - {{this}}`，当 `risks` 为 dict 列表时 `{{this}}` 输出 `str(dict)` → 用户看到的 JSON 风格 blob。
- **修复**：§5 改为与风险登记册一致的**风险表格**（含 `sev_cell` 严重度色标 emoji：🟢绿/🟡黄/🟠橙/🔴红），列含 # / Severity / Risk ID / Description / Category / Owner / Mitigation / Status；`risks` 为空时显示「_No active risks or blockers this period._」。
- 验证：LIC 9 个子项目 status_report 全部重渲染，§5 无 JSON blob；空风险分支正常。三处安装 v2.2.7。

## 2.2.6 (2026-07-20)

### WBS/排期 Pillar 2+4 落盘修复 + 已冻结 LIC 的 Payment Linkage 实化
- **`build_schedule.py` 部分图保护（防压平回归）**：项目群/program 视图缺叶子细节（部分图）时，若包已有真实 start/end 且其排程偏移为 0，则**沿用既有日期**，不再把已基线化里程碑重置为起始日。修复了 2.2.5 末次 program 视图回写把 LIC 全部里程碑压平到 2026-08-01 的回归。
- **program / 单 SOW 视图默认只读**：`--level program` 与 `--sow` 不再回写 `wbs` 日期（仅 full 视图拥有完整叶子图才回写），保护已冻结 master 索引不被视图渲染改动。
- **Pillar 4 `due` 改为逐里程碑计算**：里程碑计费（fixed）且无独立合同日历 → 付款随该里程碑达成即到期（收款节奏=交付节奏），每行 `due` 默认取自身里程碑日；仅当 `sow_map`/`program.sows` 显式给 `due_date`（早于里程碑日）才可能出现 `drift`。修复了 SOW 级 `due` 泄漏到后续里程碑导致误报 30 条 drift 的 bug。
- **LIC 元数据回填（非破坏性）**：为 LIC 37 个既有固定费率里程碑补 `billing.payment_id`（{SOW}-P{n}），未改任何日期/BAC。回填后 `plans/schedule_program_gantt.md` 的 Payment Linkage 段 37 行全部 `linked`（合同即“签字/完工触发付款”），master 未被改动，consistency/critic 仍 exit 0。
- 验证：LIC（operational）不击穿；规划期显式 late `due_date` 仍触发 `drift`（exit 1 由 6d 门禁）。三处安装 v2.2.6。

## 2.2.5 (2026-07-20)

### WBS/排期 Pillar 2（里程碑↔活动归集）+ Pillar 4（支付里程碑↔排期联动）
- **Pillar 2**：`build_schedule.py` 新增 `milestone_coverage` 计算——每个里程碑下直接归属的活动集合（叶子 `milestone_ref` 或依赖末端落在里程碑），渲染到 `schedule_gantt.md` 的「Milestone Coverage」段。一个支付里程碑可对应多个活动。
- **`parse_sow.py` 自动标注**：每叶子自动置 `milestone_ref` 指向其 Wave 里程碑；每计费里程碑自动置 `billing.payment_id = {SOW}-P{n}`（Pillar 4 映射）。
- **Pillar 4**：`build_schedule.py` 新增 `payment_linkage` 计算——每条固定费率支付行 → 其里程碑 → 排期日 vs 合同 due_date；状态 linked/drift/no-due。渲染到「Payment Linkage」段。
- **`consistency_check.py` 6d 排期联动门禁（仅规划期致命，运营期跳过）**：6d-1 里程碑覆盖缺口（叶子未归属里程碑）、6d-2 支付↔里程碑缺失（固定费率 SOW 有支付行却无计费里程碑）、6d-3 支付顺序非单调（同一 SOW 计费里程碑排期日须升序）。
- 验证：LIC（operational）不击穿（consistency/critic 均 exit 0，Payment Linkage 段正常渲染真实 ₹ 金额）；规划期样例触发 6d 门禁。
- 安全沿用 Pillar 1 设计：所有新门禁仅在 planning_now（phase∈{启动,规划,''} 或 lifecycle∈{planning,review,baselined,None}）致命。

## 2.2.4 (2026-07-20)

### WBS 拆解纪律 Pillar 1（6 因素 + Critic 自审引擎）+ Pillar 3（双周 fortnight 颗粒度）
- **新增 `scripts/critic_review.py`（可执行 Critic 自审）**：把 `sow-parsing-playbook.md` 的散文 Critic 固化为 6 因素校验——scope 可追溯 / milestone 归属 / payment 挂支付行 / assumptions 可量化边界 / constraints 外部前置须 entry_gate / dependencies 连通。规划期致命（exit 1），运营期（已冻结，如 LIC）降级为提示不阻断。
- **`consistency_check.py` 新增 6c 拆解纪律门禁（仅规划/启动期致命）**：集成 `critic_review.py --strict` 结果 + 校验 `decomposition.critic_passed==true` + assumptions 可量化边界。运营期自动跳过，保护已冻结项目不被新门禁击穿。
- **Pillar 3**：`init_project.py` 默认 `control.leaf_granularity: fortnight` + `granularity_threshold: 10`（=10 工作人天，沿用既有默认但显式化），作为 waterfall/program 叶子包标准颗粒度。
- **`sow-parsing-playbook.md` §2.6** 重写：Critic 自审列出 6 因素清单，并要求落盘后运行 `critic_review.py --strict` 并置 `critic_passed=true`。
- 验证：LIC（operational）一致性 exit 0 / critic exit 0（不击穿）；规划期样例触发 7 项致命（scope/milestone/dependency/critic_passed/assumption-bound 等），exit 1。

## 2.2.3 (2026-07-20)

### P0/P1 拆细：方法无关骨架 + 联邦式事实源（SOW 解析驱动）
- **`references/phases/p0-p1-initiation-planning.md` 重构**：
  - 新增 §1.1 **P0/P1 逐步序列**，明确方法无关骨架：P0 不建 WBS，WBS 在 P1 由 P0.2 的 draft charter 派生。
  - **P0.0** 分类（project vs program）+ 设计 PM 团队（程序=master+各 SOW PM 子 Agent）。
  - **P0.1** 抽取 SOW → 结构化理解（spec JSON），套用 `sow-parsing-playbook.md`；program 下明确「先 init 各子项目，再回填 master 索引」，master 绝不持叶子（呼应 Iron Rule #11 / operation-model.md）。
  - **P0.2** 由 spec 生成基础产物：charter 仍 **draft**，估算基准作为 **charter 内章节**（Scope / Delivery milestones / Payment milestones / Assumptions / Constraints / Dependencies），非独立文档；RAID 从 SOW 假设/约束/依赖 **seed**（非 draft）。
  - **P1** dispatch 建 WBS（源自 draft charter）→ 排期 → 5×5 风险校准 → 一致性门 → baseline 冻结 → **charter 定稿** → G1→2 门禁。
  - §2 方法论适配表改造为「P0.2 估算基准形态 / P1 排期产物 / 基线冻结与否」，明确 agile/iteration 不冻结基线、纯 agile 支付章节标 "N/A — internal release cadence"。
  - §3 交付物清单标注 charter 为「P0 draft、P1 final」，估算基准=charter 内章节。
- 背景：用户要求把「P0 判定 program/project 并设计 PM 团队、从 SOW 抽取建事实源、估算基准入 charter、P1 完成规划」固化为技能级步骤，且与 operation-model 的自底向上一致。

## 2.2.2 (2026-07-20)

### 操作模型固化：自底向上编制 + 向上汇总（技能级铁律，非项目专属）
- **新增 `references/operation-model.md`**：将「计划在子项目层编制、状态/RAID/变更/进度在子项目层维护、程序层是只读脚本汇总的视图」固化为技能级默认操作模型。明确：程序 `actuals`/RAID/status 均为派生值，禁止手工编辑；要纠偏须改源子项目并重跑 `rollup_subprojects.py`（或单文件两层的 `rollup_program_wbs.py --derive-actuals`）。
- **SKILL.md / SKILL.en.md 新增 Iron Rule #11（Bottom-up authoring & rollup）**：计划/状态/RAID/变更控制在最低归属单元（SOW/子项目）编制，程序层为只读脚本汇总，不得作为手工并行的真相源。违反后果：治理漂移、虚假状态。
- **Program-specific Rules 第 6 条** 引用 Iron Rule #11，并明确 `rollup_subprojects.py`（跨文件）与 `rollup_program_wbs.py`（单文件两层）的分工。
- **`references/program-management.md`** Per-SOW Sub-Project 段落：指向 `operation-model.md`，新增「Rollup（程序=子项目的只读聚合）」小节，写明刷新程序视图的标准命令序列（rollup → control_engine），并强调派生字段禁手工编辑。
- 背景：LIC Datalake 程序（9 份 SOW）实测时，子项目拆分后若程序级 RAID/status 与子项目各维护一套会一周内漂移；此模型从机制上消除该反模式。

## 2.2.1 (2026-07-19)

### 排期引擎 3 个修复（SOW1 依赖失效 / mermaid 里程碑报错 / 汇总包时长=0）
- **`parse_sow.py` 依赖落盘修复**：`chain_leaves` 此前只改写 spec 字典，而叶子包在 `add_wave` 时已创建（当时 `dependsOn=[]`），导致真实依赖从未写入 `project.yaml` → `build_schedule` 正向排程所有任务 `ES=0`、开始日全部等于项目起始日。现改为直接写回 `byid` 里真实包对象，叶子依赖链真正生效。
- **`build_schedule.py` 汇总包不参与顺序工期**：WBS 汇总包（Wave/SOW 根）是容器，其 `estimate` 是子项累计值，若按 `dur` 参与正向排程会注入数十天「幽灵间隙」。现汇总包排程 `dur=0`，跨度仅用于显示（自底向上 rollup 出真实 start/end）。此前 SOW1 各 Wave 间出现 ~7 周空洞即源于此。
- **mermaid 里程碑语法修复**：甘特图里程碑行原只输出 `:milestone, start`，mermaid 旧版对缺 end 的里程碑报 `undefined.endTime`。现改为 `:milestone, start, end`（start==end）。同时甘特图跳过汇总包（不再误当作零宽里程碑渲染）。
- **叶子包工期回退**：叶子包仅有 `estimate` 无 `duration` 时，用 `estimate` 作为工期（此前为 0 导致被误判里程碑）。
- **program 级视图修复**：此前 program 视图只排程 SOW 根包，叶子被排除 → 汇总包跨度算不出、duration 全 0。现 program 视图排程时把所有 SOW 后代纳入（算出真实跨度并回写叶子日期），渲染时仅显示 `tier==program` 行 + 里程碑。SOW1 现显示 210 天（2026-08-01 → 2027-02-27），不再为 0。
- 端到端验证：SOW1 叶子依赖链生效、日期连续级联、mermaid 块无裸 `&`、program 表格/甘特均无 0 时长、一致性门禁 exit 0。

## 2.2.0 (2026-07-19)

### 基础布局加固：SOW/合同解析流水线（a + c 双通道）+ 计费里程碑门禁
- **新增 `references/sow-parsing-playbook.md`**：把「专家级理解」固化为可重复、方法论无关（waterfall/agile/T&M/hybrid）、合同类型无关（固定费率/T&M/混合/LOI）的解析 Playbook。核心：(a) 文本抽取 + (c) 引导式 Q&A 双通道生成「理解记录(spec, JSON)」，从源头杜绝泛化推断。
- **新增 `scripts/parse_sow.py`**：理解记录(spec) → 自动写入 `project.yaml` 的 WBS 包（幂等可重跑，自底向上累计估算，默认依赖链保证可正向排程，自动维护 `sow_map` 的 fee/fee_type/methodology/status）。因 spec 已通过 (a)+(c) 双重确认，WBS 落盘无需人工审批。
- **`consistency_check.py` 新增「计费里程碑完整性」基础布局门禁（致命）**：`sow_map` 中任一固定费率 SOW 或其子树含 `billing.fee_type=='fixed' && fee>0` 的包，必须存在 ≥1 个 `milestone:true && billing.fee_type=='fixed' && fee>0` 的包，否则一致性门阻断交付。从机制上保证：任何基础布局都必然含计费里程碑、细粒度叶子、完整依赖——杜绝初级计划。
- **端到端验证**：dry-run/实跑/依赖链（entry_gate→Wave→叶链→计费里程碑→下一 Wave）、正向门禁（真实 SOW1 通过）、负向门禁（缺里程碑的固定费率 SOW 致命失败）全部通过。

## 2.1.8 (2026-07-19)

### Bugfix: mermaid gantt 渲染 `&` 导致 "undefined.endTime" 崩溃
- **根因**：`_gantt_name()` 只转义 `:` 为全角 `：`，未处理 `&`。mermaid gantt 中 `&` 是多任务同行运算符，任务名里的 ASCII `&`（如 "SOW1 Data Modelling **&** Engineering"）会被解析为行延续符，使后续 token 变成无日期任务 → 报错 `Cannot read properties of undefined (reading "endTime")`。
- **修复**：`_gantt_name()` 额外把 ASCII `&` 换成全角 `＆`(U+FF06)（视觉仍是 &，但不触发运算符解析）。`SOW6 SME Support (T&M)` 同理已覆盖（程序级 gantt 用 graph TD 引号标签原本安全，但 SOW 级 gantt 已修复）。
- **验证**：重新生成的 `plans/SOW1/schedule_gantt.md` 甘特块已无裸 ASCII `&`（全为 `＆`），在 mermaid 解析器下可正常渲染。
- 同步运行副本 `~/.workbuddy/skills/pm-master/scripts/render.py`。
## 2.1.7 (2026-07-19)

### SOW 解析深度修复（用户评审 SOW1 子项目后：计划仅显示首双周、缺 Wave 结构与计费里程碑）
- **根因**：此前 SOW1 计划是「初级水平」——套用一次性泛化 4 阶段瀑布，未读 SOW 真实 **4-Wave 商业结构** 与 **5 个设计文档签字里程碑**（其中 4 个为计费事件 = ₹29.11M），排期只覆盖前 ~5 周。
- **专家级重做（CoT + 评审）**：先逐字提取 SOW 计费/交付节，把每个 "<Deliverable> post sign-off" 事件建模为 `milestone: true` + `billing:{event,fee_inr,currency,status}` 包；4 个 Wave 各为 summary 包（源分析→逻辑模型→物理模型+DDL→S2T映射→签字里程碑），并按商业节奏顺序排程（W1 2026-10-15 → W4 2027-04-28，全 ~9 个月）；NOS 归档设计为独立交付里程碑（fee_inr:0，标注非独立计费）。
- **叶子包 ≤10 人天**：逻辑/物理/S2T 拆为 ≤10 天领域专家桶（W1.2a FSDM / W1.2b FSAS / W1.3a Core DDL / W1.3b Semantic DDL …），满足控制门硬阈值；summary/milestone 用子项累计估算。
- **数据就绪门**：新增 `SOW1.0 源就绪门` 作为关键路径前置（SME+真实数据+接口文档），对应 SOW 最大返工风险。
- **子项目联动**：subprojects/sow1/project.yaml 补 `billing_milestones[]` 索引（M1–M5 含金额/日期/状态）与 4 项 Wave 级风险（含 S1-R4 计费里程碑延迟现金流风险）；RAID 依赖写回 SOW2/3/7 正确前置。
- **新增参考规范**：`references/program-management.md` 加「Billing-Milestone-Driven WBS Decomposition」专家约定（解析 SOW 必须先做链路思考+评审，再写 WBS）。
- **验证**：SOW1 排期覆盖 FN01→FN20（全 ~9 个月，非仅首双周）；甘特含 11 个里程碑（4 计费+1 交付+其他）；程序级一致性门 exit 0。
> 版本号与 `SKILL.md` 的 `metadata.version`、`_user_meta.json` 的 `version` 保持一致。

## 2.1.6 (2026-07-19)

### 两个架构性缺口补齐（用户评审 LIC SOW1 后提出）

**1. 子项目（per-SOW sub-project）层级**
- 每个 SOW 现在作为独立「子项目」维护，拥有自己的 `project.yaml`、RAID 日志、风险登记册、状态报告，由各 SOW 项目经理独立负责。
- `init_project.py` 新增 `--parent <program.yaml> --sow SOW1 --slug sow1`：在 `program/subprojects/<slug>/` 下建立独立骨架，并自动回写 `program.projects[]` 索引（id/sow/methodology/status/path）。
- 新增 `build_subproject.py`：从子项目 `project.yaml`（单一事实源）渲染 `risks/raid_log.md`、`risks/risk_register.md`、`reports/status_report.md`，并把产物路径写回 `artifacts`。
- 子项目通过 `parent: {project: '../../project.yaml', sow: SOW1}` 与父项目群保持血缘关联；跨 SOW 依赖写入各子项目 `raid.dependencies[]`。

**2. 双周（Fortnight）颗粒度 + 领域专家拆解**
- SOW1 叶子包由「4 个包 × 1 角色」重拆为 4 个阶段组（SOW1.1–1.4，summary）+ 8 个双周叶子包（1.1.1–4.2），每个 ≤6 天、分配独立领域角色（requirements-analyst / data-modeler / etl-mapping-analyst / nos-architect），可独立计费与验收。
- `build_schedule.py` 新增 `--granularity fortnight`：按 2 周桶分组，排期表新增「Fortnight Plan」节（FN01… 窗口 + 任务计数 + 工作包），甘特图按 `section FNxx` 分桶。
- `render.py` 新增 `eq` 辅助函数（`{{#if (eq granularity "fortnight")}}`）以支撑条件渲染；模板 `schedule_gantt.md` 新增双周分支。
- 修复：`build_sow_kickoff.py` 仅把 `tier=program` 汇总包识别为 SOW 级（避免阶段组重复开启动会）；`consistency_check.py` 孤儿包检查仅覆盖顶层 SOW（`^SOW\d+$`），不再误报阶段组。

**验证**：LIC SOW1 子项目建立并索引成功；fortnight 排期渲染（FN01–FN03 分桶、任务命名正确）；子项目 RAID/风险/状态渲染含严重度色标；程序级一致性门 exit 0。

## 2.1.3 (2026-07-19)

### 项目群章程（Program Charter）重构（用户 WorkBuddy 实测 docs/program_charter.md 反馈）
- **Program Architecture mermaid 修复**：用户渲染稿的 `subgraph DELIVERY` 内节点 `S6/S7` 指向 subgraph 自身（`S6 --> DELIVERY`）属非法 mermaid 语法。章程模板重写为数据驱动版，架构图改为 SOW6→CORE、SOW7 作为独立节点，不再自指 subgraph（已渲染验证合法）。
- **财务与商务模型（Financials & Commercial Model）费用捕获**：原渲染稿费用整列 `（待定）`。新增 `program.sows[]`（sow/workstream/model/billing/fee），章程「财务与商务模型」表改由 `program.sows[].fee` 驱动；未锁定时须填 `TBC — 原因`，禁止整表 `（待定）`。已把 LIC 实际项目数据写入 `project.yaml` 并重渲染，费用列呈现实值/TBC。
- **一致性门新增规则 7d**：`program.sows[].fee` 必填，空白/`（待定）`/TBD 即致命（未锁定写 `TBC — 原因` 放行）。`project-schema.md` / `program-management.md` 补 `sows[]` 与 `fee` 字段定义。
- 章程结构对齐用户预期：表头 + 架构图 + 商业论证/目标/范围/范围外/财务/治理门/关键风险/成功标准 + 合同边界节。

## 2.1.2 (2026-07-19)

### WorkBuddy 实测修复（用户现场 3 条反馈）
- **RAID 日志色标**：`templates/common/raid_log.md` 新增严重度/优先级色标列，风险按 `score` 自动推导 🟢🟡🟠🔴（缺 severity 也显示），问题按 `priority` 推导色标。`render.py` 新增 `sev_cell(severity, score)` / `sev_band(score)` 辅助（score 推导色带，未知不阻塞）。
- **风险登记册色标鲁棒化**：`risk_register.md` 改用 `sev_cell(this.severity, this.score)`，即便数据缺 `severity` 也按 `score` 显示色标（修复"没用色标"）。
- **项目群章程·合同金额**：合同总览表新增「合同金额(fee)」列；新增「商务模型与费用」节，把各合同 `fee` 汇总进财务边界，费用被捕获而非留空（待定）；`consistency_check` 合同/商务语义不变。
- **项目群章程·架构图**：新增「项目群架构（Program Architecture · mermaid graph TD）」节，呈现发起人→项目经理→治理委员会→组件组合结构（用户提供的数据无此图时仅出治理骨架）。

> 说明：用户反馈的 "Program Architecture mermaid 报错" 在 2.1.1 章程中并不存在对应节；本次新增了合规 mermaid 架构图。若你看到的是别的文件里的报错 mermaid，请贴出该块，我按原文修。

## 2.1.1 (2026-07-19)

### 补齐 v2.1.0 的四处生产级缺口（用户现场反馈）
- **#1 拆解自动回写 glue**：新增 `scripts/sync_wbs.py`——专家（人或子 Agent）把 SOW/领域包拆成叶子包后，用拆解补丁 YAML 一键 merge 回 `project.yaml.wbs`；自动挂父子（parent / id 前缀）、标 tier、校验叶子包必填 role/owner/estimate/dod/dependsOn（缺则致命、不写回），并置 `artifacts.wbs_dirty` 提示重渲染。
- **#2 WBS 分解树 mermaid**：`templates/waterfall/wbs.md` 新增「WBS 分解树（graph TD 层级/分解图）」，由 `build_wbs.py` 从 `wbs[].parent`（或 id 前缀）自动构造，汇总/里程碑包标 `▶`、叶子包标 role。与甘特图为同一事实源双视图。
- **#3 Program Charter 覆盖合同/Extract/SOW**：`program_charter.md` 新增「合同边界与分包」章（contracts / extracts / sow_map 三表）；`references/program-management.md` 补充对应数据模型与一致性约束（SOW 映射须对应 `tier:program` 汇总包、外包 Extract 须绑合同）。
- **#4 单一事实源防漂移**：`consistency_check.py` 新增规则 7c（项目群 SOW 映射 ↔ wbs 一致，漂移即致命）+ `wbs_dirty` 重渲染提醒；新增 `scripts/rerender_docs.py` 从 `project.yaml` 纯函数重渲染 wbs/risk_register/program_charter，文档 = 事实源 + 模板，杜绝内容漂移。

## 2.1.0 (2026-07-19)

### 合并重构：v1.3.6 强制框架 + v2.0.0 架构方向，修复 v2 死锁与纸面特性
- **修复 v2 P0 死锁**：恢复 v1.3.6 的「专家调度」工作流（SKILL.md 新增 Step 2.5），WBS 领域活动须由领域专家拆解并标注 `role`；一致性门禁对缺 `role`/超阈值领域活动默认致命，主控不得自拆绕过。
- **子 Agent 协议真实接线**：新增 `references/subagent-protocol.md`（JSON 回报契约）+ `scripts/subagent_check.py` 实际校验每个子 Agent 产出。
- **阶段门硬/软可配**：`gate_engine.py` 读 `config.stage_gates`，新增英文阶段别名（`--to execution/closeout` 等）便于英文包使用。
- **专家调度幂等**：`dispatch.py` 对已达标的包标 `done`，重跑归零 pending。
- **巡检落盘**：`control_engine.py` 写 `last_control_check`；`execution_driver.py` 读同一字段避免重复巡检。
- **阈值配置化**：`control_engine.py` 注入 `config.operational_control` 到 `data.control.thresholds`。
- **跨会话续跑**：`project_state.py` 增加 `migrate`/`checkpoint`，`schema_version=2` + `_checkpoint` 防跳步。
- **双语双包**：中文版（WorkBuddy，`SKILL.md`）+ 英文版（OpenClaw，`SKILL.en.md`）共用 `scripts/`/`templates/`/`references/`，经 `config.yaml.execution.subagent_mode` 切换后端。

## 1.3.6 (2026-07-18)

### 修复：项目群级排期 + SOW 子计划 + Mermaid 里程碑 + 组合看板色标
- **`build_schedule.py` 新增 `--level program` 与 `--sow <SOW_ID>` 两种视图（修复 #1/#2：缺项目群级排期；SOW 排期未归属 SOW 计划）**：
  - `--level program` → `plans/schedule_program_gantt.md`：仅里程碑级 SOW 汇总包（`tier: program`）+ 阶段里程碑，聚焦**项目群级规划**，不展开叶子（修复指导 a：项目群层级聚焦项目群规划）。
  - `--sow SOW1` → `plans/<sow>/schedule_gantt.md`：仅该 SOW 子树，作为「该 SOW 自己的子计划」，与 kick-off 同处一个子计划文件夹，**可独立执行、又通过 `project.name` + SOW id 与父项目保持关联**（修复指导 b：SOW kick-off 作为子项目，既关联又可独立执行）。
  - 默认 full 视图对 program 类型自动降级为 program 视图。
- **`build_sow_kickoff.py` 输出改为 `plans/<sow>/kickoff.md`**（原 `plans/kickoff/<sow>_kickoff.md`）：与 SOW 排期同处子计划文件夹，写回 `artifacts.sow_kickoff_<slug>` 与 `artifacts.sow_plan_<slug>`。
- **修复 Mermaid 甘特里程碑语法（修复 #3：`Invalid date:M1`）**：里程碑行改为 `name :milestone, <date>`（去掉误置于日期位的 id），非里程碑行保持 `name :<mid(id)>, <start>, <end>`。
- **`portfolio_dashboard.md` 健康度单元格加 `sev_icon` 色标图标（修复 #4）**：渲染 🟢🟡🔴，与图例一致。
- **OpenClaw 英文包对齐**：`build_schedule.py` / `build_sow_kickoff.py` 运行时输出（`view_label` / 提示 / 兜底值）全部英文化，与英文模板一致；`SKILL.md` / 阶段参考文档 / `templates-index.md` 同步三视图与 SOW 子计划路径。

## 1.3.5 (2026-07-17)

### 修复：WBS→排期交付物 + per-SOW 启动会 + 风险色标图标
- **新增 `scripts/build_schedule.py`（修复 #1：WBS 没变成排期计划）**：
  - 正向排程（forward pass）：以项目起始日 + 各任务工期 + 依赖(dependsOn) 推算每个任务起止日期；
  - 回写 `project.yaml` 的 `wbs[].start/end`（单一事实源，wbs.md 与 schedule_gantt.md 共用同一套日期）；
  - 基于 wbs 派生 `tasks` 并渲染 `templates/waterfall/schedule_gantt.md` → `plans/schedule_gantt.md`，写回 `artifacts.schedule_gantt`。这是 P0/P1 规划的**主要排期交付物**（waterfall/hybrid 规划期必跑）。
- **新增 `scripts/build_wbs.py`（修掉 `wbs.md` 对 `build_wbs.py` 的悬空依赖）**：按视图（full/program/component）过滤 + 按领域(domain)分组，渲染 `plans/wbs.md`；并修正 `wbs.md` 表体只遍历组、未遍历 `this.items` 导致表体为空的缺陷。
- **新增 per-SOW 启动会（修复 #2：SOW 级 kick-off 没产出工件）**：
  - 新增模板 `templates/common/sow_kickoff.md` 与 `scripts/build_sow_kickoff.py`；
  - 自动识别 SOW 级 summary 包（`summary: true` 或带子包的顶层包），为每个 SOW 产出 `plans/kickoff/<sow>_kickoff.md`（对齐范围/交付物/责任人/首批行动），写回 `artifacts.sow_kickoffs`。
- **风险登记册色标图标（修复 #3）**：
  - `scripts/render.py` 新增 `sev_icon()` / `risk_icon()` 助手（绿→🟢 / 黄→🟡 / 橙→🟠 / 红→🔴，兼容中英文 severity 与 low/medium/high/critical）；
  - `templates/common/risk_register.md` 的 5×5 矩阵、色带与严重度列均加回颜色 emoji 图标（字符作为兜底保留）。
- 同步更新 `SKILL.md` Step 4 / §4 / §5、`references/phases/p0-p1-initiation-planning.md`、`references/templates-index.md`；三个新脚本与模板、色标助手同步进 OpenClaw 纯英文包。

## 1.3.4 (2026-07-16)

### 修复：Mermaid 渲染稳定性 + SOW 级 WBS 强制专家拆解
- **Mermaid 渲染加固（`scripts/render.py`）**：
  - 新增 mermaid 安全辅助 `mid()` / `mlabel()` / `gname()`；原 `slug()` 改为复用 `mid()`（保留中文节点 ID，仅把空格/点号/非常规字符转为下划线，保证非空且不以数字开头）。
  - 主要修复：`slug()` 直接删点号曾把 `SOW1.1` 变成 `SOW11`，造成**重复/非法节点 ID → mermaid 报错**；空值曾生成空节点 id（非法）。现统一为合法、层级保留（如 `SOW1_1`）。
  - `mlabel()` 转义标签内双引号、折叠空白；`gname()` 额外把甘特任务名里的 `:` 转全角 `：`，避免破坏 `name :id` 分隔。
  - `join()` 对 `None` 回退为 `0`，避免 xychart 数组出现 `[1, , 3]` 而崩溃。
- **`render_docx.py` 优雅处理 mermaid**：python-docx 分支新增围栏代码块检测——`mermaid` 块优先用 `mmdc`（若已装）渲染成 PNG 嵌入，否则作为带标注的代码块输出，消除原先的乱码/报错。
- **6 个 mermaid 模板改用安全辅助**：`waterfall/wbs.md`、`waterfall/schedule_gantt.md`（gname+mid）、`program/dependency_map.md`、`hybrid/macro_micro_map.md`、`hybrid/hybrid_governance.md`（mid+mlabel）；`agile/burndown.md` 受益于 `join` 加固。
- **SOW 级 WBS 强制走专家拆解（`scripts/consistency_check.py` + `SKILL.md`）**：
  - 凡「领域活动缺 `role` 标签」或「领域活动 `estimate` 超 `control.granularity_threshold`（默认 10 人天）」→ **默认致命（exit 1 阻断交付）**，强制走 `dispatch.py` → 领域专家子 Agent 拆解，主控不得直接拆分绕过。
  - 非领域活动的超阈值仅保留为告警（通用颗粒度提示）；`program` 级 `summary` / `milestone` / `tier: program` 汇总行豁免（项目群颗粒度本就到里程碑级）。
  - `SKILL.md` Step 2.5 增加「禁止主控自拆（强制）」硬规则，§6 措辞改为默认致命；`references/activity-expert-map.md §5` 同步。
  - `test_gate_engine.py` 夹具 WBS 补 `role`（建模专家产出的叶子包），套件恢复 66/66 通过。

## 1.3.3 (2026-07-16)

### 英文文档与双语文档同步规则
- 新增英文版 `README.en.md`（与 OpenClaw 纯英文技能包同源生成），作为本技能英文说明文档。
- 确立「中文与英文双语文档同步」规则：每次技能变更须同步更新 `README.md`（中文）与 `README.en.md`（英文），并与 `SKILL.md` / `CHANGELOG.md` / 版本号保持一致（延续 v1.2.1 确立的「每次技能变更同步 README」规则）。
- 同步发布 OpenClaw 兼容的纯英文技能包（`pm-master-openclaw-v1.3.2.zip`）：整包译为英文（SKILL.md / README / references / templates / scripts 注释与文案 / config / 示例），内部中文阶段与状态常量（启动 / 规划 / 执行 / 监控 / 收尾 / 组合定义 / 组合交付 / 组合收尾）统一改为英文规范词，测试套件 `test_gate_engine.py` 同步改为英文断言并 66/66 通过。

## 1.3.2 (2026-07-16)

### 进一步脱敏（合规 · 消除法律风险）
- `scripts/rollup_program_wbs.py` 的内置示例映射进一步去标识化：
  - `COMPONENT_MAP`：剥离 SOW 组件 slug 的描述性后缀（`sow1-data-modelling` → `sow1`，…，`sow9-ts` → `sow9`，`external-pii` → `ext-pii`），仅保留编号标识。
  - `PHASE_NAME`：阶段别名由客户专属描述（Wave 1–4 基础建模 / 金融与协议 / FSAS 分析结构 / NOS 归档与集成）改为中性 `Stream 1–4` 命名，移除 FSAS / NOS / 金融与协议等客户系统/领域泄露。
  - 三处「某保险数据湖项目 / 保险数据湖」注释与告警文案统一改为「示例项目」，不再暴露真实行业与客户。
- `CHANGELOG.md`：将 1.1.0 中关于内置示例的语义描述「某保险数据湖」改为中性的「示例项目」。

> 说明：保留的 `Wave` / `保险数据湖` 命中（如 `references/methodology-hybrid.md`、`hybrid_playbook.md`、`expert-roles.md`）属**通用方法论/领域示例词汇**，非真实客户或厂商名，引擎路由与设计依赖之，故维持不变。

## 1.3.1 (2026-07-16)

### 脱敏（合规 · 消除法律风险）
- 全量扫描技能文件，移除真实客户名与厂商名等敏感信息，统一改为代号：
  - 真实保险行业客户名 → `客户A`（代号 `ALPHA`）；真实 MPP 数仓厂商名 → `MPP 数仓`（通用占位）；另一被点名的集成商经扫描确认本仓库**不存在**，无需处理。
  - `references/activity-expert-map.md`：`insurance-data-lake` 的示例项目由真实客户项目名改为 `客户A 数据湖（代号 ALPHA，MPP 数仓）`，角色中的厂商专属 ETL 工程师改为 `MPP 数仓 TPT/ETL 工程师`。
  - `scripts/dispatch.py`：专家角色标题中的厂商名改为 `MPP 数仓 TPT/ETL 工程师` / `MPP 数仓/平台工程师`。
  - `references/expert-roles.md`：技术栈示例改为 `MPP 数仓、云数仓`；领域特化改为 `MPP 数仓 → 批量加载（厂商 TPT/MLOAD 类工具）`。
- 经二次全仓扫描，真实客户名 / 厂商名已实现 **0 残留**；`examples/sample_project.yaml` 与 `rollup_program_wbs.py` 内置示例均为通用占位（无客户名），予以保留。
- README / SKILL / `_user_meta.json` 版本同步至 1.3.1（延续「每次技能变更同步 README」规则）。

## 1.3.0 (2026-07-16)

### operational 双轨并行（P2 执行 + P3 监控 多 Agent）
- **编排双轨**：进入 `operational` 后，执行轨（领域专家 Agent 持续交付）与监控轨（`monitoring-agent` 周期跑 `control_engine.py` 并回流升级项）**以多 Agent 并行**落地，共享 `project.yaml`+`baselines/` 且字段零冲突（执行轨写 `actuals`/`wbs_progress`/交付物，监控轨写控制/状态报告与 RAID 更新）。
- `orchestration.md` 新增 §3.4「operational 双轨」+ §3.2 组合表增「operational 双轨」行；`lifecycle.md §6.1` 并发说明升级为双轨引用；`p2-execution.md` / `p3-monitoring.md` §8 衔接引用双轨与 `monitoring-agent`。
- `agents.md` 新增 §9 `monitoring-agent`（监控轨角色）。

### 对外沟通与邮件审批门（Communication Send Gate）
- **分层配置（policy/data 分离）**：技能根新增 `config.yaml`（安装期策略/护栏）——`email.enabled` / `email.backend`（agent-mail·himalaya·gog·smtp）/ `email.default_from` / `email.requires_send_approval`（**硬护栏，项目不可关闭**）；项目数据在 `project.yaml.communication:`（`from` / `cadence` / `approval_override`（仅可收紧）/ `contacts[]`）。
- **联络簿**：`templates/common/communication_plan.md` 新增「相关方联络簿」段（姓名/角色/组织/邮箱/电话/时区/备注）；`stakeholder-agent` 定稿时把联络人同步进 `project.yaml.communication.contacts[]`；`templates-index.md`、`project-schema.md` 同步数据键契约与 `governance.communications[]` 审计块。
- **`scripts/comm_send.py`（审批门封装）**：按角色解析收件人（查 `communication.contacts[]`）、强制 `--approve`、外部邮件按 `approval_override.require_sponsor_cosign` 须 sponsor 会签、发送后写 `governance.communications[]` 审计；`--dry-run` 仅打印+审计不真正外发；未审批/被护栏拒绝直接 `exit 1`。
- **`agents.md` 新增 §8 `communication-agent`**：起草邮件 → 呈现待批 → 经 `comm_send.py` 审批门外发 → 登记审计；明确"绝不自行外发"。
- `SKILL.md` §6 新增「operational 双轨并行」与「对外邮件须过审批门」规则；§5 脚本速查补 `comm_send.py`。
- **README.md 同步至 v1.3.0**：§2 增「operational 双轨并行 / 对外沟通与邮件审批」能力、§3.1 补 `config.yaml` 安装期说明、§7 补 `comm_send.py` 行、§12 版本说明（延续「每次技能变更同步 README」规则）。

## 1.2.2 (2026-07-16)

### 阶段门引擎单测套件（CI 门禁）
- **新增 `scripts/test_gate_engine.py`（standalone，无需 pytest）**：为 `gate_engine.py` 提供 66 条断言的回归保护，两层覆盖——
  - **纯函数/逻辑层**：`GATES` 表不变量、软门无硬准则、硬门仅含控制门/收尾门、`phase_label_for_state` 路由（含「执行→监控 必须写入监控」历史 bug 的回归锁定）、`chk_*` 助手、`entry_criteria` 按方法论分支（敏捷进执行免基线、瀑布进执行含基线准则、收尾缺交付物判不过）。
  - **CLI 集成层**：真实子进程运行 `gate_engine.py` 及其依赖的 `consistency_check.py` / `control_engine.py`，覆盖 waterfall/agile/iteration-hybrid 与项目群四方法论，验证软门（规划/监控）翻转、硬门（执行/收尾/组合收尾）通过、缺基线/缺验收/收益未实现/前置状态不符/未知目标 的阻断、dry-run 不落盘、`--status` 输出。
- 退出码契约：`0`=全过，`1`=有失败，可直接挂 CI 质量门。
- **README.md 同步至 v1.2.2**：§7 脚本速查补 `test_gate_engine.py` 行；版本号与 §12 变更说明更新（延续 v1.2.1 确立的「每次技能变更同步 README」规则）。

## 1.2.1 (2026-07-16)

### 文档同步
- **README.md 同步至 v1.2.x**：补充「阶段化交付 / 阶段门审批」核心能力、§4.5 阶段模块与阶段门、`gate_engine.py` 脚本速查、阶段流转强制门规则、4 个阶段模块参考索引；版本号升至 1.2.1。
- 确立规则：**每次技能变更都同步更新 README.md**（与 SKILL.md / CHANGELOG / 版本号保持一致）。

## 1.2.0 (2026-07-16)

### 阶段模块与阶段门（Phase Modules & Gates）
- **新增 4 个阶段模块**（`references/phases/`）：`p0-p1-initiation-planning.md`（启动+规划）、`p2-execution.md`（执行）、`p3-monitoring.md`（监控）、`p4-closeout.md`（收尾）。每个模块定义该阶段的**活动 / 必产出交付物 / 入口准则 / 出口准则 / 阶段门审批清单**，并方法论适配（waterfall/agile/iteration/hybrid/项目群）。
- **新增 `scripts/gate_engine.py`（阶段门引擎）**：按 `phase`↔`lifecycle_state` 模型评估进入目标阶段的入口准则；审批通过后翻转 `project.phase` 与 `lifecycle_state`、向 `governance.stage_gates` 追加门记录、在 `docs/gate_reports/` 产出阶段门评审报告并登记到 `artifacts`。
- **硬门复用既有引擎**（避免逻辑重复）：进 `执行` 须 `consistency_check.py` exit 0（waterfall/hybrid 另须 `baseline.py --freeze`）；进 `收尾` 须 `control_engine.py` exit 0 + 验收/复盘交付物 +（项目群）收益闭环。未通过则 **exit 1 拒绝推进，不可跳过**。
- **门映射**：G0→1 启动→规划（软门/PM）、**G1→2 规划→执行（硬门/sponsor）**、G2→3 执行→监控（软门/PM，operational 内并发）、**G3→4 监控→收尾（硬门/sponsor）**。对齐 `lifecycle.md §5/§6`。
- `SKILL.md`：Step 1 路由按 `phase` 加载对应阶段模块；§5 增加 `gate_engine.py` 用法；§6 增加"阶段流转须过阶段门（强制）"规则；§7 索引登记 4 个阶段模块。
- `lifecycle.md`：新增 §6「阶段模块与阶段门」——阶段模块↔门↔状态机映射表、硬门自动化准则、`gate_engine.py` 用法。
- `project-schema.md`：注明 `governance.stage_gates` 记录结构。

## 1.1.0 (2026-07-16)

### 可选增强（§5）
- **控制门技术强制**：`control_engine.py` 新增「控制门 Gate」控制项，校验 `lifecycle_state == operational`；未进入运营控制阶段时标记为 AMBER 并记入升级项 `gate_not_operational`，贴合 `lifecycle.md` §5 的 `planning→baselined→operational` 强制串行纪律（不破坏「仅 RED 才 exit 1」的既有契约）。
- **项目群 rollup 解耦**：`rollup_program_wbs.py` 的组件 / 阶段映射改为可从 `project.yaml` 的 `program.components`（SOW id → 组件 slug）与 `governance.waves`（阶段 key → 阶段名）读取；缺省才回退内置示例（示例项目）并给出警告，不再硬编码单一项目。
- **版本可追溯**：新增 `CHANGELOG.md`；`_user_meta.json` 增加 `version` 字段；技能版本升至 `1.1.0`。

### 同期修复与加固（来自评审第一轮）
- 修复空 `wbs` 项目群 `rollup_program_wbs.py` 崩溃。
- 修复 4 张列表模板（`risk_register` / `change_log` / `benefits_realization` / `program_charter`）因 `| {{#each}}` 写法导致表首多出一列。
- 让专家调度「领域特化」真正生效：`init_project.py` 骨架补 `domain` / `product` 并新增 `--domain` / `--product` 参数。
- 移除 4 个脚本中 `eval(f.read())` 安全兜底，改为缺 PyYAML 时显式报错。
- `usage.md` 模板计数（30→35、common 11→16）与脚本速查表同步补全。

### 文档与健壮性（来自评审第二轮）
- 新增 `references/project-schema.md`：`project.yaml` 完整字段结构、质量门必填项、子 Agent 协同约定。
- `SKILL.md` §3 说明 TeamCreate 多 Agent 派发机制；§5 增加脚本异常处理与降级说明；§7 登记 `project-schema.md`。
- `lifecycle.md` §5.3 补「项目群阶段 ↔ 状态机映射」「operational 与 monitor 关系」「退出 operational 的 5 条出口条件」。

### 发布
- **已发布至 `slearnAI/pm-master`（private）**：v1.1.0 推送至 `https://github.com/slearnAI/pm-master`（私有仓库，默认分支 `main`）。提交历史保留 `v1.0 → v1.1.0` 线性演进；本次同时清理了仓库内误提交的 `__pycache__`，并在 `.gitignore` 补充 Python 缓存忽略。Git tag：`v1.1.0`。

## 1.0.0

- 初始版本：Builder-First 项目 / 项目群管理技能。
- 适配 waterfall / agile / iteration / hybrid 四种方法论。
- 内置模板库（35 个模板 + `_macros.md`）、自研 `render.py` 迷你模板引擎、双轨产出（Markdown → DOCX）。
- 质量门 `consistency_check.py`、基线化 `baseline.py`、运营控制 `control_engine.py`、专家调度 `dispatch.py`、排期健康度 `schedule_health.py`、挣值 `evm.py`。
- 四维度路由 + 标准工作流 + `planning→baselined→operational` 强制状态机 + 多 Agent 混合调度（direct / team / fork）。

## 2.1.4 (2026-07-19)

### 用户实测三项反馈的真修
- **#1 project_state.py 数据丢失加固**：保留 2.1.3 的 PyYAML 硬失败守卫；新增 `_save` 在覆盖非空文件前做时间戳备份（`project.yaml.bak_YYYYMMDD_HHMMSS`），并拒绝「用空 dict 覆盖非空文件」（空数据=疑似 PyYAML 加载失败）的毁灭性写入（exit 5）。已用 harness 验证守卫生效，文件未被破坏。
- **#2 合同费用真实捕获**：原渲染整列 `（待定）` 实为缺数据。从归档的 9 份已签 SOW PDF 提取真实金额写入 `program.sows[].fee` 与 `program.contracts[]`（SOW1/3/4/5/7/9 固定费、SOW6 T&M、SOW8 USD 课程总额换算 INR、SOW2 T&M 封顶人天）。重渲染后章程「财务与商务模型」费用列显示真实 ₹ 金额，0 个数据单元格为（待定）。
- **#3 风险/RAID 色标**：修复此前编辑落到错误路径（templates/risks/ 不存在，实为 templates/common/）导致未生效。现模板 `risk_register.md`/`raid_log.md` 正确调用 `sev_cell`，重渲染后 risk_register 含 7 个、raid_log 含 11 个严重度色标 emoji（🔴🟠🟡🟢）。已重渲染用户项目在盘文件，mtime 更新。

## 2.1.5 (2026-07-19)

### WBS mermaid `invalid date` 修复（用户 clean test 反馈）
- 根因：`wbs.md` 无条件渲染日期型 `gantt`，当 WBS 包缺 `start`/`end`（仅含 effort/估算，用户正确指出 WBS 可无日期）时 mermaid 报 `invalid date`。
- 修复：`build_wbs.py` 新增 `wbs_has_dates` 标志（仅当所有包都有合法 YYYY-MM-DD 起止时为 true）；`wbs.md` 甘特区改为 `{{#if wbs_has_dates}}` 条件渲染。无日期时仅保留「WBS 分解树」(graph TD)，并注明日期型甘特属于排期计划（`schedule_gantt.md`），待补日期后自动出现。
- 验证：无日期 WBS 渲染 → 无 gantt 代码块、无 invalid date，分解树保留；有日期 WBS（真实项目）→ gantt 正常。EN 模板同步。
