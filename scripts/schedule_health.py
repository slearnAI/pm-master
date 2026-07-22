#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · 排期健康度校验（增强版 v2）
-------------------------------------------------
在保持向后兼容的前提下，支持：
  1. 类型化依赖 FS/SS/FF/SF + lag/lead（如 "T1+3" = FS lag+3；{id:T1,type:SS,lag:-5} = SS 提前 5 天重叠）
  2. 工作量→工期溶解：effort(person-days) / (resources × availability × productivity) = 日历工期
  3. 资源受限级联（resource leveling）：同名资源被多任务并发占用时自动顺延，得到“有效并行”
  4. 资源受限关键路径（leveled critical path）：LS/LF/slack 在级联后重算
  5. --whatif 压缩分析：对每条关键任务 +1 资源单位，给出项目总工期缩减量

两种输入模式：
  A. 独立排期文件：--data schedule.yaml(.json)
  B. 单一事实源：--project project.yaml（直接从 wbs 推导；自动启用增强引擎当存在 effort/resources/leveling）

向后兼容：
  - dependsOn: "T1"（字符串）仍按 FS lag0 解析（与旧脚本一致）
  - 无 effort/resources → 沿用 duration/estimate（旧行为）
  - 无 resources 池 / control.scheduling → 不级联，纯 CPM（旧行为）
  - 保留 _parse_deps / _parse_duration_days 供 build_schedule 等脚本 import（签名不变）
"""
import argparse
import json
import re
import sys
import math
import datetime
from collections import defaultdict

try:
    import yaml
except ImportError:
    yaml = None


# ---------------- 兼容层（供其他脚本 import，签名不变） ----------------

def _parse_deps(dep):
    """dependsOn 兼容 列表 与 逗号分隔字符串两种写法。返回 id 列表（旧行为）。"""
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


def _load_project(path):
    """读取 project.yaml / 排期 json。"""
    with open(path, 'r', encoding='utf-8') as f:
        raw = f.read()
    if path.endswith(('.yaml', '.yml')):
        return yaml.safe_load(raw)
    return json.loads(raw)


def _load(path):
    """兼容别名（旧 main 内遗留调用）。"""
    return _load_project(path)


def tasks_from_project(data):
    """从 project.yaml 的 wbs 推导 tasks 列表（旧签名，供 --data 模式/兼容）。"""
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
    """从 project.yaml 的 wbs 推导 tasks 列表（旧签名，供 --data 模式/兼容）。"""
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


# ---------------- 增强层 ----------------

_DEP_TYPES = ('FS', 'SS', 'FF', 'SF')


def _normalize_dep_entry(it):
    """单个 dependsOn 项 → {'id','type','lag'}。"""
    if isinstance(it, dict):
        raw_id = it.get('id') or it.get('to') or it.get('pred')
        typ = str((it.get('type') or 'FS')).upper()
        if typ not in _DEP_TYPES:
            typ = 'FS'
        lag = it.get('lag')
        try:
            lag = float(lag)
        except (TypeError, ValueError):
            lag = 0.0
        return {'id': str(raw_id), 'type': typ, 'lag': lag}
    # 字符串：支持 "id+N" / "id-N" 简写（FS + lag/lead）
    s = str(it).strip()
    m = re.match(r'^(.+?)([+\-]\d+(?:\.\d+)?)$', s)
    if m:
        return {'id': m.group(1).strip(), 'type': 'FS', 'lag': float(m.group(2))}
    return {'id': s, 'type': 'FS', 'lag': 0.0}


def _parse_deps_typed(dep):
    """返回 [{id,type,lag}, ...]，兼容字符串/列表/字典写法。按 id 去重（保留首次），
    避免重复依赖边导致拓扑 indegree 错配（误判成环）。"""
    if dep is None:
        return []
    if isinstance(dep, list):
        items = dep
    elif isinstance(dep, str):
        if dep.strip() in ('', '—', '-'):
            return []
        items = [p.strip() for p in re.split(r'[,;，；]', dep) if p.strip()]
    else:
        return []
    out = []
    seen = set()
    for it in items:
        e = _normalize_dep_entry(it)
        if e['id'] and e['id'] not in seen:
            seen.add(e['id'])
            out.append(e)
    return out


def _resolve_resources(w, res_index):
    """返回 (units, group)。units 用于工期计算；group(frozenset 或 None) 用于资源级联。"""
    res = w.get('resources')
    if res is None:
        return 1, None
    if isinstance(res, int):
        return (res if res > 0 else 1), None
    if isinstance(res, str):
        # 角色键：匿名单位 1，按 role 分组便于同角色级联
        return 1, ('role:' + res)
    if isinstance(res, list):
        ids = [str(x) for x in res]
        known = [i for i in ids if i in (res_index or {})]
        units = sum(float((res_index or {}).get(i, {}).get('capacity', 1.0)) for i in known) if known \
            else len(ids)
        grp = frozenset(known) if known else frozenset(ids)
        return (units if units > 0 else len(ids)), grp
    return 1, None


def _resolve_effort_duration(w, sched_cfg, res_index):
    """返回 (duration_days, effort_info)。若显式设 duration → 作为覆盖；否则由 effort 推导。"""
    dur = _parse_duration_days(w)
    if dur > 0:
        return dur, None  # 显式工期覆盖
    effort = w.get('effort')
    if effort is None:
        effort = w.get('estimate')
    try:
        effort = float(effort)
    except (TypeError, ValueError):
        effort = 0.0
    if effort is None or effort <= 0:
        return 0, None
    units, _ = _resolve_resources(w, res_index)
    avail = float((sched_cfg or {}).get('availability', 1.0) or 1.0)
    prod = float((sched_cfg or {}).get('productivity', 1.0) or 1.0)
    denom = units * avail * prod
    if denom <= 0:
        denom = units if units > 0 else 1
    dur = max(1, int(math.ceil(effort / denom)))
    return dur, {'effort': effort, 'units': units, 'avail': avail, 'prod': prod}


def _dep_start(dur_i, es_p, ef_p, typ, lag):
    """根据依赖类型计算后继任务的最早开始偏移（相对项目起点天数）。"""
    lag = lag or 0.0
    if typ == 'SS':
        return es_p + lag
    if typ == 'FF':
        return (ef_p + lag) - dur_i
    if typ == 'SF':
        return (es_p + lag) - dur_i
    return es_p + (ef_p - es_p) + lag  # FS: ef_p + lag


def _topo_order(info):
    indeg = {tid: 0 for tid in info}
    preds = {tid: sorted(set(d['id'] for d in info[tid]['deps'] if d['id'] in info))
             for tid in info}
    for tid, ps in preds.items():
        indeg[tid] = len(ps)
    queue = [t for t in info if indeg[t] == 0]
    topo = []
    while queue:
        n = queue.pop(0)
        topo.append(n)
        for t in info:
            if n in [d['id'] for d in info[t]['deps']] and n in info:
                indeg[t] -= 1
                if indeg[t] == 0:
                    queue.append(t)
    return topo  # 含环时非全量，调用方据 len 判环


def compute_schedule(wbs, resources=None, sched_cfg=None, include_ids=None,
                     level=True, recompute=True, project_start_days=0):
    """增强排期内核。

    返回 dict：{
      'tasks': {tid: {es,ef,ls,lf,slack,dur,critical,milestone,deps(group list),group,effort}},
      'project_end': int,
      'critical_path': [tid...],
      'issues': [str...],
      'leveled': bool,
    }
    es/ef/ls/lf/slack 均为相对 project_start 的天数偏移。
    """
    res_index = {r.get('id'): r for r in (resources or [])}
    info = {}
    for w in wbs:
        wid = w.get('id')
        if not wid:
            continue
        milestone = bool(w.get('milestone'))
        summary = bool(w.get('summary'))
        dur, eff = _resolve_effort_duration(w, sched_cfg, res_index)
        if summary:
            dur = 0
        deps = _parse_deps_typed(w.get('dependsOn'))
        # 里程碑由其 components 驱动（FS, lag0），实现“里程碑=一组任务完成”
        if milestone and w.get('components'):
            for c in w['components']:
                deps.append({'id': str(c), 'type': 'FS', 'lag': 0.0})
        # 去重（components 可能与 dependsOn 指向同一叶子）
        seen = set(); ded = []
        for d in deps:
            if d['id'] not in seen:
                seen.add(d['id']); ded.append(d)
        deps = ded
        units, group = _resolve_resources(w, res_index)
        info[wid] = {'dur': dur, 'deps': deps, 'milestone': milestone,
                     'summary': summary, 'group': group, 'units': units, 'effort': eff}
    if include_ids is not None:
        info = {k: v for k, v in info.items() if k in include_ids}

    issues = []
    topo = _topo_order(info)
    cyclic = [t for t in info if t not in topo]
    if cyclic:
        edges = []
        for t in cyclic:
            for d in info[t]['deps']:
                if d['id'] in cyclic:
                    edges.append(f"{t}→{d['id']}")
        issues.append("⚠ 检测到循环依赖（无法排期），请断开以下边之一："
                      + "; ".join(edges[:12]) + ("…" if len(edges) > 12 else ""))

    # ---- 正向排程（类型化依赖 + forced 地板，用于级联） ----
    forced = {}

    def forward():
        es = {}
        changed = True
        guard = 0
        # 多次迭代保证依赖传递收敛
        while changed and guard < 100000:
            changed = False
            guard += 1
            for tid in topo:
                it = info[tid]
                deps = it['deps']
                if any((d['id'] in info) and (es.get(d['id']) is None) for d in deps):
                    continue
                s = forced.get(tid, 0)
                for d in deps:
                    if d['id'] in info and es.get(d['id']) is not None:
                        dp = info[d['id']]
                        s = max(s, _dep_start(it['dur'], es[d['id']],
                                              es[d['id']] + dp['dur'], d['type'], d['lag']))
                if es.get(tid) != s:
                    es[tid] = s
                    changed = True
        return es

    es = forward()
    # 汇总包 dur=0，需自底向上回写真实跨度（用于显示，不影响级联）
    # 级联：按资源组顺延
    leveled = False
    if level and any(info[t]['group'] is not None for t in info):
        for _ in range(500):
            es = forward()
            changed = False
            groups = defaultdict(list)
            for tid, it in info.items():
                if it['group'] is not None:
                    groups[it['group']].append(tid)
            for g, members in groups.items():
                if len(members) < 2:
                    continue
                ms = sorted(members, key=lambda t: (es[t], t))
                cursor = es[ms[0]] + info[ms[0]]['dur']  # 首成员占用至其结束
                for t in ms[1:]:
                    if es[t] < cursor:
                        forced[t] = cursor
                        changed = True
                    cursor = max(cursor, es[t] + info[t]['dur'])
            if not changed:
                break
        leveled = True
        es = forward()

    # 计算 EF
    ef = {t: es[t] + info[t]['dur'] for t in info}

    # 汇总包 rollup：ES=min(子项ES), EF=max(子项EF)（按 id 前缀归集子树）
    for tid, it in info.items():
        if it['summary']:
            desc = [t for t in info if t != tid and t.startswith(tid + '.')]
            if desc:
                es[tid] = min(es[t] for t in desc)
                ef[tid] = max(ef[t] for t in desc)
                it['dur'] = ef[tid] - es[tid]

    # ---- 反向排程（类型化 LS/LF/slack） ----
    proj_end = max(ef.values()) if ef else 0
    succ = {tid: [] for tid in info}
    for tid, it in info.items():
        if it['summary']:
            # 汇总包仅作 rollup，不作为反向约束（其后继已由子叶子承载）
            continue
        for d in it['deps']:
            if d['id'] in info and not info[d['id']]['summary']:
                succ[d['id']].append((tid, d['type'], d['lag']))
    lf, ls = {}, {}
    inf = float('inf')
    for tid in reversed(topo):
        if tid in cyclic or info[tid]['summary']:
            # 汇总包不计入关键路径/浮动：LS/LF 与 ES/EF 对齐
            lf[tid] = ef[tid]; ls[tid] = es[tid]
            continue
        d = info[tid]['dur']
        cands_lf, cands_ls = inf, inf
        for (j, typ, lag) in succ[tid]:
            if j in cyclic or j not in ls:
                continue
            if typ == 'FS':
                cands_lf = min(cands_lf, ls[j])
            elif typ == 'SS':
                cands_ls = min(cands_ls, ls[j] - lag)
            elif typ == 'FF':
                cands_lf = min(cands_lf, lf[j] - lag)
            elif typ == 'SF':
                cands_ls = min(cands_ls, lf[j] - lag)
        if cands_lf != inf:
            lf[tid] = cands_lf
            ls[tid] = cands_lf - d
        elif cands_ls != inf:
            ls[tid] = cands_ls
            lf[tid] = cands_ls + d
        else:
            lf[tid] = proj_end
            ls[tid] = proj_end - d
    slack = {t: (ls[t] - es[t]) for t in info if t in ls}

    # 关键路径：slack==0 的在拓扑序中连成的链（从最早开始的关键任务回溯）
    critical = {t for t in info if t in slack and slack[t] == 0 and not info[t]['summary']}
    # 构造有序关键路径：从某 critical 起点（无 critical 前驱）沿 critical 后继走
    crit_succ = {t: [s for s in succ[t] if s in critical] for t in info}
    crit_pred = {t: [d['id'] for d in info[t]['deps'] if d['id'] in critical] for t in info}
    starts = [t for t in critical if not crit_pred[t]]
    path = []
    seen = set()
    for st in starts:
        cur = st
        while cur and cur not in seen:
            seen.add(cur)
            path.append(cur)
            nxts = [s for s in crit_succ[cur] if s not in seen]
            cur = nxts[0] if nxts else None
    # 若环或遗漏，补其余 critical
    for t in critical:
        if t not in seen:
            path.append(t)

    tasks = {}
    for tid in info:
        it = info[tid]
        tasks[tid] = {
            'es': es.get(tid), 'ef': ef.get(tid),
            'ls': ls.get(tid), 'lf': lf.get(tid),
            'slack': slack.get(tid),
            'dur': it['dur'], 'critical': tid in critical,
            'milestone': it['milestone'], 'summary': it['summary'],
            'deps': [d['id'] for d in it['deps']],
            'group': it['group'], 'effort': it['effort'],
        }
    return {'tasks': tasks, 'project_end': proj_end, 'critical_path': path,
            'issues': issues, 'leveled': leveled}


def _enhanced_active(data):
    """判断是否启用增强引擎：存在 effort/resources/leveling 任一。"""
    wbs = data.get('wbs') or []
    if any((w.get('effort') is not None) or (w.get('resources') is not None) for w in wbs):
        return True
    sched_cfg = (data.get('control') or {}).get('scheduling') or {}
    if sched_cfg.get('leveling'):
        return True
    return False


def main():
    ap = argparse.ArgumentParser(description="PM Master 排期健康度（增强版）")
    ap.add_argument('--data', default=None, help="独立排期文件 schedule.yaml(.json)")
    ap.add_argument('--project', default=None, help="单一事实源 project.yaml")
    ap.add_argument('--start', default=None, help="项目起始日期 ISO")
    ap.add_argument('--no-level', action='store_true', help="关闭资源级联（纯 CPM）")
    ap.add_argument('--whatif', action='store_true', help="输出压缩分析（关键任务 +1 资源单位的工期缩减）")
    a = ap.parse_args()
    if not a.data and not a.project:
        ap.error("必须提供 --data 或 --project 之一")

    if a.project:
        d = _load_project(a.project)
        task_list = tasks_from_project(d)
        if not task_list:
            print("⚠ project.yaml 中未找到 wbs 排期数据，无法计算关键路径。")
            sys.exit(1)
    else:
        d = load(a.data)
        task_list = d.get('tasks', [])

    # 解析排期配置与资源池
    sched_cfg = (d.get('control') or {}).get('scheduling') or {}
    resources = d.get('resources') or []
    if a.start:
        try:
            project_start = datetime.date.fromisoformat(str(a.start)[:10])
        except ValueError:
            print(f"非法的 --start：{a.start}"); sys.exit(1)
    elif a.project:
        ps = (d.get('project') or {}).get('start_date')
        project_start = datetime.date.fromisoformat(str(ps)[:10]) if ps else datetime.date.today()
    else:
        project_start = datetime.date.today()

    # 选引擎
    use_enhanced = a.project and _enhanced_active(d)
    if use_enhanced:
        level_on = bool(sched_cfg.get('leveling', True))
        level = (not a.no_level) and level_on
        res = compute_schedule(d.get('wbs') or [], resources=resources,
                               sched_cfg=sched_cfg, level=(not a.no_level), recompute=True)
        tasks = res['tasks']
        proj_end = res['project_end']
        model_label = "增强引擎（类型化依赖 + 工作量→工期 + " + \
                      ("资源级联" if res['leveled'] else "纯 CPM") + "）"
        for iss in res['issues']:
            print("⚠", iss)
        # 覆盖 task_list 的 duration/start/end，便于下方统一打印
        cal_start = {t: project_start + datetime.timedelta(days=tasks[t]['es']) for t in tasks}
        cal_end = {t: project_start + datetime.timedelta(days=tasks[t]['ef']) for t in tasks}
    else:
        # 旧行为：顺序/日历模型
        tasks_d = {t['id']: t for t in task_list}
        deps = {tid: t.get('deps', []) for tid, t in tasks_d.items()}
        issues = []
        for tid, ds in deps.items():
            for dep in ds:
                if dep not in tasks_d:
                    issues.append(f"任务 {tid} 依赖未知任务 {dep}")
        leaf_tasks = [t for t in tasks_d if not tasks_d[t].get('children')]
        have_calendar = all((tasks_d[t].get('start') and tasks_d[t].get('end')) for t in leaf_tasks)
        cal_start, cal_end = {}, {}
        for t in tasks_d:
            s = tasks_d[t].get('start'); e = tasks_d[t].get('end')
            if s and e:
                try:
                    cal_start[t] = datetime.date.fromisoformat(str(s)[:10])
                    cal_end[t] = datetime.date.fromisoformat(str(e)[:10])
                except (ValueError, TypeError):
                    pass
        if have_calendar and cal_start:
            proj_min = min(cal_start.values()); proj_max = max(cal_end.values())
            es = {t: (cal_start[t]-proj_min).days for t in cal_start}
            ef = {t: (cal_end[t]-proj_min).days for t in cal_end}
            proj_end = (proj_max-proj_min).days
            lf, ls = {}, {}
            succ_of = {t: [] for t in tasks_d}
            for t in tasks_d:
                for dp in deps[t]:
                    if dp in tasks_d:
                        succ_of[dp].append(t)
            # 拓扑序：保证 successor 先于 predecessor 被反向处理，避免 ls[s] 未就绪
            indeg = {t: 0 for t in tasks_d}
            for t in tasks_d:
                for dp in deps[t]:
                    if dp in tasks_d:
                        indeg[t] += 1
            q = [t for t in tasks_d if indeg[t] == 0]
            topo = []
            while q:
                n = q.pop(0); topo.append(n)
                for s in succ_of.get(n, []):
                    indeg[s] -= 1
                    if indeg[s] == 0:
                        q.append(s)
            for tid in reversed(topo):
                sc = succ_of.get(tid, [])
                lf[tid] = proj_end if not sc else min(ls[s] for s in sc)
                ls[tid] = lf[tid] - (ef[tid]-es[tid])
            slack = {t: ls[t]-es[t] for t in es}
            model_label = "日历模型（旧；尊重既有 start/end）"
        else:
            es, ef = {}, {}
            # 拓扑
            indeg = {t: 0 for t in tasks_d}
            for t in tasks_d:
                for dp in deps[t]:
                    if dp in tasks_d:
                        indeg[t] += 1
            q = [t for t in tasks_d if indeg[t] == 0]
            topo = []
            while q:
                n = q.pop(0); topo.append(n)
                for t in tasks_d:
                    if n in deps[t]:
                        indeg[t] -= 1
                        if indeg[t] == 0:
                            q.append(t)
            for tid in topo:
                dur = tasks_d[tid].get('duration', 0)
                start = 0
                for p in deps[tid]:
                    if p in ef:
                        start = max(start, ef[p])
                es[tid], ef[tid] = start, start + dur
            proj_end = max(ef.values()) if ef else 0
            lf, ls = {}, {}
            for tid in reversed(topo):
                sc = [t for t in tasks_d if tid in deps.get(t, [])]
                lf[tid] = proj_end if not sc else min(ls[s] for s in sc)
                ls[tid] = lf[tid] - tasks_d[tid].get('duration', 0)
            slack = {t: ls[t]-es[t] for t in es}
            model_label = "顺序模型（旧；按 duration 累加）"
        tasks = {t: {'es': es.get(t), 'ef': ef.get(t), 'ls': ls.get(t), 'lf': lf.get(t),
                     'slack': slack.get(t), 'dur': tasks_d[t].get('duration', 0),
                     'critical': (slack.get(t) == 0), 'milestone': False,
                     'deps': deps[t], 'effort': None} for t in tasks_d}

    print("=== 排期健康度 ===")
    if use_enhanced:
        print(f"排期模型: {model_label}")
    else:
        print(f"排期模型: {model_label}")
    print(f"项目总工期(日历天): {proj_end} 天（起始 {project_start.isoformat()}）")
    print(f"{'ID':<10}{'ES':>5}{'EF':>5}{'LS':>5}{'LF':>5}{'浮动':>6}  关键?  依赖")
    for tid in sorted(tasks):
        t = tasks[tid]
        if t['es'] is None:
            print(f"{tid:<10}{'(无法排期)':<30}")
            continue
        crit = '★' if t.get('critical') else ''
        depstr = ','.join(t.get('deps') or [])
        print(f"{tid:<10}{t['es']:>5}{t['ef']:>5}{t['ls']:>5}{t['lf']:>5}{t['slack']:>6}   {crit:<3}  {depstr}")
    cp = [tid for tid in tasks if tasks[tid].get('critical')]
    print("关键路径:", " -> ".join(cp) if cp else "无")

    # What-if 压缩分析
    if a.whatif and use_enhanced:
        print("\n=== 压缩分析（关键任务 +1 资源单位 → 项目总工期缩减）===")
        baseline_end = proj_end
        savings = []
        crit_tasks = [tid for tid in res['critical_path'] if not tasks[tid]['milestone']]
        for tid in crit_tasks:
            # 临时给该任务 resources+1（int 或 list 长度+1）
            wbs2 = []
            for w in (d.get('wbs') or []):
                if w.get('id') == tid:
                    w2 = dict(w)
                    res0 = w.get('resources')
                    if isinstance(res0, int):
                        w2['resources'] = res0 + 1
                    elif isinstance(res0, list):
                        w2['resources'] = res0 + [res0[0]] if res0 else 1
                    else:
                        w2['resources'] = 2
                    wbs2.append(w2)
                else:
                    wbs2.append(w)
            r2 = compute_schedule(wbs2, resources=resources, sched_cfg=sched_cfg,
                                  level=(not a.no_level) and bool(sched_cfg.get('leveling', True)), recompute=True)
            savings.append((tid, baseline_end - r2['project_end']))
        savings.sort(key=lambda x: -x[1])
        for tid, sv in savings:
            print(f"  {tid:<10} +1 资源 → 项目缩短 {sv} 天" if sv > 0 else f"  {tid:<10} +1 资源 → 无缩减（受其他约束）")
        if not savings:
            print("  （无关键任务可压缩）")


if __name__ == '__main__':
    main()
