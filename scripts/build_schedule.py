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
import sys
import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    import yaml
except ImportError:
    yaml = None

from schedule_health import _parse_deps, _parse_duration_days  # 复用工期/依赖解析


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
        return inc
    return None  # full


def forward_schedule(wbs, project_start, include_ids=None):
    """正向排程，返回 {id: (start_date, end_date, is_milestone)}。

    include_ids 不为 None 时只排程该集合内的行；集合外依赖视为已满足。
    """
    info = {}
    for w in wbs:
        wid = w.get('id')
        if not wid:
            continue
        if include_ids is not None and wid not in include_ids:
            continue
        dur = _parse_duration_days(w)
        deps = _parse_deps(w.get('dependsOn'))
        milestone = bool(w.get('milestone')) or dur == 0
        info[wid] = {'dur': dur, 'deps': deps, 'milestone': milestone}

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
    for tid, it in info.items():
        off = es.get(tid, 0)
        start = project_start + datetime.timedelta(days=off)
        end = start if it['milestone'] else start + datetime.timedelta(days=it['dur'])
        result[tid] = (start, end, it['milestone'])
    return result


def main():
    ap = argparse.ArgumentParser(description="PM Master · WBS -> 排期计划生成器")
    ap.add_argument('--project', required=True, help="单一事实源 project.yaml")
    ap.add_argument('--level', default='auto', choices=['auto', 'full', 'program'],
                    help="视图：auto=按类型自动 / full=全部 / program=项目群里程碑级")
    ap.add_argument('--sow', default=None, help="仅排程该 SOW 子树（如 SOW1），输出为该 SOW 自己的计划")
    ap.add_argument('--start', default=None, help="项目起始日 ISO，如 2026-08-01")
    ap.add_argument('--out', default=None, help="输出 .md 路径（覆盖默认）")
    ap.add_argument('--no-write-back', action='store_true', help="只渲染排期，不回写 project.yaml 的 wbs 日期")
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

    start_iso = a.start or (data.get('project') or {}).get('start_date')
    if start_iso:
        try:
            project_start = datetime.date.fromisoformat(str(start_iso)[:10])
        except ValueError:
            raise SystemExit(f"非法的 --start / project.start_date：{start_iso}")
    else:
        project_start = datetime.date.today()
        print(f"[schedule] 未指定起始日，使用今天 {project_start.isoformat()}（建议用 --start 或填 project.start_date）")

    sched = forward_schedule(wbs, project_start, include_ids)

    if not a.no_write_back:
        for w in wbs:
            tid = w.get('id')
            if tid in sched:
                s, e, _ = sched[tid]
                w['start'] = s.isoformat()
                w['end'] = e.isoformat()

    # 构造 tasks：full 跳过 summary；program/sow 包含选中集合内全部行
    tasks = []
    for w in wbs:
        tid = w.get('id')
        if not tid:
            continue
        if include_ids is not None:
            if tid not in include_ids:
                continue
        else:
            if w.get('summary'):
                continue
        s, e, milestone = sched.get(tid, (None, None, False))
        tasks.append({
            'id': tid,
            'name': w.get('name', tid),
            'duration': _parse_duration_days(w),
            'deps': _parse_deps(w.get('dependsOn')),
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

    tpl_path = a.template or os.path.join(SCRIPT_DIR, '..', 'templates', 'waterfall', 'schedule_gantt.md')
    tpl_path = os.path.abspath(tpl_path)
    if not os.path.exists(tpl_path):
        raise SystemExit(f"排期模板不存在：{tpl_path}")
    with open(tpl_path, 'r', encoding='utf-8') as f:
        tpl = f.read()
    from render import render
    rendered = render(tpl, {'project': data.get('project', {}), 'view_label': view_label, 'tasks': tasks})

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
