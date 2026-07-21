#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · 跨文件子项目进度汇总（父级 rollup）

读取每个子项目 subprojects/<slug>/project.yaml 的叶子实际进度
(actuals.wbs_progress, 键为叶子包 id, 值为完成%), 按 master 每个
program-tier 行的 `leaves:` 列表做 estimate 加权汇总, 写入 master 的
actuals.wbs_progress (键为 program-tier 行 id)。

同时汇总各子项目的 ev/ac 为程序级 ev/ac, 写入 master.actuals。

用法:
  python3 rollup_subprojects.py <program/project.yaml>
"""
import os, sys, shutil, datetime, yaml

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('project')
    a = ap.parse_args()
    master = os.path.abspath(a.project)
    mdir = os.path.dirname(master)
    d = yaml.safe_load(open(master, encoding='utf-8'))
    backup = f"{master}.bak-rollup-{datetime.date.today().isoformat()}"
    shutil.copy(master, backup)

    # load sub-projects via program.projects index
    projects = (d.get('program') or {}).get('projects', []) or []
    subs = []
    for e in projects:
        sp = os.path.join(mdir, e.get('path') or os.path.join('subprojects', e.get('slug', e['sow'])), 'project.yaml')
        if os.path.exists(sp):
            subs.append((e['sow'], yaml.safe_load(open(sp, encoding='utf-8'))))

    # collect leaf progress + ev/ac from each sub
    leaf_progress = {}   # leaf_id -> %
    tot_ev = 0.0
    tot_ac = 0.0
    for sow, sd in subs:
        aprog = (sd.get('actuals') or {})
        wp = aprog.get('wbs_progress') or {}
        for k, v in wp.items():
            leaf_progress[k] = float(v or 0)
        tot_ev += float(aprog.get('ev') or 0)
        tot_ac += float(aprog.get('ac') or 0)

    # roll up into master program-tier rows
    ms_actuals = {}
    for w in d['wbs']:
        if w.get('tier') != 'program':
            continue
        lw = w.get('leaves') or []
        if not lw:
            ms_actuals[w['id']] = 0.0
            continue
        num = den = 0.0
        for lid in lw:
            la = float(leaf_progress.get(lid, 0) or 0)
            # estimate: try master first, then sub (master no longer has leaves; read from sub)
            le = 0.0
            for sow, sd in subs:
                for sw in (sd.get('wbs') or []):
                    if sw.get('id') == lid:
                        le = float(sw.get('estimate') or 0)
                        break
                if le:
                    break
            le = le or 1.0
            num += la * le
            den += le
        ms_actuals[w['id']] = round(num / den, 1) if den else 0.0

    # write master actuals.wbs_progress (program-tier) + ev/ac
    d.setdefault('actuals', {})['wbs_progress'] = ms_actuals
    d['actuals']['ev'] = round(tot_ev, 0)
    d['actuals']['ac'] = round(tot_ac, 0)
    yaml.safe_dump(d, open(master, 'w', encoding='utf-8'), allow_unicode=True, sort_keys=False)
    print(f"[rollup] backup -> {backup}")
    print(f"[rollup] aggregated leaf progress from {len(subs)} sub-projects")
    print(f"[rollup] program-tier wbs_progress keys: {len(ms_actuals)}")
    print(f"[rollup] program EV={round(tot_ev,0)} AC={round(tot_ac,0)}")

if __name__ == '__main__':
    main()
