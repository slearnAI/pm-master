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

    # 拓扑排序（Kahn）——仅统计项目内依赖；外部依赖视为已满足
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
    if len(topo) < len(tasks):  # 存在环，补齐剩余节点避免崩溃
        for t in tasks:
            if t not in topo:
                topo.append(t)

    # 正向 ES/EF（按拓扑序；外部依赖 p∉tasks 视为已满足，不影响排期）
    es, ef = {}, {}
    for tid in topo:
        dur = tasks[tid].get('duration', 0)
        start = 0
        for p in deps[tid]:
            if p in ef:
                start = max(start, ef[p])
        es[tid], ef[tid] = start, start + dur

    project_end = max(ef.values()) if ef else 0
    # 反向 LF/LS（逆拓扑序，保证后继已先算出 LS）
    lf, ls = {}, {}
    for tid in reversed(topo):
        succ = [t for t in topo if tid in deps.get(t, [])]
        if not succ:
            lf[tid] = project_end
        else:
            lf[tid] = min(ls[s] for s in succ)
        ls[tid] = lf[tid] - tasks[tid].get('duration', 0)

    print("=== 排期健康度 ===")
    if issues:
        print("⚠ 依赖问题:")
        for i in issues:
            print("  -", i)
    else:
        print("✓ 依赖完整")
    print(f"项目总工期: {project_end} 天")
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
    print("关键路径:", " -> ".join(crit_path) if crit_path else "无")


if __name__ == '__main__':
    main()
