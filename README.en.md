# PM Master - Project and Program Management Skill

> A project + program management skill for PMs in the technology industry. Builder philosophy, executable, built-in template library, supports multi-agent dispatch, adapted to the four delivery methodologies waterfall / agile / iteration / hybrid.

- **Version**: 1.3.2
- **License**: MIT
- **Positioning**: Any project/program request must produce a real artifact (file); giving advice only is forbidden.

---

## 1. What Problem It Solves

Technology-industry project delivery often stalls on three things: inconsistent methodology (waterfall/agile/iteration/hybrid used in mixed ways), no standard for deliverables (charter/WBS/risk/status report each going their own way), and unsustainable governance (plan and execution disconnected, missing baseline, missing periodic inspection). PM Master turns these three things into a fixed executable engineering system:

- Every request -> a real file (Markdown, exportable to DOCX);
- Every project -> a single source of truth `project.yaml`, continuous across sessions/agents;
- Every discipline -> a verifiable quality gate (consistency gate, baselining, operational control).

---

## 2. Core Capabilities

| Capability | Description | Applies to |
|------|------|------|
| Project initiation / planning | Charter, stakeholder, RACI, WBS, schedule, risk, RAID | Any methodology |
| Agile delivery | Product backlog, sprint plan, DoD, burndown, retrospective | agile |
| Iteration delivery | Iteration plan / backlog / review | iteration |
| Waterfall delivery | Requirements specification, WBS, Gantt, stage gate, quality plan | waterfall |
| Hybrid governance | Governance map, macro/micro map | hybrid |
| Program governance | Program charter, portfolio dashboard, dependency map, benefits realization | program |
| Metrics analysis | Earned value EVM, schedule critical path, consistency check | Analysis scenarios |
| Multi-agent parallel | Team up to produce independent artifacts | Complex initiation / review |
| Dual-track docs | Markdown source -> DOCX formal deliverable | Delivery / reporting |
| Phased delivery | P0+P1 initiation planning / P2 execution / P3 monitoring / P4 closeout phase modules, each phase defines activities/deliverables/criteria | Full lifecycle |
| Stage gate approval | gate_engine evaluates entry criteria + hard gates (execution/closeout) force approval, flipping the state machine | Phase transition |
| Operational dual-track parallel | P2 execution track (domain expert) + P3 monitoring track (monitoring-agent) multi-agent parallel, sharing the single source of truth, zero field conflicts | Execution/monitoring |
| External communication and email approval | communication_plan registers stakeholder contact book; communication-agent drafts, comm_send.py enforces approval gate + audit, layered config (install-time guardrails / project-time data) | Communication/email |

---

## 3. Quick Start

### 3.1 Installation
Place the skill directory under CodeBuddy's `skills/`:

```bash
# Example
cp -r pm-master /root/.codebuddy/skills/pm-master
```

The skill is available automatically with each session, no extra installation needed. You can also directly unzip the distributed `pm-master.zip` into that directory.

> **Install-time configuration (policy/guardrails)**: The skill root `config.yaml` defines email capability and security guardrails -- `email.enabled` / `email.backend` (agent-mail/himalaya/gog/smtp) / `email.default_from` / `email.requires_send_approval` (hard guardrail, cannot be turned off at project level). Fill in as needed during installation; project-level data (contact book/cadence) lives in the `communication:` block of `project.yaml`. See `references/project-schema.md` and `scripts/comm_send.py`.

### 3.2 Minimal Three-Step (Command Line)

```bash
SKILL_DIR=/root/.codebuddy/skills/pm-master

# 1) Create workspace (single source of truth project.yaml is generated here)
python3 $SKILL_DIR/scripts/init_project.py "Payment Refactor" --type project --methodology agile --framework scrum

# 2) Use a template to produce a risk register (prepare the data yaml first, then render)
python3 $SKILL_DIR/scripts/render.py \
  --template $SKILL_DIR/templates/common/risk_register.md \
  --data risks.yaml --out /workspace/payment-refactor/risks/risk_register.md

# 3) Export the formal Word document
python3 $SKILL_DIR/scripts/render_docx.py /workspace/payment-refactor/risks/risk_register.md
```

> Triggering via natural language is simpler: just tell the Agent "help me launch the payment refactor project using agile" -- no need to type commands manually.

---

## 4. Core Concepts

### 4.1 Single Source of Truth `project.yaml`
One `project.yaml` per project/program (located at the workspace root `/workspace/<slug>/project.yaml`). The main controller and all sub-agents read and write through it, ensuring consistent state and continuity across sessions. See [`references/project-schema.md`](references/project-schema.md) for the full field structure; see `examples/sample_project.yaml` for a sample.

### 4.2 Four-Dimension Classification (Determine First for Each Request)
| Dimension | Values |
|------|------|
| `type` | project / program |
| `methodology` | waterfall / agile / iteration / hybrid |
| `phase` | initiation / planning / execution / monitoring / closeout (programs have additional portfolio phases) |
| `intent` | planning / build / reporting / analysis / governance |

### 4.3 Three Execution Modes (Hybrid Dispatch)
| Mode | When to use | Approach |
|------|--------|------|
| **direct (do directly)** | Single artifact / explanation / tweak | Main controller calls scripts or templates directly to complete |
| **team (parallel teaming)** | Multiple independent artifacts (e.g., initiation needs charter+WBS+risk+RACI) | Dispatch dedicated sub-agents in parallel within the same message, aggregate + consistency check |
| **fork (continue context)** | Need full-context handoff (e.g., "continue from last risk analysis") | Sub-agent inherits the entire session context |

> **TeamCreate** is the multi-agent concurrent dispatch mechanism in this environment (the team mode of the Agent tool). See [`references/agents.md`](references/agents.md) for sub-agent roles and brief templates, and [`references/orchestration.md`](references/orchestration.md) for the dispatch decision tree.

### 4.4 Mandatory State Machine: Planning -> Baseline -> Operational Control
The mandatory serial discipline of `lifecycle_state` (see [`references/lifecycle.md`](references/lifecycle.md) section 5):

```
planning -> review -> baselined -> operational -> closed
```

- **waterfall / hybrid** must `baseline.py --freeze` (freeze plan as baseline) before entering execution/monitoring;
- Only after passing the control gate to set `lifecycle_state` to `operational` can you use `control_engine.py` for periodic inspection;
- A project that is not baselined (missing `baseline` pointer) must not enter the operational phase; the consistency gate will block it directly.

### 4.5 Phase Modules and Stage Gates (Phase Modules & Gates)
Initiation -> planning -> execution -> monitoring -> closeout is split into 4 phase modules (`references/phases/`), each defining that phase's **activities / required deliverables / entry criteria / exit criteria / stage gate approval checklist**, and adapted to each methodology. Transitions between phases are governed by `gate_engine.py` (hard gates reuse `consistency_check` / `control_engine`; if not passed, exit 1 refuses to advance):

- G0->1 initiation->planning (soft gate / PM)
- **G1->2 planning->execution (hard gate / sponsor)**: requires `consistency_check.py` exit 0 (waterfall/hybrid also require `baseline.py --freeze`)
- G2->3 execution->monitoring (soft gate / PM, concurrent within operational)
- **G3->4 monitoring->closeout (hard gate / sponsor)**: requires `control_engine.py` exit 0 + acceptance/retrospective deliverables + (program) benefits closure

See `lifecycle.md` section 6 and `references/phases/*`.

---

## 5. Standard Workflow (Follow Every Time)

- **Step 0 - Locate source of truth**: find `project.yaml`; if it does not exist -> `init_project.py` to build the skeleton.
- **Step 1 - Classify and route**: determine the four dimensions type / methodology / phase / intent; after determining `phase`, read the corresponding phase module (`references/phases/*`), advance per that module's activities/deliverables/criteria, and phase transitions must pass the `gate_engine.py` stage gate.
- **Step 2 - Read methodology manual**: read `references/methodology-*.md` per methodology (read `program-management.md` for programs).
- **Step 2.5 - Expert dispatch (break WBS down to leaf packages)**: `planner-agent` produces SOW-level summary packages; `dispatch.py` audits and generates a dispatch plan; domain-expert sub-agents break packages down to leaf level (<= `control.granularity_threshold` person-days, default 10).
- **Step 3 - Choose execution mode**: direct / team / fork (see section 4.3).
- **Step 4 - Build artifacts**: scaffolding + `render.py` render + mandatory analysis scripts (`schedule_health` / `evm`) + must pass `consistency_check.py` before delivery.
- **Step 5 - Team up (team mode only)**: TeamCreate dispatches dedicated sub-agents, main controller aggregates + consistency check.
- **Step 6 - Deliver**: update `artifacts` index; `render_docx.py` as needed; summarize artifact list + metrics card to the user.

---

## 6. Template Library (35 + `_macros.md`)

| Directory | Count | Templates |
|------|------|------|
| `common/` | 16 | project_charter, stakeholder_register, raci, communication_plan, raid_log, risk_register, status_report, lessons_learned, closure_report, project_board, milestone_list, change_request, change_log, baseline_record, control_register, control_report |
| `waterfall/` | 5 | requirements_spec, wbs, schedule_gantt, stage_gate_review, quality_plan |
| `agile/` | 5 | product_backlog, sprint_plan, definition_of_done, burndown, retro |
| `iteration/` | 3 | iteration_plan, iteration_backlog, iteration_review |
| `hybrid/` | 2 | hybrid_governance, macro_micro_map |
| `program/` | 4 | program_charter, portfolio_dashboard, dependency_map, benefits_realization |

Each template's **data-key contract** is in [`references/templates-index.md`](references/templates-index.md).

---

## 7. Script Quick Reference

All scripts are in `scripts/` and run with `python3`.

| Script | Purpose | Command example |
|------|------|----------|
| `init_project.py` | Build workspace + project.yaml | `python3 init_project.py "project-name" --type project --methodology agile --framework scrum [--domain <domain> --product <product>]` |
| `render.py` | Template + data -> Markdown | `python3 render.py --template T --data D.yaml --out O.md` |
| `render_docx.py` | Markdown -> DOCX | `python3 render_docx.py O.md [--out O.docx]` |
| `evm.py` | Earned value analysis | `python3 evm.py --data metrics.yaml` |
| `schedule_health.py` | Critical path / dependencies / float | `python3 schedule_health.py --project <project>/project.yaml`(or `--data schedule.yaml [--start 2025-08-01]`) |
| `consistency_check.py` | Pre-delivery quality gate (control-level, exit 1=block) | `python3 consistency_check.py --project <project>/project.yaml [--strict]` |
| `baseline.py` | Freeze plan as baseline (pre-gate) | `python3 baseline.py --freeze --project <project>/project.yaml`;`--status` to view status |
| `control_engine.py` | Operational control engine (periodic inspection against baseline, exit 1=RED escalation) | `python3 control_engine.py --project <project>/project.yaml [--as-of 2026-08-12] [--json]` |
| `dispatch.py` | Expert dispatch plan (audits WBS for missing role / over threshold) | `python3 dispatch.py --project <project>/project.yaml [--threshold 10] [--out dispatch_plan.md] [--json]` |
| `rollup_program_wbs.py` | Two-level program WBS (milestone level / component level) | `python3 rollup_program_wbs.py <program>/project.yaml [--derive-actuals]` |
| `project_state.py` | Single source of truth read/write | `python3 project_state.py get project.phase --file project.yaml` |
| `gate_engine.py` | Stage gate engine (evaluate/approve entry to target phase, hard gates reuse consistency/control) | `python3 gate_engine.py --project <project>/project.yaml --to execution [--approve "Zhang San(sponsor)"]`;`--status` to view current status and available gates |
| `test_gate_engine.py` | Stage gate engine unit-test suite (CI gate, 66 assertions covering 4 methodologies x soft/hard gate / rejected / dry-run / --status) | `python3 test_gate_engine.py` (no args; exit code 0=all pass, 1=failure, can hook into CI) |
| `comm_send.py` | External email approval gate (resolves `communication.contacts[]` recipients by role, enforces `--approve` then delegates to backend, writes `governance.communications` audit; `--dry-run` does not actually send) | `python3 comm_send.py --project <project>/project.yaml --to "sponsor,pm" --subject "Milestone reached" --body-file draft.md --approve "Zhang San(PM)"`;`--dry-run` reviews only |

> **Script exception handling**: if a script is missing / path is wrong / arguments are invalid, do not fail silently -- give a specific error and degrade to: (1) maintain `project.yaml` with `project_state.py`; (2) render templates directly with `render.py`; (3) if PyYAML is missing, first run `pip install pyyaml`.

---

## 8. Key Rules (Summary)

- **Never advice-only**: any request must produce a file or run analysis; at minimum update `project.yaml`.
- **Source of truth first**: if there is no `project.yaml`, run `init_project.py` first.
- **Match the methodology**: agile uses backlog/sprint/burndown, waterfall uses WBS/Gantt/stage gate.
- **Estimation mandatory**: every WBS / backlog row must have a numeric estimate (>0); placeholders are not allowed.
- **Expert dispatch + leaf-package granularity**: technical work packages must be broken down by the corresponding domain expert, tagged with `role` and `domain`, with leaf packages <= threshold.
- **Analysis mandatory**: run `schedule_health` before delivery for waterfall / hybrid; run `evm` during execution/monitoring.
- **Pass quality gate before delivery**: only allow if `consistency_check.py` exits 0; fatal items (missing estimate / schedule not networked / missing EVM baseline / hybrid missing micro-plan / risk not calibrated 5x5 / benefits missing owner / not baselined) block directly.
- **Planning != operationalization (mandatory serial)**: first planning -> review -> `baseline.py --freeze` -> control gate -> only then can you enter execution/monitoring.
- **Operational control loop**: after entering `operational`, run `control_engine.py` periodically per `control.cadence`, inspecting against the baseline; RED escalation exits code 1, can be hooked to scheduled-task alerts.
- **Phase transitions must pass stage gates (mandatory)**: initiation -> planning -> execution -> monitoring -> closeout advance serially per the state machine; entering `execution` (G1->2) and `closeout` (G3->4) are **hard gates**, which require `gate_engine.py` evaluation with all automated criteria passed and approval by sponsor before flipping `lifecycle_state`; `monitoring` (G2->3) is a **soft gate** (PM approval). Hard gates cannot be skipped (see `references/phases/*`, `lifecycle.md` section 6).

---

## 9. Extension Guide (No Engine Changes Needed)

1. **Add an artifact template**: place `my_template.md` in the corresponding directory (write placeholders using `render.py` syntax).
2. **Register data keys**: add a line in `references/templates-index.md` (template file / data key / description).
3. **Add a methodology**: create `references/methodology-xxx.md` + `templates/xxx/`, and register in SKILL.md routing table and templates-index.
4. **Add an analysis script**: place it in `scripts/`, then reference it in SKILL.md script quick-reference and the corresponding reference.

---

## 10. Program Specifics

- Use `init_project.py --type program` to build a portfolio-level workspace.
- Program charter / portfolio dashboard / cross-project dependency map / benefits realization plan are all program-specific templates.
- `rollup_program_wbs.py` two-levels the single-source `wbs`: program level = milestone level, component level = leaf work-package level; component/phase mapping first reads `program.components` / `governance.waves` in `project.yaml`, falling back to built-in examples by default.
- Program phases (portfolio definition / delivery / closeout) and the lifecycle state machine (planning->...->closed) are two orthogonal layers; see `lifecycle.md` section 5.3.

---

## 11. Reference Document Index

| File | When to read |
|------|--------|
| `references/orchestration.md` | Multi-agent dispatch, determine execution mode |
| `references/agents.md` | Dispatch dedicated sub-agents, write brief |
| `references/expert-roles.md` | Domain expert role catalog + system prompt |
| `references/activity-expert-map.md` | Activity->role routing, expert specialization, leaf-package granularity |
| `references/lifecycle.md` | Phase-deliverable matrix, lifecycle and state machine |
| `references/methodology-*.md` | Each methodology (waterfall/agile/iteration/hybrid) |
| `references/hybrid_playbook.md` | Hybrid practice: cadence/micro-plan/alignment review/change control |
| `references/risk-matrix.md` | Risk 5x5 calibration scale and color bands |
| `references/program-management.md` | Program (portfolio) management |
| `references/metrics.md` | EVM / burndown / health metric definitions |
| `references/project-schema.md` | Complete field structure and collaboration conventions for `project.yaml` |
| `references/templates-index.md` | Full template library list and data-key contract |
| `references/usage.md` | Full usage manual (end-to-end examples, prompt library) |
| `references/phases/p0-p1-initiation-planning.md` | P0+P1 initiation and planning phase module |
| `references/phases/p2-execution.md` | P2 execution phase module |
| `references/phases/p3-monitoring.md` | P3 monitoring phase module |
| `references/phases/p4-closeout.md` | P4 closeout phase module |

---

## 12. Version and Changes

Change history is in [`CHANGELOG.md`](CHANGELOG.md). Current version **1.3.6** (v1.2.0 introduced phase modules P0-P4 and the stage gate engine `gate_engine.py`; v1.2.1 synced this README; v1.2.2 added the `gate_engine.py` unit-test suite; v1.3.0 added **operational dual-track parallel** and the **external email approval gate**; v1.3.1 **desensitization**: removed real client names / vendor names and other sensitive information, unified into codenames (Client A / MPP data warehouse / codename ALPHA) to eliminate legal risk; v1.3.2 further desensitization: `rollup_program_wbs.py` sample mapping de-identified (SOW slug suffix stripped / Wave→Stream / removed FSAS·NOS·finance & protocol); v1.3.3 added English `README.en.md` and established the "Chinese-English bilingual doc sync" rule; v1.3.4 **mermaid rendering stability** + **SOW-level WBS mandatory expert decomposition**; v1.3.5 **WBS -> schedule deliverables (build_schedule/build_wbs)** + **per-SOW kick-off (build_sow_kickoff)** + **risk register color-code icons (sev_icon)**; v1.3.6 **program-level schedule (build_schedule --level program)** + **SOW sub-plan (--sow)** + **Mermaid milestone syntax fix** + **portfolio dashboard color icon (sev_icon)**; OpenClaw English pack runtime output anglicized).

> This English README is the canonical English README. A Chinese README is maintained in the source repository and the two are kept in sync (per the rule to sync the README on every skill change).

---

_PM Master - making project management truly "executable"._
