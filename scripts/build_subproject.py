#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · 子项目（per-SOW）工件生成器
-------------------------------------------------
程序（项目群）层之下，每个 SOW 应作为「子项目（sub-project）」独立维护，由该 SOW 的项目经理
拥有自己的 PM 工件：RAID 日志、风险登记册、状态报告。本脚本从子项目的 project.yaml
（单一事实源）渲染这些工件到 subprojects/<slug>/risks/ 与 reports/。

前置：init_project.py --parent <program.yaml> --sow SOW1 已建立子项目骨架并写入 program.projects 索引。

用法：
  python3 build_subproject.py --project subprojects/<slug>/project.yaml
  python3 build_subproject.py --project subprojects/<slug>/project.yaml --only raid
  python3 build_subproject.py --program <program.yaml> --sow SOW1     # 按索引定位子项目

渲染工件（均来自子项目 project.yaml，单一事实源防漂移）：
  - raid_log.md        <- data.raid (risks/assumptions/issues/dependencies)
  - risk_register.md   <- data.risks
  - status_report.md   <- data.progress / data.metrics / data.risks
并把产物路径写回子项目 project.yaml 的 artifacts（raid_log / risk_register / status_report）。
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
from rerender_docs import _render_doc  # 复用 SSOT 渲染助手
from artifact_guard import DEPS as _AG_DEPS  # 交付物依赖键（OAG 漂移检测）


def _load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) if yaml else {}


def _save(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def _find_subproject(program_yaml, sow_id):
    doc = _load(program_yaml)
    prog = doc.get('program') or {}
    for e in prog.get('projects', []) or []:
        if e.get('sow') == sow_id:
            parent_dir = os.path.dirname(os.path.abspath(program_yaml))
            return os.path.join(parent_dir, e.get('path') or os.path.join('subprojects', e.get('slug', sow_id)), 'project.yaml')
    return None


def render_all(sub_yaml, data, only=None):
    done = []
    base = os.path.dirname(os.path.abspath(sub_yaml))
    art = data.setdefault('artifacts', {})

    if not only or only == 'raid':
        out_rel = art.get('raid_log') or os.path.join('risks', 'raid_log.md')
        ctx = {'project': data.get('project', {}), 'raid': data.get('raid', {}) or {}}
        p = _render_doc(sub_yaml, 'templates/common/raid_log.md', ctx, out_rel, data,
                        art_key='raid_log', deps=_AG_DEPS['raid_log'])
        art['raid_log'] = os.path.relpath(p, base)
        done.append(f'raid_log -> {p}')

    if not only or only == 'risk_register':
        out_rel = art.get('risk_register') or os.path.join('risks', 'risk_register.md')
        ctx = {'project': data.get('project', {}), 'risks': data.get('risks') or (data.get('raid') or {}).get('risks', []) or []}
        p = _render_doc(sub_yaml, 'templates/common/risk_register.md', ctx, out_rel, data,
                        art_key='risk_register', deps=_AG_DEPS['risk_register'])
        art['risk_register'] = os.path.relpath(p, base)
        done.append(f'risk_register -> {p}')

    if not only or only == 'status_report':
        out_rel = art.get('status_report') or os.path.join('reports', 'status_report.md')
        ctx = {
            'project': data.get('project', {}),
            'period': data.get('progress', {}).get('period', ''),
            'progress': data.get('progress', {}) or {},
            'metrics': data.get('metrics', {}) or {},
            'risks': data.get('risks', []) or [],
            'help': [],
        }
        p = _render_doc(sub_yaml, 'templates/common/status_report.md', ctx, out_rel, data,
                        art_key='status_report', deps=_AG_DEPS['status_report'])
        art['status_report'] = os.path.relpath(p, base)
        done.append(f'status_report -> {p}')
    return done


def main():
    ap = argparse.ArgumentParser(description="PM Master · 子项目工件生成器")
    ap.add_argument('--project', default=None, help="子项目 project.yaml")
    ap.add_argument('--program', default=None, help="程序 project.yaml（配合 --sow 定位子项目）")
    ap.add_argument('--sow', default=None, help="SOW id（配合 --program）")
    ap.add_argument('--only', default=None, choices=['raid', 'risk_register', 'status_report'])
    a = ap.parse_args()

    if yaml is None:
        raise SystemExit("需要 PyYAML")
    if a.project:
        sub_yaml = os.path.abspath(a.project)
    elif a.program and a.sow:
        sub_yaml = _find_subproject(os.path.abspath(a.program), a.sow)
        if not sub_yaml or not os.path.exists(sub_yaml):
            raise SystemExit(f"未找到 SOW {a.sow} 对应的子项目（请先 init_project.py --parent … --sow {a.sow}）")
    else:
        raise SystemExit("需提供 --project 或 --program + --sow")

    data = _load(sub_yaml)
    done = render_all(sub_yaml, data, only=a.only)
    _save(sub_yaml, data)
    print(f"[subproject] {sub_yaml}")
    for d in done:
        print("  -", d)


if __name__ == '__main__':
    main()
