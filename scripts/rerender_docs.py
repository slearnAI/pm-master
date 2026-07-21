#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · 单一事实源重渲染器（SSOT 防漂移）
-------------------------------------------------
保证所有产物都由 project.yaml（单一事实源）重新渲染，杜绝"改了事实源、文档没跟上"的漂移。

支持重渲染的工件（从 project.yaml 直接取数，不依赖外部 _data.yaml）：
  - wbs（build_wbs.py --view full，并连带 program/component 视图）
  - risk_register（templates/common/risk_register.md <- data.risks）
  - program_charter（templates/program/program_charter.md <- data.program，仅 program 类型）

用法：
  python3 rerender_docs.py --project <yaml>            # 重渲染所有已知工件
  python3 rerender_docs.py --project <yaml> --only wbs # 仅重渲染 WBS
  python3 rerender_docs.py --project <yaml> --dry-run  # 只列出会重渲染什么

设计原则：文档 = 事实源(project.yaml) + 模板 的纯函数。任何手工改动文档都应在下次重渲染被覆盖，
因此真正要改的是事实源（用 sync_wbs.py / project_state.py set），再 rerender。
"""
import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    import yaml
except ImportError:
    yaml = None

from render import render
from artifact_guard import DEPS as _AG_DEPS, _hash_deps as _ag_hash


def _load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) if yaml else {}


def _save_yaml(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _render_doc(project_yaml, tpl_rel, ctx, out_rel, project_data, art_key=None, deps=None):
    root = os.path.dirname(os.path.abspath(project_yaml))
    tpl = os.path.join(SCRIPT_DIR, '..', tpl_rel)
    if not os.path.exists(tpl):
        return f"⚠ 模板不存在 {tpl_rel}"
    with open(tpl, 'r', encoding='utf-8') as f:
        tpl_text = f.read()
    rendered = render(tpl_text, ctx)
    out_path = os.path.join(root, out_rel) if not os.path.isabs(out_rel) else out_rel
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(rendered)
    # OAG：记录 source_hash，启用交付物漂移检测（art_key+deps 由调用方传入）
    if art_key and deps is not None and project_data is not None:
        import datetime as _dt
        meta = project_data.setdefault('artifacts_meta', {})
        meta[art_key] = {
            'source_hash': _ag_hash(project_data, deps),
            'rendered_at': _dt.datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        }
    return out_path


def rerender_wbs(project_yaml, data, dry):
    out = []
    for view in ('full', 'program', 'component'):
        from build_wbs import main as bw_main
        import subprocess
        cmd = [sys.executable, os.path.join(SCRIPT_DIR, 'build_wbs.py'),
               '--project', project_yaml, '--view', view]
        if dry:
            out.append(f"[dry] build_wbs --view {view}")
        else:
            subprocess.run(cmd, check=False)
            out.append(f"build_wbs --view {view}")
    # 清除 dirty 标记
    if not dry and data.get('artifacts', {}).get('wbs_dirty'):
        data['artifacts'].pop('wbs_dirty', None)
        _save_yaml(project_yaml, data)
    return out


def rerender_risk(project_yaml, data, dry):
    if not (data.get('risks') or (data.get('raid') or {}).get('risks')):
        return ["（无 risks，跳过 risk_register）"]
    root = os.path.dirname(os.path.abspath(project_yaml))
    out_rel = data.get('artifacts', {}).get('risk_register') or os.path.join('plans', 'risk_register.md')
    if dry:
        return [f"[dry] risk_register -> {out_rel}"]
    ctx = {'project': data.get('project', {}), 'risks': data.get('risks') or (data.get('raid') or {}).get('risks', []) or []}
    p = _render_doc(project_yaml, 'templates/common/risk_register.md', ctx, out_rel, data,
                    art_key='risk_register', deps=_AG_DEPS['risk_register'])
    # OAG：持久化 source_hash（重渲染即刷新漂移检测基线）
    if not dry:
        _save_yaml(project_yaml, data)
    return [f"risk_register -> {p}"]


def rerender_charter(project_yaml, data, dry):
    if (data.get('project', {}).get('type') or '').lower() != 'program':
        return ["（非 program 类型，跳过 program_charter）"]
    root = os.path.dirname(os.path.abspath(project_yaml))
    out_rel = data.get('artifacts', {}).get('program_charter') or os.path.join('plans', 'program_charter.md')
    if dry:
        return [f"[dry] program_charter -> {out_rel}"]
    ctx = {'project': data.get('project', {}), 'program': data.get('program', {})}
    p = _render_doc(project_yaml, 'templates/program/program_charter.md', ctx, out_rel, data)
    return [f"program_charter -> {p}"]


def rerender_schedules(project_yaml, data, dry):
    """P1-5: 重渲染排期甘特 + 排期健康度（调用 build_schedule / schedule_health / render_docx）。"""
    import subprocess as sp
    out = []
    root = os.path.dirname(os.path.abspath(project_yaml))
    bs = os.path.join(SCRIPT_DIR, 'build_schedule.py')
    sh = os.path.join(SCRIPT_DIR, 'schedule_health.py')
    rd = os.path.join(SCRIPT_DIR, 'render_docx.py')
    if dry:
        return ["[dry] build_schedule + schedule_health + render_docx (schedule_gantt/health)"]
    if os.path.isfile(bs):
        r = sp.run([sys.executable, bs, '--project', project_yaml], capture_output=True, text=True)
        out.append(f"build_schedule: rc={r.returncode}")
    if os.path.isfile(sh):
        r = sp.run([sys.executable, sh, '--project', project_yaml], capture_output=True, text=True)
        out.append(f"schedule_health: rc={r.returncode}")
    # 渲染 docx（若存在 gantt 模板）
    sg = data.get('artifacts', {}).get('schedule_gantt') or os.path.join('plans', 'schedule_gantt.md')
    sgp = os.path.join(root, sg)
    if os.path.isfile(sgp) and os.path.isfile(rd):
        r = sp.run([sys.executable, rd, '--md', sgp], capture_output=True, text=True)
        out.append(f"render_docx(schedule_gantt): rc={r.returncode}")
    return out


def main():
    ap = argparse.ArgumentParser(description="PM Master · SSOT 重渲染器")
    ap.add_argument('--project', required=True)
    ap.add_argument('--only', default=None,
                    choices=['wbs', 'risk_register', 'program_charter', 'schedules'])
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    if yaml is None:
        raise SystemExit("需要 PyYAML")
    data = _load(a.project)
    done = []
    targets = [a.only] if a.only else ['wbs', 'risk_register', 'program_charter', 'schedules']
    for t in targets:
        if t == 'wbs':
            done += rerender_wbs(a.project, data, a.dry_run)
        elif t == 'risk_register':
            done += rerender_risk(a.project, data, a.dry_run)
        elif t == 'program_charter':
            done += rerender_charter(a.project, data, a.dry_run)
        elif t == 'schedules':
            done += rerender_schedules(a.project, data, a.dry_run)
    print("[rerender]")
    for d in done:
        print("  -", d)


if __name__ == '__main__':
    main()
