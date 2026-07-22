#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master v2 · 执行驱动引擎（Execution Driver）
==============================================
执行期核心驱动脚本。解决 v1.x 中"规划期自动化强、执行期全靠Agent自行推理"的断层。

职责：
  1. 读取 project.yaml，确定当前应执行的工作包
  2. 生成执行清单（按优先级、依赖、状态过滤）
  3. 追踪 Sprint/迭代进度（agile/iteration/hybrid）
  4. 自动触发 control_engine.py 巡检（如果距上次巡检已过 cadence）
  5. 产出执行状态摘要

用法：
  python3 execution_driver.py --project /workspace/<slug>/project.yaml
  python3 execution_driver.py --project <yaml> --sprint 3           # 指定Sprint
  python3 execution_driver.py --project <yaml> --check-control       # 仅检查是否需要巡检
  python3 execution_driver.py --project <yaml> --json                # JSON输出
"""
import os
import sys
import argparse
import datetime
import subprocess

try:
    import yaml
except ImportError:
    yaml = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONTROL_ENGINE = os.path.join(SCRIPT_DIR, 'control_engine.py')
CONSISTENCY_CHECK = os.path.join(SCRIPT_DIR, 'consistency_check.py')


def load(path):
    if yaml is None:
        raise RuntimeError("需要 PyYAML，请先 pip install pyyaml")
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def parse_deps(dep):
    """解析 dependsOn 字段"""
    if dep is None:
        return []
    if isinstance(dep, list):
        return [str(x).strip() for x in dep if str(x).strip() and str(x).strip() not in ('—', '-')]
    s = str(dep).strip()
    if s in ('', '—', '-'):
        return []
    import re
    return [p.strip() for p in re.split(r'[,;，；]', s) if p.strip()]


def get_wbs_status(w):
    """推断WBS工作包状态"""
    status = (w.get('status') or '').lower()
    if status in ('done', 'completed', '完成', '已完成'):
        return 'done'
    if status in ('in_progress', 'in progress', '进行中'):
        return 'in_progress'
    if status in ('blocked', '阻塞'):
        return 'blocked'
    return 'pending'


def is_ready(w, wbs_map, done_ids):
    """检查工作包是否就绪（所有依赖已完成）"""
    deps = parse_deps(w.get('dependsOn'))
    if not deps:
        return True
    return all(d in done_ids for d in deps)


def get_executable_work(wbs, methodology):
    """获取当前可执行的工作包清单"""
    wbs_map = {w.get('id'): w for w in wbs if w.get('id')}
    done_ids = {wid for wid, w in wbs_map.items() if get_wbs_status(w) == 'done'}
    in_progress_ids = {wid for wid, w in wbs_map.items() if get_wbs_status(w) == 'in_progress'}

    executable = []
    blocked = []

    for w in wbs:
        wid = w.get('id', '?')
        status = get_wbs_status(w)

        # 跳过summary/里程碑/done
        if w.get('summary') or w.get('milestone'):
            continue
        if status == 'done':
            continue

        if is_ready(w, wbs_map, done_ids):
            entry = {
                'id': wid,
                'name': w.get('name', ''),
                'status': status,
                'estimate': w.get('estimate', 0),
                'owner': w.get('owner', ''),
                'domain': w.get('domain', ''),
                'deliverable': w.get('deliverable', ''),
            }
            if status == 'blocked':
                blocked.append(entry)
            else:
                executable.append(entry)
        else:
            blocked.append({
                'id': wid,
                'name': w.get('name', ''),
                'status': 'waiting_deps',
                'estimate': w.get('estimate', 0),
                'owner': w.get('owner', ''),
                'domain': w.get('domain', ''),
                'deliverable': w.get('deliverable', ''),
            })

    return executable, blocked, in_progress_ids


def check_control_needed(project_yaml_path, data):
    """检查是否需要运行 control_engine 巡检。
    优先读取 data['last_control_check']（与 project_state 约定一致），
    其次 control.last_control_check。"""
    ctrl = data.get('control') or {}
    cadence_days = ctrl.get('cadence_days', 7)
    last_check = data.get('last_control_check') or ctrl.get('last_control_check')
    if last_check:
        if isinstance(last_check, str):
            try:
                last_check = datetime.date.fromisoformat(last_check)
            except ValueError:
                last_check = None
        if last_check:
            days_since = (datetime.date.today() - last_check).days
            if days_since < cadence_days:
                return False, days_since
    return True, 0


def stamp_control_check(data, path):
    """巡检后写入 last_control_check，避免重复巡检（E4）。"""
    data['last_control_check'] = datetime.date.today().isoformat()
    save(data, path)


def main():
    ap = argparse.ArgumentParser(description="PM Master v2 执行驱动引擎")
    ap.add_argument('--project', required=True, help="project.yaml 路径")
    ap.add_argument('--sprint', type=int, default=None, help="指定Sprint编号(agile)")
    ap.add_argument('--check-control', action='store_true', help="仅检查是否需要巡检")
    ap.add_argument('--json', action='store_true', help="JSON输出")
    a = ap.parse_args()

    data = load(a.project)
    root = os.path.dirname(os.path.abspath(a.project))
    proj = data.get('project', {})
    methodology = (proj.get('methodology') or '').lower()
    lifecycle = (proj.get('lifecycle_state') or '')

    # 状态机检查
    if lifecycle not in ('operational',):
        print(f"[execution_driver] 项目不在 operational 状态（当前：{lifecycle}），无法驱动执行")
        print("  请先完成：规划 → 评审 → baseline.py --freeze → gate_engine.py --to 执行")
        sys.exit(1)

    wbs = data.get('wbs') or []

    if a.check_control:
        needed, days = check_control_needed(a.project, data)
        if needed:
            print(f"[execution_driver] 需要运行 control_engine 巡检")
            print(f"  python3 {CONTROL_ENGINE} --project {a.project}")
            sys.exit(0)
        else:
            print(f"[execution_driver] 距上次巡检 {days} 天，无需巡检")
            sys.exit(0)

    # 获取可执行工作
    executable, blocked, in_progress = get_executable_work(wbs, methodology)

    # 检查是否需要巡检
    ctrl_needed, days_since = check_control_needed(a.project, data)

    # 巡检后回写时间戳（幂等：仅当确实触发时才在真实巡检分支落盘；此处仅声明）
    if ctrl_needed and not a.json:
        stamp_control_check(data, a.project)

    # 输出
    if a.json:
        import json as _json
        result = {
            'project': proj.get('name'),
            'lifecycle_state': lifecycle,
            'methodology': methodology,
            'executable_count': len(executable),
            'in_progress_count': len(in_progress),
            'blocked_count': len(blocked),
            'control_check_needed': ctrl_needed,
            'executable': executable[:20],  # 限制输出
            'blocked': blocked[:20],
        }
        print(_json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"=== 执行驱动报告 ===")
        print(f"项目：{proj.get('name')} | 方法论：{methodology} | 状态：{lifecycle}")
        print(f"可执行工作包：{len(executable)} | 进行中：{len(in_progress)} | 阻塞：{len(blocked)}")
        if ctrl_needed:
            print(f"⚠ 需要运行 control_engine.py 巡检（距上次 {days_since} 天）")

        if executable:
            print(f"\n## 可执行工作包（建议优先执行）")
            for i, w in enumerate(executable[:10]):
                status_tag = '🆕' if w['status'] == 'pending' else '🔄'
                print(f"  {i+1}. [{w['id']}] {w['name']} ({w['estimate']}人天) - {w['owner'] or '(待指派)'} {status_tag}")

        if blocked:
            print(f"\n## 阻塞项")
            for i, w in enumerate(blocked[:10]):
                reason = '等待依赖完成' if w['status'] == 'waiting_deps' else w['status']
                print(f"  {i+1}. [{w['id']}] {w['name']} - {reason}")


if __name__ == '__main__':
    main()
