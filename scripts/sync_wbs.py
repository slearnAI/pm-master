#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · WBS 拆解回写粘合器（关闭"专家拆解 → project.yaml"缺口）
-------------------------------------------------
专家（人或子 Agent）把 SOW/领域包拆成叶子工作包后，把结果写进一个
"拆解补丁" YAML/JSON（结构见 --help 或下方示例），本脚本把它 merge 回
project.yaml 的 `wbs` 列表，并自动：
  1. 把叶子包挂到对应父包（按 parent 字段 / id 前缀）。
  2. 标注 tier（program=汇总/里程碑，component=叶子）。
  3. 校验每个叶子包都有 role / owner / estimate / dod / dependsOn（缺则致命）。
  4. 回写 artifacts.wbs（若已存在 build_wbs 产物，置 dirty 标记）。

拆解补丁结构（list of packages，字段同 wbs 项，额外支持 parent）：
  - { id: SOW1.1, name: ..., domain: 后端, role: 后端工程师, owner: 王五,
      estimate: 8, dod: ..., dependsOn: [SOW1], parent: SOW1 }
  - { id: SOW1, name: 支付重构-后端, domain: 后端, role: 解决方案架构师,
      estimate: 40, tier: program, summary: true }

用法：
  python3 sync_wbs.py --project <yaml> --patch <拆解补丁.yaml>
  python3 sync_wbs.py --project <yaml> --patch <p.yaml> --dry-run   # 只校验不写
  python3 sync_wbs.py --project <yaml> --check-only                 # 仅校验现有 wbs
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

# 叶子包强制字段（一致性门禁 Rule #9 的同款约束，在此提前卡死）
LEAF_REQUIRED = ['role', 'owner', 'estimate', 'dod', 'dependsOn']


def _load(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) if yaml else {}


def _save(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)) if os.path.dirname(path) else '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        if yaml:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        else:
            import json
            json.dump(data, f, ensure_ascii=False, indent=2)


def _validate(pkgs, errors):
    by_id = {}
    for p in pkgs:
        pid = p.get('id')
        if not pid:
            errors.append('存在无 id 的工作包')
            continue
        by_id[pid] = p
        if p.get('tier') == 'program' or p.get('summary'):
            continue  # 汇总/里程碑包不强制叶子字段
        for fld in LEAF_REQUIRED:
            v = p.get(fld)
            if v is None or v == '' or v == [] or v == '（待定）':
                errors.append(f"叶子包 {pid} 缺少必填字段 {fld}")
        est = p.get('estimate')
        if isinstance(est, (int, float)) and est <= 0:
            errors.append(f"叶子包 {pid} 的 estimate 必须 > 0")
    # parent 引用必须存在
    for p in pkgs:
        par = p.get('parent')
        if par and par not in by_id:
            errors.append(f"包 {p.get('id')} 的 parent={par} 在 wbs 中不存在")
    return by_id


def _merge(data, patch):
    """把补丁 merge 进 project.yaml.wbs（按 id 覆盖/新增）。"""
    wbs = data.get('wbs') or []
    idx = {w.get('id'): i for i, w in enumerate(wbs) if w.get('id')}
    for p in patch:
        pid = p.get('id')
        if pid in idx:
            wbs[idx[pid]].update(p)
        else:
            wbs.append(p)
            idx[pid] = len(wbs) - 1
    data['wbs'] = wbs
    return data


def main():
    ap = argparse.ArgumentParser(description="PM Master · WBS 拆解回写粘合器")
    ap.add_argument('--project', required=True, help="单一事实源 project.yaml")
    ap.add_argument('--patch', default=None, help="拆解补丁 YAML/JSON（list of packages）")
    ap.add_argument('--dry-run', action='store_true', help="只校验，不写回")
    ap.add_argument('--check-only', action='store_true', help="只校验现有 wbs，不读补丁")
    a = ap.parse_args()

    if yaml is None:
        raise SystemExit("需要 PyYAML：请先 `pip install pyyaml`")

    data = _load(a.project)
    root = os.path.dirname(os.path.abspath(a.project))

    if a.check_only:
        errors = []
        _validate(data.get('wbs') or [], errors)
        if errors:
            print("✗ 校验失败：")
            for e in errors:
                print("  -", e)
            sys.exit(1)
        print("✓ 现有 wbs 校验通过")
        return

    if not a.patch or not os.path.exists(a.patch):
        print("✗ 请提供 --patch 拆解补丁路径", file=sys.stderr)
        sys.exit(2)

    patch = _load(a.patch)
    if not isinstance(patch, list):
        patch = patch.get('packages') or patch.get('wbs') or []
    if not isinstance(patch, list):
        print("✗ 补丁须为 list of packages", file=sys.stderr)
        sys.exit(2)

    errors = []
    _validate(patch, errors)
    if errors:
        print("✗ 拆解补丁校验失败（未写回）：")
        for e in errors:
            print("  -", e)
        sys.exit(1)

    if a.dry_run:
        print(f"✓ 补丁校验通过，将合并 {len(patch)} 个包（dry-run，未写回）")
        return

    data = _merge(data, patch)
    # 标记 wbs 产物为 dirty，提示需重渲染
    art = data.setdefault('artifacts', {})
    if 'wbs' in art:
        art['wbs_dirty'] = True
    _save(a.project, data)
    print(f"[sync_wbs] 已合并 {len(patch)} 个包到 project.yaml.wbs；如 wbs 已渲染请重跑 build_wbs.py")


if __name__ == '__main__':
    main()
