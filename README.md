# PM Master · Project & Program Management Skill

> A **project + program** management skill for PMs in the tech industry. Builder philosophy, executable, with a built-in template library and multi-Agent orchestration, supporting four delivery methodologies: **waterfall / agile / iteration / hybrid**.

- **Version**: 2.2.12
- **License**: MIT
- **Branch**: `openclaw` — the **OpenClaw-compatible** edition (English `SKILL.md`; sub-agent dispatch via the Agent tool). The Chinese/WorkBuddy edition lives on other branches; both share the same `scripts/`, `templates/`, and `references/`.
- **Positioning**: Every project/program request must produce a real artifact (file); advice-only responses are prohibited.

---

## 1. What Problems It Solves

Project delivery in the tech industry often gets stuck on three things: **inconsistent methodologies** (waterfall/agile/iteration/hybrid mixed arbitrarily), **no standard deliverables** (charter/WBS/risk/status reports each done their own way), and **unsustainable governance** (plans disconnected from execution, missing baselines, no periodic inspection). PM Master turns these three problems into an **executable engineering system**:

- Every request → a real file (Markdown, exportable to DOCX);
- Every project → a single source of truth `project.yaml`, continuous across sessions/Agents;
- Every discipline → a verifiable quality gate (consistency gate, decomposition critic, estimator calibration, baselining, operational control, artifact guard).

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
| Expert Decomposition | Domain experts break WBS down to leaf packages (`role`/`domain`, ≤ threshold person-days); `dispatch.py` audits, `critic_review.py` self-reviews | Planning |
| Estimator Calibration | Independent `estimator.py` calibrates leaf effort (parametric/three-point/analogous), flags divergence >20%, emits split-needed | Planning |
| Metrics Analysis | Earned value (EVM), schedule critical path, consistency check | Analysis scenarios |
| Multi-Agent Parallelism | Team up to produce mutually independent artifacts | Complex initiation / review |
| Dual-track Docs | Markdown source → DOCX formal document | Delivery / reporting |
| Phased Delivery | P0+P1 initiation & planning / P2 execution / P3 monitoring / P4 closeout phase modules; each phase defines activities/deliverables/criteria | Full lifecycle |
| Stage Gate Approval | `gate_engine` evaluates entry criteria + hard gates (execution/closeout) enforce approval, flipping the state machine | Phase transitions |
| Operational Artifact Guard (OAG) | Any operational change to `project.yaml` must re-render dependent deliverables; `artifact_guard.py` detects content-hash drift | Execution/Monitoring |
| External Communication & Email Approval | `communication_plan` registers the stakeholder contact book; `comm_send.py` enforces an approval gate + audit | Communication/Email |

---

## 3. Quick Start

### 3.1 Installation (OpenClaw)
Place the skill directory under OpenClaw's skills folder:

```bash
# for example
cp -r pm-master ~/.qclaw/skills/pm-master
```

The skill is automatically discovered per session — no extra installation needed. You can also install a distributed `pm-master.zip` via your OpenClaw skill installer.

> **Install-time configuration (policy/guardrails)**: The skill root `config.yaml` defines the sub-agent dispatch backend (`execution.subagent_mode`; use `agent` for OpenClaw's Agent-tool parallel dispatch, `fork` for cross-session context relay), plus email capability and security guardrails — `email.enabled` / `email.backend` / `email.default_from` / `email.requires_send_approval` (hard guardrail, cannot be disabled at project level). Project-level data (contact book/cadence) lives in the `communication:` block of `project.yaml`. See `references/project-schema.md` and `scripts/comm_send.py`.

### 3.2 Minimal Three-Step Workflow (Command Line)

```bash
SKILL_DIR=~/.qclaw/skills/pm-master

# 1) Build the workspace (the single source of truth project.yaml is generated here)
python3 $SKILL_DIR/scripts/init_project.py "Payment Refactor" --type project --methodology agile --framework scrum

# 2) Produce a risk register from a template (prepare the data yaml first, then render)
python3 $SKILL_DIR/scripts/render.py \
  --template $SKILL_DIR/templates/common/risk_register.md \
  --data risks.yaml --out "/workspace/Payment Refactor/risks/risk_register.md"

# 3) Export a formal Word document
python3 $SKILL_DIR/scripts/render_docx.py "/workspace/Payment Refactor/risks/risk_register.md"
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

> **Backend mapping** (`config.yaml` `execution.subagent_mode`): on **OpenClaw**, team mode maps to the **Agent tool** parallel dispatch (`agent`), and fork maps to `sessions_spawn context:"fork"`. The orchestrator only says "dispatch planner-agent / risk-agent …"; the platform maps that to the real mechanism. For sub-Agent roles and brief templates see [`references/agents.md`](references/agents.md); for the orchestration decision tree see [`references/orchestration.md`](references/orchestration.md); for the report contract see [`references/subagent-protocol.md`](references/subagent-protocol.md).

### 4.4 Mandatory State Machine: Plan → Baseline → Operational Control
The mandatory serial discipline of `lifecycle_state` (see [`references/lifecycle.md`](references/lifecycle.md) §5):

```
planning → review → baselined → operational → closed
```

- **waterfall / hybrid** **must** run `baseline.py --freeze` (freeze the plan as baseline) before entering execution/monitoring;
- Only after a control gate sets `lifecycle_state` to `operational` can `control_engine.py` be used for periodic inspection;
- Projects that are not baselined (missing `baseline` pointer) **may not** enter the operational phase; the consistency gate will block directly.

### 4.5 Phase Modules & Stage Gates
Initiation→Planning→Execution→Monitoring→Closeout is split into 4 phase modules (`references/phases/`), each defining the phase's **activities / mandatory deliverables / entry criteria / exit criteria / stage-gate approval checklist**, adapted per methodology. Transitions are governed by `gate_engine.py` (hard gates reuse `consistency_check` / `control_engine`; if not passed, exits 1 and refuses to proceed):

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
- **Step 2.5 · Expert dispatch (break WBS down to leaf packages)**: `planner-agent` produces SOW-level summary packages tagged with `domain`; `dispatch.py` audits and generates the (idempotent) dispatch plan; domain-expert sub-Agents break packages down to leaf level (≤ `control.granularity_threshold` person-days, default 10) with `role`/`domain`/`owner`/estimate/DoD/dependencies, written back to `project.yaml.wbs`. Domain activities missing `role` / over threshold make the consistency gate **fatal** — the orchestrator must not self-decompose to bypass it. Run `critic_review.py` (6-factor self-review) and set `decomposition.critic_passed=true` before proceeding.
- **Step 2.5b · Effort calibration (estimator-agent)**: Decomposition ≠ estimation. After experts decompose leaves, run `estimator.py` to calibrate effort with `parametric`/`three-point`/`analogous` methods + the shared calibration factor; it flags divergence >20% as `recalibrated`, emits `split-needed` if over threshold (no inflation), and writes back `effort`/`estimate_method`/`estimate_basis`/`estimate_confidence`/`estimate_flag` per leaf. The loop closes when `calibrate_estimates.py --global` reads closed-leaf `actual_effort` back into `references/estimate-calibration.yaml`.
- **Step 3 · Choose execution mode**: direct / team / fork (see §4.3).
- **Step 4 · Build artifacts**: scaffolding + `render.py` rendering + **mandatory analysis scripts** (`build_wbs` / `build_schedule` / `schedule_health` / `build_sow_kickoff` for planning; `evm` for execution) + **must pass `consistency_check.py`** before delivery + `artifact_guard.py` after every operational action.
- **Step 5 · Team up (team mode only)**: dispatch dedicated sub-Agents in the same message; each obeys `references/subagent-protocol.md`; the controller runs `subagent_check.py` on each report, sends failures back to fix, then aggregates and writes `project.yaml`.
- **Step 6 · Deliver**: Update the `artifacts` index; run `render_docx.py` as needed; summarize the artifact list + metrics card for the user.

---

## 6. Template Library (37 templates + `_macros.md`)

| Directory | Count | Templates |
|------|------|------|
| `common/` | 18 | project_charter, stakeholder_register, raci, communication_plan, raid_log, risk_register, status_report, lessons_learned, closure_report, project_board, milestone_list, change_request, change_log, baseline_record, control_register, control_report, estimate_report, dispatch_plan (+ others) |
| `waterfall/` | 5 | requirements_spec, wbs, schedule_gantt, stage_gate_review, quality_plan |
| `agile/` | 5 | product_backlog, sprint_plan, definition_of_done, burndown, retro |
| `iteration/` | 3 | iteration_plan, iteration_backlog, iteration_review |
| `hybrid/` | 2 | hybrid_governance, macro_micro_map |
| `program/` | 4 | program_charter, portfolio_dashboard, dependency_map, benefits_realization |

The **data-key contract** for each template is in [`references/templates-index.md`](references/templates-index.md).

---

## 7. Script Quick Reference

All scripts are under `scripts/`, run with `python3`.

| Script | Purpose | Example / When |
|------|------|----------|
| `init_project.py` | Build workspace + project.yaml (schema v2) | `init_project.py "Name" --type project --methodology agile --framework scrum [--domain <d> --product <p>]` |
| `project_state.py` | Single source of truth read/write/migrate/checkpoint | `project_state.py get project.phase --file project.yaml` |
| `render.py` | Template + data → Markdown | `render.py --template T --data D.yaml --out O.md` |
| `render_docx.py` | Markdown → DOCX | `render_docx.py O.md [--out O.docx]` |
| `rerender_docs.py` | Bulk re-render deliverables from source of truth | after `project.yaml` changes |
| `dispatch.py` | Expert dispatch plan (idempotent; flags missing role / over-threshold; emits `estimate` action) | before WBS decomposition (Step 2.5) |
| `critic_review.py` | WBS decomposition Critic self-review (6 factors: scope/milestone/payment/assumptions/constraints/dependencies) | after decomposition, before `consistency_check` |
| `estimator.py` | Effort calibration: recalibrate leaf effort, flag divergence >20%, emit split-needed | after decomposition (Step 2.5b), before `build_schedule` |
| `calibrate_estimates.py` | Feedback loop: closed-leaf `actual_effort` → shared `estimate-calibration.yaml` factors | on leaf closeout / retrospective |
| `parse_sow.py` | Parse a SOW into summary/leaf WBS packages with inferred domain/role | SOW-driven planning |
| `role_catalog.py` | Single source of truth for domain/role inference & specialization (imported by dispatch/consistency) | library (imported) |
| `build_wbs.py` | Render WBS view (`--view full|program|component`) | waterfall/hybrid planning |
| `build_schedule.py` | WBS→schedule+Gantt (`--level program`/`--sow <ID>`) | waterfall/hybrid planning |
| `build_sow_kickoff.py` | Per-SOW kickoff artifacts | waterfall/hybrid planning |
| `schedule_health.py` | Critical path / dependencies / float | `schedule_health.py --project <p>/project.yaml` |
| `sync_wbs.py` | Sync WBS edits back / keep views consistent | after manual WBS edits |
| `evm.py` | Earned value analysis (CPI/SPI) | execution/monitoring |
| `baseline.py` | Freeze plan as baseline (prerequisite quality gate) | `baseline.py --freeze --project <p>/project.yaml`; `--status` to view |
| `consistency_check.py` | Pre-delivery quality gate (control level, exit 1 = blocker) | **before every delivery**; `[--strict]` |
| `artifact_guard.py` | **OAG** operational artifact guard (content-hash drift; `--stamp` records source_hash for manual docs) | **after every operational action / before delivery** |
| `control_engine.py` | Operational control engine (periodic inspection vs baseline, exit 1 = RED escalation) | during operational (cadence) |
| `execution_driver.py` | Execution driver (executable list + self patrol) | during operational |
| `gate_engine.py` | Stage gate engine (evaluate/approve; hard gates reuse consistency/control) | `gate_engine.py --project <p> --to Execution [--approve "Name(sponsor)"]`; `--status` |
| `test_gate_engine.py` | Stage gate engine unit-test suite (CI gate, 66 assertions) | `test_gate_engine.py` (exit 0 = all pass) |
| `subagent_check.py` | Sub-agent output validation (report contract) | team-mode consolidation |
| `comm_send.py` | External email approval gate (resolves recipients by role, requires `--approve`, writes audit) | formal external comms; `--dry-run` to review |
| `confidentiality_check.py` | Pre-release scanner (text + byte-level binary scan for leaked absolute paths / sensitive tokens) | **before pushing to a shared branch** |
| `build_subproject.py` / `rollup_subprojects.py` / `rollup_program_wbs.py` | Sub-project scaffolding + program rollups (milestone level / component level) | program planning |

> ⚠️ **Script exception handling**: If a script is missing / path is wrong / arguments are invalid, do not fail silently — give a specific error, and degrade to: ① use `project_state.py` to maintain `project.yaml`; ② use `render.py` to render templates directly; ③ if PyYAML is missing, first run `pip install pyyaml`.

---

## 8. Key Rules (Summary)

- **Never advice-only**: Every request must produce a file or run analysis; at minimum update `project.yaml`.
- **Source of truth first**: If there's no `project.yaml`, run `init_project.py` first.
- **Use the right methodology**: agile uses backlog/sprint/burndown, waterfall uses WBS/Gantt/stage gates.
- **Estimation mandatory**: Every WBS / backlog row must have a numeric estimate (>0); placeholders are not allowed.
- **Expert dispatch + leaf-package granularity**: Technical-domain work packages must be broken down by the corresponding domain expert, tagged with `role` and `domain`, with leaf packages ≤ threshold; run `critic_review.py` and set `decomposition.critic_passed=true`.
- **Estimator calibration**: After decomposition run `estimator.py`; single-point guesses are flagged and calibrated with a defensible method + basis.
- **Analysis mandatory**: Run `build_wbs`/`build_schedule`/`schedule_health` before delivering waterfall / hybrid; run `evm` during execution/monitoring.
- **Pass the quality gate before delivery**: `consistency_check.py` must exit 0; fatal items (missing estimate / schedule not networked / missing EVM baseline / hybrid missing micro-plan / risk not calibrated 5×5 / benefit missing owner / not baselined / domain activity missing role or over threshold) are blocked directly.
- **Planning ≠ operationalization (mandatory serial)**: First plan → review → `baseline.py --freeze` → control gate → only then enter execution/monitoring.
- **Operational artifact guard (OAG, Iron Rule #12)**: In `operational`/`monitoring`, any change to `project.yaml` MUST re-render the dependent deliverable(s) and pass `artifact_guard.py` exit 0; stale/missing deliverables are blocked at closeout and flagged RED by `control_engine`.
- **Operational control loop**: After entering `operational`, run `control_engine.py` periodically per `control.cadence`; RED escalation exits 1 and can be wired to a scheduled alert.
- **Phase transitions must pass stage gates**: entering `Execution` (G1→2) and `Closeout` (G3→4) are **hard gates** requiring `gate_engine.py` evaluation + sponsor approval; hard gates cannot be skipped.
- **Confidentiality before release**: run `confidentiality_check.py` (exit 0) before pushing to any shared branch.

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
- `rollup_program_wbs.py` two-levels the single-source `wbs`: program level = milestone level, component level = leaf work-package level; component/phase mapping preferentially reads `program.components` / `governance.waves` from `project.yaml`.
- **Bottom-up rule (Iron Rule #11)**: plans/status/RAID/change-control are authored in each sub-project; the program view is a read-only scripted rollup (`rollup_subprojects.py`). Never hand-edit program-level RAID/status/`ev`/`ac` — fix the source sub-project and re-run the rollup. See `references/operation-model.md`.
- Program phases (Portfolio Definition/Delivery/Closeout) and the lifecycle state machine (planning→…→closed) are two orthogonal layers; see `lifecycle.md` §5.3.

---

## 11. Reference Index

| File | When to read |
|------|--------|
| `references/orchestration.md` | Multi-Agent orchestration, deciding execution mode |
| `references/agents.md` | Dispatch dedicated sub-Agents, write briefs |
| `references/subagent-protocol.md` | Sub-agent report JSON contract |
| `references/expert-roles.md` | Domain expert role catalog + system prompt |
| `references/activity-expert-map.md` | Activity→role routing, expert specialization, leaf-package granularity |
| `references/sow-parsing-playbook.md` | SOW parsing → WBS decomposition |
| `references/lifecycle.md` | Phase-deliverable matrix, lifecycle and state machine |
| `references/methodology-*.md` | Each methodology (waterfall/agile/iteration/hybrid) |
| `references/hybrid_playbook.md` | Hybrid practice: cadence/micro-plan/alignment review/change control |
| `references/risk-matrix.md` | Risk 5×5 calibration scale and color bands |
| `references/program-management.md` | Program (portfolio) management |
| `references/operation-model.md` | Bottom-up authoring & rollup model |
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

Full changelog history is in [`CHANGELOG.md`](CHANGELOG.md). **Current version 2.2.12.**

Recent highlights:
- **2.2.12** — Domain-agnostic role inference + SOW auto-alignment: new `scripts/role_catalog.py` single source of truth covering 10 technical domains + cross-domain roles; `dispatch.py` / `consistency_check.py` import it (removing duplicated keyword maps); `parse_sow.py` writes `domain` from SOW text with sensible fallbacks; legacy domains kept backward-compatible.
- **2.2.11** — Confidentiality review made byte-deep: new `confidentiality_check.py` recursively scans the whole package (text line-match + binary byte-scan, catching absolute paths embedded in `.pyc`); fixed as a mandatory pre-release gate.
- **2.2.x** — Estimator-agent effort calibration (`estimator.py` + `calibrate_estimates.py`), decomposition Critic (`critic_review.py`), Operational Artifact Guard (`artifact_guard.py`, Iron Rule #12), RAID assumptions render fix.
- **2.1.0–2.2.0** — v2 architectural rewrite into an *enforced operating manual*; restored v1.3.6 expert-dispatch workflow; wired the sub-agent protocol / execution driver / config knobs.
- **1.3.x** — Phase modules P0–P4 + stage-gate engine, operational dual-track parallelism, external email approval gate, desensitization, WBS→schedule deliverables, per-SOW kickoff, program-level scheduling, Mermaid stability, English/OpenClaw runtime output.

> **Doc sync rule**: Every skill change must keep `README.md`, `SKILL.md`, `CHANGELOG.md`, and the version number consistent. This `openclaw` branch ships the English `SKILL.md` (OpenClaw-compatible) as the canonical manual.

_PM Master · Making project management truly "executable."_
