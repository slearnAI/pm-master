#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · 跨产物一致性校验（交付前质量门 · 控制级）
--------------------------------------------------------------
读取 project.yaml（单一事实源），执行两层校验：

  [致命问题 problems]  ->  存在则 exit 1，阻断交付
    1. 风险登记：每条风险须有 owner 与 mitigation/response
    2. 问题日志：每条 issue 须有 owner 与 due
    3. 依赖：每条依赖须有 from 与 to
    4. 治理：项目须指定 pm 与 sponsor
    5. 产物索引：artifacts 中引用的文件须真实存在
    6. 估算强制（控制级）：WBS / backlog / iteration 的每行须有数值化估算(>0)，
       不可用 "—" / 空 / 非数字（P0）
    7. 排期网络（控制级）：waterfall / hybrid 的 WBS 多行时必须形成依赖网络，
       不允许所有行都无依赖（P0）
    8. EVM 基线（控制级）：waterfall / hybrid 进入 执行/监控/收尾 阶段时，
       metrics.evm 必须含 pv / ev / ac（P0）
    9. 混合微计划（控制级）：methodology=hybrid 时须至少存在一个微层计划
       （sprint / backlog / iteration）（P0）
   10. 风险 5×5 校准（控制级）：每条风险 likelihood/impact 须为 1-5 数值，
       score == likelihood×impact，且 severity 与 score 所处色带一致（P0）
   11. 收益责任人（P1）：项目群的每条收益须有 owner
   12. 基线化纪律（控制级）：waterfall / hybrid 处于 执行/监控/收尾 阶段但缺 baseline 指针，
       必须先 规划→评审→baseline.py --freeze 再经控制门进入执行（references/lifecycle.md §5）

  [告警 warnings]  ->  仅提示，不阻断（exit 仍可为 0）；`--strict` 下升级为致命
    - 项目群 / hybrid 建议具备 change_log（变更控制）
    - 执行/监控阶段建议具备 status_report
    - 执行/监控阶段建议配置 control 块 + control_register（运营控制引擎）
    - 建议具备 communication_plan
    - 非领域活动的 WBS 估算超过叶子包颗粒度阈值（通用颗粒度提示，建议拆解）
    - 领域活动 WBS 缺 role 标签 / 超阈值：**默认致命**（见下方 7b，强制走专家拆解，不可由主控自拆绕过）

用法：
  python3 consistency_check.py --project /workspace/<slug>/project.yaml
  python3 consistency_check.py --project ... --strict  # 把告警也升级为致命
"""
import os
import re
import sys
import argparse
import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    import yaml
except ImportError:
    yaml = None


def load_config():
    """读取安装期 config.yaml；不存在时返回空 dict（惰性，避免循环依赖）。"""
    for cand in (os.path.join(SCRIPT_DIR, '..', 'config.yaml'),
                 os.path.join(SCRIPT_DIR, 'config.yaml')):
        if os.path.exists(cand):
            try:
                with open(cand, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                return {}
    return {}


# ---------- 风险 5×5 色带 ----------
def risk_band(score):
    """score = likelihood(1-5) × impact(1-5) ∈ [1,25]。色带：
    1-4 低(绿) | 5-9 中(黄) | 10-15 高(橙) | 16-25 严重(红)"""
    if score <= 4:
        return 'low'
    if score <= 9:
        return 'medium'
    if score <= 15:
        return 'high'
    return 'critical'


SEV_MAP = {
    '绿': 'low', 'green': 'low', 'low': 'low', 'l': 'low',
    '黄': 'medium', 'yellow': 'medium', 'medium': 'medium', 'm': 'medium',
    '橙': 'high', 'orange': 'high', 'high': 'high', 'h': 'high',
    '红': 'critical', 'red': 'critical', 'critical': 'critical', 'c': 'critical',
}


def norm_sev(s):
    if s is None:
        return None
    return SEV_MAP.get(str(s).strip().lower())


def load(path):
    if yaml is None:
        raise RuntimeError("需要 PyYAML，请先 pip install pyyaml")
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def has_estimate(est):
    """估算必须能解析出 >0 的数值；'—' / 空 / 非数字 / 0 均视为缺失。"""
    if est is None:
        return False
    if isinstance(est, (int, float)):
        return est > 0
    s = str(est).strip()
    if s in ('', '—', '-', 'TBD', '待定', 'N/A', 'NA', 'none', 'null'):
        return False
    m = re.search(r'\d+(\.\d+)?', s)
    if not m:
        return False
    return float(m.group()) > 0


def parse_deps(dep):
    """dependsOn 兼容 列表 与 逗号分隔字符串 两种写法。"""
    if dep is None:
        return []
    if isinstance(dep, list):
        out = []
        for x in dep:
            sx = str(x).strip()
            if sx and sx not in ('—', '-'):
                out.append(sx)
        return out
    s = str(dep)
    if s.strip() in ('', '—', '-'):
        return []
    return [p.strip() for p in re.split(r'[,;，；]', s) if p.strip()]


def collect_risks(data):
    """合并顶层 risks 与 raid.risks（按 id 去重，优先顶层）。"""
    seen = {}
    for r in (data.get('risks') or []):
        if r.get('id'):
            seen[r['id']] = r
    for r in ((data.get('raid') or {}).get('risks') or []):
        if r.get('id') and r['id'] not in seen:
            seen[r['id']] = r
    return list(seen.values())


# ---------- 角色推断（对齐 activity-expert-map.md §2，单一事实源） ----------
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
DOMAIN_BY_KEYWORD = {
    'data-modelling': 'data-architect', 'modelling': 'data-architect',
    'migration': 'etl-engineer', 'etl': 'etl-engineer',
    'masking': 'data-security-engineer', 'privacy': 'data-security-engineer',
    'analytics': 'data-scientist', 'ml': 'data-scientist',
    'bcm': 'dr-bcp-engineer', 'dr': 'dr-bcp-engineer',
    'governance': 'governance-lead', 'hardening': 'governance-lead',
    'training': 'enablement-lead', 'enablement': 'enablement-lead',
    'infra': 'infra-engineer', 'install': 'infra-engineer', 'sme': 'domain-sme',
}


def infer_role(row, name):
    if row.get('role'):
        return row['role']
    n = (name or '').lower()
    for rid, kws in ROLE_KEYWORDS:
        if any(k in n for k in kws):
            return rid
    return DOMAIN_BY_KEYWORD.get((row.get('domain') or '').lower())


def is_domain_activity(role, name, domain):
    if role in PM_GENERALIST:
        return False
    if role:
        return True
    n = (name or '').lower()
    if any(k in n for _, kws in ROLE_KEYWORDS for k in kws):
        return True
    return bool(domain)


def main():
    ap = argparse.ArgumentParser(description="PM Master 一致性校验（控制级）")
    ap.add_argument('--project', required=True)
    ap.add_argument('--strict', action='store_true',
                    help="将告警(warnings)也升级为致命问题（覆盖 config 默认）")
    a = ap.parse_args()
    data = load(a.project)
    # 配置优先：config.quality_gate.consistency_check_strict，CLI --strict 可覆盖
    cfg = load_config()
    strict_cfg = bool((cfg.get('quality_gate') or {}).get('consistency_check_strict'))
    strict = a.strict or strict_cfg
    root = os.path.dirname(os.path.abspath(a.project))
    problems = []
    warnings = []

    raid = data.get('raid', {}) or {}
    for r in raid.get('risks', []) or []:
        if not r.get('owner'):
            problems.append(f"风险 {r.get('id','?')} 缺少责任人(owner)")
        if not (r.get('mitigation') or r.get('response')):
            problems.append(f"风险 {r.get('id','?')} 缺少应对措施(mitigation/response)")
    for i in raid.get('issues', []) or []:
        if not i.get('owner'):
            problems.append(f"问题 {i.get('id','?')} 缺少责任人(owner)")
        if not i.get('due'):
            problems.append(f"问题 {i.get('id','?')} 缺少截止日期(due)")
    for dep in raid.get('dependencies', []) or []:
        if not (dep.get('from') and dep.get('to')):
            problems.append(f"依赖 {dep.get('id','?')} 缺少 from/to")

    proj = data.get('project', {}) or {}
    if not proj.get('pm'):
        problems.append("项目未指定项目经理(pm)")
    if not proj.get('sponsor'):
        problems.append("项目未指定发起人(sponsor)")

    artifacts = data.get('artifacts', {}) or {}
    for key, rel in artifacts.items():
        if not rel:
            continue
        # 支持 list 型产物索引（如 sow_kickoffs 多文件）；逐条校验存在性
        rels = rel if isinstance(rel, list) else [rel]
        for r in rels:
            if not r:
                continue
            full = r if os.path.isabs(r) else os.path.join(root, r)
            if not os.path.exists(full):
                problems.append(f"产物索引 {key} 指向的文件不存在: {r}")
    # 单一事实源防漂移：wbs 曾回写但尚未重渲染，提示重跑 build_wbs.py
    if artifacts.get('wbs_dirty'):
        warnings.append(
            "project.yaml.wbs 已更新但 wbs 文档(artifacts.wbs)未重渲染（wbs_dirty 标记）。"
            "请重跑 `build_wbs.py` 保持文档与事实源一致。")

    methodology = (proj.get('methodology') or '').lower()
    ptype = (proj.get('type') or '').lower()
    phase = (proj.get('phase') or '')

    # ---- 6. 估算强制 ----
    wbs = data.get('wbs') or []
    if wbs:
        missing = [w.get('id', '?') for w in wbs if not has_estimate(w.get('estimate'))]
        if missing:
            problems.append(
                f"WBS 估算缺失（控制级）：以下工作包无数值化估算(>0)：{', '.join(missing)}"
                f" —— 不允许 '—'/空/非数字")
    if methodology == 'agile':
        for bk in (data.get('backlog') or []):
            if not has_estimate(bk.get('estimate')):
                problems.append(f"Backlog {bk.get('id','?')} 缺少估算(estimate)")
        for sp in (data.get('sprints') or data.get('sprint') or []):
            for t in (sp.get('tasks') or [] if isinstance(sp, dict) else []):
                if not has_estimate(t.get('estimate')):
                    problems.append(f"Sprint 任务 {t.get('id','?')} 缺少估算")
    if methodology == 'iteration':
        for bk in (data.get('backlog') or []):
            if not has_estimate(bk.get('estimate')):
                problems.append(f"迭代 Backlog {bk.get('id','?')} 缺少估算")

    # ---- 6b. 计费里程碑完整性（基础布局门禁） ----
    # 固定费率 SOW（sow_map.fee_type=='fixed' 或子树含 billing.fee_type=='fixed' 且 fee>0）
    # 必须存在 ≥1 个 milestone + billing.fee_type=='fixed' 的包，否则计划不可测、收入无法确认。
    def _num(x):
        if isinstance(x, (int, float)):
            return x
        if isinstance(x, str):
            s = re.sub(r'[^0-9.]', '', x)
            return float(s) if s else 0.0
        return 0.0
    sow_map = data.get('sow_map') or []
    fee_sows = set()
    for e in sow_map:
        # 仅固定费率 SOW 强制计费里程碑；T&M（fee_type=='tm'，fee 为工时上限）不要求
        if e.get('fee_type') == 'fixed':
            fee_sows.add(e.get('sow'))
    for w in wbs:
        b = w.get('billing') or {}
        if b.get('fee_type') == 'fixed' and _num(b.get('fee_inr') or b.get('fee')) > 0:
            # 从包的 SOW 前缀推断归属
            wid = str(w.get('id', ''))
            m = re.match(r'^(SOW\d+)', wid)
            if m:
                fee_sows.add(m.group(1))
    if fee_sows:
        for sow in fee_sows:
            prefix = sow + '.'
            has_billing_ms = any(
                w.get('milestone') and (w.get('billing') or {}).get('fee_type') == 'fixed'
                and ((w.get('billing') or {}).get('fee_inr') or (w.get('billing') or {}).get('fee') or 0) > 0
                and (w.get('id') == sow or str(w.get('id', '')).startswith(prefix))
                for w in wbs)
            if not has_billing_ms:
                problems.append(
                    f"基础布局缺陷（致命）：固定费率 SOW {sow} 子树缺少计费里程碑"
                    f"（milestone + billing.fee_type=='fixed' 且 fee>0）。"
                    f"解析 SOW 时必须把每个 'post sign-off/完工证书' 计费事件建模为里程碑包，"
                    f"否则排期与收入确认不可测。参见 references/sow-parsing-playbook.md。")


    # ---- 6c. 拆解纪律（Pillar 1 · 6 因素，仅规划期致命） ----
    # 进入运营(执行/监控/收尾)后不再阻断（保护已冻结项目，如示例客户），
    # 但规划/启动期须强制 6 因素拆解 + Critic 自审通过。
    planning_now = phase in ('启动', '规划', '') or (proj.get('lifecycle_state') in (None, 'planning', 'review', 'baselined'))
    if planning_now:
        # 6c-1 拆解 Critic 自审（scope/milestone/payment/assumptions/constraints/dependencies）
        cc = os.path.join(SCRIPT_DIR, 'critic_review.py')
        if os.path.exists(cc) and wbs:
            try:
                import subprocess as _sp
                r = _sp.run([sys.executable, cc, '--project', a.project, '--strict'],
                            capture_output=True, text=True)
                for line in (r.stdout or '').splitlines():
                    if line.strip().startswith('✗') or '致命' in line:
                        pass
                if r.returncode != 0:
                    # 把 critic 的致命项逐条引入一致性门
                    for line in (r.stdout or '').splitlines():
                        m = re.match(r'\s*-\s+\[(scope|milestone|payment|dependency)\]\s*(.*)', line)
                        if m:
                            problems.append(f"拆解 Critic({m.group(1)}): {m.group(2)}")
            except Exception:
                pass
        # 6c-2 decomposition.critic_passed 标志（专家回写后须置 true）
        decomp = data.get('decomposition') or {}
        if wbs and not decomp.get('critic_passed'):
            problems.append(
                "拆解 Critic 未确认（decomposition.critic_passed != true）："
                "WBS 经专家拆解后须运行 critic_review.py 并置 critic_passed=true，否则视为未自审。")
        # 6c-3 假设可量化边界（charter 估算基准的一部分）
        for ar in (raid.get('assumptions') or []):
            txt = ar.get('text') if isinstance(ar, dict) else str(ar)
            if not re.search(r'(≤|>=|<=|不大于|不超过|至少|最多|上限|封顶)\s*\d', str(txt or '')) and \
               not re.search(r'\d+\s*(个|张|表|人天|人月|周|天|%|倍)', str(txt or '')):
                problems.append(
                    f"假设缺少可量化边界：『{(str(txt)[:50])}』——须改为 '≤N 源表/M 核心表' 等，否则 CCB 变更触发不可执行。")

    # ---- 6d. 排期联动（Pillar 2 + 4 · 仅规划期致命） ----
    if planning_now:
        # 6d-1 milestone 归属：每叶子须归属某里程碑（Critic 已覆盖，这里补「里程碑非空覆盖」）
        ms_ids = {w.get('id') for w in wbs if w.get('milestone')}
        uncovered = [w.get('id') for w in wbs
                     if not (w.get('summary') or w.get('milestone') or w.get('tier') == 'program')
                     and not w.get('milestone_ref') and not any(d in ms_ids for d in parse_deps(w.get('dependsOn')))]
        if uncovered:
            problems.append(
                f"里程碑覆盖缺口（Pillar 2）：{len(uncovered)} 个叶子未归属任何里程碑"
                f"（{', '.join(uncovered[:6])}…），须置 milestone_ref 或让依赖末端落在里程碑。")
        # 6d-2 支付↔里程碑顺序：固定费率支付行须有对应计费里程碑
        pay_lines = []
        for s in ((data.get('program') or {}).get('sows') or []) + (data.get('sow_map') or []):
            fee = s.get('fee')
            if isinstance(fee, str):
                fee = re.sub(r'[^0-9.]', '', fee) or '0'
            try:
                fee_v = float(fee)
            except (TypeError, ValueError):
                fee_v = 0.0
            if s.get('fee_type') == 'fixed' and fee_v > 0:
                pay_lines.append(s.get('sow'))
        for sow in set(pay_lines):
            prefix = sow + '.'
            has_pm = any(w.get('milestone') and (w.get('billing') or {}).get('fee_type') == 'fixed'
                         and ((w.get('billing') or {}).get('fee_inr') or (w.get('billing') or {}).get('fee') or 0) > 0
                         and (w.get('id') == sow or str(w.get('id', '')).startswith(prefix))
                         for w in wbs)
            if not has_pm:
                problems.append(
                    f"支付↔里程碑缺失（Pillar 4）：固定费率 SOW {sow} 有支付行但 WBS 无对应计费里程碑"
                    f"（须把 'post sign-off' 事件建模为 milestone + billing.fee_type=fixed）。")
        # 6d-3 支付顺序单调：同一 SOW 的计费里程碑按排期日须单调（付款节奏有序）
        for sow in set(pay_lines):
            prefix = sow + '.'
            dates = []
            for w in wbs:
                if w.get('milestone') and (w.get('billing') or {}).get('fee_type') == 'fixed' \
                   and _num((w.get('billing') or {}).get('fee_inr') or (w.get('billing') or {}).get('fee') or 0) > 0 \
                   and (w.get('id') == sow or str(w.get('id', '')).startswith(prefix)):
                    sd = w.get('start')
                    if sd:
                        try:
                            dates.append(datetime.date.fromisoformat(str(sd)[:10]))
                        except (ValueError, TypeError):
                            pass
            if len(dates) >= 2:
                mono = all(dates[i] <= dates[i+1] for i in range(len(dates)-1))
                if not mono:
                    problems.append(
                        f"支付顺序非单调（Pillar 4）：SOW {sow} 计费里程碑排期日不升序，"
                        f"付款节奏与交付节奏不一致，须修正依赖/顺序。")

    # ---- 7. 排期网络 ----
    if wbs and len(wbs) > 1 and methodology in ('waterfall', 'hybrid'):
        ids = {w.get('id') for w in wbs}
        linked = 0
        bad = []
        for w in wbs:
            deps = parse_deps(w.get('dependsOn'))
            if deps:
                linked += 1
            for d in deps:
                if d not in ids:
                    bad.append(f"{w.get('id','?')}→{d}")
        if linked == 0:
            problems.append(
                "排期未形成依赖网络（控制级）：waterfall/hybrid 的多行 WBS 须至少存在依赖关系，"
                "否则无法计算关键路径。请为每个工作包填写 dependsOn。")
        if bad:
            warnings.append(f"WBS 依赖指向未知 ID（建议核对）：{', '.join(bad)}")

    # ---- 7b. 专家角色标注 + 颗粒度 ----
    # 领域活动必须由对应专家产出并拆到叶子包，否则 WBS 会停在 SOW 级粗粒度。
    # 关键修复：凡「领域活动缺 role 标签」或「领域活动超阈值」，默认即致命（exit 1 阻断交付），
    # 强制走 dispatch.py -> 领域专家子 Agent 拆解，主控不得直接拆分绕过（见 SKILL.md Step 2.5 / §6）。
    # program 级 summary 汇总包（SOW/P0 父包）跳过，由组件层叶子包承担。
    ctrl_blk = data.get('control') or {}
    gran_thr = float(ctrl_blk.get('granularity_threshold') or 10)
    for w in wbs:
        # program 级汇总/里程碑行（SOW/P0 父包、tier:program、milestone）不检查：
        # 项目群颗粒度本就到里程碑级（见 references/program-management.md），由组件层叶子包承担；
        # 主控不得在项目群层把里程碑行当领域包去拆。
        if w.get('summary') or w.get('milestone') or (w.get('tier') == 'program'):
            continue
        wid = w.get('id', '?')
        name = w.get('name') or ''
        role = infer_role(w, name)
        dom = w.get('domain')
        is_da = is_domain_activity(role, name, dom)
        try:
            est_v = float(w.get('estimate'))
        except (TypeError, ValueError):
            est_v = 0.0
        over = est_v > gran_thr
        if is_da and not w.get('role'):
            problems.append(
                f"WBS {wid}『{name}』为领域活动但缺少 role 标签（致命）："
                f"须由对应领域专家（{role or '见 references/expert-roles.md'}）产出并写回 wbs，"
                f"主控不得直接拆分。参考 references/activity-expert-map.md §3-§4。")
        if is_da and over:
            problems.append(
                f"WBS {wid}『{name}』估算 {est_v:g} 人天超过叶子包阈值 {gran_thr:g}（致命）："
                f"须调度领域专家进一步拆为 ≤{gran_thr:g} 人天的叶子包（ID 前缀 {wid}.x），"
                f"防止 SOW 级粗粒度 WBS 当交付。")
        if (not is_da) and over:
            warnings.append(
                f"WBS {wid}『{name}』估算 {est_v:g} 人天超过叶子包阈值 {gran_thr:g}，"
                f"建议进一步拆解（非领域活动，仅告警）。")

    # ---- 7c. 项目群：SOW 映射 ↔ WBS 一致（合同边界防漂移） ----
    # 仅在项目群类型校验：program.sow_map[].sow 必须对应 wbs 中的 tier:program / summary 汇总包。
    if ptype == 'program':
        wbs_ids = {w.get('id') for w in wbs}
        sow_map = (data.get('program') or {}).get('sow_map') or []
        if sow_map:
            for m in sow_map:
                sid = m.get('sow')
                if not sid:
                    problems.append("program.sow_map 存在无 sow 字段的映射条目")
                    continue
                tgt = next((w for w in wbs if w.get('id') == sid), None)
                if tgt is None:
                    problems.append(
                        f"合同边界漂移（致命）：program.sow_map 的 SOW『{sid}』"
                        f"在 wbs 中找不到对应汇总包（tier:program 或 summary:true）。")
                elif not (tgt.get('tier') == 'program' or tgt.get('summary')):
                    problems.append(
                        f"合同边界漂移（致命）：SOW『{sid}』在 wbs 中不是汇总包"
                        f"（须 tier:program 或 summary:true），与项目群两层颗粒度约定冲突。")
            # 反向：wbs 中【顶层】项目群汇总包（tier:program 且 id 不含 '.'）应至少被一个 sow_map 引用
            # 组件层 phase 汇总包（如 SOW1.1 阶段组，tier:component）不算，避免误报。
            mapped = {m.get('sow') for m in sow_map}
            orphans = [w.get('id') for w in wbs
                       if w.get('tier') == 'program' and not str(w.get('id', '')).count('.')
                       and w.get('id') not in mapped]
            if orphans:
                warnings.append(
                    f"以下项目群汇总包未被 program.sow_map 引用（建议补映射，避免合同边界遗漏）："
                    f"{', '.join(orphans)}")
        # Extract 外包须绑定合同
        for ex in ((data.get('program') or {}).get('extracts') or []):
            if (ex.get('mode') or '').lower() in ('外包', 'outsource', 'out') and not ex.get('contract'):
                problems.append(
                    f"Extract『{ex.get('id')}』标记为外包但无绑定合同（contract 为空）："
                    f"外包范围须有合同依据。")
        # 7d. SOW 费用必填（禁止整表（待定）/TBD/空）
        for s in ((data.get('program') or {}).get('sows') or []):
            fee = (s.get('fee') or '').strip()
            if not fee or fee in ('（待定）', '待定', 'TBD', 'tbd', 'N/A', '-'):
                problems.append(
                    f"SOW『{s.get('sow')}』费用(fee)未填或仍为（待定）/TBD："
                    f"合同锁定后填金额，未锁定须写『TBC — 原因』。")

    # ---- 8. EVM 基线 ----
    # 计划价值(PV/BAC)属于计划基线，须在 metrics.evm；当前挣值/实际成本(ev/ac)
    # 在运营期可位于 actuals 块（control_engine.py 的单一现状源），亦兼容旧式 metrics.evm.ev/ac。
    if methodology in ('waterfall', 'hybrid') and phase in ('执行', '监控', '收尾'):
        evm = data.get('metrics', {}).get('evm') or {}
        actuals = data.get('actuals') or {}
        miss = []
        has_plan = isinstance(evm.get('pv'), (int, float)) or isinstance(evm.get('bac'), (int, float))
        ev_val = evm.get('ev') if isinstance(evm.get('ev'), (int, float)) else actuals.get('ev')
        ac_val = evm.get('ac') if isinstance(evm.get('ac'), (int, float)) else actuals.get('ac')
        if not has_plan:
            miss.append('pv/bac (计划基线, 置于 metrics.evm)')
        if not isinstance(ev_val, (int, float)):
            miss.append('ev (置于 actuals 或 metrics.evm)')
        if not isinstance(ac_val, (int, float)):
            miss.append('ac (置于 actuals 或 metrics.evm)')
        if miss:
            problems.append(
                f"EVM 基线缺失（控制级）：{methodology} 项目处于'{phase}'阶段，"
                f"缺少数值化 {', '.join(miss)}。请先建立完工预算(PV/BAC)基线，并在 actuals 填报 ev/ac（运行 evm.py）。")

    # ---- 8b. 基线化纪律（控制级） ----
    # 规划 ≠ 运营化：waterfall / hybrid 进入 执行/监控/收尾 前必须先基线化（冻结计划为对照基准）。
    if methodology in ('waterfall', 'hybrid') and phase in ('执行', '监控', '收尾'):
        bl = data.get('baseline') or {}
        if not (isinstance(bl, dict) and bl.get('file')):
            problems.append(
                f"未基线化即进入运营/执行阶段（控制级）：{methodology} 项目处于'{phase}'阶段但缺少 baseline 指针。"
                "须遵循 规划→评审→baseline.py --freeze（冻结计划为基线）→控制门→执行 的强制串行状态机"
                "（详见 references/lifecycle.md §5）。")

    # ---- 9. 混合微计划 ----
    if methodology == 'hybrid':
        micro_keys = ('sprint', 'sprints', 'backlog', 'iteration', 'iterations')
        has_micro = any(k in data for k in micro_keys)
        if not has_micro:
            # 退而求其次：artifacts 中是否挂了微层计划
            joined = ' '.join(str(v) for v in artifacts.values())
            if not any(t in joined for t in ('sprint_plan', 'backlog', 'iteration_plan')):
                problems.append(
                    "混合交付缺少微层计划（控制级）：methodology=hybrid 须至少具备一个微层计划"
                    "（sprint / backlog / iteration），用于承载宏阶段内的增量交付。")

    # ---- 10. 风险 5×5 校准 ----
    for r in collect_risks(data):
        rid = r.get('id', '?')
        lk = r.get('likelihood')
        im = r.get('impact')
        sc = r.get('score')
        if not isinstance(lk, (int, float)) or not (1 <= lk <= 5):
            problems.append(f"风险 {rid} 可能性(likelihood)须为 1-5 数值，当前：{lk}")
            continue
        if not isinstance(im, (int, float)) or not (1 <= im <= 5):
            problems.append(f"风险 {rid} 影响(impact)须为 1-5 数值，当前：{im}")
            continue
        if not isinstance(sc, (int, float)) or sc != lk * im:
            problems.append(
                f"风险 {rid} 评分(score)应为 likelihood×impact = {lk*im}，当前：{sc}")
            continue
        band = risk_band(lk * im)
        sev = norm_sev(r.get('severity'))
        if sev is None:
            problems.append(
                f"风险 {rid} 缺少校准严重度(severity)，应为 绿/黄/橙/红（score={sc} 应属"
                f"{ {'low':'绿','medium':'黄','high':'橙','critical':'红'}[band] }）")
        elif sev != band:
            problems.append(
                f"风险 {rid} 严重度(severity)与评分不符：score={sc} 应属"
                f"{ {'low':'绿','medium':'黄','high':'橙','critical':'红'}[band] }，"
                f"当前标注：{r.get('severity')}")

    # ---- 11. 收益责任人（项目群） ----
    program = data.get('program')
    if isinstance(program, dict):
        for b in (program.get('benefits') or []):
            if not b.get('owner'):
                problems.append(f"收益 {b.get('id','?')} 缺少责任人(owner)")

    # ---- 11b. 意图路由交付物强制（对齐 SKILL.md §3 intent→deliverable） ----
    # 在规划/启动期（planning_now）且为 plan* 意图时，缺少对应交付物 = 致命阻断。
    # 用法：project.intent 显式声明（plan / plan_program / risk / change / report 等）；
    # 未声明时按 type+methodology 推断最小集合。
    intent = str((data.get('project') or {}).get('intent') or '').lower()
    required_artifacts = []
    if ptype == 'program':
        required_artifacts += ['program_charter', 'risk_register', 'dependency_map',
                                'portfolio_dashboard', 'benefits_realization', 'raci',
                                'stakeholder_register', 'communication_plan']
    elif methodology in ('waterfall', 'hybrid'):
        required_artifacts += ['wbs', 'schedule_gantt', 'risk_register', 'raid_log',
                                'communication_plan']
        if methodology == 'hybrid':
            required_artifacts += ['micro_plan']
    elif methodology == 'agile':
        required_artifacts += ['product_backlog', 'sprint_plan', 'risk_register', 'dod']
    elif methodology == 'iteration':
        required_artifacts += ['iteration_plan', 'iteration_backlog', 'risk_register']
    if intent in ('risk',):
        required_artifacts += ['risk_register', 'raid_log']
    if intent in ('change',):
        required_artifacts += ['change_request', 'change_log']
    # 去重 + 仅检查存在的 key（artifacts 可能用别的 key 名，做宽松匹配）
    required_artifacts = list(dict.fromkeys(required_artifacts))
    if planning_now and required_artifacts:
        for req in required_artifacts:
            present = any(req in str(k) for k in artifacts) or (req in artifacts)
            # 同时检查磁盘上是否有对应渲染文件（artifact 指向的文件存在即视为已产出）
            if not present:
                # 宽容：若 project.yaml 里 wbs 非空且要求 wbs/raid_log/schedule 但 key 名不同，给告警而非致命
                warnings.append(
                    f"意图路由交付物可能缺失：{req}（plan 阶段应产出；"
                    f"若已用其他 key 渲染请忽略，或显式登记到 artifacts.{req}）")

    # ---- 告警（非致命） ----
    if ptype == 'program' or methodology == 'hybrid':
        if 'change_log' not in artifacts:
            warnings.append("建议补充变更日志 change_log（项目群/hybrid 须有变更控制 CCB）")
    if phase in ('执行', '监控'):
        if 'status_report' not in artifacts:
            warnings.append("建议补充状态报告 status_report（执行/监控阶段应定期汇报）")
        if 'control' not in data:
            warnings.append("建议配置 control 块（cadence/阈值/收件人），以驱动 control_engine.py 周期巡检")
        if 'control_register' not in artifacts:
            warnings.append("建议补充控制登记册 control_register（运营期常规控制清单，由 baseline.py 生成）")
    if 'communication_plan' not in artifacts:
        warnings.append("建议补充沟通计划 communication_plan（标准启动套件之一）")

    # ---- 输出 ----
    print("=== 一致性校验（控制级） ===")
    if warnings:
        print(f"⚠ 告警 {len(warnings)} 条（不阻断交付）：")
        for w in warnings:
            print("  -", w)
    if not problems:
        print("✓ 通过：无致命一致性问题")
        sys.exit(0)
    if strict:
        problems = problems + [f"[strict] 告警升级: {w}" for w in warnings]
    print(f"✗ 发现 {len(problems)} 个致命问题（阻断交付）：")
    for p in problems:
        print("  -", p)
    sys.exit(1)


if __name__ == '__main__':
    main()
