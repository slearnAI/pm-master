# Changelog · PM Master

> 版本号与 `SKILL.md` 的 `metadata.version`、`_user_meta.json` 的 `version` 保持一致。

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

## 1.0.0

- 初始版本：Builder-First 项目 / 项目群管理技能。
- 适配 waterfall / agile / iteration / hybrid 四种方法论。
- 内置模板库（35 个模板 + `_macros.md`）、自研 `render.py` 迷你模板引擎、双轨产出（Markdown → DOCX）。
- 质量门 `consistency_check.py`、基线化 `baseline.py`、运营控制 `control_engine.py`、专家调度 `dispatch.py`、排期健康度 `schedule_health.py`、挣值 `evm.py`。
- 四维度路由 + 标准工作流 + `planning→baselined→operational` 强制状态机 + 多 Agent 混合调度（direct / team / fork）。
