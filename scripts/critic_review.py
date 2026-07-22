#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · WBS 拆解 Critic 自审引擎（Pillar 1 · 6 因素拆解纪律）

把 references/sow-parsing-playbook.md §2 的「专家级理解链路 + Critic 自审」固化为
**可执行**的校验，而不是散文建议。每次拆解 WBS（parse_sow / dispatch 专家回写）后运行，
列出未通过的 Critic 项；--strict 下退出码非 0。

覆盖的 6 个拆解驱动因素：
  1. scope        —— 每叶子须可追溯 charter Scope / 有 deliverable
  2. milestone     —— 每叶子须归属某 milestone（milestone_ref）；每固定费率 SOW 有计费里程碑
  3. payment       —— 计费里程碑须挂在 sow_map 支付行上（fee_type/fee 一致）
  4. assumptions   —— raid.assumptions 须可量化边界（"≤N ..."），否则变更触发不可执行
  5. constraints   —— 约束须显式，且外部前置约束须有 entry_gate 叶子作为前置
  6. dependencies  —— 依赖网络连通（无孤立叶子、无指向未知 ID、关键路径含 entry_gate）

用法：
  python3 critic_review.py --project <program/project.yaml>
  python3 critic_review.py --project <program/project.yaml> --strict
"""
import os
import re
import sys
import argparse

try:
    import yaml
except ImportError:
    yaml = None

NUM_RE = re.compile(r'\d+(\.\d+)?')


def load(path):
    if yaml is None:
        raise RuntimeError("需要 PyYAML，请先 pip install pyyaml")
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def parse_deps(dep):
    if dep is None:
        return []
    if isinstance(dep, list):
        out = []
        for x in dep:
            if isinstance(x, dict):
                sx = str(x.get('id') or x.get('to') or '').strip()
            else:
                sx = str(x).strip()
            if sx and sx not in ('—', '-'):
                out.append(sx)
        return out
    s = str(dep).strip()
    if s in ('', '—', '-'):
        return []
    return [p.strip() for p in re.split(r'[,;，；]', s) if p.strip()]


def has_bound(text):
    """假设/约束须含可量化边界：≤N / 至少 N / 不超过 N / N 个 / N 张 / N 表。"""
    if not text:
        return False
    t = str(text)
    if re.search(r'(≤|>=|>=|<=|不大于|不超过|至少|最多|上限|封顶)\s*\d', t):
        return True
    if re.search(r'\d+\s*(个|张|表|人天|人月|周|天|%%|倍)', t):
        return True
    return False


def main():
    ap = argparse.ArgumentParser(description="PM Master · WBS 拆解 Critic 自审")
    ap.add_argument('--project', required=True)
    ap.add_argument('--strict', action='store_true', help="未通过任一项即 exit 1")
    a = ap.parse_args()
    data = load(a.project)
    root = os.path.dirname(os.path.abspath(a.project))
    findings = []          # (severity, code, msg)
    problems = []          # 致命

    proj = data.get('project', {}) or {}
    phase = proj.get('phase') or ''
    wbs = data.get('wbs') or []
    raid = data.get('raid', {}) or {}
    ptype = (proj.get('type') or '').lower()

    # 仅在规划/启动期强制致命；运营期（已冻结，如示例客户）降级为告警，不阻断。
    lifecycle = proj.get('lifecycle_state')
    enforce = phase in ('启动', '规划', '') or lifecycle in (None, 'planning', 'review', 'baselined')
    byid = {w.get('id'): w for w in wbs}
    milestone_ids = {w.get('id') for w in wbs if w.get('milestone')}

    # ---- 1. scope 可追溯 ----
    for w in wbs:
        if w.get('summary') or w.get('milestone') or w.get('tier') == 'program':
            continue
        if not (w.get('deliverable') or w.get('scope')):
            problems.append(
                f"[scope] 叶子 {w.get('id')}『{w.get('name')}』缺 deliverable/scope，"
                f"须可追溯 charter Scope。")

    # ---- 2. milestone 归属 ----
    for w in wbs:
        if w.get('summary') or w.get('milestone') or w.get('tier') == 'program':
            continue
        mref = w.get('milestone_ref')
        # 若未显式标 milestone_ref，则要求依赖链末端/直接 dependsOn 命中某里程碑
        deps = parse_deps(w.get('dependsOn'))
        links_ms = mref in milestone_ids or any(d in milestone_ids for d in deps)
        if not links_ms:
            problems.append(
                f"[milestone] 叶子 {w.get('id')}『{w.get('name')}』未归属任何里程碑"
                f"（缺 milestone_ref 且 dependsOn 未指向里程碑）；"
                f"须显式标 milestone_ref 或让依赖末端落在里程碑上。")

    # ---- 3. payment 挂在支付行 ----
    sow_map = data.get('sow_map') or []
    fee_sows = {e.get('sow') for e in sow_map if e.get('fee_type') == 'fixed'}
    # program 层用 program.sow_map/sows；单层用 sow_map 或 wbs billing
    prog = data.get('program') or {}
    if prog:
        fee_sows |= {s.get('sow') for s in (prog.get('sows') or []) if s.get('fee_type') == 'fixed'}
    for w in wbs:
        b = w.get('billing') or {}
        if w.get('milestone') and b.get('fee_type') == 'fixed':
            wid = str(w.get('id', ''))
            sow = wid.split('.')[0] if wid else ''
            if sow not in fee_sows and not (b.get('fee') or b.get('fee_inr')):
                problems.append(
                    f"[payment] 计费里程碑 {w.get('id')}『{w.get('name')}』"
                    f"未在 sow_map 找到对应固定费率支付行（fee_type=fixed 且 fee>0）。")

    # ---- 4. assumptions 可量化边界 ----
    for ar in (raid.get('assumptions') or []):
        txt = ar.get('text') if isinstance(ar, dict) else str(ar)
        if not has_bound(txt):
            findings.append(('warn', 'assumption-bound',
                f"[assumption] 假设缺少可量化边界：『{txt[:60]}』——"
                f"无边界则 CCB 变更触发不可执行，须改为 '≤N 源表 / M 核心表' 等。"))

    # ---- 5. constraints + entry_gate 前置 ----
    for c in (raid.get('constraints') or []):
        txt = c.get('text') if isinstance(c, dict) else str(c)
        external = bool(re.search(r'(依赖|待|需|前置|就绪|提供|available|ready|pending|外部)', txt or '', re.I))
        if external and not has_bound(txt):
            findings.append(('warn', 'constraint-entrygate',
                f"[constraint] 外部前置约束『{txt[:50]}』未标 entry_gate 前置包——"
                f"须有 entry_gate 叶子作为该里程碑路径上的显式前置。"))

    # entry_gate 存在性（关键路径前置条件）
    has_entry_gate = any(str(w.get('id', '')).split('.')[-1].lower().startswith('e') or
                         'entry' in str(w.get('name', '')).lower() or
                         w.get('entry_gate') for w in wbs)
    if not has_entry_gate and wbs:
        findings.append(('warn', 'entry-gate',
            "[entry-gate] WBS 中未识别任何进入条件/数据就绪门(entry_gate)叶子；"
            "若外部前置（SME/真实数据/接口）是最大返工风险，须显式建模为前置包。"))

    # ---- 6. dependencies 连通 ----
    ids = {w.get('id') for w in wbs}
    orphan = []
    dangling = []
    # 被他人依赖的 id 集合（有后继即非孤立，允许作为起始节点无前置）
    referenced = set()
    for w in wbs:
        for d in parse_deps(w.get('dependsOn')):
            referenced.add(d)
    for w in wbs:
        if w.get('summary'):
            continue
        deps = parse_deps(w.get('dependsOn'))
        is_ms = w.get('milestone')
        if is_ms and w.get('components'):
            continue
        if not deps and not is_ms and w.get('id') not in referenced:
            orphan.append(w.get('id'))
        for d in deps:
            if d not in ids:
                dangling.append(f"{w.get('id')}→{d}")
    if len(wbs) > 1 and orphan:
        problems.append(
            f"[dependency] {len(orphan)} 个包无任何 dependsOn（孤立）：{', '.join(orphan[:8])}…"
            f"——须形成依赖网络（关键路径可算）。")
    if dangling:
        problems.append(
            f"[dependency] 依赖指向未知 ID：{', '.join(dangling[:8])}…——须修正。")

    # ---- 7. estimate sanity（补充透镜，仅告警，与 consistency/estimator 互补） ----
    # 在拆解后（规划期）提示：超大叶子（>2× 颗粒度阈值）或明显缺 DoD 的估算包，
    # 这类最易「拍脑袋估算」。不致命（避免阻断既有实时项目），交由 estimator-agent 校准 + 主控重拆。
    est_thr = float((data.get('control') or {}).get('granularity_threshold') or 10.0)
    for w in wbs:
        if w.get('summary') or w.get('milestone') or w.get('tier') == 'program':
            continue
        try:
            ev = float(w.get('effort') or w.get('estimate'))
        except (TypeError, ValueError):
            ev = 0.0
        if ev > 2 * est_thr:
            findings.append(('warn', 'estimate-outlier',
                f"[estimate] 叶子 {w.get('id')}『{w.get('name')}』effort={ev:g} 超 2× 颗粒度阈值"
                f"({est_thr:g})，最可能拍脑袋估算；须交专家重拆 + estimator-agent 校准。"))
        if ev > 0 and not (w.get('deliverable') or w.get('dod') or w.get('acceptance')):
            findings.append(('warn', 'estimate-dod',
                f"[estimate] 叶子 {w.get('id')}『{w.get('name')}』有估算但缺 DoD/交付物，"
                f"估算无验收锚点，estimate_confidence 应标 low。"))


    # ---- 输出 ----
    print("=== WBS 拆解 Critic 自审（6 因素） ===")
    if findings:
        print(f"⚠ 建议 {len(findings)} 条：")
        for sev, code, msg in findings:
            print("  -", msg)
    if not problems:
        print("✓ Critic 通过：6 因素拆解纪律无致命缺口")
        sys.exit(0)
    # 运营期（已冻结）降级为告警，不阻断
    if not enforce:
        print(f"ℹ 运营期({phase}/{lifecycle})不强制：以下 {len(problems)} 条为规划期纪律缺口，仅提示：")
        for p in problems:
            print("  -", p)
        sys.exit(0)
    print(f"✗ 致命 {len(problems)} 条（阻断交付，须重拆）：")
    for p in problems:
        print("  -", p)
    sys.exit(1)  # 规划期 Critic 致命项一律阻断


if __name__ == '__main__':
    main()
