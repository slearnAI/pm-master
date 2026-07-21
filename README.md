# PM Master · Project & Program Management Skill

> A **project + program** management skill for PMs in the tech industry. Builder philosophy, executable, with a built-in template library and multi-Agent orchestration, supporting four delivery methodologies: **waterfall / agile / iteration / hybrid**.

- **Version**: 2.1.0
- **License**: MIT
- **Positioning**: Every project/program request must produce a real artifact (file); advice-only responses are prohibited.

---

## 1. What Problems It Solves

Project delivery in the tech industry often gets stuck on three things: **inconsistent methodologies** (waterfall/agile/iteration/hybrid mixed arbitrarily), **no standard deliverables** (charter/WBS/risk/status reports each done their own way), and **unsustainable governance** (plans disconnected from execution, missing baselines, no periodic inspection). PM Master turns these three problems into a **executable engineering system**:

- Every request → a real file (Markdown, exportable to DOCX);
- Every project → a single source of truth `project.yaml`, continuous across sessions/Agents;
- Every discipline → a verifiable quality gate (consistency gate, baselining, operational control).

---

## 2. Core Capabilities

| Capability | Description | Applies To |
|------|------|------|
| Project Initiation / Planning | Charter, stakeholders, RACI, WBS, schedule, risk, RAID | Any methodology |
| Agile Delivery | Product Backlog, Sprint Plan, DoD, burndown, retrospective | agile |
| Iteration Delivery | Iteration Plan / Backlog / Review | iteration |
| Waterfall Delivery | Requirements Spec, WBS, Gantt, stage gates, quality plan | waterfall |
| Hybrid Governance | Governance map, macro-micro mapping | hybrid |
| Program Governance | Portfolio charter, portfolio dashboard, dependency map, benefits realization | program |
| Metrics Analysis | Earned value (EVM), schedule critical path, consistency check | Analysis scenarios |
| Multi-Agent Parallelism | Team up to produce mutually independent artifacts | Complex initiation / review |
| Dual-track Docs | Markdown source → DOCX formal document | Delivery / reporting |
| Phased Delivery | P0+P1 initiation & planning / P2 execution / P3 monitoring / P4 closeout phase modules; each phase defines activities/deliverables/criteria | Full lifecycle |
| Stage Gate Approval | `gate_engine` evaluates entry criteria + hard gates (execution/closeout) enforce approval, flipping the state machine | Phase transitions |
| Operational Dual-track Parallel | P2 execution track (domain experts) + P3 monitoring track (`monitoring-agent`) multi-Agent parallel, sharing the source of truth with zero field conflicts | Execution/Monitoring |
| External Communication & Email Approval | `communication_plan` registers the stakeholder contact book; `communication-agent` drafts, `comm_send.py` enforces an approval gate + audit, with layered configuration (install-time guardrails / project-time data) | Communication/Email |

---

## 3. Quick Start

### 3.1 Installation
Place the skill directory under CodeBuddy's `skills/`:

```bash
# for example
cp -r pm-master /root/.codebuddy/skills/pm-master
```

The skill is automatically available per session, no extra installation needed. You can also extract the distributed `pm-master.zip` directly into that directory.

> **Install-time configuration (policy/guardrails)**: The skill root `config.yaml` defines email capability and security guardrails — `email.enabled` / `email.backend` (agent-mail·himalaya·gog·smtp) / `email.default_from` / `email.requires_send_approval` (hard guardrail, cannot be disabled at project level). Fill in as needed during install; project-level data (contact book/cadence) lives in the `communication:` block of `project.yaml`. See `references/project-schema.md` and `scripts/comm_send.py` for details.

### 3.2 Minimal Three-Step Workflow (Command Line)

```bash
SKILL_DIR=/root/.codebuddy/skills/pm-master

# 1) Build the workspace (the single source of truth project.yaml is generated here)
python3 $SKILL_DIR/scripts/init_project.py "Payment Refactor" --type project --methodology agile --framework scrum

# 2) Produce a risk register from a template (prepare the data yaml first, then render)
python3 $SKILL_DIR/scripts/render.py \
  --template $SKILL_DIR/templates/common/risk_register.md \
  --data risks.yaml --out /workspace/Payment Refactor/risks/risk_register.md

# 3) Export a formal Word document
python3 $SKILL_DIR/scripts/render_docx.py /workspace/Payment Refactor/risks/risk_register.md
```

> Natural-language triggers are simpler: just tell the Agent "Use agile to help me initiate the payment refactor project" — no need to type commands manually.

---

## 4. Core Concepts

### 4.1 Single Source of Truth `project.yaml`
One `project.yaml` per project/program (located at the workspace root `/workspace/<slug>/project.yaml`). The controller and all sub-Agents read and write through it, ensuring consistent state and continuity across sessions. For the full field structure see [`references/project-schema.md`](references/project-schema.md); for an example see `examples/sample_project.yaml`.

### 4.2 Four-Dimension Classification (decide per request first)
| Dimension | Values |
|------|------|
| `type` | project / program |
| `methodology` | waterfall / agile / iteration / hybrid |
| `phase` | Initiation / Planning / Execution / Monitoring / Closeout (programs additionally have portfolio phases) |
| `intent` | Planning / Build / Report / Analysis / Governance |

### 4.3 Three Execution Modes (Hybrid Orchestration)
| Mode | When to use | Approach |
|------|--------|------|
| **direct (do it yourself)** | Single artifact / explanation / fine-tuning | The controller directly calls scripts or templates to complete it |
| **team (parallel teaming)** | Multiple independent artifacts (e.g., initiation needs charter+WBS+risk+RACI) | Dispatch dedicated sub-Agents in parallel within the same message, then aggregate + consistency check |
| **fork (continue context)** | Needs full-context handoff (e.g., "continue from last risk analysis") | Sub-Agent inherits the entire context of this session |

> **TeamCreate** is this environment's multi-Agent concurrent dispatch mechanism (the team mode of the Agent tool). For sub-Agent roles and brief templates see [`references/agents.md`](references/agents.md); for the orchestration decision tree see [`references/orchestration.md`](references/orchestration.md).

### 4.4 Mandatory State Machine: Plan → Baseline → Operational Control
The mandatory serial discipline of `lifecycle_state` (see [`references/lifecycle.md`](references/lifecycle.md) §5):

```
planning → review → baselined → operational → closed
```

- **waterfall / hybrid** **must** run `baseline.py --freeze` (freeze the plan as baseline) before entering execution/monitoring;
- Only after a control gate sets `lifecycle_state` to `operational` can `control_engine.py` be used for periodic inspection;
- Projects that are not baselined (missing `baseline` pointer) **may not** enter the operational phase; the consistency gate will block directly.

### 4.5 Phase Modules & Stage Gates (Phase Modules & Gates)
Initiation→Planning→Execution→Monitoring→Closeout is split into 4 phase modules (`references/phases/`), each defining the phase's **activities / mandatory deliverables / entry criteria / exit criteria / stage-gate approval checklist**, adapted per methodology. Transitions between phases are governed by `gate_engine.py` (hard gates reuse `consistency_check` / `control_engine`; if not passed, exits 1 and refuses to proceed):

- G0→1 Initiation→Planning (soft gate / PM)
- **G1→2 Planning→Execution (hard gate / sponsor)**: requires `consistency_check.py` exit 0 (waterfall/hybrid additionally require `baseline.py --freeze`)
- G2→3 Execution→Monitoring (soft gate / PM, parallel within operational)
- **G3→4 Monitoring→Closeout (hard gate / sponsor)**: requires `control_engine.py` exit 0 + acceptance/retrospective deliverables + (program) benefits closure

See `lifecycle.md` §6 and `references/phases/*` for details.

---

## 5. Standard Workflow (follow every time)

- **Step 0 · Locate the source of truth**: Find `project.yaml`; if it doesn't exist → `init_project.py` builds the skeleton.
- **Step 1 · Classify & route**: Determine the four dimensions type / methodology / phase / intent; once `phase` is determined, read the corresponding phase module (`references/phases/*`) and proceed per its activities/deliverables/criteria; transitions between phases must pass `gate_engine.py` stage gates.
- **Step 2 · Read the methodology manual**: Per methodology read `references/methodology-*.md` (for programs read `program-management.md`).
- **Step 2.5 · Expert dispatch (break WBS down to leaf packages)**: `planner-agent` produces SOW-level summary packages; `dispatch.py` audits and generates the dispatch plan; domain-expert sub-Agents break packages down to leaf level (≤ `control.granularity_threshold` person-days, default 10).
- **Step 3 · Choose execution mode**: direct / team / fork (see §4.3).
- **Step 4 · Build artifacts**: scaffolding + `render.py` rendering + **mandatory analysis scripts** (`schedule_health` / `evm`) + **must pass `consistency_check.py`** before delivery.
- **Step 5 · Team up (team mode only)**: TeamCreate dispatches dedicated sub-Agents; the controller aggregates + consistency check.
- **Step 6 · Deliver**: Update the `artifacts` index; run `render_docx.py` as needed; summarize the artifact list + metrics card for the user.

---

## 6. Template Library (35 templates + `_macros.md`)

| Directory | Count | Templates |
|------|------|------|
| `common/` | 16 | project_charter, stakeholder_register, raci, communication_plan, raid_log, risk_register, status_report, lessons_learned, closure_report, project_board, milestone_list, change_request, change_log, baseline_record, control_register, control_report |
| `waterfall/` | 5 | requirements_spec, wbs, schedule_gantt, stage_gate_review, quality_plan |
| `agile/` | 5 | product_backlog, sprint_plan, definition_of_done, burndown, retro |
| `iteration/` | 3 | iteration_plan, iteration_backlog, iteration_review |
| `hybrid/` | 2 | hybrid_governance, macro_micro_map |
| `program/` | 4 | program_charter, portfolio_dashboard, dependency_map, benefits_realization |

The **data-key contract** for each template is in [`references/templates-index.md`](references/templates-index.md).

---

## 7. Script Quick Reference

All scripts are under `scripts/`, run with `python3`.

| Script | Purpose | Example Command |
|------|------|----------|
| `init_project.py` | Build workspace + project.yaml | `python3 init_project.py "Project name" --type project --methodology agile --framework scrum [--domain <domain> --product <product>]` |
| `render.py` | Template + data → Markdown | `python3 render.py --template T --data D.yaml --out O.md` |
| `render_docx.py` | Markdown → DOCX | `python3 render_docx.py O.md [--out O.docx]` |
| `evm.py` | Earned value analysis | `python3 evm.py --data metrics.yaml` |
| `schedule_health.py` | Critical path / dependencies / float | `python3 schedule_health.py --project <project>/project.yaml` (or `--data schedule.yaml [--start 2025-08-01]`) |
| `consistency_check.py` | Pre-delivery quality gate (control level, exit 1 = blocker) | `python3 consistency_check.py --project <project>/project.yaml [--strict]` |
| `baseline.py` | Freeze plan as baseline (prerequisite quality gate) | `python3 baseline.py --freeze --project <project>/project.yaml`; `--status` to view status |
| `control_engine.py` | Operational control engine (periodic inspection against baseline, exit 1 = RED escalation) | `python3 control_engine.py --project <project>/project.yaml [--as-of 2026-08-12] [--json]` |
| `dispatch.py` | Expert dispatch plan (audits WBS for missing role / over-threshold) | `python3 dispatch.py --project <project>/project.yaml [--threshold 10] [--out dispatch_plan.md] [--json]` |
| `rollup_program_wbs.py` | Program WBS two-level rollup (milestone level / component level) | `python3 rollup_program_wbs.py <program>/project.yaml [--derive-actuals]` |
| `project_state.py` | Single source of truth read/write | `python3 project_state.py get project.phase --file project.yaml` |
| `gate_engine.py` | Stage gate engine (evaluate/approve entry into target phase; hard gates reuse consistency/control) | `python3 gate_engine.py --project <project>/project.yaml --to Execution [--approve "Zhang San(sponsor)"]`; `--status` shows current state and available gates |
| `test_gate_engine.py` | Stage gate engine unit-test suite (CI gate, 66 assertions covering 4 methodologies × soft/hard gates / rejected / dry-run / --status) | `python3 test_gate_engine.py` (no args; exit code 0 = all pass, 1 = failure, can be wired to CI) |
| `comm_send.py` | External email approval gate (resolves `communication.contacts[]` recipients by role, requires `--approve` before delegating to backend, writes `governance.communications` audit; `--dry-run` does not actually send) | `python3 comm_send.py --project <project>/project.yaml --to "sponsor,pm" --subject "Milestone achieved" --body-file draft.md --approve "Zhang San(PM)"`; `--dry-run` only reviews |

> ⚠️ **Script exception handling**: If a script is missing / path is wrong / arguments are invalid, do not fail silently — give a specific error, and degrade to: ① use `project_state.py` to maintain `project.yaml`; ② use `render.py` to render templates directly; ③ if PyYAML is missing, first run `pip install pyyaml`.

---

## 8. Key Rules (Summary)

- **Never advice-only**: Every request must produce a file or run analysis; at minimum update `project.yaml`.
- **Source of truth first**: If there's no `project.yaml`, run `init_project.py` first.
- **Use the right methodology**: agile uses backlog/sprint/burndown, waterfall uses WBS/Gantt/stage gates.
- **Estimation mandatory**: Every WBS / backlog row must have a numeric estimate (>0); placeholders are not allowed.
- **Expert dispatch + leaf-package granularity**: Technical-domain work packages must be broken down by the corresponding domain expert, tagged with `role` and `domain`, with leaf packages ≤ threshold.
- **Analysis mandatory**: Run `schedule_health` before delivering waterfall / hybrid; run `evm` during execution/monitoring.
- **Pass the quality gate before delivery**: `consistency_check.py` must exit 0 to pass; fatal items (missing estimate / schedule not networked / missing EVM baseline / hybrid missing micro-plan / risk not calibrated 5×5 / benefit missing owner / not baselined) are blocked directly.
- **Planning ≠ operationalization (mandatory serial)**: First plan → review → `baseline.py --freeze` → control gate → only then enter execution/monitoring.
- **Operational control loop**: After entering `operational`, run `control_engine.py` periodically per `control.cadence` to inspect against the baseline; RED escalation exits with code 1 and can be wired to a scheduled alert.
- **Phase transitions must pass stage gates (mandatory)**: Initiation→Planning→Execution→Monitoring→Closeout advances serially per the state machine; entering `Execution` (G1→2) and `Closeout` (G3→4) are **hard gates** that require `gate_engine.py` evaluation with all automated criteria passing and sponsor approval before flipping `lifecycle_state`; `Monitoring` (G2→3) is a **soft gate** (PM approval). Hard gates cannot be skipped (see `references/phases/*`, `lifecycle.md` §6).

---

## 9. Extension Guide (no engine changes needed)

1. **Add an artifact template**: Place `my_template.md` in the relevant directory (use `render.py` syntax for placeholders).
2. **Register data keys**: Add a line in `references/templates-index.md` (template file / data key / description).
3. **Add a methodology**: Create `references/methodology-xxx.md` + `templates/xxx/`, and register them in the SKILL.md routing table and templates-index.
4. **Add an analysis script**: Place it in `scripts/`, and reference it in the SKILL.md script quick-reference and the corresponding reference.

---

## 10. Program-Specific

- Use `init_project.py --type program` to build the portfolio-level workspace.
- Portfolio charter / portfolio dashboard / cross-project dependency map / benefits realization plan are all program-specific templates.
- `rollup_program_wbs.py` two-levels the single-source `wbs`: program level = milestone level, component level = leaf work-package level; component/phase mapping preferentially reads `program.components` / `governance.waves` from `project.yaml`, falling back to built-in examples by default.
- Program phases (Portfolio Definition/Delivery/Closeout) and the lifecycle state machine (planning→…→closed) are two orthogonal layers; see `lifecycle.md` §5.3 for details.

---

## 11. Reference Index

| File | When to read |
|------|--------|
| `references/orchestration.md` | Multi-Agent orchestration, deciding execution mode |
| `references/agents.md` | Dispatch dedicated sub-Agents, write briefs |
| `references/expert-roles.md` | Domain expert role catalog + system prompt |
| `references/activity-expert-map.md` | Activity→role routing, expert specialization, leaf-package granularity |
| `references/lifecycle.md` | Phase-deliverable matrix, lifecycle and state machine |
| `references/methodology-*.md` | Each methodology (waterfall/agile/iteration/hybrid) |
| `references/hybrid_playbook.md` | Hybrid practice: cadence/micro-plan/alignment review/change control |
| `references/risk-matrix.md` | Risk 5×5 calibration scale and color bands |
| `references/program-management.md` | Program (portfolio) management |
| `references/metrics.md` | EVM / burndown / health metric definitions |
| `references/project-schema.md` | `project.yaml` full field structure and collaboration conventions |
| `references/templates-index.md` | Full template library list and data-key contract |
| `references/usage.md` | Full usage manual (end-to-end examples, prompt library) |
| `references/phases/p0-p1-initiation-planning.md` | P0+P1 initiation & planning phase module |
| `references/phases/p2-execution.md` | P2 execution phase module |
| `references/phases/p3-monitoring.md` | P3 monitoring phase module |
| `references/phases/p4-closeout.md` | P4 closeout phase module |

---

## 12. Version & Changes

Changelog history is in [`CHANGELOG.md`](CHANGELOG.md). Current version **2.2.0** (v1.2.0 introduced phase modules P0–P4 and the stage-gate engine `gate_engine.py`; v1.2.1 synced this README; v1.2.2 added the `gate_engine.py` unit-test suite; v1.3.0 added **operational dual-track parallelism** and the **external email approval gate**; v1.3.1 **desensitization**: removed real customer names / vendor names and other sensitive info, unified into code names (Customer A / MPP data warehouse / code name ALPHA) to eliminate legal risk; v1.3.2 further desensitization: de-identified `rollup_program_wbs.py` example mappings (SOW slug suffix stripped / Wave→Stream / removed 客户系统A·客户系统B·示例主题域); v1.3.3 added the English `README.en.md` and established the "Chinese and English bilingual doc sync" rule; v1.3.4 **Mermaid rendering stability + SOW-level WBS mandatory expert breakdown**; v1.3.5 **WBS→schedule deliverables (build_schedule/build_wbs) + per-SOW kickoff (build_sow_kickoff) + risk register color icons (sev_icon)**; v1.3.6 **program-level scheduling (build_schedule --level program) + SOW sub-plan (--sow) + Mermaid milestone syntax fix + portfolio dashboard color icons (sev_icon); OpenClaw English package runtime output anglicized**).

> **Doc sync rule**: Every skill change must sync-update both `README.md` (Chinese) and `README.en.md` (English), and stay consistent with `SKILL.md` / `CHANGELOG.md` / version number; the English version is generated from the same source as the pure-English OpenClaw skill package.

_PM Master · Making project management truly "executable."_
