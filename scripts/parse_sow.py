#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · SOW / Contract 解析器（基础布局加固 v2.2）

把「理解记录(spec, JSON)」转换为 WBS 包并**自动写入** program/project.yaml。
spec 来自：(a) SOW 文本抽取 + (c) 引导式 Q&A 双重确认，故无需人工审批即可落盘。

行为：
  - 幂等：删除该 SOW 旧子树（id==SOWn 或 id 以 "SOWn." 开头）后追加新包。
  - 自底向上累计 summary/milestone 估算；estimate 缺省 = duration_days。
  - 默认依赖链：entry_gate -> Wave1 -> 叶链 -> W1 里程碑 -> Wave2 ... -> 交付里程碑。
  - 在 sow_map 写入/更新 fee / fee_type / methodology / status。
  - 末尾自动跑 consistency_check.py（固定费率 SOW 必须有计费里程碑，否则致命失败）。

用法：
  python3 parse_sow.py --emit-spec-template
  python3 parse_sow.py --project <program/project.yaml> --spec <sowN.spec.json>
  python3 parse_sow.py --project <program/project.yaml> --spec <sowN.spec.json> --dry-run
"""
import argparse
import json
import os
import re
import subprocess
import sys
import datetime

try:
    import yaml
except ImportError:
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))


def _emit_template():
    tpl = {
        "sow": "SOW1",
        "name": "示例 SOW 名称",
        "methodology": "waterfall",
        "objective": "从 SOW 文本逐字提取的目标",
        "scope": "in-scope（逐字）",
        "out_of_scope": "out-of-scope（逐字）",
        "assumptions": ["假设1（变更触发）", "假设2"],
        "roles": ["requirements-analyst", "data-modeler"],
        "entry_gates": [
            {"id": "SOW1.0", "name": "进入条件/数据就绪门", "role": "requirements-analyst",
             "duration_days": 10, "estimate": 8, "acceptance": "SME+真实数据+接口文档齐备",
             "dependsOn": []}
        ],
        "waves": [
            {
                "id": "SOW1.W1", "name": "Wave 1",
                "billing": {"event": "Wave 1 Design Document post sign-off",
                            "fee": 11645092, "currency": "INR", "fee_type": "fixed"},
                "leaves": [
                    {"id": "SOW1.W1.1", "name": "源分析", "role": "requirements-analyst",
                     "duration_days": 8, "estimate": 6, "acceptance": "源接口文档齐备"},
                    {"id": "SOW1.W1.2a", "name": "逻辑模型", "role": "data-modeler",
                     "duration_days": 8, "estimate": 6, "acceptance": "逻辑 ERD 评审通过"}
                ]
            }
        ],
        "deliverables_non_billing": [
            {"id": "SOW1.AR", "name": "非计费交付物",
             "billing": {"event": "Deliverable sign-off", "fee": 0, "fee_type": "none"},
             "leaves": [
                 {"id": "SOW1.AR.1a", "name": "设计", "role": "data-modeler",
                  "duration_days": 9, "estimate": 7, "acceptance": "设计文档评审"}]}
        ]
    }
    print(json.dumps(tpl, ensure_ascii=False, indent=2))


def _default_methodology_chain(spec, byid):
    """为未显式给 dependsOn 的包生成默认依赖链。"""
    sow = spec['sow']
    gates = spec.get('entry_gates') or []
    gate_ids = [g['id'] for g in gates]
    first_prev = gate_ids[0] if gate_ids else None

    def chain_leaves(wid, leaves):
        # 叶链：leaf[i] dependsOn leaf[i-1]；首叶依赖其 Wave summary
        # 必须写回 byid 里的真实包（add_wave 建包时 dependsOn 还是空），否则依赖丢失
        prev = wid
        for lf in leaves:
            pkg = byid.get(lf['id'])
            if pkg is None:
                continue
            deps = lf.get('dependsOn')
            if deps is None:
                deps = [prev]
            pkg['dependsOn'] = deps
            lf['dependsOn'] = deps  # 同步 spec，便于审计
            prev = lf['id']
        return prev  # 最后一叶 id

    # waves
    prev_wave_tail = first_prev
    wave_ms = []
    for w in spec.get('waves') or []:
        wp = byid[w['id']]
        if wp.get('dependsOn') is None:
            wp['dependsOn'] = [prev_wave_tail] if prev_wave_tail else []
        tail = chain_leaves(w['id'], w.get('leaves') or [])
        # milestone
        mid = w['id'] + '.M'
        m = byid.get(mid)
        if m is not None:
            if m.get('dependsOn') is None:
                m['dependsOn'] = [tail]
            wave_ms.append(mid)
        prev_wave_tail = mid if mid in byid else tail
    # non-billing deliverables
    for dl in spec.get('deliverables_non_billing') or []:
        dlp = byid[dl['id']]
        if dlp.get('dependsOn') is None:
            dlp['dependsOn'] = [first_prev] if first_prev else []
        tail = chain_leaves(dl['id'], dl.get('leaves') or [])
        mid = dl['id'] + '.M'
        m = byid.get(mid)
        if m is not None:
            if m.get('dependsOn') is None:
                m['dependsOn'] = [tail]


def build_packages(spec):
    """返回 (packages 列表, sow_summary_id)。"""
    sow = spec['sow']
    pkgs = []
    meth = spec.get('methodology', 'waterfall')

    def P(id, name, **kw):
        o = {'id': id, 'name': name}
        o.update(kw)
        return o

    # summary
    summary = P(sow, spec.get('name', sow),
                tier='program', summary=True, component='sow' + sow.replace('SOW', '').lower(),
                role='data-architect',
                objective=spec.get('objective', ''),
                scope=spec.get('scope', ''),
                out_of_scope=spec.get('out_of_scope', ''),
                assumptions=spec.get('assumptions', []),
                owner=spec.get('owner', 'SOW Project Manager'),
                methodology=meth,
                dependsOn=spec.get('dependsOn', []))
    pkgs.append(summary)

    byid = {}
    # entry gates
    _first_wave = (spec.get('waves') or [{}])[0]
    _first_mid = (_first_wave.get('id') + '.M') if _first_wave.get('id') else None
    for g in spec.get('entry_gates') or []:
        p = P(g['id'], g['name'], tier='component', component=summary.get('component'),
              role=g.get('role', 'requirements-analyst'),
              duration=(str(g.get('duration_days', g.get('estimate', 0))) + 'd') if g.get('duration_days') or g.get('estimate') else None,
              estimate=g.get('estimate', 0),
              acceptance=g.get('acceptance', ''),
              owner=g.get('owner', ''),
              deliverable=g.get('deliverable'),
              scope=g.get('scope'),
              dependsOn=g.get('dependsOn', []),
              milestone_ref=g.get('milestone_ref', _first_mid))  # Pillar 2: entry gate belongs to first-wave milestone
        pkgs.append(p); byid[g['id']] = p

    def add_wave(w, is_billing=True, pay_index=None):
        billing = w.get('billing') or {}
        mid = w['id'] + '.M'  # Pillar 2: 叶子 milestone_ref 目标（须在叶循环前定义）
        p = P(w['id'], w['name'], tier='component', component=summary.get('component'),
              summary=True, role=w.get('role', 'data-modeler'),
              methodology=meth,
              objective=w.get('objective', ''),
              dependsOn=w.get('dependsOn'))  # None 时由默认链填充
        pkgs.append(p); byid[w['id']] = p
        for lf in w.get('leaves') or []:
            lp = P(lf['id'], lf['name'], tier='component', component=summary.get('component'),
                   role=lf.get('role', 'data-modeler'),
                   duration=(str(lf.get('duration_days', lf.get('estimate', 0))) + 'd') if (lf.get('duration_days') or lf.get('estimate')) else None,
                   estimate=lf.get('estimate', 0),
                   acceptance=lf.get('acceptance', ''),
                   owner=lf.get('owner', ''),
                   deliverable=lf.get('deliverable'),
                   scope=lf.get('scope'),
                   dependsOn=lf.get('dependsOn', []),
                   milestone_ref=mid)  # Pillar 2: 每叶子归属其 Wave 里程碑
            pkgs.append(lp); byid[lf['id']] = lp
        # milestone
        mid = w['id'] + '.M'
        pay_id = (f"{sow}-P{pay_index}" if (is_billing and pay_index) else None)
        mp = P(mid, (billing.get('event') or (w['name'] + ' sign-off')),
               tier='program', milestone=True, component=summary.get('component'),
               methodology=meth,
               billing={'event': billing.get('event'),
                        'fee_inr': billing.get('fee'),
                        'currency': billing.get('currency', 'INR'),
                        'fee_type': billing.get('fee_type', 'fixed'),
                        'payment_id': pay_id,  # Pillar 4: 支付行↔里程碑映射
                        'status': 'planned'},
               dependsOn=None)
        pkgs.append(mp); byid[mid] = mp

    for i, w in enumerate(spec.get('waves') or [], start=1):
        add_wave(w, True, pay_index=i)
    for dl in spec.get('deliverables_non_billing') or []:
        add_wave(dl, False, pay_index=None)

    _default_methodology_chain(spec, byid)

    # rollup estimates bottom-up
    children = {}
    for p in pkgs:
        did = p['id']
        for c in pkgs:
            cid = c['id']
            if cid.startswith(did + '.') and '.' not in cid[len(did) + 1:]:
                children.setdefault(did, []).append(cid)
    for p in sorted(pkgs, key=lambda x: -x['id'].count('.')):
        i = p['id']
        if i in children and children[i]:
            s = sum((byid[c].get('estimate') or 0) for c in children[i])
            if s:
                p['estimate'] = s
    # milestones: ensure small positive sign-off effort
    for p in pkgs:
        if p.get('milestone') and not p.get('estimate'):
            p['estimate'] = 2

    return pkgs, sow


def main():
    ap = argparse.ArgumentParser(description="PM Master · SOW/合同解析器（spec -> WBS 自动写入）")
    ap.add_argument('--project', help="program/project.yaml（单一事实源）")
    ap.add_argument('--spec', help="理解记录 JSON（由文本抽取+Q&A 生成）")
    ap.add_argument('--emit-spec-template', action='store_true', help="打印空白 spec 模板")
    ap.add_argument('--dry-run', action='store_true', help="只打印将写入的包，不落盘")
    args = ap.parse_args()

    if args.emit_spec_template:
        _emit_template(); return

    if not args.project or not args.spec:
        ap.error("需提供 --project 与 --spec（或 --emit-spec-template）")

    spec = json.load(open(args.spec, encoding='utf-8'))
    pkgs, sow = build_packages(spec)

    if args.dry_run:
        print(json.dumps(pkgs, ensure_ascii=False, indent=2))
        return

    if yaml is None:
        print("ERROR: 需要 PyYAML 写入 project.yaml", file=sys.stderr); sys.exit(5)
    d = yaml.safe_load(open(args.project, encoding='utf-8'))
    wbs = d.get('wbs') or []
    prefix = sow + '.'
    wbs = [w for w in wbs if w.get('id') != sow and not str(w.get('id', '')).startswith(prefix)]
    wbs.extend(pkgs)
    d['wbs'] = wbs

    # update sow_map
    sm = d.get('sow_map') or []
    fee = 0
    for w in spec.get('waves') or []:
        fee += (w.get('billing') or {}).get('fee') or 0
    feetype = 'fixed' if any((w.get('billing') or {}).get('fee_type') == 'fixed' for w in spec.get('waves') or []) else ('tm' if any((w.get('billing') or {}).get('fee_type') == 'tm' for w in spec.get('waves') or []) else 'none')
    found = False
    for e in sm:
        if e.get('sow') == sow:
            e['fee'] = fee
            e['fee_type'] = feetype
            e['methodology'] = spec.get('methodology', e.get('methodology'))
            e['status'] = e.get('status', '规划中')
            found = True
    if not found:
        sm.append({'sow': sow, 'name': spec.get('name', sow), 'contract': 'C1',
                   'component': 'sow' + sow.replace('SOW', '').lower(),
                   'milestone': (spec.get('waves') or [{}])[0].get('billing', {}).get('event', ''),
                   'fee': fee, 'fee_type': feetype, 'methodology': spec.get('methodology', 'waterfall'),
                   'status': '规划中'})
    d['sow_map'] = sm

    # defensive backup
    import shutil
    shutil.copy(args.project, args.project + '.bak-' + datetime.date.today().isoformat())
    yaml.safe_dump(d, open(args.project, 'w', encoding='utf-8'), allow_unicode=True, sort_keys=False)
    print(f"[parse_sow] SOW {sow} WBS 已写入 {args.project}（{len(pkgs)} 个包，计费合计 {fee} {((spec.get('waves') or [{}])[0].get('billing') or {}).get('currency','INR')}）")

    # run consistency gate
    cc = os.path.join(HERE, 'consistency_check.py')
    if os.path.exists(cc):
        print("--- consistency_check ---")
        r = subprocess.run([sys.executable, cc, '--project', args.project])
        sys.exit(r.returncode)


if __name__ == '__main__':
    main()
