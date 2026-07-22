#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · estimator-agent —— 独立工作量校准子 Agent 逻辑

职责（单一职责，不负责拆解）：
  对分解好的 WBS 叶子包做「与分解者无关」的工作量估算校准。
  - 每个叶子选一种方法：three-point / parametric / analogous / expert
  - 应用 (role,domain) 校准因子（来自共享 estimate-calibration.yaml）
  - 对比分解者原 estimate 与校准后 expected：
      * 偏差 <= DIVERGENCE(20%) -> 保留，仅记 basis
      * 偏差 > 20% -> effort=校准expected，estimate_flag=recalibrated，报告原因
  - 无历史/无 DoD -> estimate_confidence=low，绝不捏造 actuals
  - 若校准后 effort 将超过颗粒度阈值 -> 不膨胀，estimate_flag=split-needed，交主控重派拆解

输入：project.yaml（单一事实源，含已分解的 wbs）
输出：
  - 写回每个叶子的 effort/estimate_method/estimate_basis/estimate_o/m/p/
    estimate_confidence/estimate_source/estimate_flag（向后兼容：estimate 作为 effort 的别名）
  - 生成 plans/estimate_report.md（render.py 渲染）
  - 控制台打印 key findings（供主控聚合）

用法：
  python3 estimator.py --project <project.yaml>
  python3 estimator.py --project <project.yaml> --calib <estimate-calibration.yaml>
  python3 estimator.py --project <project.yaml> --json     # 仅输出 JSON 结果（供主控聚合）
"""
import os
import re
import sys
import json
import argparse
import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    import yaml
except ImportError:
    yaml = None

import role_catalog as rc

# ---- 校准参数（与用户决策一致） ----
DIVERGENCE = 0.20          # 校准 vs 分解者原估算 偏差阈值；超过则 recalibrated
ESTIMATE_BASIS_FLOOR = 5.0  # 叶子 effort >= 此值 必须提供 estimate_method + estimate_basis
DEFAULT_THRESHOLD = 10.0    # 颗粒度阈值（超出则 split-needed），可被 control.granularity_threshold 覆盖


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


def role_of(w, name, domain):
    return w.get('role') or rc.infer_role(name, domain, explicit_role=w.get('role'))


def is_leaf(w):
    return not (w.get('summary') or w.get('milestone') or w.get('tier') == 'program')


def calibrate_leaf(w, name, domain, calib_path, threshold):
    """对一个叶子做校准，返回 (result_dict, finding_str)。"""
    role = role_of(w, name, domain)
    original = to_float(w.get('effort') or w.get('estimate'))
    # 1) 选择方法，得到校准 expected + 区间
    method = (str(w.get('estimate_method') or '')).lower()
    o = to_float(w.get('estimate_o'))
    m = to_float(w.get('estimate_m'))
    p = to_float(w.get('estimate_p'))
    # 参数化锚点
    anchor = rc.parametric_anchor(role, domain)
    factor = rc.calibration_factor(role, domain, calib_path)

    expected = None
    basis = None
    conf = 'low'
    source = 'expert'
    low, high = None, None

    if method == 'three-point' and o > 0 and m > 0 and p >= m:
        expected = (o + 4 * m + p) / 6.0 * factor   # 应用历史校准因子，修正系统性估算偏差
        low, high = o, p
        basis = f"three-point: o={o:g}, m={m:g}, p={p:g} -> expected={expected:.2f}; cal={factor:.2f}"
        source = 'history' if factor != 1.0 else 'expert'
        conf = 'high' if (p - o) <= 2 * m else 'medium'
    elif method == 'parametric' and anchor:
        rate, unit, note = anchor
        # 需已知规模（如 table/story 数）；优先取叶子上的规模字段，否则回退原 estimate 反推
        scale = to_float(w.get('scale')) or to_float(w.get('size'))
        if scale > 0:
            expected = rate * scale * factor
            basis = f"parametric: {rate:g} {unit} × {scale:g} ({note}); cal={factor:.2f}"
        else:
            # 无规模数据 -> 用原 estimate 作为规模隐含值，仅应用校准因子
            expected = (original if original > 0 else rate * 1.0) * factor
            basis = f"parametric(fallback): anchor {rate:g} {unit} 但缺规模字段，按原估算×cal({factor:.2f})"
            conf = 'low'
        source = 'parametric'
        conf = 'medium' if conf == 'low' else conf
    elif method == 'analogous' and (w.get('estimate_basis') or ''):
        base = to_float(w.get('analogous_base'))
        scale_ratio = to_float(w.get('analogous_ratio')) or 1.0
        expected = (base if base > 0 else original) * scale_ratio * factor
        basis = f"analogous: base={base:g} × ratio={scale_ratio:g} ({w.get('estimate_basis')}); cal={factor:.2f}"
        source = 'history'
        conf = 'medium'
    else:
        # 无可用方法 -> expert 兜底，标记 low
        expected = original
        basis = (w.get('estimate_basis') or '专家经验估算（无方法/历史，须补 basis）')
        source = 'expert'
        conf = 'low'

    if expected is None or expected <= 0:
        expected = original if original > 0 else 1.0
        conf = 'low'

    # 2) 对比分解者原估算
    flag = 'none'
    note = ''
    if original > 0:
        div = abs(expected - original) / original
        if div > DIVERGENCE:
            flag = 'recalibrated'
            note = (f"分解者原估算 {original:g} vs 校准 {expected:.2f} "
                    f"(偏差 {div*100:.0f}% > {DIVERGENCE*100:.0f}%) -> 采用校准值")
        else:
            note = f"与原估算一致（偏差 {div*100:.0f}% ≤ {DIVERGENCE*100:.0f}%）"
    else:
        flag = 'tbd' if expected == 0 else flag
        note = "原估算缺失，采用校准值"

    # 3) 颗粒度/拆分门
    if expected > threshold:
        flag = 'split-needed'
        note = (f"校准后 effort={expected:.2f} 超阈值 {threshold:g}，"
                f"不膨胀；交主控重派专家拆为 ≤{threshold:g} 的叶子包")

    # 4) 强制 basis 门槛
    basis_required = expected >= ESTIMATE_BASIS_FLOOR
    if basis_required and not (w.get('estimate_basis') or basis):
        note += " [WARNING: effort≥%.0f 须补 estimate_basis]" % ESTIMATE_BASIS_FLOOR

    return {
        'id': w.get('id'), 'role': role, 'domain': domain,
        'original_effort': original, 'expected_effort': round(expected, 2),
        'method': method or ('expert' if conf == 'low' else 'expert'),
        'basis': basis, 'low': low, 'high': high,
        'confidence': conf, 'source': source, 'flag': flag, 'note': note,
    }


def main():
    ap = argparse.ArgumentParser(description="PM Master · estimator-agent (effort calibration)")
    ap.add_argument('--project', required=True)
    ap.add_argument('--calib', default=None, help="共享校准表路径（缺省自动查找）")
    ap.add_argument('--json', action='store_true', help="仅输出 JSON 结果")
    ap.add_argument('--write', action='store_true', default=True,
                    help="写回 project.yaml 的 wbs 叶子（默认开）")
    a = ap.parse_args()
    if yaml is None:
        raise SystemExit("需要 PyYAML：pip install pyyaml")

    data = load(a.project)
    wbs = data.get('wbs') or []
    proj = data.get('project', {}) or {}
    domain0 = proj.get('domain')
    ctrl = data.get('control') or {}
    threshold = float(ctrl.get('granularity_threshold') or DEFAULT_THRESHOLD)
    root = os.path.dirname(os.path.abspath(a.project))

    results = []
    recal = 0
    split_needed = 0
    low_conf = 0
    for w in wbs:
        if not is_leaf(w):
            continue
        name = w.get('name') or ''
        dom = w.get('domain') or domain0
        res = calibrate_leaf(w, name, dom, a.calib, threshold)
        results.append(res)
        if res['flag'] == 'recalibrated':
            recal += 1
        if res['flag'] == 'split-needed':
            split_needed += 1
        if res['confidence'] == 'low':
            low_conf += 1
        if a.write:
            w['effort'] = res['expected_effort']
            w['estimate_method'] = res['method']
            w['estimate_basis'] = res['basis']
            w['estimate_confidence'] = res['confidence']
            w['estimate_source'] = res['source']
            w['estimate_flag'] = res['flag']
            if res['low'] is not None:
                w['estimate_o'] = res['low']
                w['estimate_p'] = res['high']
            # 向后兼容别名
            w['estimate'] = res['expected_effort']

    if a.write and wbs:
        with open(a.project, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    findings = [
        f"校准叶子 {len(results)} 个；recalibrated={recal}，split-needed={split_needed}，low-confidence={low_conf}",
    ]
    if recal:
        findings.append(f"{recal} 个叶子经校准与原估算偏差 > {DIVERGENCE*100:.0f}%，已采用校准值")
    if split_needed:
        findings.append(f"{split_needed} 个叶子校准后超颗粒度阈值，已标 split-needed 交主控重拆")
    if low_conf:
        findings.append(f"{low_conf} 个叶子无方法/历史支持（estimate_confidence=low），须补 basis 或规模数据")

    if a.json:
        print(json.dumps({'threshold': threshold, 'results': results,
                          'findings': findings}, ensure_ascii=False, indent=2))
        return

    print("=== estimator-agent · 工作量校准报告 ===")
    for r in results:
        print(f"  [{r['flag']:>12}] {r['id']:<10} role={r['role']:<16} "
              f"orig={r['original_effort']:g} -> eff={r['expected_effort']:<6} "
              f"({r['method']}/{r['confidence']})")
    print("\n".join("  - " + f for f in findings))

    # 渲染计划级报告（render.py）；写回 artifacts.estimate_report
    try:
        from render import render
        tpl = os.path.join(SCRIPT_DIR, '..', 'templates', 'common', 'estimate_report.md')
        if os.path.exists(tpl):
            rendered = render(open(tpl, 'r', encoding='utf-8').read(), {
                'project': proj, 'results': results, 'findings': findings,
                'divergence_pct': int(DIVERGENCE * 100), 'basis_floor': int(ESTIMATE_BASIS_FLOOR),
            })
            out_dir = os.path.join(root, 'plans')
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, 'estimate_report.md')
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(rendered)
            rel = os.path.relpath(out_path, root)
            if 'artifacts' not in data or not isinstance(data['artifacts'], dict):
                data['artifacts'] = {}
            data['artifacts']['estimate_report'] = rel
            with open(a.project, 'w', encoding='utf-8') as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
            print(f"\n[estimator] 报告已写入 {out_path}；artifacts.estimate_report={rel}")
    except Exception as e:
        print(f"[estimator] 报告渲染跳过（{e}）")


if __name__ == '__main__':
    main()
