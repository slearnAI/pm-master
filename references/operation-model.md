# Operation Model · Bottom-Up Authoring & Rollup (canonical)

> This is a **skill-level operating principle**, not specific to any one program. Every program/project
> governed by PM Master follows it. It resolves the recurring failure mode where program-level RAID/status/
> plans are hand-maintained in parallel with sub-projects and silently drift out of sync.

## 1. The Principle (one sentence)

**Everything is authored at the lowest owning unit (the component / sub-project / SOW level); the program
level is a *read-only rollup view* produced by a script — never a hand-edited source of truth.**

## 2. What "author at project level" covers

For each sub-project (`subprojects/<slug>/project.yaml`), the owning PM is the **single writer** of:

| Artifact | Where authored | Where it rolls up |
|----------|----------------|-------------------|
| **Plan / WBS / schedule** | sub-project `wbs` (leaf packages, `tier: component`) | program `wbs` holds only milestone summary rows (`tier: program`, `milestone: true`) |
| **Status report** | sub-project `actuals.wbs_progress` + `progress.narrative` + `reports/status_report.md` | program status = rollup of sub-project progress |
| **RAID** | sub-project `raid.risks / assumptions / issues / dependencies` + top-level `risks` | program RAID = consolidated register (rollup), not re-keyed by hand |
| **Change control** | sub-project `change_log` + `actuals.cr_refs` (each CR filed where the change happens) | program `change_log` = consolidated registry of all component CRs |
| **Progress / actuals** | sub-project `actuals.wbs_progress` (leaf %), `ev`, `ac`, `as_of` | program `actuals.wbs_progress` (milestone %) + `ev/ac` = sum |

The program `project.yaml` itself only *authors*: the program charter, the `program.projects[]` index,
the `program.sow_map[]` / `contracts[]` / `extracts[]` mapping tables, and the milestone summary rows whose
`leaves:` lists point at component leaves. **It does not re-author component detail.**

## 3. What "aggregate to program level" means (and how)

Aggregation is **unidirectional and scripted** — it always flows sub-project → program, never the reverse:

```
sub-project A  ┐
sub-project B  ├─►  rollup_subprojects.py --program <program_dir>
sub-project C  ┘       → reads each subprojects/<sow>/project.yaml (read-only)
                         → per sub-project: milestone done/total + BAC/EV/AC/EAC/CPI
                         → prints (or --json exports) a program-level aggregate view
                           (master is NOT mutated)
```

- After rollup, run `control_engine.py --project <program.yaml> --as-of <date>` for the program-level
  health dashboard (CPI/SPI, risk drift, milestone slippage, RAID issues, change volume).
- Program-level **status_report** / **portfolio_dashboard** are *rendered* from the rolled-up
  `actuals`, not typed by hand.

### Two-tier (single-file) variant
If the program does **not** use full sub-project split (Option B — leaves kept in one `project.yaml` with
`leaves:` sub-lists), use `scripts/rollup_program_wbs.py` with `--derive-actuals` instead. Same principle:
leaf actuals are the source; milestone actuals are derived.

## 4. Hard Rules (consistency guards)

1. **Never hand-edit a rolled-up field.** If a program-level milestone `%`, `ev`, `ac`, or RAID count looks
   wrong, fix the *source sub-project* and re-run the rollup. Editing the rolled-up number directly breaks
   single-source-of-truth and will be flagged.
2. **RAID is not duplicated.** The program RAID is a rollup/consolidation of sub-project RAIDs. Do not maintain
   a separate parallel program RAID that people also edit — that is the drift bug.
3. **Change control originates at the component.** A change is filed in the sub-project where the work lives
   (or raised there and escalated). The program `change_log` is the *registry*, not the origination point.
   Program-level CCB approves cross-component / program-scope changes; single-component CRs are approved by
   the component PM and surfaced upward.
4. **Re-baseline after rollup, not before.** Rollup first (captures real progress), then `baseline.py --freeze`
   snapshots the program baseline. Operational control (`control_engine`) runs against that baseline.
5. **Cadence = rollup → control.** Periodic program oversight is always: run rollup, then control engine, then
   render the dashboard. No manual "update the program status" step.

## 4.6 Operational Artifact Guardrail (OAG) — 每次动作必须刷新交付物

> **这是运营期不可妥协的护栏（Iron Rule #12）。** 示例客户项目曾因在运营期忽略该护栏，导致 `raid_log`
> / `risk_register` / `portfolio_dashboard` 落后于事实源数周，直到人工发现 —— 属于护栏违规，不是小瑕疵。

**规则**：在 `operational` / `monitoring` 阶段，任何对 `project.yaml` 的变更动作（状态 / EVM / RAID /
WBS / actuals）都必须伴随对应交付物的重新渲染，并通过 `scripts/artifact_guard.py` 校验（exit 0）。

**机制（可执行，非口头）**：
- 每次渲染（`build_subproject.py` / `rerender_docs.py`）会向 `project.yaml` 的 `artifacts_meta.<key>`
  写入该交付物所依赖数据的 **content-hash（`source_hash`）+ 渲染时间**。
- `artifact_guard.py` 用当前数据重算依赖哈希，与 `source_hash` 比对：
  - 一致 → 新鲜（OK）；
  - 不一致 → **数据漂移（STALE_HASH）**，视为护栏违规（exit 1）；
  - 存量文档（本护栏启用前产出、无 `source_hash`）→ 仅给 ADVISORY，不记违规（避免误杀）。
- 未登记 / 文件缺失 / 数据漂移 → 违规。
- `control_engine.py` 周期巡检内置该检查：发现漂移即 RED 升级并 `exit 1`（可挂定时任务告警）。
- `gate_engine.py` 收尾门（G3→4）将「交付物与事实源一致 (OAG)」列为**硬准则**：交付物漂移则禁止收尾。

**编排器义务（每次 operational 动作后）**：
1. 改完 `project.yaml` → 重渲染受影响交付物（`build_subproject.py --only <key>` 或 `rerender_docs.py`）；
2. 手工/外部渲染的文档（如 `portfolio_dashboard`）产出后调用
   `artifact_guard.py --project <yaml> --stamp <key>` 记录 `source_hash`；
3. 跑 `artifact_guard.py --project <yaml>` 确认 exit 0；非零则回到第 1 步。

**诊断（如何证明它能抓到违规）**：临时改动 `raid` 后直接跑 `artifact_guard.py`，会立即报
`[数据漂移] raid_log` —— 这正是示例客户当初漏掉的环节。

## 5. Why this is the default (anti-pattern it prevents)

- ❌ Old way: program manager keeps a separate program RAID/status spreadsheet, component PMs keep their own,
  they diverge within a week.
- ✅ This way: component PMs own the only copy of their data; program view is regenerated on demand and is
  always consistent by construction.

## 6. Quick checklist for the orchestrator

- [ ] Each SOW/sub-project has its own `project.yaml` (via `init_project.py --parent <program> --sow <id>`)
- [ ] Component PMs edit **only** their sub-project file
- [ ] Program `project.yaml` holds charter + `program.projects[]` + milestone rows (`leaves:` lists)
- [ ] To refresh program view: `rollup_subprojects.py --program <program_dir>` → `control_engine.py ...`
- [ ] To freeze: `baseline.py --freeze` after rollup
- [ ] No program-level RAID/status/wbs_progress hand-edits
