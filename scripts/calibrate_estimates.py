#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · calibrate_estimates.py —— 估算反馈回路（估计 -> 实际）

问题根因 R3：estimates 从不学习。本脚本把「已关闭叶子」的实际工作量回填为校准偏差因子，
使 estimator-agent 的 parametric/analogous 方法能自我修正。

数据来源（单一事实源 project.yaml）：
  - 每个叶子的 estimator 输出：estimate_method / estimate_source / estimate_confidence
  - 实际工作量：wbs[].actual_effort（>0），或由 control_engine/evm 写入 actuals.effort{}

校准逻辑：
  factor(role@domain) = mean( actual_effort / estimator_expected )
  分组键优先 'role@domain'，不足样本(默认<3)则回退 'role'（跨域聚合）。
  factor>1 => 历史持续低估（上调）；<1 => 高估（下调）。

输出：
  - 默认写回共享校准表 references/estimate-calibration.yaml（--global，推荐，跨项目共享）
  - 或 --out <path> 指定
  - 或 --project-only 只更新当前项目局部的 calibration 块（不污染全局）

用法：
  python3 calibrate_estimates.py --project <project.yaml> --global
  python3 calibrate_estimates.py --project <project.yaml> --out my-cal.yaml
"""
import os
import sys
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    import yaml
except ImportError:
    yaml = None

import role_catalog as rc

MIN_SAMPLES = 3


def load(path):
    if yaml is None:
        raise RuntimeError("需要 PyYAML，请先 pip install pyyaml")
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def collect_samples(wbs, proj):
    """返回 [(role, domain, ratio)]，仅取有 actual_effort 且预计>0 的叶子。"""
    domain0 = proj.get('domain')
    samples = []
    for w in wbs:
        if w.get('summary') or w.get('milestone') or w.get('tier') == 'program':
            continue
        actual = to_float(w.get('actual_effort'))
        expected = to_float(w.get('effort') or w.get('estimate'))
        if actual <= 0 or expected <= 0:
            continue
        role = w.get('role') or rc.infer_role(w.get('name', ''), w.get('domain'),
                                              explicit_role=w.get('role'))
        dom = w.get('domain') or domain0
        samples.append((role, dom, actual / expected))
    return samples


def aggregate(samples):
    """返回 { 'role@domain': factor, 'role': factor }（满足最小样本才输出）。"""
    by_rd = {}
    by_r = {}
    for role, dom, ratio in samples:
        by_rd.setdefault((role, dom), []).append(ratio)
        by_r.setdefault(role, []).append(ratio)

    out = {}
    def mean(xs):
        return sum(xs) / len(xs)

    for (role, dom), xs in by_rd.items():
        if len(xs) >= MIN_SAMPLES:
            out[f"{role}@{dom}"] = round(mean(xs), 2)
    for role, xs in by_r.items():
        if len(xs) >= MIN_SAMPLES and f"{role}@{dom}" not in out:
            # 仅当该 role 无足够按域样本时，才用跨域聚合
            if all(len(by_rd.get((role, d), [])) < MIN_SAMPLES for (r, d) in by_rd if r == role):
                out[role] = round(mean(xs), 2)
    return out


def main():
    ap = argparse.ArgumentParser(description="PM Master · 估算校准反馈回路")
    ap.add_argument('--project', required=True)
    ap.add_argument('--global', dest='global_', action='store_true',
                    help="写回技能共享校准表 references/estimate-calibration.yaml")
    ap.add_argument('--out', default=None, help="写回指定路径")
    ap.add_argument('--project-only', action='store_true',
                    help="仅更新当前 project.yaml 的 control.calibration 块（不污染全局）")
    ap.add_argument('--min-samples', type=int, default=MIN_SAMPLES)
    ap.add_argument('--dry-run', action='store_true', help="只算不算写")
    a = ap.parse_args()
    if yaml is None:
        raise SystemExit("需要 PyYAML：pip install pyyaml")

    data = load(a.project)
    wbs = data.get('wbs') or []
    proj = data.get('project', {}) or {}
    samples = collect_samples(wbs, proj)
    factors = aggregate(samples)
    print(f"=== calibrate_estimates · 样本 {len(samples)} 个，生成因子 {len(factors)} 个 ===")
    for k, v in sorted(factors.items()):
        print(f"  {k:<32} factor={v:g}")

    if a.dry_run:
        return

    target = None
    if a.out:
        target = a.out
    elif a.global_:
        target = os.path.join(SCRIPT_DIR, '..', 'references', 'estimate-calibration.yaml')
    elif a.project_only:
        target = None  # 写 project.yaml
    else:
        target = os.path.join(SCRIPT_DIR, '..', 'references', 'estimate-calibration.yaml')

    if target:
        doc = {}
        if os.path.exists(target):
            try:
                with open(target, 'r', encoding='utf-8') as f:
                    doc = yaml.safe_load(f) or {}
            except Exception:
                doc = {}
        doc.setdefault('factors', {})
        doc['factors'].update(factors)
        doc['updated_at'] = __import__('datetime').date.today().isoformat()
        with open(target, 'w', encoding='utf-8') as f:
            yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False)
        print(f"[calibrate] 已写回共享校准表: {target}")
    elif a.project_only:
        ctrl = data.setdefault('control', {})
        ctrl['calibration'] = factors
        root = os.path.dirname(os.path.abspath(a.project))
        with open(a.project, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        print(f"[calibrate] 已写回 project.yaml control.calibration（局部，不污染全局）")


if __name__ == '__main__':
    main()
