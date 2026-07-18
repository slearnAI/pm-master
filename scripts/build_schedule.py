#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · WBS -> 排期计划（Schedule / Gantt）生成器
-------------------------------------------------
把 `project.yaml` 的 WBS 真正「转成」一份可跟踪的排期计划交付物（schedule_gantt.md），
而不是只把关键路径打印到 stdout（那是 schedule_health.py 的职责）。

做什么：
  1. 正向排程（forward pass）：以项目起始日 + 各任务工期(duration) + 依赖(dependsOn)
     推算每个任务的 最早开始(ES)/最早结束(EF)，得到每个任务的 开始/结束 日期。
  2. 把推算出的 start/end 回写 project.yaml 的 wbs[].start/end（单一事实源，
     让 wbs.md 与 schedule_gantt.md 共用同一套日期）。
  3. 基于 wbs 派生 `tasks` 列表，渲染 templates/waterfall/schedule_gantt.md
     -> <项目根>/plans/schedule_gantt.md（排期计划交付物）。
  4. 把产物路径写回 project.yaml 的 artifacts.schedule_gantt。

这是 P0/P1 规划的「主要交付物」之一（见 references/phases/p0-p1-initiation-planning.md）。
waterfall / hybrid 在规划期必须运行本脚本；agile/iteration 无甘特排期，可跳过。

用法：
  python3 build_schedule.py --project /workspace/<slug>/project.yaml
  python3 build_schedule.py --project <yaml> --start 2026-08-01          # 指定项目起始日
  python3 build_schedule.py --project <yaml> --out /path/to/schedule.md   # 自定义输出
  python3 build_schedule.py --project <yaml> --no-write-back              # 只渲染，不回写 yaml
"""
import argparse
import os
import sys
import datetime

# 允许以脚本方式 import 同目录的 render / schedule_health
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


def forward_schedule(wbs, project_start):
    """对每个可排程的 wbs 任务做正向排程，返回 {id: (start_date, end_date, is_milestone)}。

    - 工期：优先 start/end 日期差；否则由 _parse_duration_days 解析 duration 字段。
    - 依赖：wbs[].dependsOn（列表或逗号串），经 _parse_deps 解析。
    - 项目内依赖未排程前先跳过，迭代松弛到稳定（DAG 必然收敛）。
    - 外部依赖（id 不在本 wbs）视作已满足，不影响排程。
    """
    info = {}  # id -> {dur, deps, milestone}
    for w in wbs:
        wid = w.get('id')
        if not wid:
            continue
        dur = _parse_duration_days(w)
        deps = _parse_deps(w.get('dependsOn'))
        milestone = bool(w.get('milestone')) or dur == 0
        info[wid] = {'dur': dur, 'deps': deps, 'milestone': milestone}

    es = {}  # id -> 偏移天数（自项目起始）
    changed = True
    guard = 0
    while changed and guard < 10000:
        changed = False
        guard += 1
        for tid, it in info.items():
            deps = it['deps']
            if not deps:
                new_s = 0
            else:
                in_proj = [d for d in deps if d in info]
                if len(in_proj) < len([d for d in deps if d]):
                    # 仍有项目内前置未排程，本轮跳过
                    continue
                new_s = max([es[d] + info[d]['dur'] for d in in_proj] + [0])
            if es.get(tid) != new_s:
                es[tid] = new_s
                changed = True

    result = {}
    for tid, it in info.items():
        off = es.get(tid, 0)
        start = project_start + datetime.timedelta(days=off)
        if it['milestone']:
            end = start
        else:
            end = start + datetime.timedelta(days=it['dur'])
        result[tid] = (start, end, it['milestone'])
    return result


def main():
    ap = argparse.ArgumentParser(description="PM Master · WBS -> 排期计划生成器")
    ap.add_argument('--project', required=True, help="单一事实源 project.yaml")
    ap.add_argument('--start', default=None, help="项目起始日 ISO，如 2026-08-01（缺省取 project.start_date，再缺省取今天）")
    ap.add_argument('--out', default=None, help="输出 .md 路径（缺省 <项目根>/plans/schedule_gantt.md）")
    ap.add_argument('--no-write-back', action='store_true', help="只渲染排期，不回写 project.yaml 的 wbs 日期")
    ap.add_argument('--template', default=None, help="排期模板路径（缺省取技能内 templates/waterfall/schedule_gantt.md）")
    a = ap.parse_args()

    if yaml is None:
        raise SystemExit("需要 PyYAML：请先 `pip install pyyaml`")

    data = _load(a.project)
    wbs = data.get('wbs') or []
    if not wbs:
        raise SystemExit("⚠ project.yaml 中未找到 wbs，无法生成排期计划（请先完成 WBS 拆解）。")

    # 项目起始日
    start_iso = a.start or (data.get('project') or {}).get('start_date')
    if start_iso:
        try:
            project_start = datetime.date.fromisoformat(str(start_iso)[:10])
        except ValueError:
            raise SystemExit(f"非法的 --start / project.start_date：{start_iso}")
    else:
        project_start = datetime.date.today()
        print(f"[schedule] 未指定起始日，使用今天 {project_start.isoformat()}（建议用 --start 或填 project.start_date）")

    sched = forward_schedule(wbs, project_start)

    # 回写 start/end
    if not a.no_write_back:
        for w in wbs:
            tid = w.get('id')
            if tid in sched:
                s, e, _ = sched[tid]
                w['start'] = s.isoformat()
                w['end'] = e.isoformat()

    # 构造渲染用的 tasks 列表（跳过纯汇总行 summary；里程碑保留）
    tasks = []
    for w in wbs:
        tid = w.get('id')
        if not tid or w.get('summary'):
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

    # 渲染
    tpl_path = a.template or os.path.join(SCRIPT_DIR, '..', 'templates', 'waterfall', 'schedule_gantt.md')
    tpl_path = os.path.abspath(tpl_path)
    if not os.path.exists(tpl_path):
        raise SystemExit(f"排期模板不存在：{tpl_path}")
    with open(tpl_path, 'r', encoding='utf-8') as f:
        tpl = f.read()
    from render import render
    rendered = render(tpl, {'project': data.get('project', {}), 'tasks': tasks})

    root = os.path.dirname(os.path.abspath(a.project))
    out_path = a.out or os.path.join(root, 'plans', 'schedule_gantt.md')
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(rendered)

    # 写回 artifacts 索引（相对项目根）
    rel = os.path.relpath(out_path, root)
    if 'artifacts' not in data or not isinstance(data['artifacts'], dict):
        data['artifacts'] = {}
    data['artifacts']['schedule_gantt'] = rel

    if not a.no_write_back:
        _save(a.project, data)
    else:
        # 仅当 --no-write-back 时仍需保存 artifacts；否则上面已整体保存
        _save(a.project, data)

    print(f"[schedule] 已生成排期计划：{out_path}（{len(tasks)} 个任务，项目起始 {project_start.isoformat()}）")
    print(f"[schedule] artifacts.schedule_gantt = {rel}")


if __name__ == '__main__':
    main()
