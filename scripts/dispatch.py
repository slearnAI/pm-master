#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · 专家调度计划生成器（Expert Dispatch Planner）
--------------------------------------------------------------
读取 project.yaml，审计每个 WBS 工作包：
  - 是否为领域活动却缺少 role 标签（应由专家产出）
  - 颗粒度是否过粗（estimate > granularity_threshold）→ 须调度专家拆解
依据 project.domain / project.product 把 role_id 特化为推荐专家名，
输出「调度计划」（Markdown + JSON），每项含可直接派给子 Agent 的 brief。

实际拆解由主控按计划派出领域专家子 Agent 完成（见 references/expert-roles.md /
activity-expert-map.md）。本脚本只做审计与计划，不改动 project.yaml。

角色/域路由来自 `role_catalog.py`（单一事实源，域无关，支持从合同/SOW 自动对齐）。
"""
import os
import sys
import json
import argparse

try:
    import yaml
except ImportError:
    yaml = None

# 单一事实源：领域 + 专家角色目录（域无关，自动从 SOW/合同对齐）
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import role_catalog as rc

PM_GENERALIST = rc.PM_GENERALIST


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


def infer_role(row, name):
    """先取显式 role；否则按名称关键词（域专属 -> 跨域 -> 中立回退）。"""
    return rc.infer_role(name, row.get('domain'), explicit_role=row.get('role'))


def is_domain_activity(role, name, domain):
    return rc.is_domain_activity(role, name, domain)


def specialize(role, domain, product):
    return rc.specialize(role, domain, product)


def build_plan(data, threshold):
    proj = data.get('project', {}) or {}
    domain = proj.get('domain')
    product = proj.get('product') or proj.get('name')
    wbs = data.get('wbs') or []
    plan = []
    for w in wbs:
        name = w.get('name') or ''
        est = to_float(w.get('estimate'))
        role = infer_role(w, name)
        dom = w.get('domain')
        actions = []
        if role and role not in PM_GENERALIST and not w.get('role'):
            actions.append('tag_role')
        if est > threshold:
            actions.append('decompose')
        if is_domain_activity(role, name, dom) and not role:
            actions.append('dispatch_expert')
        if not actions:
            continue
        expert = specialize(role, domain, product)
        pid = w.get('id')
        # 幂等：role 已存在且未超阈值 -> 视为已解决，标记 done（避免重复派专家）
        already_done = bool(w.get('role')) and est <= threshold and not (is_domain_activity(role, name, dom) and not role)
        if already_done:
            brief = (f"『{name}』已具备 role={role} 且颗粒度达标（{est:g}≤{threshold:g} 人天），"
                     f"无需再调度；如仍需细化可由专家增量拆解。")
            plan.append({
                'id': pid, 'name': name, 'estimate': est,
                'domain': dom, 'role': role, 'expert': expert,
                'actions': ['done'], 'brief': brief,
            })
            continue
        brief = (f"调度 {expert or '领域专家'}：把『{name}』（当前 {est:g} 人天）拆成叶子工作包"
                 f"（每个 ≤{threshold:g} 人天），含 唯一ID(前缀 {pid}.x)、交付物、责任人角色、估算、"
                 f"验收准则(DoD)、依赖(dependsOn)；回写 project.yaml 的 wbs 列表。")
        plan.append({
            'id': pid, 'name': name, 'estimate': est,
            'domain': dom, 'role': role, 'expert': expert,
            'actions': actions, 'brief': brief,
        })
    return plan, domain, product


def render_md(plan, domain, product, threshold):
    lines = []
    lines.append("# 专家调度计划 · Expert Dispatch Plan")
    lines.append("")
    lines.append(f"> 依据 `project.domain={domain}` / `product={product}` 特化；"
                 f"叶子包阈值 = {threshold:g} 人天。")
    lines.append("")
    if not plan:
        lines.append("✓ 无需调度：所有 WBS 包均已角色标注且颗粒度达标。")
        return "\n".join(lines)
    # 按角色分组
    by_role = {}
    for it in plan:
        by_role.setdefault(it['role'] or '未定', []).append(it)
    for role, items in by_role.items():
        lines.append(f"## 角色：{role}")
        lines.append("")
        lines.append("| WBS ID | 名称 | 估算(人天) | 领域 | 动作 | 推荐专家 |")
        lines.append("|--------|------|------------|------|------|----------|")
        for it in items:
            acts = ", ".join(it['actions'])
            lines.append(f"| {it['id']} | {it['name']} | {it['estimate']:g} | {it['domain'] or '—'} "
                         f"| {acts} | {it['expert'] or '—'} |")
        lines.append("")
        for it in items:
            lines.append(f"- **{it['id']} {it['name']}**：{it['brief']}")
        lines.append("")
    lines.append("---")
    lines.append("*由 `dispatch.py` 生成；实际拆解请用 `expert-roles.md` 对应角色的 system_prompt "
                 "派出子 Agent（或路由至 WorkBuddy 专家中心已安装的对应专家）。*")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="PM Master 专家调度计划生成器")
    ap.add_argument('--project', required=True)
    ap.add_argument('--threshold', type=float, default=10.0,
                    help="叶子包人天阈值，超过须拆解（默认 10）")
    ap.add_argument('--out', default=None, help="输出 Markdown 计划路径")
    ap.add_argument('--json', action='store_true', help="仅输出 JSON")
    a = ap.parse_args()

    data = load(a.project)
    ctrl = data.get('control') or {}
    threshold = float(ctrl.get('granularity_threshold') or a.threshold)
    plan, domain, product = build_plan(data, threshold)

    if a.json:
        print(json.dumps({'threshold': threshold, 'domain': domain, 'product': product,
                          'plan': plan}, ensure_ascii=False, indent=2))
        return

    md = render_md(plan, domain, product, threshold)
    pending = [p for p in plan if 'done' not in p['actions']]
    done = [p for p in plan if 'done' in p['actions']]
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, 'w', encoding='utf-8') as f:
            f.write(md)
        print(f"[dispatch] 计划已写入 {a.out}（{len(pending)} 项待调度 / {len(done)} 项已达标）")
    else:
        print(md)
    print(f"\n共 {len(pending)} 个工作包需调度专家（阈值 {threshold:g} 人天），{len(done)} 项已达标可跳过。", file=sys.stderr)


if __name__ == '__main__':
    main()
