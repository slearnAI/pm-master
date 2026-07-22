#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · 项目群 WBS 两层化（tagged single-source model）
============================================================

将单源 project.yaml 的 wbs 改造为两层结构，满足"项目群层级 = 里程碑级、
组件层级 = 叶子工作包级"的颗粒度约定：

  - SOW 汇总包（id 无 '.' 或 summary:true）           → tier: program, summary: true
  - 每层为每个 SOW / P0 的**阶段(phase)**生成里程碑汇总包
                                                      → tier: program, milestone: true
  - 所有叶子工作包（id 含 '.'）                      → tier: component, component: <slug>

组件视图（build_wbs.py --view component --component <slug>）只筛 tier:component 的叶子；
项目群视图（build_wbs.py --view program）只筛 tier!=component 的汇总+里程碑包。

`--derive-actuals`：把叶子实际进度按 estimate 加权汇总为每个里程碑的实际%，
写入 project.yaml 的 actuals.wbs_progress（里程碑 id 为键），使项目群层级的
进度控制表（control_engine）可直接以里程碑颗粒度呈现。

只重写 project.yaml 的 `wbs:`（及可选的 `actuals.wbs_progress:`）块，其余段落与
注释完整保留；执行前自动备份为 <project.yaml>.bak-<date>。

> 组件 / 阶段映射（`COMPONENT_MAP` / `PHASE_NAME`）为**示例默认值**（取自示例项目）。
> 生产环境请在 `project.yaml` 提供 `program.components`（SOW id → 组件 slug）与
> `governance.waves`（阶段 key → 阶段名），引擎优先使用项目级配置，缺省才回退示例并告警。

用法：
  python3 rollup_program_wbs.py <program/project.yaml>
  python3 rollup_program_wbs.py <program/project.yaml> --derive-actuals
"""
import os
import sys
import shutil
import datetime
import collections
import yaml

# 示例默认值（取自示例项目）。生产环境请改用 project.yaml 的
# program.components / governance.waves，见下方 COMPONENT_MAP_EFF / PHASE_NAME_EFF。
COMPONENT_MAP = {
    'P0': 'pmo-program-management',
    'SOW1': 'sow1',
    'SOW2': 'sow2',
    'SOW3': 'sow3',
    'SOW4': 'sow4',
    'SOW5': 'sow5',
    'SOW6': 'sow6',
    'SOW7': 'sow7',
    'SOW8': 'sow8',
    'SOW9': 'sow9',
    'EXT-PII': 'ext-pii',
}
PHASE_NAME = {
    'M0': 'M0 动员与就绪',
    'W1': 'Stream 1 基础建模',
    'W2': 'Stream 2 协议处理',
    'W3': 'Stream 3 分析结构',
    'W4': 'Stream 4 归档与集成',
}
# 运行时生效映射：由 main() 按 project.yaml 覆盖；缺省回退示例。
COMPONENT_MAP_EFF = dict(COMPONENT_MAP)
PHASE_NAME_EFF = dict(PHASE_NAME)
P0_KEYWORD = [
    ('章程', 'Charter'), ('方法', 'Charter'),
    ('治理', 'Governance'), ('RACI', 'Governance'),
    ('阶段门', 'StageGate'),
    ('IMS', 'IMS基线'), ('主进度', 'IMS基线'),
    ('指导委员会', 'Steering'), ('例会', 'Steering'),
]


def parse_date(s):
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%Y/%m/%d'):
        try:
            return datetime.datetime.strptime(str(s), fmt).date()
        except ValueError:
            continue
    return None


def dur_str(s, e):
    if not s or not e:
        return None
    d = (e - s).days
    return f"{d}d" if d >= 0 else None


def clean(row):
    return {k: v for k, v in row.items() if v is not None}


# 取消/终止态，则里程碑行也应携带 cancelled 状态，避免控制引擎误报逾期。
_CANCELLED_LEAF_STATES = {'cancelled', 'canceled', '已取消', '取消',
                          'descoped', '已降级', '移出范围', 'out-of-scope',
                          'terminated', '已终止', '终止'}


def _rollup_status(items):
    """根据叶子包状态汇总里程碑状态：全部取消/终止→cancelled；否则不设（由进度%推导）。"""
    if not items:
        return None
    sts = {str(i.get('status', '')).lower() for i in items}
    if sts and sts <= _CANCELLED_LEAF_STATES:
        return 'cancelled'
    return None


def build_milestone(top, phase, items, prev_id, label=None):
    ests = [float(i.get('estimate') or 0) for i in items]
    est = round(sum(ests), 1)
    starts = [parse_date(i.get('start')) for i in items]
    ends = [parse_date(i.get('end')) for i in items]
    s = min([x for x in starts if x], default=None)
    e = max([x for x in ends if x], default=None)
    name = label if label else PHASE_NAME_EFF.get(phase, phase)
    mid = f"{top}-{label}" if label else f"{top}-{phase}"
    dlv = ' / '.join(str(i.get('deliverable', '')) for i in items[:3] if i.get('deliverable'))
    row = {
        'id': mid,
        'name': f"{top} · {name}",
        'level': 2,
        'milestone': True,
        'tier': 'program',
        'summary': False,
        'component': COMPONENT_MAP_EFF.get(top, top.lower()),
        'deliverable': dlv[:160],
        'owner': items[0].get('owner', ''),
        'estimate': est,
        'duration': dur_str(s, e),
        'start': s.isoformat() if s else None,
        'end': e.isoformat() if e else None,
    }
    if prev_id:
        row['dependsOn'] = prev_id
    rolled = _rollup_status(items)
    if rolled:
        row['status'] = rolled
    return clean(row), [i['id'] for i in items]


def find_block(path, key_line):
    """返回 (start_idx, end_idx) 覆盖 key_line 起的整块（到下一个顶层 key 止）。"""
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.rstrip('\n') == key_line:
            start = i
            break
    if start is None:
        for i, ln in enumerate(lines):
            if ln.strip() == key_line:
                start = i
                break
    if start is None:
        return None, None, lines
    end = len(lines)
    for i in range(start + 1, len(lines)):
        stripped = lines[i].lstrip(' ')
        if lines[i][:1] not in (' ', '\t', '\n', '#') and stripped and not stripped.startswith('- '):
            end = i
            break
    return start, end, lines


def rewrite_wbs_block(path, new_wbs):
    start, end, lines = find_block(path, 'wbs:')
    if start is None:
        # 骨架无 wbs: 块（如旧版 init 产物）时，整文件末尾追加，保证兼容
        lines.append('\nwbs:\n')
        start = len(lines) - 1
        end = len(lines) - 1
    dumped = yaml.safe_dump(new_wbs, allow_unicode=True, sort_keys=False,
                            default_flow_style=False)
    block = ['wbs:\n'] + [dumped]
    lines[start:end] = block
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(lines)


def inject_milestone_actuals(path, ms_actuals):
    """在 actuals.wbs_progress 块末尾（ev: 之前）插入里程碑实际% 键。"""
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    # 定位 wbs_progress: 行
    wp = None
    for i, ln in enumerate(lines):
        if ln.rstrip('\n') == '  wbs_progress:':
            wp = i
            break
    if wp is None:
        print("[warn] 未找到 actuals.wbs_progress:，跳过里程碑实际% 注入")
        return
    # 找到其后第一个 2 空格顶层键（ev: / ac:）作为插入点
    insert_at = None
    for i in range(wp + 1, len(lines)):
        if lines[i].startswith('  ') and not lines[i].startswith('    ') and lines[i].strip():
            insert_at = i
            break
    if insert_at is None:
        insert_at = len(lines)
    new_lines = [f"    {mid}: {val:.1f}\n" for mid, val in ms_actuals]
    lines[insert_at:insert_at] = new_lines
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(lines)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="PM Master 项目群 WBS 两层化")
    ap.add_argument('project')
    ap.add_argument('--derive-actuals', action='store_true',
                    help="把叶子实际%% 加权汇总为里程碑实际%%，写入 actuals.wbs_progress")
    a = ap.parse_args()

    path = os.path.abspath(a.project)
    if not os.path.exists(path):
        print(f"✗ 文件不存在: {path}")
        sys.exit(2)
    backup = f"{path}.bak-{datetime.date.today().isoformat()}"
    shutil.copy(path, backup)

    doc = yaml.safe_load(open(path, encoding='utf-8'))
    wbs = doc.get('wbs', [])

    # 组件 / 阶段映射：优先取项目级配置，缺省回退示例并告警（解耦硬编码）
    prog = doc.get('program') or {}
    gov = doc.get('governance') or {}
    comp_override = prog.get('components') if isinstance(prog.get('components'), dict) else None
    wave_override = (gov.get('waves') if isinstance(gov.get('waves'), dict) else None) or \
                    (prog.get('waves') if isinstance(prog.get('waves'), dict) else None)
    if comp_override:
        COMPONENT_MAP_EFF.update(comp_override)
    else:
        print("[rollup] 警告：未提供 program.components，使用内置示例 COMPONENT_MAP（示例项目）。"
              "生产请在 project.yaml 配置 program.components（SOW id → 组件 slug）。", file=sys.stderr)
    if wave_override:
        PHASE_NAME_EFF.update(wave_override)
    else:
        print("[rollup] 警告：未提供 governance.waves，使用内置示例 PHASE_NAME。"
              "生产请在 project.yaml 配置 governance.waves（阶段 key → 阶段名）。", file=sys.stderr)

    # 幂等保护：若已存在 tier:program 的里程碑汇总包，视为已两层化，
    # 不再重新生成（避免重复 / 误把里程碑当 summary）。
    already = any(w.get('milestone') and w.get('tier') == 'program' for w in wbs)

    summaries = []
    leaves = []
    existing_ms = []
    for w in wbs:
        wid = str(w.get('id', ''))
        if w.get('milestone') and w.get('tier') == 'program':
            existing_ms.append(w)
            continue
        if w.get('summary') or ('.' not in wid):
            w['tier'] = 'program'
            w['summary'] = True
            top = wid.split('.')[0]
            w['component'] = COMPONENT_MAP_EFF.get(top, top.lower())
            summaries.append(w)
        else:
            top = wid.split('.')[0]
            w['tier'] = 'component'
            w['component'] = COMPONENT_MAP_EFF.get(top, top.lower())
            leaves.append(w)

    by_top = collections.OrderedDict()
    for w in leaves:
        top = str(w['id']).split('.')[0]
        by_top.setdefault(top, []).append(w)

    # 始终按确定性规则重建 里程碑→叶子 映射（供 --derive-actuals 使用）
    ms_leaves = {}
    ms_est = {}
    milestone_rows = existing_ms[:] if already else []
    for top, lvs in by_top.items():
        phases = collections.OrderedDict()
        unphased = []
        for w in lvs:
            segs = str(w['id']).split('.')
            if len(segs) >= 3:
                phases.setdefault(segs[1], []).append(w)
            else:
                unphased.append(w)
        prev_id = None
        for ph, items in phases.items():
            m, lids = build_milestone(top, ph, items, prev_id)
            ms_leaves[m['id']] = lids
            ms_est[m['id']] = m.get('estimate', 0)
            if not already:
                milestone_rows.append(m)
            prev_id = m['id']
        if unphased:
            if top == 'P0':
                kg = collections.OrderedDict()
                for w in unphased:
                    label = 'PMO'
                    for kw, lab in P0_KEYWORD:
                        if kw in str(w.get('name', '')):
                            label = lab
                            break
                    kg.setdefault(label, []).append(w)
                for lab, items in kg.items():
                    m, lids = build_milestone(top, lab, items, prev_id, label=lab)
                    ms_leaves[m['id']] = lids
                    ms_est[m['id']] = m.get('estimate', 0)
                    if not already:
                        milestone_rows.append(m)
                    prev_id = m['id']
            else:
                m, lids = build_milestone(top, 'DELIVERY', unphased, prev_id,
                                          label=f"{top} 交付")
                ms_leaves[m['id']] = lids
                ms_est[m['id']] = m.get('estimate', 0)
                if not already:
                    milestone_rows.append(m)
                prev_id = m['id']

    new_wbs = summaries + milestone_rows + leaves
    rewrite_wbs_block(path, new_wbs)
    print(f"[rollup] backup -> {backup}")
    print(f"[rollup] summaries={len(summaries)} milestones={len(milestone_rows)} "
          f"leaves={len(leaves)} -> program wbs total={len(new_wbs)}")

    if a.derive_actuals:
        actuals = (doc.get('actuals') or {})
        prog = actuals.get('wbs_progress') or {}
        ms_actuals = []
        for mid, lids in ms_leaves.items():
            num = 0.0
            den = 0.0
            for lid in lids:
                la = float(prog.get(lid, 0) or 0)
                le = float(ms_est.get(lid) or 0) or 1.0  # 兜底权重
                num += la * le
                den += le
            val = round(num / den, 1) if den else 0.0
            ms_actuals.append((mid, val))
        inject_milestone_actuals(path, ms_actuals)
        print(f"[rollup] derived {len(ms_actuals)} milestone actual% -> actuals.wbs_progress")


if __name__ == '__main__':
    main()
