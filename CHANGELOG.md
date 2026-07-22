# Changelog · PM Master v2

## 2.2.13 (2026-07-22)

### 控制引擎健壮性 + 重渲染覆盖扩展
- **根因**：真实项目运行暴露 4 类状态/渲染错位，导致控制门误报与文档漂移。
- **control_engine.py**：
  - 新增统一状态常量 `DONE/CLOSED/CANCELLED_STATES` 与 `_norm_status()` 归一（兼容中英文同义词），杜绝各支柱内联 hardcode 产生的「已降降」类错字。
  - 进度汇总跳过 `summary` 包（其估算是子叶子的 rollup，纳入会重复计数）。
  - 已取消/降级/终止/移出范围的包与风险不计入逾期与活跃漂移（非在办工作/已关闭不误报）。
  - 新增 `TERMINAL_LS`（closed/closeout/archived 等）：程序/项目进入终态后控制门判 GREEN、不再误报 `gate_not_operational`。
- **rerender_docs.py**：
  - 新增 `change_log`（title→description 映射，杜绝事实源有 CR 却渲染空壳）、`raid_log`（dict 假设自动展平为字符串）、`evm_report`（调用 `evm.py` 按现值重算）、`baseline_record` + `control_register` 重渲染。
  - `--only` 选项扩展覆盖上述类型。
- **rollup_program_wbs.py**：新增 `_rollup_status()`，叶子包全为取消/终止态时里程碑行携带 `cancelled`，避免控制引擎误报逾期。
- **rollup_subprojects.py**：`eac_vs_bac_var` 为 None 时回退 `n/a`，避免 None 格式化崩溃。
- 验证：对示例客户项目复跑控制引擎/重渲染，原误报消失；机密性扫描 exit 0。

## 2.2.12 (2026-07-21)
- **域无关 + SOW 自动对齐**：消除开箱即偏向数据域的硬编码默认（`data-architect`/`etl-engineer`/`data-modeler`/`requirements-analyst`）。
  - 新增 `scripts/role_catalog.py`（单一事实源）：覆盖 10 个技术域（data-platform / software-dev / cloud-infra / ai-ml / cybersecurity / product / qa / integration / erp / biz-analytics）+ 跨域角色；提供 `infer_domain(text)` / `infer_role(name, domain)` / `specialize()` / `align_from_sow(spec)`。
  - `dispatch.py` / `consistency_check.py` 改为 import `role_catalog`，删除各自重复的 `ROLE_KEYWORDS` / `DOMAIN_BY_KEYWORD` / `DOMAIN_SPECIALIZATION`。
  - `parse_sow.py` 默认角色改为 `solution-architect`（summary/wave）与按域推断兜底 `domain-sme`（leaf），并从 SOW 文本自动写入 `domain`。
  - 旧项目域（insurance-data-lake / payments / ecommerce / fintech-core）经 `LEGACY_SPECIALIZATION` 向后兼容，仍保留特化名。
  - `expert-roles.md` / `activity-expert-map.md` 扩展为全技术域角色目录；`sow-parsing-playbook.md` / `program-management.md` 示例去数据偏向。

## 2.2.11 (2026-07-21)

### 机密性评审穿透化 · 新增 `confidentiality_check.py`（发布前必跑）
- **背景**：用户指出机密性评审不能「仅限路径」，必须覆盖「所有文件的内容（scripts / examples / 任意文件，含二进制）」。
  早期评审只扫文本，漏掉了编译缓存 `__pycache__/*.pyc`——其字节码内嵌 `co_filename` 绝对路径
  （如 `/Users/<user>/...` 或历史工作区路径），会泄露本机用户名/历史工作区。
- **新增 `scripts/confidentiality_check.py`**：递归穿透扫描整个 skill 包。
  - 文本文件按行匹配；**二进制（.pyc 等）按字节级扫描**，可抓到内嵌绝对路径；
  - HIGH 令牌（命中即泄露，exit 1）：`LIC` / `Teradata` / `Vertica` / `Vantage` / `FSAS` / `lic-datalake` /
    `/Users/` `/home/` `C:\Users` / `qclaw` / `Stephen Lau`；
  - 白名单（已评审安全，不报警）：`示例客户` / `示例数据湖项目` / `MPP数仓` / `nos-architect` /
    通用示例邮箱 / `示例 ₹ 金额`；
  - 自动排除自身源码，避免模式定义自匹配误报。
- **清理**：删除本地 `__pycache__`（路径泄露源）；`.gitignore` 本已忽略 `*.pyc`，故 `origin/v2` 不含泄露。
- **固化**：`references/usage.md` §14 将本扫描定为「发布到共享分支前的必跑门禁」。
- 验证：对当前包运行 exit 0（PASS）；向包内注入含 `/Users/` 绝对路径的 .pyc 后运行立即 FAIL（字节级命中 `@offset`），证明二进制穿透有效。

## 2.2.10 (2026-07-21)

### Bug fix · RAID 日志「A · Assumptions」渲染为 JSON 字面量
- **根因**：`templates/common/raid_log.md`（及 `sow_kickoff.md`）的假设段落用 `{{#each assumptions}} - {{this}}`，
  当假设以 `{'text': '...'}` dict 形式存储时，`{{this}}` 输出整段 dict 的 `str()`（`{'text': '<=1600 源表...'}`），
  用户看到 JSON 风格 blob，可读性被破坏。
- **修复**：渲染引擎 `scripts/render.py` 新增 `assume_text` 助手——dict 取 `.text`、纯字符串/标量直出、None 回退空串；
  两模板假设段落改为 `- {{ assume_text(this) }}`。该助手对两种写法均安全，杜绝 dict 被字符串化。
- 验证：示例客户 程序 `risks/raid_log.md` 的 A 段重渲染为干净项目符号（「- <=1600 source tables…」等 6 条）；
  纯字符串假设（如 SOW kickoff）亦正常。

## 2.2.9 (2026-07-21)

### 运营期交付物护栏（OAG, Operational Artifact Guardrail）— 新增可执行护栏
- **根因**：示例客户 项目在 operational 阶段修改了 `project.yaml`（RAID/EVM）却未重渲染对应交付物，导致
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
- 验证：示例客户 程序 `artifact_guard.py --project` 在重渲染后 exit 0；临时改动 `raid` 后运行立即报
  `[数据漂移] raid_log`，证明可抓到当初漏掉的环节。

### Bug fix · 程序级 RAID 渲染读取 `raid.*` 而非顶层 `risks`
- **根因**：`build_subproject.py` / `rerender_docs.py` 读取 RAID 时取顶层 `data['risks']`，但程序层 RAID 存于
  `data['raid']['risks']`，导致 `rerender_docs.py` 静默跳过风险文档（`if not data.get('risks'): skip`），
  且 `risk_register.md` 被喂空列表；`consistency_check.py` 读 `raid.risks` 故门禁仍过，造成「门过但文档陈旧」的静默漂移。
- **修复**：两脚本的 risk 渲染路径回退到 `data['raid']['risks']`；`rerender_docs.py` 去掉 `KeyError` 隐患。
- 验证：示例客户 程序 `risks/raid_log.md` / `risks/risk_register.md` 正确反映 R1–R12 / I1–I6；`rerender_docs.py` 不再跳过。

## 2.2.7 (2026-07-20)

### Bug fix · 子项目状态报告「5. Risks & Blockers」渲染为 JSON 字符串
- **根因**：`templates/common/status_report.md` 的 §5 用 `{{#each risks}} - {{this}}`，当 `risks` 为 dict 列表时 `{{this}}` 输出 `str(dict)` → 用户看到的 JSON 风格 blob。
- **修复**：§5 改为与风险登记册一致的**风险表格**（含 `sev_cell` 严重度色标 emoji：🟢绿/🟡黄/🟠橙/🔴红），列含 # / Severity / Risk ID / Description / Category / Owner / Mitigation / Status；`risks` 为空时显示「_No active risks or blockers this period._」。
- 验证：示例客户 9 个子项目 status_report 全部重渲染，§5 无 JSON blob；空风险分支正常。三处安装 v2.2.7。

## 2.2.6 (2026-07-20)

### WBS/排期 Pillar 2+4 落盘修复 + 已冻结 示例客户 的 Payment Linkage 实化
- **`build_schedule.py` 部分图保护（防压平回归）**：项目群/program 视图缺叶子细节（部分图）时，若包已有真实 start/end 且其排程偏移为 0，则**沿用既有日期**，不再把已基线化里程碑重置为起始日。修复了 2.2.5 末次 program 视图回写把 示例客户 全部里程碑压平到 2026-08-01 的回归。
- **program / 单 SOW 视图默认只读**：`--level program` 与 `--sow` 不再回写 `wbs` 日期（仅 full 视图拥有完整叶子图才回写），保护已冻结 master 索引不被视图渲染改动。
- **Pillar 4 `due` 改为逐里程碑计算**：里程碑计费（fixed）且无独立合同日历 → 付款随该里程碑达成即到期（收款节奏=交付节奏），每行 `due` 默认取自身里程碑日；仅当 `sow_map`/`program.sows` 显式给 `due_date`（早于里程碑日）才可能出现 `drift`。修复了 SOW 级 `due` 泄漏到后续里程碑导致误报 30 条 drift 的 bug。
- **示例客户 元数据回填（非破坏性）**：为 示例客户 37 个既有固定费率里程碑补 `billing.payment_id`（{SOW}-P{n}），未改任何日期/BAC。回填后 `plans/schedule_program_gantt.md` 的 Payment Linkage 段 37 行全部 `linked`（合同即“签字/完工触发付款”），master 未被改动，consistency/critic 仍 exit 0。
- 验证：示例客户（operational）不击穿；规划期显式 late `due_date` 仍触发 `drift`（exit 1 由 6d 门禁）。三处安装 v2.2.6。

## 2.2.5 (2026-07-20)

### WBS/排期 Pillar 2（里程碑↔活动归集）+ Pillar 4（支付里程碑↔排期联动）
- **Pillar 2**：`build_schedule.py` 新增 `milestone_coverage` 计算——每个里程碑下直接归属的活动集合（叶子 `milestone_ref` 或依赖末端落在里程碑），渲染到 `schedule_gantt.md` 的「Milestone Coverage」段。一个支付里程碑可对应多个活动。
- **`parse_sow.py` 自动标注**：每叶子自动置 `milestone_ref` 指向其 Wave 里程碑；每计费里程碑自动置 `billing.payment_id = {SOW}-P{n}`（Pillar 4 映射）。
- **Pillar 4**：`build_schedule.py` 新增 `payment_linkage` 计算——每条固定费率支付行 → 其里程碑 → 排期日 vs 合同 due_date；状态 linked/drift/no-due。渲染到「Payment Linkage」段。
- **`consistency_check.py` 6d 排期联动门禁（仅规划期致命，运营期跳过）**：6d-1 里程碑覆盖缺口（叶子未归属里程碑）、6d-2 支付↔里程碑缺失（固定费率 SOW 有支付行却无计费里程碑）、6d-3 支付顺序非单调（同一 SOW 计费里程碑排期日须升序）。
- 验证：示例客户（operational）不击穿（consistency/critic 均 exit 0，Payment Linkage 段正常渲染示例 ₹ 金额）；规划期样例触发 6d 门禁。
- 安全沿用 Pillar 1 设计：所有新门禁仅在 planning_now（phase∈{启动,规划,''} 或 lifecycle∈{planning,review,baselined,None}）致命。

## 2.2.4 (2026-07-20)

### WBS 拆解纪律 Pillar 1（6 因素 + Critic 自审引擎）+ Pillar 3（双周 fortnight 颗粒度）
- **新增 `scripts/critic_review.py`（可执行 Critic 自审）**：把 `sow-parsing-playbook.md` 的散文 Critic 固化为 6 因素校验——scope 可追溯 / milestone 归属 / payment 挂支付行 / assumptions 可量化边界 / constraints 外部前置须 entry_gate / dependencies 连通。规划期致命（exit 1），运营期（已冻结，如 示例客户）降级为提示不阻断。
- **`consistency_check.py` 新增 6c 拆解纪律门禁（仅规划/启动期致命）**：集成 `critic_review.py --strict` 结果 + 校验 `decomposition.critic_passed==true` + assumptions 可量化边界。运营期自动跳过，保护已冻结项目不被新门禁击穿。
- **Pillar 3**：`init_project.py` 默认 `control.leaf_granularity: fortnight` + `granularity_threshold: 10`（=10 工作人天，沿用既有默认但显式化），作为 waterfall/program 叶子包标准颗粒度。
- **`sow-parsing-playbook.md` §2.6** 重写：Critic 自审列出 6 因素清单，并要求落盘后运行 `critic_review.py --strict` 并置 `critic_passed=true`。
- 验证：示例客户（operational）一致性 exit 0 / critic exit 0（不击穿）；规划期样例触发 7 项致命（scope/milestone/dependency/critic_passed/assumption-bound 等），exit 1。

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
- 背景：示例数据湖项目 程序（9 份 SOW）实测时，子项目拆分后若程序级 RAID/status 与子项目各维护一套会一周内漂移；此模型从机制上消除该反模式。

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
- **根因**：此前 SOW1 计划是「初级水平」——套用一次性泛化 4 阶段瀑布，未读 SOW 真实 **4-Wave 商业结构** 与 **5 个设计文档签字里程碑**（其中 4 个为计费事件 = 示例金额），排期只覆盖前 ~5 周。
- **专家级重做（CoT + 评审）**：先逐字提取 SOW 计费/交付节，把每个 "<Deliverable> post sign-off" 事件建模为 `milestone: true` + `billing:{event,fee_inr,currency,status}` 包；4 个 Wave 各为 summary 包（源分析→逻辑模型→物理模型+DDL→S2T映射→签字里程碑），并按商业节奏顺序排程（W1 2026-10-15 → W4 2027-04-28，全 ~9 个月）；客户系统B 归档设计为独立交付里程碑（fee_inr:0，标注非独立计费）。
- **叶子包 ≤10 人天**：逻辑/物理/S2T 拆为 ≤10 天领域专家桶（W1.2a FSDM / W1.2b 客户系统A / W1.3a Core DDL / W1.3b Semantic DDL …），满足控制门硬阈值；summary/milestone 用子项累计估算。
- **数据就绪门**：新增 `SOW1.0 源就绪门` 作为关键路径前置（SME+真实数据+接口文档），对应 SOW 最大返工风险。
- **子项目联动**：subprojects/sow1/project.yaml 补 `billing_milestones[]` 索引（M1–M5 含金额/日期/状态）与 4 项 Wave 级风险（含 S1-R4 计费里程碑延迟现金流风险）；RAID 依赖写回 SOW2/3/7 正确前置。
- **新增参考规范**：`references/program-management.md` 加「Billing-Milestone-Driven WBS Decomposition」专家约定（解析 SOW 必须先做链路思考+评审，再写 WBS）。
- **验证**：SOW1 排期覆盖 FN01→FN20（全 ~9 个月，非仅首双周）；甘特含 11 个里程碑（4 计费+1 交付+其他）；程序级一致性门 exit 0。
> 版本号与 `SKILL.md` 的 `metadata.version`、`_user_meta.json` 的 `version` 保持一致。

## 2.1.6 (2026-07-19)

### 两个架构性缺口补齐（用户评审 示例客户 SOW1 后提出）

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

**验证**：示例客户 SOW1 子项目建立并索引成功；fortnight 排期渲染（FN01–FN03 分桶、任务命名正确）；子项目 RAID/风险/状态渲染含严重度色标；程序级一致性门 exit 0。

## 2.1.3 (2026-07-19)

### 项目群章程（Program Charter）重构（用户 WorkBuddy 实测 docs/program_charter.md 反馈）
- **Program Architecture mermaid 修复**：用户渲染稿的 `subgraph DELIVERY` 内节点 `S6/S7` 指向 subgraph 自身（`S6 --> DELIVERY`）属非法 mermaid 语法。章程模板重写为数据驱动版，架构图改为 SOW6→CORE、SOW7 作为独立节点，不再自指 subgraph（已渲染验证合法）。
- **财务与商务模型（Financials & Commercial Model）费用捕获**：原渲染稿费用整列 `（待定）`。新增 `program.sows[]`（sow/workstream/model/billing/fee），章程「财务与商务模型」表改由 `program.sows[].fee` 驱动；未锁定时须填 `TBC — 原因`，禁止整表 `（待定）`。已把 示例客户 实际项目数据写入 `project.yaml` 并重渲染，费用列呈现实值/TBC。
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

### 进一步脱敏（合规 · 消除法律风险）
- `scripts/rollup_program_wbs.py` 的内置示例映射进一步去标识化：
  - `COMPONENT_MAP`：剥离 SOW 组件 slug 的描述性后缀（`sow1-data-modelling` → `sow1`，…，`sow9-ts` → `sow9`，`external-pii` → `ext-pii`），仅保留编号标识。
  - `PHASE_NAME`：阶段别名由客户专属描述（Wave 1–4 基础建模 / 示例主题域 / 客户系统A 分析结构 / 客户系统B 归档与集成）改为中性 `Stream 1–4` 命名，移除 客户系统A / 客户系统B / 示例主题域等客户系统/领域泄露。
  - 三处「某示例数据湖项目 / 示例数据湖项目」注释与告警文案统一改为「示例项目」，不再暴露真实行业与客户。
- `CHANGELOG.md`：将 1.1.0 中关于内置示例的语义描述「某示例数据湖项目」改为中性的「示例项目」。

> 说明：保留的 `Wave` / `示例数据湖项目` 命中（如 `references/methodology-hybrid.md`、`hybrid_playbook.md`、`expert-roles.md`）属**通用方法论/领域示例词汇**，非真实客户或厂商名，引擎路由与设计依赖之，故维持不变。

## 1.3.1 (2026-07-16)

### 脱敏（合规 · 消除法律风险）
- 全量扫描技能文件，移除真实客户名与厂商名等敏感信息，统一改为代号：
  - 真实保险行业客户名 → `客户A`（代号 `ALPHA`）；真实 MPP 数仓厂商名 → `MPP 数仓`（通用占位）；另一被点名的集成商经扫描确认本仓库**不存在**，无需处理。
  - `references/activity-expert-map.md`：`example-data-lake` 的示例项目由真实客户项目名改为 `客户A 数据湖（代号 ALPHA，MPP 数仓）`，角色中的厂商专属 ETL 工程师改为 `MPP 数仓 TPT/ETL 工程师`。
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
- **#2 合同费用真实捕获**：原渲染整列 `（待定）` 实为缺数据。从归档的 9 份示例 SOW 文档 提取示例金额写入 `program.sows[].fee` 与 `program.contracts[]`（SOW1/3/4/5/7/9 固定费、SOW6 T&M、SOW8 USD 课程总额换算 INR、SOW2 T&M 封顶人天）。重渲染后章程「财务与商务模型」费用列显示示例 ₹ 金额，0 个数据单元格为（待定）。
- **#3 风险/RAID 色标**：修复此前编辑落到错误路径（templates/risks/ 不存在，实为 templates/common/）导致未生效。现模板 `risk_register.md`/`raid_log.md` 正确调用 `sev_cell`，重渲染后 risk_register 含 7 个、raid_log 含 11 个严重度色标 emoji（🔴🟠🟡🟢）。已重渲染用户项目在盘文件，mtime 更新。

## 2.1.5 (2026-07-19)

### WBS mermaid `invalid date` 修复（用户 clean test 反馈）
- 根因：`wbs.md` 无条件渲染日期型 `gantt`，当 WBS 包缺 `start`/`end`（仅含 effort/估算，用户正确指出 WBS 可无日期）时 mermaid 报 `invalid date`。
- 修复：`build_wbs.py` 新增 `wbs_has_dates` 标志（仅当所有包都有合法 YYYY-MM-DD 起止时为 true）；`wbs.md` 甘特区改为 `{{#if wbs_has_dates}}` 条件渲染。无日期时仅保留「WBS 分解树」(graph TD)，并注明日期型甘特属于排期计划（`schedule_gantt.md`），待补日期后自动出现。
- 验证：无日期 WBS 渲染 → 无 gantt 代码块、无 invalid date，分解树保留；有日期 WBS（真实项目）→ gantt 正常。EN 模板同步。
