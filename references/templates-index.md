# 模板库索引（Templates Index）

本技能内置模板库，按方法论/用途分目录。每个模板是带占位符的 Markdown，用
`scripts/render.py --template <模板> --data <数据.yaml> --out <产物.md>` 渲染。

> **字段契约**：下方每个模板列出渲染所需的数据键（YAML 顶层键）。子 Agent / 用户填数据时
> 必须提供这些键（缺失则渲染为空，但一致性校验仍可能失败，故未知项填"（待定）"）。

> **图表渲染**：所有图表类交付物（WBS 甘特、进度甘特、燃尽图、依赖图、治理地图、宏微对齐图）
> 均使用 Mermaid 代码块渲染，可在 GitHub / VS Code / Typora 等支持 Mermaid 的查看器中直接可视化。

## common/ 跨方法论核心（16）
| 模板文件 | 数据键 | 说明 |
|----------|--------|------|
| project_charter.md | project{name,type,methodology,objectives[],scope,out_of_scope,sponsor,pm,team[],start_date,target_end} | 项目章程 |
| stakeholder_register.md | project{name,pm}, stakeholders[{name,role,interest,influence,engagement}] | 干系人登记册 |
| raci.md | project{name}, raci[{activity,responsible,accountable,consulted,informed}] | RACI 矩阵 |
| communication_plan.md | project{name}, comms[{audience,info,channel,frequency,owner}], contacts[{name,role,org,email,phone,tz,note}] | 沟通计划（含相关方联络簿，定稿同步 project.yaml.communication.contacts[]） |
| raid_log.md | project{name}, raid{risks[],assumptions[],issues[],dependencies[]} | RAID 日志 |
| sow_kickoff.md | project{name}, sow{id,name,domain,owner,objective,scope}, deliverables[{id,name}], experts[], participants[{name,role}], kickoff_date, decisions[], assumptions[], next_actions[], artifacts[], status | SOW 启动会（per-SOW Kick-off，由 build_sow_kickoff.py 从 WBS 生成，输出 `plans/<sow>/kickoff.md`，与该 SOW 排期同处子计划文件夹） |
| risk_register.md | project{name}, risks[{id,description,category,likelihood,impact,score,severity,owner,mitigation,status}] | 风险登记册（5×5 校准，须 severity） |
| status_report.md | project{name,phase}, period, progress{summary,completed[],next[]}, metrics{cpi,spi,pv,ev,ac} , risks[], help[] | 状态报告 |
| lessons_learned.md | project{name}, lessons[{what,went_well,improve,action_owner}] | 经验教训 |
| closure_report.md | project{name}, closure{scope_done,acceptance,handover[],metrics{},lessons_ref} | 收尾报告 |
| project_board.md | project{name}, board[{id,title,owner,status,priority}] | 项目看板 |
| milestone_list.md | project{name}, milestones[{id,name,date,owner,status}] | 里程碑清单 |
| change_request.md | project{name}, cr{id,requester,date,gate,scope_before,scope_after,schedule_before,schedule_after,cost_before,cost_after,resource_before,resource_after,rationale,impact_schedule,impact_cost,impact_risk,impact_dependency} | 变更请求（CCB 评审） |
| change_log.md | project{name}, changes[{id,date,type,description,impact,decision,status}] | 变更日志（变更控制追溯） |
| baseline_record.md | project{name,id,methodology,lifecycle_state,baselined_on}, baseline{on,by,file} | 基线记录（冻结基准，对照来源） |
| control_register.md | project{name,id,pm}, control{cadence,thresholds{},recipients[]} | 控制登记册（常规控制清单/频次/责任人） |
| control_report.md | project{name}, as_of, overall_status, controls[{name,status,detail}], escalations[], metrics{} | 运营控制报告（控制引擎输出） |

## waterfall/ 瀑布专属（5）
| 模板文件 | 数据键 | 说明 |
|----------|--------|------|
| requirements_spec.md | project{name}, requirements[{id,title,type,priority,acceptance,status}] | 需求规格 |
| wbs.md | project{name}, wbs_groups[{name,items[{id,name,level,deliverable,owner,role,expert,estimate,duration,start,end,dependsOn,acceptance,gantt_name}]], view_label, view_note, view_group_note | 工作分解结构（含 DoD 列 + Mermaid 甘特；由 build_wbs.py 从 wbs 派生 wbs_groups 后渲染） |
| schedule_gantt.md | project{name}, view_label, tasks[{id,name,duration,deps[],start,end,milestone}] | 进度甘特（由 build_schedule.py 从 wbs 正向排程生成，P0/P1 主要排期交付物；view_label 区分 项目/项目群/SOW 视图） |
| stage_gate_review.md | project{name}, gate{name,phase,checklist[{item,status,comment}],decision} | 阶段门评审 |
| quality_plan.md | project{name}, quality{objectives[],checkpoints[{name,criteria,entry,exit}],std} | 质量计划 |

## agile/ 敏捷专属（5）
| 模板文件 | 数据键 | 说明 |
|----------|--------|------|
| product_backlog.md | project{name}, backlog[{id,title,epic,priority,estimate,status}] | 产品 Backlog |
| sprint_plan.md | project{name}, sprint{num,goal,commitment[],tasks[{id,title,owner,estimate}]} | Sprint 计划 |
| definition_of_done.md | project{name}, dod[{area,checklist[]}] | 完成定义 DoD |
| burndown.md | project{name}, sprint{num}, burndown[{day,remaining,ideal}] | 燃尽图数据 |
| retro.md | project{name}, sprint{num}, retro{good[],improve[],actions[{item,owner,due}]} | 回顾 |

## iteration/ 迭代专属（3）
| 模板文件 | 数据键 | 说明 |
|----------|--------|------|
| iteration_plan.md | project{name}, iteration{num,goal,scope[],milestones[],resources[]} | 迭代计划 |
| iteration_backlog.md | project{name}, iteration{num}, backlog[{id,title,owner,estimate,status}] | 迭代 Backlog |
| iteration_review.md | project{name}, iteration{num}, review{completed[],deviation, demo,next_input[]} | 迭代评审 |

## hybrid/ 混合专属（2）
| 模板文件 | 数据键 | 说明 |
|----------|--------|------|
| hybrid_governance.md | project{name}, governance{parts[{name,methodology,gate,decision_owner}], principles[]} | 治理地图 |
| macro_micro_map.md | project{name}, map[{macro_milestone,micro_iteration,alignment_status}] | 宏微映射 |

## program/ 项目群专属（4）
| 模板文件 | 数据键 | 说明 |
|----------|--------|------|
| program_charter.md | project{name,type}, program{vision,goals[],success_criteria[],scope,budget{total,funding,baseline,constraint},governance{model,cadence,change_control},milestones[{id,name,date,owner}],benefits_target[]} | 项目群章程（含财务边界/成功标准/签署） |
| portfolio_dashboard.md | project{name}, components[{name,methodology,health, cpi,spi,owner, note}] | 组合看板（health 单元格用 `sev_icon` 渲染 🟢🟡🔴 色标图标，见 render.py） |
| dependency_map.md | project{name}, dependencies[{id,from,to,type,status,blocker}] | 依赖图 |
| benefits_realization.md | project{name}, benefits[{id,description,metric,target,baseline,realized,owner,realization_date,status}] | 收益实现（含 owner/baseline/实现日） |

## _macros.md
共享片段（表头、版本角标、状态图例）。模板可用 `{{#each}}` 调用；如需复用片段，
渲染前由主控把 `_macros.md` 内容拼入，或在数据里提供等效字段。

## 扩展方式
新增方法论/产物 = 在对应目录加 `.md` 模板（遵循 render.py 语法）+ 在此表登记数据键，
无需改动引擎或 SKILL.md。

## 标准启动 / 治理套件（建议默认产出）
- **任何项目启动**：project_charter + stakeholder_register + raci + communication_plan
  + 计划模板(wbs / backlog / iteration_plan) + risk_register + raid_log。
- **waterfall / hybrid**：wbs（估算+依赖网络+DoD）+ stage_gate_review + quality_plan +
  schedule_health 分析；执行/监控阶段须 status_report + evm 分析。
- **agile / iteration**：product_backlog / iteration_plan + sprint_plan + definition_of_done +
  burndown + retro。
- **项目群 / hybrid（必备变更控制）**：program_charter + portfolio_dashboard + dependency_map +
  benefits_realization + **change_log**（CCB）；hybrid 另须至少 1 个微层计划(sprint/backlog/iteration)。
- **运营控制（operational，强制执行）**：planning→review→**baseline**→控制门→operational 为强制串行状态机；
  waterfall / hybrid 进入执行/监控前**必须** `baseline.py --freeze`（产 baseline_record + control_register），
  之后按 `control.cadence` 周期性跑 `control_engine.py` 生成 control_report。详见 references/lifecycle.md §5。
- 上述套件缺项时，`consistency_check.py` 会按控制级规则**阻断**或**告警**（详见脚本说明）。
