#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · 排期健康度校验
-------------------------------------------------
两种输入模式：
  A. 独立排期文件：--data schedule.yaml(.json)，tasks 列表，每项：
       id, name, duration(天), deps: [前置任务id...]   （deps 可选）
     可选：start(项目起始日期, ISO) 用于推算各任务日期。
  B. 单一事实源：--project project.yaml —— 直接从其中的 wbs 推导排期网络：
     - 工期(duration)：优先用 start/end 日期差(日历天)；否则解析 duration 字段
       （"N wks" → N×7 天；"Gate" → 0）。
     - 依赖(deps)：解析 wbs 每行的 dependsOn（兼容 列表 与 逗号分隔字符串）。

输出：
  - 缺失/未知依赖告警
  - 关键路径（最长工期路径）
  - 每个任务的 最早开始/结束、最晚开始/结束、浮动时间(slack)

用法：
  python3 schedule_health.py --data schedule.yaml [--start 2025-08-01]
  python3 schedule_health.py --project /workspace/<slug>/project.yaml
"""
import argparse
import json
import re
import sys
import datetime
from collections import defaultdict

try:
    import yaml
except ImportError:
    yaml = None


def load(path):
    with open(path, 'r', encoding='utf-8') as f:
        raw = f.read()
    if path.endswith(('.yaml', '.yml')):
        return yaml.safe_load(raw)
    return json.loads(raw)


def _parse_deps(dep):
    """dependsOn 兼容 列表 与 逗号分隔字符串。"""
    if dep is None:
        return []
    if isinstance(dep, list):
        out = []
        for x in dep:
            sx = str(x).strip()
            if sx and sx not in ('—', '-'):
                out.append(sx)
        return out
    s = str(dep)
    if s.strip() in ('', '—', '-'):
        return []
    return [p.strip() for p in re.split(r'[,;，；]', s) if p.strip()]


def _parse_duration_days(item):
    """优先用 start/end 日期差；否则解析 duration 字段。"""
    s, e = item.get('start'), item.get('end')
    if s and e:
        try:
            d0 = datetime.date.fromisoformat(str(s)[:10])
            d1 = datetime.date.fromisoformat(str(e)[:10])
            return max((d1 - d0).days, 0)
        except ValueError:
            pass
    dur = str(item.get('duration', '') or '')
    m = re.search(r'(\d+(?:\.\d+)?)\s*w', dur, re.I)
    if m:
        return int(float(m.group(1)) * 7)  # 周 → 日历天
    m = re.search(r'(\d+(?:\.\d+)?)\s*d', dur, re.I)
    if m:
        return int(float(m.group(1)))
    if 'gate' in dur.lower():
        return 0
    m = re.search(r'(\d+(?:\.\d+)?)', dur)
    return int(float(m.group(1))) if m else 0


def tasks_from_project(data):
    """从 project.yaml 的 wbs 推导 tasks 列表。"""
    wbs = data.get('wbs') or []
    tasks = []
    for w in wbs:
        tasks.append({
            'id': w.get('id'),
            'name': w.get('name', w.get('id')),
            'duration': _parse_duration_days(w),
            'deps': _parse_deps(w.get('dependsOn')),
            'start': w.get('start'),
            'end': w.get('end'),
            'children': w.get('children'),
        })
    return tasks


def main():
    ap = argparse.ArgumentParser(description="PM Master 排期健康度")
    ap.add_argument('--data', default=None, help="独立排期文件 schedule.yaml(.json)")
    ap.add_argument('--project', default=None, help="单一事实源 project.yaml（直接读 wbs）")
    ap.add_argument('--start', default=None, help="项目起始日期 ISO，如 2025-08-01")
    a = ap.parse_args()
    if not a.data and not a.project:
        ap.error("必须提供 --data 或 --project 之一")

    if a.project:
        d = load(a.project)
        task_list = tasks_from_project(d)
        if not task_list:
            print("⚠ project.yaml 中未找到 wbs 排期数据，无法计算关键路径。")
            sys.exit(1)
    else:
        d = load(a.data)
        task_list = d.get('tasks', [])

    tasks = {t['id']: t for t in task_list}
    deps = {tid: t.get('deps', []) for tid, t in tasks.items()}

    issues = []
    for tid, ds in deps.items():
        for dep in ds:
            if dep not in tasks:
                issues.append(f"任务 {tid} 依赖未知任务 {dep}")

    # ---- 环检测（Kahn 拓扑排序；未排完的节点 = 存在循环依赖）----
    indeg = {tid: 0 for tid in tasks}
    for tid, ds in deps.items():
        for p in ds:
            if p in tasks:
                indeg[tid] += 1
    topo = []
    queue = [t for t in tasks if indeg[t] == 0]
    while queue:
        n = queue.pop(0)
        topo.append(n)
        for t in tasks:
            if n in deps.get(t, []):
                indeg[t] -= 1
                if indeg[t] == 0:
                    queue.append(t)
    cyclic = [t for t in tasks if t not in topo]
    if cyclic:
        # 定位构成环的边（依赖指向环内节点），便于用户修复
        cycle_edges = []
        for t in cyclic:
            for d in deps[t]:
                if d in cyclic:
                    cycle_edges.append(f"{t} → {d}")
        issues.append("⚠ 检测到循环依赖（无法排期），请断开以下边之一："
                      + "; ".join(cycle_edges[:12]) + ("…" if len(cycle_edges) > 12 else ""))

    # ---- 优先使用 project.yaml 中已有的日历 start/end 计算浮动 ----
    # 若同一行既有 deps 又有真实 start/end，以日历日期为准（尊重 build_schedule 的波次并行）；
    # 否则退回顺序模型（duration 累加）。两种模型不可混用，避免 "项目总工期" 口径失真。
    # 仅统计叶子任务（children 为空）的日历日期；含 children 的汇总行即使无日期也算“有”
    leaf_tasks = [t for t in tasks if t not in cyclic and not tasks[t].get('children')]
    have_calendar = all((tasks[t].get('start') and tasks[t].get('end')) for t in leaf_tasks)
    cal_start = {}
    cal_end = {}
    for t in tasks:
        s = tasks[t].get('start'); e = tasks[t].get('end')
        if s and e:
            try:
                cal_start[t] = datetime.date.fromisoformat(str(s)[:10])
                cal_end[t] = datetime.date.fromisoformat(str(e)[:10])
            except (ValueError, TypeError):
                pass
    use_calendar = have_calendar and len(cal_start) > 0

    if use_calendar:
        # 浮动 = 允许最晚完成 - 计划完成（以日历天计，非顺序天）
        # LF 反向传播：无后继的节点 LF = 项目最晚 end；否则 LF = min(后继 LS)
        # 先求 project 基准（最早 start 与最晚 end），用于无后继节点的 LF
        proj_min = min(cal_start.values())
        proj_max = max(cal_end.values())
        # 正向：planned day 偏移（相对 proj_min）
        def dayoff(d):
            return (d - proj_min).days
        es = {t: dayoff(cal_start[t]) for t in cal_start}
        ef = {t: dayoff(cal_end[t]) for t in cal_end}
        # 反向 LF/LS（仅在 acyclic 子图上；cyclic 节点跳过，避免崩溃）
        lf, ls = {}, {}
        succ_of = {t: [] for t in tasks}
        for t in topo:
            for d in deps[t]:
                if d in topo:
                    succ_of[d].append(t)
        for tid in reversed(topo):
            succ = succ_of.get(tid, [])
            if not succ:
                # 无后继：LF = 项目最晚 end 的偏移
                lf[tid] = dayoff(proj_max)
            else:
                lf[tid] = min(ls[s] for s in succ)
            ls[tid] = lf[tid] - (ef[tid] - es[tid])
        model_label = "日历模型（尊重波次并行，start/end 来自 project.yaml）"
        project_end = dayoff(proj_max)
    else:
        # 顺序模型（无日历日期时）
        es, ef = {}, {}
        for tid in topo:
            dur = tasks[tid].get('duration', 0)
            start = 0
            for p in deps[tid]:
                if p in ef:
                    start = max(start, ef[p])
            es[tid], ef[tid] = start, start + dur
        project_end = max(ef.values()) if ef else 0
        lf, ls = {}, {}
        for tid in reversed(topo):
            succ = [t for t in topo if tid in deps.get(t, [])]
            if not succ:
                lf[tid] = project_end
            else:
                lf[tid] = min(ls[s] for s in succ)
            ls[tid] = lf[tid] - tasks[tid].get('duration', 0)
        model_label = "顺序模型（按 duration 累加；无 start/end 时为上界估算）"

    print("=== 排期健康度 ===")
    if issues:
        print("⚠ 依赖问题:")
        for i in issues:
            print("  -", i)
    else:
        print("✓ 依赖完整")
    print(f"排期模型: {model_label}")
    print(f"项目总工期(日历天): {project_end} 天")
    print(f"{'ID':<8}{'名称':<14}{'ES':>4}{'EF':>4}{'LS':>4}{'LF':>4}{'浮动':>6}  关键?")
    crit_path = []
    for tid in topo:
        if tid not in es:
            print(f"{tid:<8}{tasks[tid].get('name',''):<14}  (无法排期: 缺前置或成环)")
            continue
        slack = ls[tid] - es[tid]
        crit = '★' if slack == 0 else ''
        if crit:
            crit_path.append(tid)
        print(f"{tid:<8}{str(tasks[tid].get('name',''))[:12]:<14}"
              f"{es[tid]:>4}{ef[tid]:>4}{ls[tid]:>4}{lf[tid]:>4}{slack:>6}   {crit}")
    for tid in cyclic:
        print(f"{tid:<8}{tasks[tid].get('name',''):<14}  (循环依赖，已排除在关键路径外)")
    print("关键路径:", " -> ".join(crit_path) if crit_path else "无")
    if cyclic:
        print("⚠ 注：存在循环依赖的节点未参与关键路径计算，修复后重新运行以获得完整结果。")


if __name__ == '__main__':
    main()
