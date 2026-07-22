# Dedicated Sub-Agent Role Definitions

Dedicated sub-Agents dispatched by the master controller in team mode. Each role has a single responsibility and clear inputs/outputs, making them easy to run in parallel without conflicts.
Sub-Agents **never reach the user directly**; they only produce files and report back to the master controller.

> Common constraint: all roles use `project_state.py` to read/write `<project>/project.yaml`, and use `render.py` to produce files;
> fill unknown fields with "(TBD)" and annotate them to avoid consistency-check failures.

## 1. planner-agent
- **Responsibility**: decompose scope → WBS / product Backlog / iteration plan; produce milestones and schedule.
- **Input**: `project.yaml`; methodology-specific plan templates (waterfall/wbs, agile/product_backlog, iteration/iteration_plan).
- **Output**: `plans/wbs.md` or `plans/product_backlog.md` etc.; write back `artifacts.wbs` / `artifacts.backlog`; `project.scope` / `metrics.burndown` (if applicable) in `project.yaml`.
- **brief essentials**: the WBS must cover all scope; each item has a unique ID, deliverable, owner, and effort estimate.

## 2. scheduler-agent
- **Responsibility**: turn the WBS/Backlog into a dependency-aware schedule, marking the critical path and milestone dates.
- **Input**: planner artifacts; `templates/waterfall/schedule_gantt.md`.
- **Output**: schedule data `plans/schedule.yaml` (for validation by `schedule_health.py`) + rendered Gantt notes.
- **brief essentials**: tasks include id/name/duration/deps; dependencies must point to existing task IDs.

## 3. risk-agent
- **Responsibility**: identify risks/assumptions/issues/dependencies (RAID), rate each risk by probability × impact, assign an owner, and write mitigation measures.
- **Input**: `project.yaml`; `templates/common/risk_register.md`, `templates/common/raid_log.md`.
- **Output**: `risks/risk_register.md`, `risks/raid_log.md`; write back `raid.risks[]` (with owner, mitigation), `artifacts.risk`.
- **brief essentials**: every risk must have an owner and mitigation, otherwise the consistency check fails.

## 4. stakeholder-agent
- **Responsibility**: map stakeholders, build the RACI, and define the communication plan.
- **Input**: `project.yaml`; `templates/common/stakeholder_register.md`, `templates/common/raci.md`, `templates/common/communication_plan.md`.
- **Output**: `docs/stakeholder_register.md`, `docs/raci.md`, `docs/communication_plan.md`; write back `project.sponsor` / `project.pm` / `project.team[]`.
- **brief essentials**: sponsor and pm must be explicit (mandatory quality gate item).
- **Contact-book sync (critical)**: after finalizing the "stakeholder contact book" in `communication_plan.md`, you **must sync every row into `communication.contacts[]` in `project.yaml`** (using `project_state.py set communication.contacts '<yaml>'`). This is the machine-readable recipient library for email communication—`communication-agent` / `comm_send.py` only reads `project.yaml`, not Markdown. Fields: `{ name, role, org, email, phone, tz, note }`; `email` is required.

## 5. reporter-agent
- **Responsibility**: aggregate progress, produce status reports/retrospectives/closure reports, and compute health-metric cards.
- **Input**: `project.yaml` + all artifacts; `templates/common/status_report.md`, `templates/common/closure_report.md`, `templates/common/lessons_learned.md`.
- **Output**: `reports/status_report.md` etc.; if evm data is provided, run `evm.py` to attach a metrics card.
- **brief essentials**: the status report must include current progress / variance / risks / next-period plan / help needed.

## 6. program-agent
- **Responsibility**: portfolio-level governance—portfolio charter, portfolio dashboard, cross-project dependency map, benefits realization plan.
- **Input**: `project.yaml` (type=program); `templates/program/*`.
- **Output**: `docs/program_charter.md`, `reports/portfolio_dashboard.md`, `risks/dependency_map.md`, `reports/benefits_realization.md`; write back `program.projects[]` / `program.dependencies[]` / `program.benefits[]`.
- **brief essentials**: focus on "dependencies, coordination, benefits" rather than single-project details.

## 6b. estimator-agent (effort-calibration · cross-cutting)
- **Responsibility**: independently calibrate the **effort** of each domain-activity leaf after experts decompose it. Does NOT decompose work. Picks one method per leaf (three-point / parametric / analogous / expert), applies the shared `(role,domain)` calibration factor, and flags divergence >20% from the decomposer's original estimate as `recalibrated`. Never invents actuals; missing history ⇒ `estimate_confidence=low`. If calibrated effort would exceed the granularity threshold, emits `split-needed` (no inflation) for the master to re-dispatch decomposition.
- **Why a separate agent**: decomposition ≠ estimation. The expert who breaks work into leaves also throws a single point estimate with no method/bias-check. `estimator-agent` is the independent second opinion that closes this gap (root cause R1–R5 in the estimator design doc).
- **Input**: `project.yaml` (decomposed `wbs` with `role`/`domain`); `scripts/role_catalog.py` (parametric anchors + shared calibration table).
- **Output**: writes back per leaf `effort` / `estimate_method` / `estimate_basis` / `estimate_o`/`estimate_p` / `estimate_confidence` / `estimate_source` / `estimate_flag` (and `estimate` as a backward-compatible alias); `plans/estimate_report.md` (via `render.py`); console key findings for the master to aggregate.
- **How dispatched**: `dispatch.py` emits an `estimate` action for every domain-activity leaf missing `effort`/`estimate_method`; the master runs `scripts/estimator.py --project <project.yaml>` after expert decomposition and before `build_schedule.py`.
- **Guardrails (hard)**: read `project.yaml` first (source of truth); numeric `effort>0` only; method ∈ {three-point, parametric, analogous, expert}; `estimate_basis` mandatory when `effort ≥ 5pd`; missing history ⇒ `estimate_confidence=low` (never fabricated); divergence >20% must be flagged, not silently accepted; independent of the decomposer (no self-approval); render via `render.py`; report only to master; never modify other agents' files.
- **Complementary**: `consistency_check.py` §7e adds estimate-quality warnings; `critic_review.py` §7 adds an effort-sanity lens; `calibrate_estimates.py` feeds closed-leaf `actual_effort` back into the shared factor table.
- [ ] All role artifact files have been generated
- [ ] `consistency_check.py` passes (risks have owner/mitigation, pm/sponsor filled, dependencies complete)
- [ ] `artifacts` index has been written back
- [ ] `render_docx.py` renders the formal document when needed

## 8. communication-agent (Communication / Email Agent)

> A formal email is an **external, irreversible, security-sensitive** action. This role only drafts and orchestrates; it **never sends on its own**—
> any send must go through explicit approval (see the hard approval gate in `scripts/comm_send.py` and `requires_send_approval` in the skill-root `config.yaml`).

- **Responsibility**: based on the communication plan and contact book, draft formal emails (status notifications, milestone reminders, risk escalations, change notices, etc.), send them after approval, and record the audit trail.
- **Input**: `communication.contacts[]` (recipient library) in `project.yaml`, `email.*` (backend/sender/approval guardrails) in `config.yaml`, and reusable notification templates in `templates/` (e.g., `status_report` / `closure_report` summaries).
- **Output**: drafted email drafts (presented to the user for confirmation); after approval, call the email skill / `comm_send.py` to actually send; the send record is written to `governance.communications[]` (audit: `to / subject / on / approved_by / backend / status`).
- **Standard flow (mandatory)**:
  1. **Draft**: resolve recipients by role (e.g., `sponsor,pm` → look up `communication.contacts[]` to get emails), write the body.
  2. **Present for approval**: hand "recipients + subject + body summary" to the user/PM and **wait for explicit approve**.
  3. **Send after approval**: `python3 $SKILL_DIR/scripts/comm_send.py --project <project>/project.yaml --to <role or email> --subject "..." --body-file <draft.md> --approve "Zhang San(PM)"`. Without `--approve`, or when the install guardrail requires sponsor co-signature and the approver does not include the sponsor → the script directly `exit 1` and **does not send**.
  4. **Audit**: after a successful send / dry-run, `comm_send.py` automatically appends a `governance.communications` record for traceability.
- **brief essentials**: the email body must include the project name and explicit action items/deadlines; external emails (recipients not in `contacts` or `approval_override.require_sponsor_cosign=true`) must be escalated to sponsor co-signature; under no circumstances may the approval gate be bypassed.

## 9. monitoring-agent (Monitoring / Control Agent)

> The "monitoring track" of the operational dual-track (see `references/orchestration.md §3.4`). Runs in parallel with the execution track; it only "watches" and does not produce deliverables itself.

- **Responsibility**: on the `control.cadence` cycle, run `control_engine.py` to inspect against the baseline; produce `status_report` / `control_report`; roll-update `risk_register` / `raid_log` / `milestone_list`; report RED escalation items back to the master controller.
- **Input**: `project.yaml` (must already be `operational` with `baseline.file` present), `baselines/`, all artifacts.
- **Output**: `reports/status_report.md`, `artifacts/control_report.md`, `risks/raid_log.md` (rolling); write back `raid.risks[]` / `raid.issues[]` status.
- **brief essentials**: only read the baseline, write control/status reports and RAID updates; **do not touch** the execution track's deliverables; upon finding a RED escalation, immediately flow it back to the master controller, which routes corrective action back to the execution track.
