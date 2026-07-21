#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · 项目脚手架
-------------------------------------------------
在 /workspace/<slug>/ 下建立标准目录结构并写入 project.yaml 骨架（单一事实源）。

用法：
  python3 init_project.py "支付重构" --type project --methodology agile --framework scrum
  python3 init_project.py "数字化转型项目群" --type program --methodology hybrid

生成结构：
  <slug>/
  ├── project.yaml          # 单一事实源
  ├── docs/                 # 章程、范围、需求等文档
  ├── plans/                # WBS、排期、迭代计划
  ├── risks/                # 风险登记册、RAID
  ├── reports/              # 状态报告、复盘
  └── artifacts/            # 渲染产出的正式文档
"""
import os
import sys
import argparse
import datetime

try:
    import yaml
except ImportError:
    yaml = None

BASE = "/workspace"


def slugify(name):
    s = name.strip().lower()
    s = ''.join(c if (c.isalnum() or c in '-_') else '-' for c in s)
    return s.strip('-') or 'project'


def build_skeleton(name, ptype, methodology, framework, domain='', product=''):
    today = datetime.date.today().isoformat()
    return {
        'schema_version': 2,
        '_checkpoint': {'step': 'init', 'at': today, 'phase': '启动' if ptype == 'project' else '组合定义'},
        'project': {
            'id': slugify(name),
            'name': name,
            'type': ptype,
            'methodology': methodology,
            'framework': framework if methodology == 'agile' else None,
            'phase': '启动' if ptype == 'project' else '组合定义',
            'status': '规划中',
            'lifecycle_state': 'planning',
            'baselined_on': None,
            'domain': domain,
            'product': product,
            'created': today,
            'start_date': None,
            'target_end': None,
            'objectives': [],
            'scope': '',
            'out_of_scope': '',
            'sponsor': '',
            'pm': '',
            'team': [],
        },
        'governance': {'stage_gates': [], 'cadence': ''},
        'artifacts': {},
        'raid': {'risks': [], 'assumptions': [], 'issues': [], 'dependencies': []},
        'metrics': {'evm': {}, 'burndown': []},
        'wbs': [],
        'milestones': [],
        'actuals': {},
        'control': {
            'leaf_granularity': 'fortnight',  # Pillar 3: 叶子包默认双周颗粒度
            'granularity_threshold': 10,     # = 10 工作人天（≈ fortnight）
            'cadence': '',
        },
        'program': (
            {'projects': [], 'dependencies': [], 'benefits': []}
            if ptype == 'program' else None
        ),
    }


def main():
    ap = argparse.ArgumentParser(description="PM Master 项目脚手架")
    ap.add_argument('name', help="项目/项目群名称")
    ap.add_argument('--type', default='project', choices=['project', 'program'])
    ap.add_argument('--methodology', default='agile',
                    choices=['waterfall', 'agile', 'iteration', 'hybrid'])
    ap.add_argument('--framework', default='scrum', choices=['scrum', 'kanban'])
    ap.add_argument('--domain', default='', help="领域标签，如 insurance-data-lake / payments，用于专家调度领域特化")
    ap.add_argument('--product', default='', help="产品名，用于专家调度特化（缺 domain 时作为兜底）")
    ap.add_argument('--base', default=BASE, help="工作区根目录")
    ap.add_argument('--parent', default=None, help="父项目/项目群 project.yaml（建子项目时填写）")
    ap.add_argument('--sow', default=None, help="关联父项目群的 SOW id（如 SOW1），写入 program.projects")
    ap.add_argument('--slug', default=None, help="子项目目录 slug（缺省按 name slugify）")
    a = ap.parse_args()

    # 子项目模式：在父项目根下 subprojects/<slug>/ 建立独立 project.yaml
    if a.parent:
        parent_path = os.path.abspath(a.parent)
        if not os.path.exists(parent_path):
            print(f"[init] 父项目不存在: {parent_path}"); sys.exit(2)
        parent_dir = os.path.dirname(parent_path)
        slug = a.slug or slugify(a.name)
        root = os.path.join(parent_dir, 'subprojects', slug)
        if os.path.exists(root):
            print(f"[init] 子项目已存在，跳过: {root}"); return
        os.makedirs(os.path.join(root, 'docs'))
        os.makedirs(os.path.join(root, 'plans'))
        os.makedirs(os.path.join(root, 'risks'))
        os.makedirs(os.path.join(root, 'reports'))
        os.makedirs(os.path.join(root, 'artifacts'))
        skeleton = build_skeleton(a.name, a.type, a.methodology, a.framework,
                                  domain=a.domain, product=a.product)
        skeleton['parent'] = {
            'project': os.path.relpath(parent_path, root),
            'sow': a.sow,
        }
        with open(os.path.join(root, 'project.yaml'), 'w', encoding='utf-8') as f:
            yaml.safe_dump(skeleton, f, allow_unicode=True, sort_keys=False)
        # 回写 program.projects 索引
        pdoc = yaml.safe_load(open(parent_path, encoding='utf-8'))
        pdoc.setdefault('program', {})
        pdoc['program'].setdefault('projects', [])
        entry = {'id': slug, 'name': a.name, 'sow': a.sow, 'slug': slug,
                 'methodology': a.methodology, 'status': '规划中',
                 'path': os.path.relpath(root, parent_dir)}
        if not any(e.get('id') == slug for e in pdoc['program']['projects']):
            pdoc['program']['projects'].append(entry)
        yaml.safe_dump(pdoc, open(parent_path, 'w', encoding='utf-8'),
                       allow_unicode=True, sort_keys=False)
        print(f"[init] 已创建子项目(从项目): {root}")
        print(f"[init] program.projects 已索引: {slug} -> {a.sow or '(未指定 SOW)'}")
        return

    root = os.path.join(a.base, slugify(a.name))
    if os.path.exists(root):
        print(f"[init] 已存在，跳过: {root}")
        return
    os.makedirs(os.path.join(root, 'docs'))
    os.makedirs(os.path.join(root, 'plans'))
    os.makedirs(os.path.join(root, 'risks'))
    os.makedirs(os.path.join(root, 'reports'))
    os.makedirs(os.path.join(root, 'artifacts'))

    skeleton = build_skeleton(a.name, a.type, a.methodology, a.framework,
                              domain=a.domain, product=a.product)
    with open(os.path.join(root, 'project.yaml'), 'w', encoding='utf-8') as f:
        if yaml:
            yaml.safe_dump(skeleton, f, allow_unicode=True, sort_keys=False)
        else:
            import json
            json.dump(skeleton, f, ensure_ascii=False, indent=2)

    print(f"[init] 已创建项目工作区: {root}")
    print(f"       类型={a.type}  方法论={a.methodology}"
          + (f"  框架={a.framework}" if a.methodology == 'agile' else ""))


if __name__ == '__main__':
    main()
