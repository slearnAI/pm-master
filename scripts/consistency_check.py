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
    - 领域活动 WBS 缺 role 标签（应调度对应专家产出，见 references/expert-roles.md）
    - WBS 估算超过叶子包颗粒度阈值（须由领域专家进一步拆解，防 SOW 级粗粒度）

用法：
  python3 consistency_check.py --project /workspace/<slug>/project.yaml
  python3 consistency_check.py --project ... --strict  # 把告警也升级为致命
"""
import os
import re
import sys
import argparse

try:
    import yaml
except ImportError:
    yaml = None


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
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) if yaml else eval(f.read())


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
                    help="将告警(warnings)也升级为致命问题")
    a = ap.parse_args()
    data = load(a.project)
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
        full = rel if os.path.isabs(rel) else os.path.join(root, rel)
        if not os.path.exists(full):
            problems.append(f"产物索引 {key} 指向的文件不存在: {rel}")

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

    # ---- 7b. 专家角色标注 + 颗粒度（默认告警；--strict 致命） ----
    # 领域活动必须由对应专家产出并拆到叶子包，否则 WBS 会停在 SOW 级粗粒度。
    ctrl_blk = data.get('control') or {}
    gran_thr = float(ctrl_blk.get('granularity_threshold') or 10)
    for w in wbs:
        if w.get('summary'):  # 汇总行（SOW/P0 父包）不检查角色/颗粒度，交由叶子包承担
            continue
        wid = w.get('id', '?')
        name = w.get('name') or ''
        role = infer_role(w, name)
        dom = w.get('domain')
        if is_domain_activity(role, name, dom) and not w.get('role'):
            warnings.append(
                f"WBS {wid}『{name}』为领域活动但缺少 role 标签"
                f"（应调度 {role or '对应领域专家'} 产出，见 references/expert-roles.md）")
        try:
            est_v = float(w.get('estimate'))
        except (TypeError, ValueError):
            est_v = 0.0
        if est_v > gran_thr:
            warnings.append(
                f"WBS {wid}『{name}』估算 {est_v:g} 人天超过叶子包阈值 {gran_thr:g}，"
                f"须调度领域专家进一步拆解（防止 SOW 级粗粒度 WBS 当交付）")

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
    if a.strict:
        problems = problems + [f"[strict] 告警升级: {w}" for w in warnings]
    print(f"✗ 发现 {len(problems)} 个致命问题（阻断交付）：")
    for p in problems:
        print("  -", p)
    sys.exit(1)


if __name__ == '__main__':
    main()
