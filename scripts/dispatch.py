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

路由表与 references/activity-expert-map.md §2 保持一致（单一事实源）。
"""
import os
import sys
import json
import argparse

try:
    import yaml
except ImportError:
    yaml = None


# ---------- 角色关键词路由（对齐 activity-expert-map.md §2） ----------
ROLE_KEYWORDS = [
    ('data-architect', ['建模', '模型', '主题域', 'schema', 'erd', '数据模型', 'model', 'datamodel']),
    ('etl-engineer', ['迁移', '历史加载', '抽取', 'etl', '加载', '接入', 'migration', 'load']),
    ('data-security-engineer', ['脱敏', '掩码', '隐私', 'pii', '令牌', '加密', 'mask', 'privacy']),
    ('data-scientist', ['分析', '建模', '特征', 'ml', 'modelops', '用例', 'analytic']),
    ('dr-bcp-engineer', ['容灾', '业务连续', 'bcm', 'dr', 'rpo', 'rto', '故障切换']),
    ('governance-lead', ['治理', '元数据', '血缘', '审计', '加固', 'governance', 'meta', 'audit', 'hardening']),
    ('enablement-lead', ['培训', '赋能', '课程', 'training', 'enable']),
    ('infra-engineer', ['基础设施', '安装', '环境', 'infra', 'install', 'env', '部署']),
    ('domain-sme', ['sme', '业务知识', '源系统', '领域支持']),
    ('qa-lead', ['测试', 'uat', '质量', 'test', 'quality']),
    ('ba', ['需求', '用户故事', '规格', 'requirement', 'story']),
    ('change-manager', ['变更', 'ccb', 'change']),
    ('solution-architect', ['蓝图', '集成', '方案', 'blueprint', 'integration', 'solution']),
]

PM_GENERALIST = {'planner', 'scheduler', 'risk', 'stakeholder', 'reporter', 'program'}

DOMAIN_SPECIALIZATION = {
    'insurance-data-lake': {
        'data-architect': '保险主题域数据架构师',
        'etl-engineer': 'Teradata TPT/ETL 工程师',
        'data-security-engineer': '个保法/PII 合规工程师',
        'data-scientist': '保险精算/分析建模工程师',
        'governance-lead': '保险数据治理与审计负责人',
        'dr-bcp-engineer': '保险 BC/DR 工程师',
        'infra-engineer': 'Teradata/IFX 平台工程师',
    },
    'payments': {
        'data-architect': '支付领域架构师',
        'etl-engineer': '支付 ETL 工程师',
        'data-security-engineer': 'PCI-DSS 安全工程师',
        'data-scientist': '反欺诈/风控建模工程师',
    },
    'ecommerce': {
        'data-architect': '电商域建模师',
        'data-scientist': '推荐/搜索 ML 工程师',
        'etl-engineer': '电商数据工程师',
    },
    'fintech-core': {
        'data-architect': '核心银行领域架构师',
        'etl-engineer': '账务/清算工程师',
        'data-security-engineer': '监管报送工程师',
    },
}

DOMAIN_BY_KEYWORD = {
    'data-modelling': 'data-architect', 'modelling': 'data-architect',
    'migration': 'etl-engineer', 'etl': 'etl-engineer',
    'masking': 'data-security-engineer', 'privacy': 'data-security-engineer',
    'analytics': 'data-scientist', 'ml': 'data-scientist',
    'bcm': 'dr-bcp-engineer', 'dr': 'dr-bcp-engineer',
    'governance': 'governance-lead', 'hardening': 'governance-lead',
    'training': 'enablement-lead', 'enablement': 'enablement-lead',
    'infra': 'infra-engineer', 'install': 'infra-engineer',
    'sme': 'domain-sme',
}


def load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) if yaml else eval(f.read())


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def infer_role(row, name):
    """先取显式 role；否则按名称关键词；否则按 domain。"""
    if row.get('role'):
        return row['role']
    n = (name or '').lower()
    for rid, kws in ROLE_KEYWORDS:
        if any(k in n for k in kws):
            return rid
    dom = (row.get('domain') or '').lower()
    if dom in DOMAIN_BY_KEYWORD:
        return DOMAIN_BY_KEYWORD[dom]
    return None


def is_domain_activity(role, name, domain):
    if role in PM_GENERALIST:
        return False
    if role:
        return True
    n = (name or '').lower()
    if any(k in n for _, kws in ROLE_KEYWORDS for k in kws):
        return True
    if domain:
        return True
    return False


def specialize(role, domain, product):
    if not role:
        return None
    spec = DOMAIN_SPECIALIZATION.get((domain or '').lower(), {})
    if role in spec:
        return spec[role]
    if product:
        return f"{role}（{product}）"
    if domain:
        return f"{role}（{domain}）"
    return role


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
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, 'w', encoding='utf-8') as f:
            f.write(md)
        print(f"[dispatch] 计划已写入 {a.out}（{len(plan)} 项待调度）")
    else:
        print(md)
    print(f"\n共 {len(plan)} 个工作包需调度专家（阈值 {threshold:g} 人天）。", file=sys.stderr)


if __name__ == '__main__':
    main()
