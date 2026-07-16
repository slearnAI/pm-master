# Changelog · PM Master

> 版本号与 `SKILL.md` 的 `metadata.version`、`_user_meta.json` 的 `version` 保持一致。

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
- **项目群 rollup 解耦**：`rollup_program_wbs.py` 的组件 / 阶段映射改为可从 `project.yaml` 的 `program.components`（SOW id → 组件 slug）与 `governance.waves`（阶段 key → 阶段名）读取；缺省才回退内置示例（某保险数据湖）并给出警告，不再硬编码单一项目。
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
