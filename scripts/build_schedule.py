#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · WBS -> 排期计划（Schedule / Gantt）生成器
-------------------------------------------------
把 `project.yaml` 的 WBS 真正「转成」一份可跟踪的排期计划交付物（schedule_gantt.md），
而不是只把关键路径打印到 stdout（那是 schedule_health.py 的职责）。

视图（--level / --sow）：
  - full（默认；项目群自动降级为 program）：全部可排程任务（跳过 summary 汇总包）。
  - program：仅项目群里程碑级（tier: program 的 SOW 汇总包 + 阶段里程碑），聚焦
            项目群级规划，不展开叶子细节。输出 plans/schedule_program_gantt.md。
  - sow <SOW_ID>：仅该 SOW 子树（SOW 汇总包 + 其下叶子包 + 依赖它的里程碑），
            输出到 plans/<sow>/schedule_gantt.md，作为「该 SOW 自己的计划」（可独立执行，
            通过 project.name + SOW id 与父项目/项目群保持关联）。

做什么：
  1. 正向排程（forward pass）：以项目起始日 + 各任务工期(duration) + 依赖(dependsOn)
     推算每个任务的 最早开始(ES)/最早结束(EF)，得到 开始/结束 日期。
     集外依赖（不在本视图内）视为已满足，不影响本视图排程。
  2. 把推算出的 start/end 回写 project.yaml 的 wbs[].start/end（单一事实源）。
  3. 基于选中行派生 `tasks` 列表，渲染 templates/waterfall/schedule_gantt.md。
  4. 把产物路径写回 project.yaml 的 artifacts（schedule_gantt / schedule_program /
     schedule_sow_<slug>）。

用法：
  python3 build_schedule.py --project /workspace/<slug>/project.yaml
  python3 build_schedule.py --project <yaml> --level program            # 项目群级排期
  python3 build_schedule.py --project <yaml> --sow SOW1                 # 单 SOW 排期（子计划）
  python3 build_schedule.py --project <yaml> --start 2026-08-01 --no-write-back
"""
import argparse
import os
import re
import sys
import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    import yaml
except ImportError:
    yaml = None

from schedule_health import (_parse_deps, _parse_duration_days, compute_schedule,
                             _resolve_effort_duration, _parse_deps_typed, _enhanced_active)


def _load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def _save(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def _select_ids(wbs, level, sow_id, ptype):
    """返回本视图要排程的 wbs id 集合；None 表示全部（full）。"""
    if sow_id:
        inc = set()
        for w in wbs:
            wid = w.get('id')
            if not wid:
                continue
            if wid == sow_id or str(wid).startswith(sow_id + '.'):
                inc.add(wid)
        # 纳入依赖全部落在本集合内的里程碑（如该 SOW 的上线里程碑）
        for w in wbs:
            wid = w.get('id')
            if wid in inc or not wid:
                continue
            deps = _parse_deps(w.get('dependsOn'))
            if w.get('milestone') and (not deps or all(d in inc for d in deps)):
                inc.add(wid)
        return inc
    if level == 'program' or (level == 'auto' and ptype == 'program'):
        inc = set()
        for w in wbs:
            if w.get('tier') == 'program' and w.get('id'):
                inc.add(w.get('id'))
        if not inc:  # 兜底：高层视图 = 汇总包 + 里程碑
            for w in wbs:
                if (w.get('summary') or w.get('milestone')) and w.get('id'):
                    inc.add(w.get('id'))
        # 排程时需把各 SOW 子树的全部后代纳入，才能算出汇总包真实跨度并回写叶子日期；
        # 渲染阶段再按 tier/milestone 过滤（仅显示项目群级行）。
        descendants = set()
        for w in wbs:
            wid = w.get('id')
            if not wid:
                continue
            for p in inc:
                if str(wid).startswith(p + '.') and wid != p:
                    descendants.add(wid)
        inc |= descendants
        return inc
    return None  # full


def _normalize_date_keys(w):
    """统一日期键：仅允许 `start`/`end` 作为规范键。
    兼容历史/模板中误用的 `finish` 键 —— 若某行同时存在 `end` 与 `finish` 且冲突，
    以 `end` 为准；若只有 `finish` 没有 `end`，把 `finish` 归一为 `end` 并从行中删除 `finish`。
    返回 (start, end, warned)，warned 为告警信息列表。
    """
    warned = []
    start = w.get('start')
    end = w.get('end')
    finish = w.get('finish')
    if finish is not None:
        if end is None:
            end = finish
            warned.append(f"{w.get('id')}: 非规范键 `finish` 已归一为 `end`")
        elif str(end) != str(finish):
            warned.append(f"{w.get('id')}: `end`({end}) 与 `finish`({finish}) 冲突，以 `end` 为准，丢弃 `finish`")
        # 不论冲突与否，删除 finish，避免双键漂移
        w.pop('finish', None)
    if 'finish' in w:
        w.pop('finish', None)
    return start, end, warned


def forward_schedule(wbs, project_start, include_ids=None):
    """正向排程，返回 {id: (start_date, end_date, is_milestone)}。

    include_ids 不为 None 时只排程该集合内的行；集合外依赖视为已满足。
    若某包在集合内的依赖不全（如项目群视图缺叶子细节），且其 YAML 已有真实
    start/end，则**沿用既有日期**（不重置为起始日），避免把已基线化的排期压平。
    但沿用前会校验既有日期是否被前置/后继拓扑推翻：若被推翻（用户输入了错误日期），
    则重新推算并告警，不再静默保留错误日期。
    """
    # 先统一日期键，收集归一告警
    _date_warns = []
    for w in wbs:
        s, e, wn = _normalize_date_keys(w)
        _date_warns.extend(wn)
    if _date_warns:
        for wmsg in _date_warns:
            print(f"[schedule][warn] {wmsg}")
    orig = {w.get('id'): w for w in wbs}  # 既有日期来源
    info = {}
    byid = {w.get('id'): w for w in wbs}
    for w in wbs:
        wid = w.get('id')
        if not wid:
            continue
        if include_ids is not None and wid not in include_ids:
            continue
        dur = _parse_duration_days(w)
        if dur == 0 and w.get('estimate'):
            # 叶子包可能只有 estimate 没有 duration；用 estimate 作为工期
            dur = _parse_duration_days({'duration': str(w.get('estimate', 0)) + 'd'})
        deps = _parse_deps(w.get('dependsOn'))
        milestone = bool(w.get('milestone')) or dur == 0
        is_summary = bool(w.get('summary'))
        # 汇总包是容器，不贡献顺序工期；其跨度由子项 rollup（display 用），排程 dur=0
        sched_dur = 0 if is_summary else dur
        info[wid] = {'dur': sched_dur, 'deps': deps, 'milestone': milestone, 'summary': is_summary}

    es = {}
    changed = True
    guard = 0
    while changed and guard < 10000:
        changed = False
        guard += 1
        for tid, it in info.items():
            deps = it['deps']
            # 仅等待「本集合内且尚未排程」的前置；集合外依赖视为已满足
            if any(d in info and es.get(d) is None for d in deps):
                continue
            new_s = 0
            for d in deps:
                if d in info and es.get(d) is not None:
                    new_s = max(new_s, es[d] + info[d]['dur'])
            if es.get(tid) != new_s:
                es[tid] = new_s
                changed = True

    result = {}
    # 先算叶子/非汇总跨度；再自底向上 rollup 汇总包（summary）的真实工期
    for tid, it in info.items():
        off = es.get(tid, 0)
        o = orig.get(tid) or {}
        ostart = o.get('start'); oend = o.get('end')
        has_real = bool(ostart and oend)
        # 既有日期沿用校验：仅当 (a) 本包无前置驱动(offset==0) 且 (b) 既有日期不超过任一前置的 end
        # 且 (c) 既有 end 不晚于其后继的最早 start 时才沿用；否则重新推算并告警（防静默错误日期）。
        carry = (off == 0) and has_real
        if carry:
            try:
                cstart = datetime.date.fromisoformat(str(ostart)[:10])
                cend = datetime.date.fromisoformat(str(oend)[:10])
                # 拓扑冲突检查：前置的最晚 end 必须 <= 本 starts；后继的最早 start 必须 >= 本 end
                pred_max_end = None
                for d in deps:
                    if d in result:
                        pred_max_end = cend if pred_max_end is None else max(pred_max_end, result[d][1])
                succ_min_start = None
                for t in wbs:
                    if t.get('id') in info and tid in _parse_deps(t.get('dependsOn')):
                        ts = result.get(t['id'])
                        if ts:
                            succ_min_start = ts[0] if succ_min_start is None else min(succ_min_start, ts[0])
                conflict = (pred_max_end is not None and cstart < pred_max_end) or \
                           (succ_min_start is not None and cend > succ_min_start)
                if conflict:
                    print(f"[schedule][warn] {tid} 既有日期 {cstart}–{cend} 与依赖拓扑冲突，已重新推算")
                    carry = False
                if carry:
                    result[tid] = (cstart, cend, it['milestone'])
                    continue
            except (ValueError, TypeError):
                carry = False
        start = project_start + datetime.timedelta(days=off)
        if it['milestone']:
            end = start
        else:
            end = start + datetime.timedelta(days=it['dur'])
        result[tid] = (start, end, it['milestone'])
    # rollup summary：取子（直接子包）最早开始与最晚结束
    children = {}
    for tid, it in info.items():
        pass
    # 构建 parent->children（按 id 前缀，取直接子）
    childmap = {}
    for tid in info:
        for cand in info:
            if cand != tid and cand.startswith(tid + '.') and '.' not in cand[len(tid) + 1:]:
                childmap.setdefault(tid, []).append(cand)
    # 自底向上（按 '.' 数降序）
    for tid in sorted(info, key=lambda x: -x.count('.')):
        if info[tid]['summary'] and not info[tid]['milestone']:
            kids = childmap.get(tid, [])
            if kids:
                starts = [result[k][0] for k in kids if result.get(k)]
                ends = [result[k][1] for k in kids if result.get(k)]
                if starts and ends:
                    s0 = min(starts); e0 = max(ends)
                    result[tid] = (s0, e0, False)
                    info[tid]['dur'] = (e0 - s0).days
    return result


def _fortnight_groups(tasks, project_start):
    """把任务按双周(2-week)桶聚合，返回 [{label,start,end,tasks}]。"""
    if not tasks:
        return []
    starts = []
    for t in tasks:
        try:
            starts.append(datetime.date.fromisoformat(str(t.get('start', ''))[:10]))
        except (ValueError, TypeError):
            pass
    if not starts:
        return []
    first = min(starts)
    last = max(starts)
    # 以项目起始为锚，每 14 天一个桶
    anchor = project_start
    groups = []
    wk = 1
    cur = anchor
    while cur <= last:
        nxt = cur + datetime.timedelta(days=14)
        gtasks = [t for t in tasks
                  if (t.get('start') and cur <= datetime.date.fromisoformat(str(t['start'])[:10]) < nxt)]
        groups.append({
            'label': f'FN{wk:02d} {cur.isoformat()}–{(nxt - datetime.timedelta(days=1)).isoformat()}',
            'start': cur.isoformat(),
            'end': (nxt - datetime.timedelta(days=1)).isoformat(),
            'tasks': gtasks,
            'count': len(gtasks),
            'task_ids': ' '.join(t.get('id', '') for t in gtasks),
        })
        cur = nxt
        wk += 1
    return groups


def main():
    ap = argparse.ArgumentParser(description="PM Master · WBS -> 排期计划生成器")
    ap.add_argument('--project', required=True, help="单一事实源 project.yaml")
    ap.add_argument('--level', default='auto', choices=['auto', 'full', 'program'],
                    help="视图：auto=按类型自动 / full=全部 / program=项目群里程碑级")
    ap.add_argument('--sow', default=None, help="仅排程该 SOW 子树（如 SOW1），输出为该 SOW 自己的计划")
    ap.add_argument('--start', default=None, help="项目起始日 ISO，如 2026-08-01")
    ap.add_argument('--granularity', default='task', choices=['task', 'fortnight'],
                    help="排期颗粒度：task=按任务(默认)；fortnight=按双周(2-week)桶聚合显示")
    ap.add_argument('--out', default=None, help="输出 .md 路径（覆盖默认）")
    ap.add_argument('--no-write-back', action='store_true', help="只渲染排期，不回写 project.yaml 的 wbs 日期")
    ap.add_argument('--no-level', action='store_true', help="关闭资源级联（纯 CPM，覆盖 control.scheduling.leveling）")
    ap.add_argument('--template', default=None, help="排期模板路径")
    a = ap.parse_args()

    if yaml is None:
        raise SystemExit("需要 PyYAML：请先 `pip install pyyaml`")

    data = _load(a.project)
    wbs = data.get('wbs') or []
    if not wbs:
        raise SystemExit("⚠ project.yaml 中未找到 wbs，无法生成排期计划（请先完成 WBS 拆解）。")

    ptype = (data.get('project') or {}).get('type', 'project')
    include_ids = _select_ids(wbs, a.level, a.sow, ptype)
    # 渲染集合：program 视图只显示 tier==program 行 + 里程碑（后代叶子已排程但不渲染）
    render_ids = set(include_ids) if include_ids is not None else None
    if a.level == 'program' or (a.level == 'auto' and ptype == 'program' and a.sow is None):
        render_ids = set()
        for w in wbs:
            if w.get('id') in include_ids and (w.get('tier') == 'program' or w.get('milestone')):
                render_ids.add(w.get('id'))

    start_iso = a.start or (data.get('project') or {}).get('start_date')
    if start_iso:
        try:
            project_start = datetime.date.fromisoformat(str(start_iso)[:10])
        except ValueError:
            raise SystemExit(f"非法的 --start / project.start_date：{start_iso}")
    else:
        project_start = datetime.date.today()
        print(f"[schedule] 未指定起始日，使用今天 {project_start.isoformat()}（建议用 --start 或填 project.start_date）")

    sched_cfg = (data.get('control') or {}).get('scheduling') or {}
    resources = data.get('resources') or []
    use_enhanced = _enhanced_active(data)
    if use_enhanced:
        level_on = bool(sched_cfg.get('leveling', True))
        level = (not a.no_level) and level_on
        res = compute_schedule(wbs, resources=resources, sched_cfg=sched_cfg,
                               include_ids=include_ids, level=level, recompute=True)
        sched = {}
        for tid, td in res['tasks'].items():
            if td['es'] is None:
                continue
            s = project_start + datetime.timedelta(days=td['es'])
            e = project_start + datetime.timedelta(days=td['ef'])
            sched[tid] = (s, e, td['milestone'])
    else:
        sched = forward_schedule(wbs, project_start, include_ids)

    if not a.no_write_back and include_ids is None and a.level in ('auto', 'full'):
        # 仅 full 视图（拥有完整叶子图）才回写日期；program/SOW 视图是只读视图，不改动索引
        for w in wbs:
            tid = w.get('id')
            if tid in sched:
                s, e, _ = sched[tid]
                w['start'] = s.isoformat()
                w['end'] = e.isoformat()

    # 构造 tasks：full 跳过 summary；program/sow 用 render_ids 过滤（program 仅 tier==program + 里程碑）
    tasks = []
    for w in wbs:
        tid = w.get('id')
        if not tid:
            continue
        if render_ids is not None:
            if tid not in render_ids:
                continue
        else:
            if w.get('summary'):
                continue
        s, e, milestone = sched.get(tid, (None, None, False))
        # duration 用回算后的真实工期（汇总包为子项 rollup 跨度；叶子为自身工期）
        dur = (e - s).days if (s and e) else _parse_duration_days(w)
        # 可读的依赖标签：SOW1.2(SS-5d) / SOW1.1(FS)
        deps_typed = _parse_deps_typed(w.get('dependsOn'))
        dep_labels = []
        for d in deps_typed:
            lag = d.get('lag') or 0
            if lag:
                dep_labels.append(f"{d['id']}({d['type']}{lag:+.0f}d)")
            else:
                dep_labels.append(f"{d['id']}({d['type']})")
        tasks.append({
            'id': tid,
            'name': w.get('name', tid),
            'duration': dur,
            'is_summary': bool(w.get('summary')),
            'deps': _parse_deps(w.get('dependsOn')),
            'dep_label': ', '.join(dep_labels),
            'start': s.isoformat() if s else (w.get('start') or ''),
            'end': e.isoformat() if e else (w.get('end') or ''),
            'milestone': milestone,
        })

    if not tasks:
        raise SystemExit("⚠ 本视图下没有可排程的任务（检查 wbs 的 tier / summary / milestone 标记）。")

    # 视图标签 + 输出路径
    if a.sow:
        view_label = f'SOW {a.sow}'
        slug = str(a.sow).replace('.', '_')
        out_def = os.path.join('plans', slug, 'schedule_gantt.md')
        art_key = f'schedule_sow_{slug}'
    elif include_ids is not None:  # program
        view_label = '项目群'
        out_def = os.path.join('plans', 'schedule_program_gantt.md')
        art_key = 'schedule_program'
    else:
        view_label = '项目'
        out_def = os.path.join('plans', 'schedule_gantt.md')
        art_key = 'schedule_gantt'

    # Pillar 2: 里程碑覆盖 —— 每个里程碑下直接归属的活动集合（按 milestone_ref / 依赖末端）
    milestone_coverage = []
    byid = {w.get('id'): w for w in wbs}
    ms_map = {w.get('id'): w for w in wbs if w.get('milestone')}
    for m in ms_map.values():
        mid_ = m.get('id')
        leaves = []
        for w in wbs:
            if w.get('summary') or w.get('milestone') or w.get('tier') == 'program':
                continue
            mref = w.get('milestone_ref')
            if mref == mid_:
                leaves.append(w.get('id'))
                continue
            deps = _parse_deps(w.get('dependsOn'))
            # 依赖末端（无前置的链尾）落在里程碑上，也视为归属
            if mid_ in deps:
                leaves.append(w.get('id'))
        b = m.get('billing') or {}
        milestone_coverage.append({
            'id': mid_,
            'name': m.get('name', mid_),
            'payment_id': b.get('payment_id'),
            'fee': b.get('fee_inr') or b.get('fee'),
            'fee_type': b.get('fee_type'),
            'date': sched.get(mid_, (None, None, False))[0].isoformat() if mid_ in sched else (m.get('start') or ''),
            'leaves': leaves,
            'leaf_count': len(leaves),
        })
    # Pillar 4: 支付↔排期联动 —— 每条固定费率支付行 + 其里程碑 + 排期日 vs 合同 due_date
    payment_linkage = []
    prog = data.get('program') or {}
    sows_src = (prog.get('sows') or []) + (data.get('sow_map') or [])
    for s in sows_src:
        fee = s.get('fee')
        if isinstance(fee, str):
            fee = re.sub(r'[^0-9.]', '', fee) or '0'
        try:
            fee_v = float(fee)
        except (TypeError, ValueError):
            fee_v = 0.0
        ft = s.get('fee_type')
        if ft != 'fixed' or fee_v <= 0:
            continue
        sid = s.get('sow')
        # 该 SOW 下所有计费里程碑
        ms_for_sow = [mc for mc in milestone_coverage if mc['payment_id'] and str(mc['id']).startswith(sid + '.')]
        for mc in ms_for_sow:
            # 里程碑计费（fixed）且无独立合同日历 → 付款随该里程碑达成即到期（收款节奏=交付节奏）；
            # 若合同显式给了 due_date，则按合同日历比对（可触发 drift）。
            due = (s.get('due_date') or (s.get('billing') or {}).get('due_date') or mc['date'])
            payment_linkage.append({
                'sow': sid,
                'payment_id': mc['payment_id'],
                'milestone': mc['id'],
                'scheduled': mc['date'],
                'contract_due': due or '',
                'fee': mc['fee'],
                'status': ('linked' if (due and mc['date'] and mc['date'] <= due) else ('drift' if due else 'no-due')),
            })
    if not payment_linkage:
        # 单层项目：直接用 billing 里程碑
        for mc in milestone_coverage:
            if mc['fee_type'] == 'fixed' and mc['fee']:
                payment_linkage.append({
                    'sow': str(mc['id']).split('.')[0],
                    'payment_id': mc['payment_id'] or mc['id'],
                    'milestone': mc['id'],
                    'scheduled': mc['date'],
                    'contract_due': '',
                    'fee': mc['fee'],
                    'status': 'no-due',
                })

    tpl_path = a.template or os.path.join(SCRIPT_DIR, '..', 'templates', 'waterfall', 'schedule_gantt.md')
    tpl_path = os.path.abspath(tpl_path)
    if not os.path.exists(tpl_path):
        raise SystemExit(f"排期模板不存在：{tpl_path}")
    with open(tpl_path, 'r', encoding='utf-8') as f:
        tpl = f.read()
    from render import render
    ctx = {'project': data.get('project', {}), 'view_label': view_label,
           'tasks': tasks, 'granularity': a.granularity,
           'milestone_coverage': milestone_coverage, 'payment_linkage': payment_linkage}
    if a.granularity == 'fortnight':
        ctx['fortnight_groups'] = _fortnight_groups(tasks, project_start)
    rendered = render(tpl, ctx)

    root = os.path.dirname(os.path.abspath(a.project))
    out_path = a.out or os.path.join(root, out_def)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(rendered)

    rel = os.path.relpath(out_path, root)
    if 'artifacts' not in data or not isinstance(data['artifacts'], dict):
        data['artifacts'] = {}
    data['artifacts'][art_key] = rel
    _save(a.project, data)

    print(f"[schedule] 已生成排期计划（{view_label} 视图，{len(tasks)} 个任务，项目起始 {project_start.isoformat()}）：{out_path}")
    print(f"[schedule] artifacts.{art_key} = {rel}")


if __name__ == '__main__':
    main()
