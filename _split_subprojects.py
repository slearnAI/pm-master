#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split a two-tiered LIC Datalake program master into per-SOW sub-projects (Option A).

- Master keeps ONLY program-tier rows (summary + milestone); each gets a `leaves:` list
  (component leaf ids it rolls up from) so the parent cross-file rollup is trivial.
- Each SOW's component leaves move into subprojects/<slug>/project.yaml, owned by that SOW-PM.
- program.projects index rebuilt for all 9 SOWs.
- metrics.evm (program BAC) stays in master.
"""
import os, sys, shutil, datetime, yaml

ROOT = "/Users/wanman/Workbuddy/pm214/lic-datalake"
MASTER = os.path.join(ROOT, "project.yaml")
SKILL = "/Users/wanman/.qclaw/workspace/skills/pm-master"

# map SOW id -> (slug, display name, methodology)
SOW_META = {
    'SOW1': ('sow1', 'SOW1 Data Modelling & Engineering', 'waterfall'),
    'SOW2': ('sow2', 'SOW2 Historical Data Load / Migration', 'waterfall'),
    'SOW3': ('sow3', 'SOW3 Data Masking', 'waterfall'),
    'SOW4': ('sow4', 'SOW4 Data Analytics / ModelOps + UC + EFS', 'waterfall'),
    'SOW5': ('sow5', 'SOW5 BCM / Disaster Recovery', 'waterfall'),
    'SOW6': ('sow6', 'SOW6 SME Support (T&M)', 'time-material'),
    'SOW7': ('sow7', 'SOW7 Project Management / Governance + OS Hardening', 'waterfall'),
    'SOW8': ('sow8', 'SOW8 Training / Teradata Education', 'waterfall'),
    'SOW9': ('sow9', 'SOW9 Transaction Services / Infrastructure', 'waterfall'),
}

def main():
    d = yaml.safe_load(open(MASTER, encoding='utf-8'))
    # idempotency guard: if master already holds only program-tier rows, abort
    tiers = {w.get('tier') for w in d.get('wbs', [])}
    if tiers and tiers == {'program'}:
        print("[split] ABORT: master already split (only program-tier rows present). "
              "Restore from a 239-row backup before re-running.")
        sys.exit(0)
    # backup
    shutil.copy(MASTER, f"{MASTER}.bak-split-{datetime.date.today().isoformat()}")

    wbs = d['wbs']
    program_rows = [w for w in wbs if w.get('tier') == 'program']
    component_rows = [w for w in wbs if w.get('tier') == 'component']

    # group component leaves by SOW top-prefix (used to seed sub-project wbs)
    by_sow = {}
    for w in component_rows:
        top = w['id'].split('.')[0]
        by_sow.setdefault(top, []).append(w)

    # program-level info
    prog = d.get('program', {}) or {}
    master_start = d.get('project', {}).get('start_date')
    master_target = prog.get('target_end') or d.get('project', {}).get('target_end')
    sponsor = prog.get('sponsor')
    pm = prog.get('manager')

    # write sub-projects
    projects_index = []
    sub_leaves = {}  # sow -> list of leaf ids (true leaves from sub-project)
    for sow, (slug, name, method) in SOW_META.items():
        leaves = by_sow.get(sow, [])
        sdir = os.path.join(ROOT, 'subprojects', slug)
        os.makedirs(sdir, exist_ok=True)
        # pull sow_map entry for fee/objective
        sowmap = {}
        for e in (d.get('sow_map') or []):
            if e.get('sow') == sow:
                sowmap = e
        sub = {
            'schema_version': 2,
            'project': {
                'id': slug,
                'name': name,
                'type': 'project',
                'methodology': method,
                'framework': None,
                'phase': '执行',
                'status': 'kicked_off',
                'lifecycle_state': 'execution',
                'baselined_on': d.get('baseline', {}).get('on') if isinstance(d.get('baseline'), dict) else None,
                'domain': 'lic-datalake',
                'product': 'LIC Datalake',
                'created': datetime.date.today().isoformat(),
                'start_date': master_start,
                'target_end': master_target,
                'sponsor': sponsor,
                'pm': f"{sow} Project Manager",
                'team': sorted({w.get('role') for w in leaves if w.get('role')}),
                'objective': sowmap.get('objective') or (leaves[0].get('objective') if leaves else None),
                'scope': sowmap.get('scope'),
                'fee_type': sowmap.get('fee_type'),
                'fee': sowmap.get('fee'),
            },
            'parent': {
                'project': '../../project.yaml',
                'sow': sow,
            },
            'governance': {'stage_gates': [], 'cadence': 'weekly'},
            'artifacts': {
                'raid_log': 'risks/raid_log.md',
                'risk_register': 'risks/risk_register.md',
                'status_report': 'reports/status_report.md',
            },
            'raid': {'risks': [], 'assumptions': [], 'issues': [], 'dependencies': []},
            'risks': [],
            'progress': {'period': '', 'as_of': None, 'narrative': ''},
            'metrics': {'evm': {}},
            'actuals': {'as_of': None, 'wbs_progress': {}, 'ev': 0, 'ac': 0},
            'control': {'cadence': 'weekly', 'thresholds': {}},
            'wbs': leaves,
            'program': {'sow': sow, 'slug': slug},
        }
        spy = os.path.join(sdir, 'project.yaml')
        yaml.safe_dump(sub, open(spy, 'w', encoding='utf-8'), allow_unicode=True, sort_keys=False)
        # true leaves = non-summary, non-milestone in the sub-project wbs
        sub_leaves[sow] = [w['id'] for w in leaves
                           if not w.get('summary') and not w.get('milestone')]
        projects_index.append({
            'id': slug, 'sow': sow, 'name': name, 'slug': slug,
            'methodology': method, 'status': '执行中',
            'path': f"subprojects/{slug}",
        })
        print(f"[split] {sow} -> {spy} ({len(leaves)} leaves, {len(sub_leaves[sow])} true leaves)")

    # annotate each master program-tier row with its leaf id list (from sub-projects)
    for w in program_rows:
        wid = w['id']
        top = wid.split('.')[0]
        lw = sub_leaves.get(top, [])
        if w.get('milestone'):
            segs = wid.split('.')
            phase = segs[1] if len(segs) >= 2 else None
            w['leaves'] = [x for x in lw if x.split('.')[1] == phase] if phase else []
        else:
            w['leaves'] = list(lw)
    # rebuild program.projects index
    d.setdefault('program', {})['projects'] = projects_index
    # rewrite master wbs = program rows only (component leaves now live in sub-projects)
    d['wbs'] = program_rows
    # clear stale program-tier actuals (will be re-derived by parent rollup)
    if 'actuals' in d and isinstance(d['actuals'], dict):
        d['actuals']['wbs_progress'] = {}
    # keep metrics.evm in master (program BAC) — already there
    yaml.safe_dump(d, open(MASTER, 'w', encoding='utf-8'), allow_unicode=True, sort_keys=False)
    print(f"[split] master wbs -> {len(program_rows)} program-tier rows (leaves moved to sub-projects)")
    print(f"[split] program.projects index -> {len(projects_index)} SOWs")

if __name__ == '__main__':
    main()
