# 多 Agent 混合调度 · 编排手册

本文件是 PM Master 的「调度大脑」。主控 Agent（即加载本技能的 PM）按此决策如何把工作
自己做完、组队并行、或 fork 接力。

## 1. 分类（每次请求先做）

判定四个维度，写进 `project.yaml`（或直接用于路由）：

| 维度 | 取值 | 来源 |
|------|------|------|
| `type` | project / program | 用户说"项目"还是"项目群/组合" |
| `methodology` | waterfall / agile / iteration / hybrid | 用户指定或按交付性质推断 |
| `phase` | 启动/规划/执行/监控/收尾（项目群另有组合阶段） | 当前进展 |
| `intent` | 规划/构建/汇报/分析/治理 | 用户要什么 |

## 2. 执行模式决策树

```
请求进来
  │
  ├─ 单产物 or 解释/微调 or 跑一个分析  ──►  direct（主控直做，调 render.py / evm.py 等）
  │
  ├─ 多「互相独立」产物（如启动需 章程+WBS+排期+风险+RACI）
  │     且彼此无强依赖  ──►  team（TeamCreate 并行专职子 Agent）
  │
  └─ 需完整上下文接力（如"接着上次风险分析继续"、"基于我们刚讨论的范围重写 WBS"）
         ──►  fork（子 Agent 继承本会话全部上下文）
```

**不要无谓组队**：简单任务直做更省上下文；只有产物彼此独立且量大才组队。

## 3. team 模式：并行专职子 Agent

用 Agent 工具在**同一条消息里**派出多个 `general-purpose` 子 Agent（即并行），每个带一份
自包含 brief。主控随后汇总、跑一致性校验。

### 3.1 标准子 Agent brief 模板

```
你是 PM Master 的【<角色>】专职子 Agent。请独立产出以下 PM 产物，不要直接回复用户。

## 输入
- 项目事实源：<绝对路径>/project.yaml（先用 project_state.py 读取，了解项目背景）
- 模板：<绝对路径>/templates/<方法论>/<模板>.md
- 渲染引擎：<绝对路径>/scripts/render.py

## 任务
1. 基于 project.yaml 与用户需求，整理本产物所需数据，写成 <slug>_data.yaml。
2. 运行：python3 <SKILL_DIR>/scripts/render.py --template <模板> --data <slug>_data.yaml --out <输出路径>
3. 把产物路径回写 project.yaml 的 artifacts.<key>（用 project_state.py set）。
4. 简要回报：产出了什么文件、关键结论 3 条。

## 约束
- 只产出你负责的产物，不要碰其他角色的文件。
- 数据必须落到文件，禁止只在对话里给文字。
- 责任人/日期等字段若未知，填"（待定）"并标注，不要留空导致一致性校验失败。
```

### 3.2 典型组队组合

| 场景 | 并行子 Agent |
|------|--------------|
| 项目启动 | planner(WBS+排期) · risk(风险+RAID) · stakeholder(RACI+沟通) |
| 敏捷启动 | planner(产品Backlog) · risk(风险+RAID) · stakeholder(干系人+RACI) |
| 阶段评审 | reporter(状态报告) · risk(风险更新) · scheduler(排期更新) |
| 项目群启动 | program(组合章程+看板) · risk(组合风险) · dependency(依赖图) |

## 3.3 第二层：领域专家调度（Expert Dispatch）

第一层（PM-generalist）只产 PM 治理产物；**技术工作包必须由对应领域专家产出**，否则 WBS 会停在
SOW 级粗粒度。这是本技能"多 Agent"的真正含义——按活动的**领域/产品/任务**调度专家。

**流程（规划阶段）：**
1. 初稿 WBS 为 SOW 级 summary 包，标 `domain`（如 `data-modelling`、`migration`、`masking`）。
2. 运行 `python3 scripts/dispatch.py --project <项目>/project.yaml` 生成**调度计划**：
   自动标出缺 `role` 标签的领域活动、以及 `estimate` 超阈值需拆解的包，并特化推荐专家名。
3. 对每个待调度包，派出领域专家子 Agent（用 `references/expert-roles.md` 对应角色的 `system_prompt`，
   代入 `project.domain`/`product`），或路由至 **WorkBuddy 专家中心**已安装的对应**专家**会话。
4. 专家子 Agent 把包拆成叶子工作包（≤ `control.granularity_threshold` 人天，默认 10），
   写回 `project.yaml` 的 `wbs`（ID 前缀 `<包ID>.x`），含 交付物/role/owner/estimate/DoD/依赖。
5. 主控重新渲染 `wbs.md` → 跑 `consistency_check.py`（新门禁校验 role 标签 + 颗粒度）→ 未过则退回专家续拆。

**角色路由与特化**：见 `references/activity-expert-map.md`（活动关键词 → 角色；domain/product → 专家特化名）。
**专家 prompt 库**：见 `references/expert-roles.md`（13 个领域角色 + 通用 PM 角色）。

> 经验团队的 WBS 不是 10 个 SOW 包，而是数百个叶子包——这是靠领域专家逐域拆解出来的，
> 而非 PM-generalist 一个人拍脑袋。本第二层就是把这个纪律固化进工作流与质量门。

## 4. fork 模式：上下文接力

当用户要求"接着做""基于前文"等强依赖任务时，用 Agent 工具以 `subagent_type="fork"` 派出子 Agent，
它会继承本会话全部上下文，适合需要长链条推理的深度任务（如风险情景推演、WBS 逐层拆解）。

## 5. 聚合与质量门

1. 收集各子 Agent 回报，确认产物文件均已生成。
2. 主控运行一致性校验：
   ```bash
   python3 <SKILL_DIR>/scripts/consistency_check.py --project <项目>/project.yaml
   ```
3. 有问题时，把问题清单交给对应子 Agent 修复，或主控直接修；通过后再交付。
4. 交付：更新 `project.yaml.artifacts`，按需 `render_docx.py` 渲染正式文档，向用户给产物清单 + 指标卡。

## 6. 示例（敏捷项目启动）

用户："用敏捷帮我启动『支付重构』项目"

1. `init_project.py "支付重构" --type project --methodology agile --framework scrum`
2. 分类 → {project, agile, 启动, 构建} → team 模式
3. 同消息并行派出：
   - planner-agent → `templates/agile/product_backlog.md`
   - risk-agent → `templates/common/risk_register.md` + `templates/common/raid_log.md`
   - stakeholder-agent → `templates/common/stakeholder_register.md` + `templates/common/raci.md`
4. 汇总 → `consistency_check.py` → `render_docx.py` 渲染 → 交付清单。
