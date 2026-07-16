#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · 基线化（Plan → Baseline → Control Gate）

把"已评审批准"的项目计划冻结为基线快照，作为后续运营控制的对照基准。

用法：
  # 冻结基线（前置：一致性门禁 exit 0）
  python3 baseline.py --freeze --project /workspace/<slug>/project.yaml

  # 查看基线状态
  python3 baseline.py --status --project /workspace/<slug>/project.yaml

前置纪律：
  --freeze 会先跑 consistency_check.py；若不通过（计划尚未达控制级），拒绝基线化。
  基线化后写入 baselines/<YYYY-MM-DD>.yaml，并在 project.yaml 记录指针：
    baseline: {file: baselines/2026-07-15.yaml, on: 2026-07-15, by: <pm>}
    project.lifecycle_state: baselined
    project.baselined_on: 2026-07-15
  同时渲染 baseline_record.md 与 control_register.md（运营期控制清单）。
"""
import os
import sys
import json
import subprocess
import datetime
import argparse

try:
    import yaml
except ImportError:
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER = os.path.join(HERE, 'render.py')
CONSISTENCY = os.path.join(HERE, 'consistency_check.py')


def load(path):
    if yaml is None:
        raise RuntimeError("需要 PyYAML，请先 pip install pyyaml")
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def collect_risks(data):
    seen = {}
    for r in (data.get('risks') or []):
        if r.get('id'):
            seen[r['id']] = r
    for r in ((data.get('raid') or {}).get('risks') or []):
        if r.get('id') and r['id'] not in seen:
            seen[r['id']] = r
    return list(seen.values())


def run(cmd):
    return subprocess.run([sys.executable] + cmd, capture_output=True, text=True)


def freeze(project_path):
    root = os.path.dirname(os.path.abspath(project_path))
    data = load(project_path)
    proj = data.get('project', {}) or {}

    # ---- 门禁：计划须达控制级才允许基线化 ----
    chk = run([CONSISTENCY, '--project', project_path])
    if chk.returncode != 0:
        print("✗ 基线化被拒绝：一致性门禁未通过。请先修正以下问题，再冻结基线：")
        print(chk.stdout)
        print(chk.stderr)
        sys.exit(2)

    today = datetime.date.today().isoformat()
    bdir = os.path.join(root, 'baselines')
    os.makedirs(bdir, exist_ok=True)
    bfile = os.path.join(bdir, today + '.yaml')

    snapshot = {
        'baselined_on': today,
        'by': proj.get('pm') or '未指定',
        'project_id': proj.get('id'),
        'project_name': proj.get('name'),
        'methodology': proj.get('methodology'),
        'wbs': data.get('wbs') or [],
        'milestones': data.get('milestones') or [],
        'risks': collect_risks(data),
        'metrics': {'evm': (data.get('metrics') or {}).get('evm') or {}},
    }
    save(bfile, snapshot)

    # ---- 回写指针到 project.yaml（经 project_state.py 保持原位） ----
    rel = os.path.relpath(bfile, root)
    st = run([os.path.join(HERE, 'project_state.py'),
              'set', 'baseline.file', rel, '--file', project_path])
    run([os.path.join(HERE, 'project_state.py'),
         'set', 'baseline.on', today, '--file', project_path])
    run([os.path.join(HERE, 'project_state.py'),
         'set', 'baseline.by', str(proj.get('pm') or '未指定'), '--file', project_path])
    run([os.path.join(HERE, 'project_state.py'),
         'set', 'project.lifecycle_state', 'baselined', '--file', project_path])
    run([os.path.join(HERE, 'project_state.py'),
         'set', 'project.baselined_on', today, '--file', project_path])

    # ---- 渲染 baseline_record + control_register ----
    arts = data.get('artifacts', {}) or {}
    brec = arts.get('baseline_record') or 'artifacts/baseline_record.md'
    crec = arts.get('control_register') or 'artifacts/control_register.md'
    run([RENDER, '--template',
         os.path.join(HERE, '..', 'templates', 'common', 'baseline_record.md'),
         '--data', project_path, '--out', os.path.join(root, brec)])
    run([RENDER, '--template',
         os.path.join(HERE, '..', 'templates', 'common', 'control_register.md'),
         '--data', project_path, '--out', os.path.join(root, crec)])

    # ---- 注册产物指针（便于发现 + 满足一致性门禁的运营期产物要求） ----
    run([os.path.join(HERE, 'project_state.py'),
         'set', 'artifacts.baseline_record', brec, '--file', project_path])
    run([os.path.join(HERE, 'project_state.py'),
         'set', 'artifacts.control_register', crec, '--file', project_path])

    print(f"✓ 基线化完成（{today}）")
    print(f"  快照: {rel}")
    print(f"  WBS 包: {len(snapshot['wbs'])} | 风险: {len(snapshot['risks'])} | "
          f"里程碑: {len(snapshot['milestones'])}")
    print(f"  状态: project.lifecycle_state = baselined")
    print(f"  已渲染: {brec}, {crec}")
    print(f"  下一步: 通过控制门（stage_gate_review）后，将 lifecycle_state 置为 operational，"
          f"即可用 control_engine.py 周期性巡检。")
    if st.returncode != 0:
        print("[warn] project_state.py 写入指针失败，请手动设置 baseline.file", file=sys.stderr)


def status(project_path):
    data = load(project_path)
    proj = data.get('project', {}) or {}
    bl = data.get('baseline') or {}
    print("=== 基线状态 ===")
    print(f"项目: {proj.get('name')} ({proj.get('id')})")
    print(f"生命周期状态: {proj.get('lifecycle_state', 'planning')}")
    print(f"阶段: {proj.get('phase')}")
    if bl.get('file'):
        print(f"基线文件: {bl.get('file')}")
        print(f"基线日期: {bl.get('on')}  基线人: {bl.get('by')}")
    else:
        print("⚠ 尚未基线化（无 baseline 指针）。waterfall/hybrid 进入执行/监控前必须先基线化。")


def main():
    ap = argparse.ArgumentParser(description="PM Master 基线化")
    ap.add_argument('--project', required=True)
    ap.add_argument('--freeze', action='store_true', help="冻结基线（默认动作）")
    ap.add_argument('--status', action='store_true', help="查看基线状态")
    a = ap.parse_args()
    if a.status:
        status(a.project)
    else:
        freeze(a.project)


if __name__ == '__main__':
    main()
