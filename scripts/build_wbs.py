#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · WBS 渲染器（两层颗粒度视图）
-------------------------------------------------
`templates/waterfall/wbs.md` 需要 `wbs_groups` / `view_label` / `view_note` / `view_group_note`
等数据键（由本脚本从 project.yaml 的 wbs 派生），不能直接用 render.py 渲染。

做什么：
  1. 从 project.yaml 读取 wbs。
  2. 按视图过滤 + 按领域(domain)分组，构造 wbs_groups（每个分组含 name + items，
     每个 item 附带 gantt_name 供 mermaid 甘特使用）。
  3. 渲染 templates/waterfall/wbs.md -> <项目根>/plans/wbs.md，并写回 artifacts.wbs。

视图（--view）：
  - full（默认）：全部工作包，按领域分组。
  - program：仅项目群里程碑级（tier: program 的汇总/里程碑行），按领域分组。
  - component：仅组件层最细叶子（非 program 层），按领域分组。

用法：
  python3 build_wbs.py --project /workspace/<slug>/project.yaml
  python3 build_wbs.py --project <yaml> --view program
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


def _load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def _save(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def _group_by_domain(rows):
    groups = []
    seen = {}
    for w in rows:
        dom = w.get('domain') or '（未分类）'
        if dom not in seen:
            seen[dom] = len(groups)
            groups.append({'name': dom, 'items': []})
        item = dict(w)
        item['gantt_name'] = w.get('name', w.get('id', ''))
        groups[seen[dom]]['items'].append(item)
    return groups


def _build_tree(rows):
    """把扁平 wbs 构造成层级分解树（parent 字段或 id 前缀 'X.Y' 决定父子）。
    返回 list of 节点：{id, name, role, domain, children:[...]}。
    用于模板渲染 mermaid 分解树（graph TD）。"""
    nodes = {}
    for w in rows:
        pid = w.get('id')
        if not pid:
            continue
        nodes[pid] = {
            'id': pid,
            'name': w.get('name', pid),
            'role': w.get('role') or '',
            'domain': w.get('domain') or '',
            'tier': w.get('tier', ''),
            'parent': w.get('parent'),
            'children': [],
        }
    roots = []
    for pid, n in nodes.items():
        par = n.get('parent')
        # 无 parent 时，尝试用 id 前缀推断（如 SOW1.1 -> SOW1）
        if not par and '.' in pid:
            cand = pid.rsplit('.', 1)[0]
            par = cand if cand in nodes else None
        if par and par in nodes:
            n['parent_id'] = par
            nodes[par]['children'].append(n)
        else:
            roots.append(n)
    return roots


def main():
    ap = argparse.ArgumentParser(description="PM Master · WBS 渲染器（两层颗粒度）")
    ap.add_argument('--project', required=True, help="单一事实源 project.yaml")
    ap.add_argument('--view', default='full', choices=['full', 'program', 'component'],
                    help="视图：full=全部 / program=项目群里程碑级 / component=组件叶子层")
    ap.add_argument('--out', default=None, help="输出 .md 路径（缺省 <项目根>/plans/wbs.md）")
    ap.add_argument('--template', default=None, help="WBS 模板路径（缺省取技能内 templates/waterfall/wbs.md）")
    a = ap.parse_args()

    if yaml is None:
        raise SystemExit("需要 PyYAML：请先 `pip install pyyaml`")

    data = _load(a.project)
    wbs = data.get('wbs') or []
    if not wbs:
        raise SystemExit("⚠ project.yaml 中未找到 wbs，无法渲染 WBS（请先完成 WBS 拆解）。")

    if a.view == 'program':
        rows = [w for w in wbs if w.get('tier') == 'program']
        view_label = '项目群里程碑级'
        view_note = '仅呈现各 SOW 汇总包 + 各阶段里程碑汇总包（组件叶子包在各自 component 项目持有）'
        view_group_note = '领域（项目群里程碑级）'
    elif a.view == 'component':
        rows = [w for w in wbs if w.get('tier') != 'program']
        view_label = '组件叶子层'
        view_note = '呈现最细叶子工作包级（含领域专家拆解包）'
        view_group_note = '领域（组件叶子层）'
    else:
        rows = list(wbs)
        view_label = '全部工作包'
        view_note = '项目全生命周期工作包（汇总 + 叶子）'
        view_group_note = '领域'

    wbs_groups = _group_by_domain(rows)
    wbs_tree = _build_tree(rows)

    tpl_path = a.template or os.path.join(SCRIPT_DIR, '..', 'templates', 'waterfall', 'wbs.md')
    tpl_path = os.path.abspath(tpl_path)
    if not os.path.exists(tpl_path):
        raise SystemExit(f"WBS 模板不存在：{tpl_path}")
    with open(tpl_path, 'r', encoding='utf-8') as f:
        tpl = f.read()
    from render import render
    rendered = render(tpl, {
        'project': data.get('project', {}),
        'view_label': view_label,
        'view_note': view_note,
        'view_group_note': view_group_note,
        'wbs_groups': wbs_groups,
        'wbs_tree': wbs_tree,
    })

    root = os.path.dirname(os.path.abspath(a.project))
    out_path = a.out or os.path.join(root, 'plans', 'wbs.md')
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(rendered)

    rel = os.path.relpath(out_path, root)
    if 'artifacts' not in data or not isinstance(data['artifacts'], dict):
        data['artifacts'] = {}
    data['artifacts']['wbs'] = rel
    _save(a.project, data)

    print(f"[wbs] 已渲染 WBS（{a.view} 视图，{len(wbs_groups)} 个领域分组，{len(rows)} 个包）：{out_path}")
    print(f"[wbs] artifacts.wbs = {rel}")


if __name__ == '__main__':
    main()
