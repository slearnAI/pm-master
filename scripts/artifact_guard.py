#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · 运营期交付物护栏（Operational Artifact Guardrail, OAG）
==================================================================

强制（可执行）：在 operational / monitoring 阶段，任何对 project.yaml（事实源）的变更动作，
都必须伴随对应交付物（artifact）的刷新。否则视为护栏违规（guardrail breach）。

这是对手工/执行阶段「改了事实源、文档没跟上」漂移的根因封堵 —— 之前示例客户项目就因该护栏在
运营期被忽略，导致 raid_log / risk_register / portfolio_dashboard 落后于事实源，直到被人工发现。

判定逻辑（内容哈希，不依赖 mtime 技巧）：
  1. 计算「必需交付物」集合 = 已注册 artifacts 的全部 key ∪ 按数据存在性推导的强制 key
     （存在 raid → raid_log / risk_register；存在 metrics/actuals → status_report；
      program 类型且存在 metrics/actuals → 额外 portfolio_dashboard；存在 wbs → wbs 等）。
  2. 对每个必需 artifact：
     - 必须在 artifacts 中登记且文件存在；否则违规。
     - 若 artifacts_meta.<key>.source_hash 存在：用当前数据重算依赖哈希，一致=新鲜，不一致=漂移（违规）。
     - 若 artifacts_meta.<key>.source_hash 缺失（本护栏启用前产出的存量文档）：无法判定，给出
       ADVISORY（建议重渲染以启用漂移检测），不记为违规（避免存量文档被误杀）。
  3. 任一违规 → exit 1 并列出明细；全部通过 → exit 0。

可作为：
  - 编排器每次 operational 动作后的硬门（Step 4 后置 / 交付前）；
  - control_engine.py 周期巡检的一项（交付物漂移，RED 升级）；
  - gate_engine.py 监控门的检查项。

用法：
  python3 artifact_guard.py --project <yaml> [--json]
  python3 artifact_guard.py --project <yaml> --stamp status_report portfolio_dashboard
      # 手工撰写/外部渲染的文档，在产出后调用，记录 source_hash 以启用漂移检测
"""
import os
import sys
import json
import hashlib
import datetime
import argparse

try:
    import yaml
except ImportError:
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))


# artifact key -> 该交付物依赖的 project.yaml 顶层键（任一变化即应重渲染）
DEPS = {
    'raid_log': ['raid'],
    'risk_register': ['risks', 'raid'],
    'status_report': ['metrics', 'actuals', 'progress', 'risks', 'raid', 'program'],
    'portfolio_dashboard': ['metrics', 'actuals', 'program', 'sows', 'project'],
    'wbs': ['wbs'],
    'program_charter': ['program', 'project'],
    'schedule_gantt': ['schedule', 'wbs'],
    'closure_report': ['actuals', 'metrics'],
    'lessons_learned': ['actuals', 'metrics'],
    'control_report': [],  # 依赖全部，走 advisory（无 meta 即建议重渲染）
}


def _cond_required(data):
    """根据数据存在性推导强制交付物 key。"""
    req = set()
    if data.get('raid') or data.get('risks'):
        req.add('raid_log')
        req.add('risk_register')
    if data.get('metrics') or data.get('actuals'):
        req.add('status_report')
        if str(data.get('project', {}).get('type', '')).lower() == 'program':
            req.add('portfolio_dashboard')
    if data.get('wbs'):
        req.add('wbs')
    if str(data.get('project', {}).get('type', '')).lower() == 'program':
        req.add('program_charter')
    return req


def _hash_deps(data, keys):
    """对相关数据切片做稳定哈希（含键存在性，故缺失/新增亦可被检出）。"""
    slices = [(k, data.get(k)) for k in keys]
    blob = json.dumps(slices, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()[:16]


def check_artifacts(project_yaml, data=None, quiet=False):
    """返回 (ok:bool, violations:list, details:list[dict])。"""
    if yaml is None:
        return False, ['需要 PyYAML'], []
    if data is None:
        with open(project_yaml, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
    root = os.path.dirname(os.path.abspath(project_yaml))
    arts = data.get('artifacts', {}) or {}
    meta = data.get('artifacts_meta', {}) or {}
    registered = set(arts.keys())
    required = _cond_required(data) | registered

    violations = []
    details = []
    for key in sorted(required):
        rel = arts.get(key)
        if not rel:
            violations.append(f"[未登记] {key}：必需交付物未在 artifacts 登记")
            details.append({'key': key, 'status': 'MISSING_REG', 'path': ''})
            continue
        # 多文件交付物（如 sow_kickoffs: [...]）：逐个检查存在性
        if isinstance(rel, list):
            missing = []
            for r in rel:
                if not isinstance(r, str):
                    continue
                rp = r if os.path.isabs(r) else os.path.join(root, r)
                if not os.path.exists(rp):
                    missing.append(r)
            if missing:
                violations.append(f"[缺失文件] {key}：{', '.join(missing)} 不存在")
                details.append({'key': key, 'status': 'MISSING_FILE', 'path': ','.join(missing)})
            else:
                details.append({'key': key, 'status': 'OK', 'path': f'{len(rel)} files'})
            continue
        if not isinstance(rel, str):
            details.append({'key': key, 'status': 'ADVISORY_NO_META', 'path': ''})
            continue
        path = rel if os.path.isabs(rel) else os.path.join(root, rel)
        if not os.path.exists(path):
            violations.append(f"[缺失文件] {key}：{rel} 不存在")
            details.append({'key': key, 'status': 'MISSING_FILE', 'path': rel})
            continue
        m = meta.get(key) or {}
        if m.get('source_hash'):
            cur = _hash_deps(data, DEPS.get(key, []))
            if cur != m.get('source_hash'):
                violations.append(f"[数据漂移] {key}：源数据已变更（{rel}）未重新渲染")
                details.append({'key': key, 'status': 'STALE_HASH', 'path': rel})
            else:
                details.append({'key': key, 'status': 'OK', 'path': rel})
        else:
            # 存量文档（本护栏启用前产出）：无法判定，给 advisory，不记违规
            details.append({'key': key, 'status': 'ADVISORY_NO_META', 'path': rel})
    return (len(violations) == 0), violations, details


def stamp(project_yaml, keys):
    """为指定 artifact key 记录 source_hash（手工/外部渲染文档在产出后调用）。"""
    if yaml is None:
        raise RuntimeError("需要 PyYAML")
    with open(project_yaml, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    meta = data.setdefault('artifacts_meta', {})
    now = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    stamped = []
    for key in keys:
        deps = DEPS.get(key)
        if deps is None:
            print(f"  ⚠ {key}：未定义 DEPS，跳过（如需检测请在 artifact_guard.DEPS 登记）")
            continue
        h = _hash_deps(data, deps)
        meta[key] = {'source_hash': h, 'rendered_at': now}
        stamped.append(f"{key} -> {h}")
    with open(project_yaml, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
    return stamped


def main():
    ap = argparse.ArgumentParser(description="PM Master · 运营期交付物护栏 (OAG)")
    ap.add_argument('--project', required=True)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--stamp', nargs='+', metavar='KEY',
                    help="为指定 artifact key 记录 source_hash（手工/外部渲染文档产出后调用）")
    a = ap.parse_args()

    if a.stamp:
        stamped = stamp(a.project, a.stamp)
        print("=== 已记录 source_hash ===")
        for s in stamped:
            print("  -", s)
        return

    ok, violations, details = check_artifacts(a.project)
    if a.json:
        print(json.dumps({'ok': ok, 'violations': violations, 'details': details},
                         ensure_ascii=False, indent=2))
    else:
        print("=== 运营期交付物护栏 (OAG) ===")
        for d in details:
            icon = '✓' if d['status'] == 'OK' else ('ℹ' if d['status'] == 'ADVISORY_NO_META' else '✗')
            print(f"  {icon} {d['key']:20s} {d['status']}")
        if violations:
            print(f"\n护栏违规 {len(violations)} 项（exit 1）：")
            for v in violations:
                print("  -", v)
        else:
            adv = [d for d in details if d['status'] == 'ADVISORY_NO_META']
            if adv:
                print(f"\n✓ 全部已追踪交付物与事实源一致（exit 0）")
                print(f"  ℹ {len(adv)} 个存量文档未启用漂移检测（建议重渲染以记录 source_hash）")
            else:
                print("\n✓ 全部交付物与事实源一致（exit 0）")
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
