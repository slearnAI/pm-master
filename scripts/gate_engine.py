#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · 阶段门引擎（Phase Gate Engine）
============================================
读取 project.yaml（单一事实源），按"阶段（phase）↔ 状态机（lifecycle_state）"模型，
校验**进入目标阶段的 Entry 准则**；审批通过后翻转 project.phase 与 lifecycle_state，
并把阶段门记录写入 governance.stage_gates，同时产出一份阶段门评审报告（Markdown）。

硬门复用既有引擎，避免逻辑重复：
  - 进 执行/监控（operational）前：consistency_check.py 必须 exit 0（计划基线无致命问题）
  - 进 收尾（closed）前：control_engine.py 必须 exit 0（无 RED 升级）

阶段门（对齐 references/phases/* 与 lifecycle.md §5/§6）：
  G0→1  启动→规划        （轻门，仅置 phase）
  G1→2  规划→执行        （控制门：强制串行，须 baseline + 一致性 exit 0，sponsor 审批）
  G2→3  执行→监控        （软门：operational 内并发，PM 标记监控节奏）
  G3→4  监控→收尾        （收尾门：须 control_engine exit 0 + 验收/复盘/收益闭环，sponsor 审批）

用法：
  # 评估能否进入"执行"阶段（dry-run，不改动状态）
  python3 gate_engine.py --project /workspace/<slug>/project.yaml --to 执行

  # 评估能否进入"收尾"并列出缺口
  python3 gate_engine.py --project /workspace/<slug>/project.yaml --to 收尾

  # 审批通过：翻转状态 + 记录阶段门 + 产出报告
  python3 gate_engine.py --project /workspace/<slug>/project.yaml --to 执行 --approve "张三(sponsor)"

  # 仅查看当前状态与可走的门
  python3 gate_engine.py --project /workspace/<slug>/project.yaml --status
"""
import os
import sys
import argparse
import subprocess
import datetime

try:
    import yaml
except ImportError:
    yaml = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------- 阶段 / 状态机模型 ----------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

PROJECT_PHASES = ['启动', '规划', '执行', '监控', '收尾']
PROGRAM_PHASES = ['组合定义', '组合交付', '组合收尾']

# 双语阶段别名：英文/小写 token 归一化为内部中文键（让 EN 包可用 --to execution 等）。
PHASE_ALIASES = {
    'initiation': '启动', 'initiate': '启动', 'init': '启动',
    'planning': '规划', 'plan': '规划',
    'execution': '执行', 'execute': '执行', 'exec': '执行',
    'monitoring': '监控', 'monitor': '监控', 'control': '监控',
    'closeout': '收尾', 'closure': '收尾', 'close': '收尾',
    'program-definition': '组合定义', 'program_definition': '组合定义', 'portfolio-definition': '组合定义',
    'program-delivery': '组合交付', 'program_delivery': '组合交付', 'portfolio-delivery': '组合交付',
    'program-closeout': '组合收尾', 'program_closeout': '组合收尾', 'portfolio-closeout': '组合收尾',
}


def normalize_phase(token):
    """把 --to 的英文/小写别名归一化为内部中文阶段键；中文原样返回。"""
    if not token:
        return token
    t = token.strip()
    return PHASE_ALIASES.get(t.lower(), t)

# 目标阶段 -> 门定义
#   requires_state: 进入此门前的 lifecycle_state 取值
#   set_state:      审批通过后的 lifecycle_state
#   hard:           硬门（True=必须自动化校验通过，否则阻断；False=软门，仅置 phase）
#   approver:       审批角色
#   gate:           门名
GATES = {
    '启动':   dict(requires_state={'planning'}, set_state='planning', hard=False, approver='PM',
                  gate='G0 启动'),
    '规划':   dict(requires_state={'planning', 'review'}, set_state='planning', hard=False, approver='PM',
                  gate='G0→1 启动→规划'),
    '执行':   dict(requires_state={'planning', 'review', 'baselined'}, set_state='operational', hard=True, approver='sponsor',
                  gate='G1→2 规划→执行（控制门）'),
    '监控':   dict(requires_state={'operational'}, set_state='operational', hard=False, approver='PM',
                  gate='G2→3 执行→监控（软门）'),
    '收尾':   dict(requires_state={'operational'}, set_state='closed', hard=True, approver='sponsor',
                  gate='G3→4 监控→收尾（收尾门）'),
    # 项目群同义目标
    '组合交付': dict(requires_state={'planning', 'review', 'baselined'}, set_state='operational', hard=True, approver='sponsor',
                  gate='G1→2 组合定义→组合交付（控制门）'),
    '组合收尾': dict(requires_state={'operational'}, set_state='closed', hard=True, approver='sponsor',
                  gate='G3→4 组合交付→组合收尾（收尾门）'),
}


def load_config():
    """读取安装期 config.yaml（stage_gates 块决定硬/软门）。"""
    for cand in (os.path.join(SCRIPT_DIR, '..', 'config.yaml'),
                 os.path.join(SCRIPT_DIR, 'config.yaml')):
        if os.path.exists(cand):
            try:
                with open(cand, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                return {}
    return {}


def apply_stage_gate_config():
    """用 config.stage_gates 重写 GATES 的 hard 标志，使配置旋钮真正生效。
    硬门串形如 'G1→2' / 'G3→4'，软门 'G0→1' / 'G2→3'。"""
    cfg = load_config()
    sg = cfg.get('stage_gates') or {}
    hard = set(sg.get('hard_gates') or [])
    soft = set(sg.get('soft_gates') or [])
    if not hard and not soft:
        return
    for g in GATES.values():
        gate_name = g['gate']
        # 匹配形如 'G1→2 ...' 的前缀
        prefix = gate_name.split()[0] if gate_name else ''
        if prefix in hard:
            g['hard'] = True
        elif prefix in soft:
            g['hard'] = False


def load(path):
    if yaml is None:
        raise RuntimeError("需要 PyYAML，请先 pip install pyyaml")
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def has(path):
    return os.path.exists(path)


def run_script(name, project):
    """运行同目录下的其他引擎，返回 (returncode, stdout)。"""
    cmd = [sys.executable, os.path.join(SCRIPT_DIR, name), '--project', project]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return p.returncode, p.stdout + p.stderr
    except Exception as e:  # noqa
        return 2, f"无法运行 {name}: {e}"


# ---------- 单条准则检查 ----------
def chk_consistency(project):
    rc, _ = run_script('consistency_check.py', project)
    return rc == 0, 'consistency_check.py exit 0' if rc == 0 else 'consistency_check.py 发现致命问题（exit≠0）'


def chk_baseline(data):
    bl = (data.get('baseline') or {}) if isinstance(data.get('baseline'), dict) else {}
    ok = bool(bl.get('file'))
    return ok, ('baseline 指针存在（已冻结基线）' if ok
                else '缺少 baseline 指针（须先 baseline.py --freeze 冻结计划为基线）')


def chk_control(data, project):
    rc, _ = run_script('control_engine.py', project)
    return rc == 0, 'control_engine.py exit 0（无 RED 升级）' if rc == 0 else 'control_engine.py 存在 RED 升级（exit≠0）'


def chk_artifact(data, key):
    arts = data.get('artifacts') or {}
    return key in arts, f'artifacts.{key} 已登记' if key in arts else f'缺少 artifacts.{key}（交付物未产出/未登记）'


def chk_artifact_fresh(data, project):
    """OAG：交付物是否与事实源一致（内容哈希漂移检测）。违规即视为护栏 breach。"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from artifact_guard import check_artifacts
        ok, viol, _ = check_artifacts(project, data)
        if ok:
            return True, '交付物均与事实源一致（OAG 通过）'
        return False, f'存在 {len(viol)} 项交付物未随事实源刷新：{"；".join(viol[:2])}'
    except Exception as e:
        return True, f'OAG 检查跳过（{e}）'


def chk_program_benefits(data):
    prog = data.get('program')
    if not isinstance(prog, dict):
        return True, '非项目群，无需收益核实'
    benefits = prog.get('benefits') or []
    if not benefits:
        return False, '项目群未定义 benefits（须先 benefits_realization）'
    realized = {'realized', '实现', 'closed', '关闭', 'done', '完成'}
    open_b = [b.get('id', '?') for b in benefits
              if str(b.get('status', '')).strip().lower() not in realized]
    ok = not open_b
    return ok, ('全部收益已实现/闭环' if ok else f'存在未实现收益：{", ".join(open_b)}')


# ---------- 入口准则（按目标阶段） ----------
def entry_criteria(target, data, project):
    """返回 [(name, ok, detail), ...]。"""
    methodology = ((data.get('project', {}) or {}).get('methodology') or '').lower()
    crit = []
    if target in ('执行', '组合交付'):
        crit.append(('计划基线一致性', *chk_consistency(project)))
        # 基线化仅对 waterfall / hybrid 强制（对齐 lifecycle.md §5 与 consistency_check）
        if methodology in ('waterfall', 'hybrid'):
            crit.append(('已冻结基线', *chk_baseline(data)))
        else:
            crit.append(('基线（敏捷/迭代免基线，以 backlog/sprint 为基准）', True,
                         'methodology=%s，按 agile/iteration 约定免强制基线' % methodology))
    elif target in ('收尾', '组合收尾'):
        crit.append(('运营控制无 RED', *chk_control(data, project)))
        crit.append(('验收交付物', *chk_artifact(data, 'closure_report')))
        crit.append(('经验教训沉淀', *chk_artifact(data, 'lessons_learned')))
        crit.append(('交付物与事实源一致 (OAG)', *chk_artifact_fresh(data, project)))
        if target == '组合收尾':
            crit.append(('收益核实闭环', *chk_program_benefits(data)))
    # 软门（监控/规划/启动）无硬准则
    return crit


def phase_label_for_state(data, state, target):
    """审批通过后应写入的 project.phase 标签。
    目标阶段本身即合法 phase 标签时优先用目标；否则按状态回退映射。"""
    if target in PROJECT_PHASES:
        return target
    if target in PROGRAM_PHASES:
        return target
    ptype = (data.get('project', {}) or {}).get('type', 'project')
    mapping = {
        'operational': '组合交付' if ptype == 'program' else '执行',
        'closed': '组合收尾' if ptype == 'program' else '收尾',
        'planning': '规划',
    }
    return mapping.get(state, target)


def current_state(data):
    proj = data.get('project', {}) or {}
    return proj.get('lifecycle_state', 'planning'), proj.get('phase', '启动')


def main():
    ap = argparse.ArgumentParser(description="PM Master 阶段门引擎（Phase Gate Engine）")
    ap.add_argument('--project', required=True)
    ap.add_argument('--to', help='目标阶段：启动/规划/执行/监控/收尾（项目群：组合定义/组合交付/组合收尾）；亦受英文别名 execution/closeout 等')
    ap.add_argument('--approve', metavar='APPROVER', default=None,
                    help='审批人（如 "张三(sponsor)"）。给定则审批通过并翻转状态；否则仅做评估（dry-run）')
    ap.add_argument('--status', action='store_true', help='仅查看当前状态与可走的门')
    a = ap.parse_args()

    if not has(a.project):
        print(f"✗ 未找到 project.yaml: {a.project}", file=sys.stderr)
        sys.exit(2)
    data = load(a.project)
    root = os.path.dirname(os.path.abspath(a.project))

    # OAG：运营期交付物护栏（信息性提示，每次阶段门评估都可见）
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from artifact_guard import check_artifacts as _chk
        _ok, _viol, _ = _chk(a.project, data)
        if _ok:
            print("ℹ 交付物护栏 (OAG)：全部交付物与事实源一致")
        else:
            print(f"⚠ 交付物护栏 (OAG)：{len(_viol)} 项违规（交付前须刷新：{'; '.join(_viol[:2])}）")
    except Exception:
        pass
    state, phase = current_state(data)

    # ---- 状态查看 ----
    if a.status or not a.to:
        print("=== 阶段门状态 ===")
        print(f"当前 lifecycle_state: {state}")
        print(f"当前 project.phase:   {phase}")
        print("可走的门（按目标阶段）：")
        for t, g in GATES.items():
            ok_states = '/'.join(sorted(g['requires_state']))
            print(f"  → {t:6s} | 门 {g['gate']:28s} | 前置状态 {ok_states} | {'硬门' if g['hard'] else '软门'} | 审批 {g['approver']}")
        if a.status:
            return
        if not a.to:
            return

    target = normalize_phase(a.to)
    if target not in GATES:
        print(f"✗ 未知目标阶段: {a.to}（可选：{', '.join(GATES.keys())}；英文别名如 execution/closeout）", file=sys.stderr)
        sys.exit(2)

    apply_stage_gate_config()
    g = GATES[target]
    # 前置状态检查
    if state not in g['requires_state']:
        print(f"✗ 阶段门被拒：当前 lifecycle_state={state}，进入「{target}」要求处于 {sorted(g['requires_state'])}")
        sys.exit(1)

    # 入口准则
    crit = entry_criteria(target, data, a.project)
    print(f"=== 阶段门评估：{g['gate']} → 「{target}」 ===")
    passed = True
    for name, ok, detail in crit:
        mark = '✓' if ok else '✗'
        if not ok:
            passed = False
        print(f"  {mark} {name}：{detail}")

    if not passed:
        print("\n✗ 入口准则未满足，禁止进入该阶段。请先修复上述 ✗ 项（硬门不可跳过，详见 lifecycle.md §5）。")
        sys.exit(1)

    # dry-run：仅评估
    if not a.approve:
        print("\n✓ 入口准则全部满足，可进入该阶段。请由"
              f" {g['approver']} 审批：")
        print(f"    python3 gate_engine.py --project {a.project} --to {target} --approve \"<审批人>\"")
        sys.exit(0)

    # ---- 审批通过：翻转状态 + 记录 + 报告 ----
    approver = a.approve
    new_state = g['set_state']
    new_phase = phase_label_for_state(data, new_state, target)
    today = datetime.date.today().isoformat()

    # 更新 project
    proj = data.setdefault('project', {})
    prev_phase = proj.get('phase')
    proj['lifecycle_state'] = new_state
    proj['phase'] = new_phase
    if new_state == 'operational' and not proj.get('baselined_on'):
        proj['baselined_on'] = today

    # 阶段门记录
    gov = data.setdefault('governance', {})
    gates = gov.setdefault('stage_gates', [])
    record = {
        'gate': g['gate'],
        'from_phase': prev_phase,
        'to_phase': new_phase,
        'on': today,
        'by': approver,
        'decision': '通过',
        'lifecycle_before': state,
        'lifecycle_after': new_state,
        'criteria': [{'name': n, 'pass': ok, 'detail': d} for n, ok, d in crit],
    }
    gates.append(record)

    # 写回 project.yaml
    save(a.project, data)

    # 阶段门评审报告（Markdown）
    report_dir = os.path.join(root, 'docs', 'gate_reports')
    os.makedirs(report_dir, exist_ok=True)
    slug = (proj.get('id') or 'project')
    report_path = os.path.join(report_dir, f"gate_{new_phase}_{today}.md")
    lines = [
        f"# 阶段门评审报告 · {proj.get('name', slug)}",
        "",
        f"- **阶段门**：{g['gate']}",
        f"- **从 → 到**：{prev_phase} → {new_phase}",
        f"- **状态机**：{state} → {new_state}",
        f"- **审批人**：{approver}",
        f"- **日期**：{today}",
        f"- **决策**：✅ 通过",
        "",
        "## 入口准则核验",
        "",
        "| 准则 | 结果 | 说明 |",
        "|------|------|------|",
    ]
    for n, ok, d in crit:
        lines.append(f"| {n} | {'通过' if ok else '未过'} | {d} |")
    lines += ["", "_由 PM Master · gate_engine.py 生成_", ""]
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    # 登记到 artifacts
    arts = data.get('artifacts') or {}
    arts[f'gate_{new_phase}'] = os.path.relpath(report_path, root)
    # 重新写回 artifacts（save 已经写全量，这里补登记）
    data['artifacts'] = arts
    save(a.project, data)

    print(f"\n✅ 阶段门审批通过：{prev_phase} → {new_phase}（{state} → {new_state}）")
    print(f"   审批人：{approver}")
    print(f"   阶段门记录已写入 governance.stage_gates（共 {len(gates)} 条）")
    print(f"   评审报告：{arts[f'gate_{new_phase}']}")
    sys.exit(0)


if __name__ == '__main__':
    main()
