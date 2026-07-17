#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · gate_engine.py 单测套件（standalone，无需 pytest）
============================================================
两层覆盖：
  A. 纯函数/逻辑层：直接 import gate_engine，验证阶段↔状态路由、入口准则分支、
     chk_* 助手、GATES 表不变量（快速、确定、无子进程）。
  B. CLI 集成层：以子进程真实运行 gate_engine.py（及其依赖的 consistency_check.py /
     control_engine.py），覆盖 4 种方法论 × 软/硬门、被拒、dry-run 不落盘、--status。

运行：
  python3 scripts/test_gate_engine.py
退出码：0 = 全过；1 = 有失败（可挂 CI 门禁）。
"""
import os
import sys
import shutil
import subprocess
import tempfile
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gate_engine as G  # noqa

PASS = 0
FAIL = 0


def ok(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  \033[32m✓\033[0m {name}")
    else:
        FAIL += 1
        print(f"  \033[31m✗\033[0m {name}  {detail}")


def run_gate(project, to=None, approve=None, status=False):
    cmd = [sys.executable, os.path.join(HERE, 'gate_engine.py'), '--project', project]
    if status:
        cmd.append('--status')
    if to:
        cmd += ['--to', to]
    if approve:
        cmd += ['--approve', approve]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def write_yaml(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        import yaml
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


# ------------------------------------------------------------------ #
# 夹具构造
# ------------------------------------------------------------------ #
def make_project(slug, data, extra=None):
    root = os.path.join(_ROOT, slug)
    os.makedirs(root, exist_ok=True)
    proj = os.path.join(root, 'project.yaml')
    write_yaml(proj, data)
    for rel, content in (extra or {}).items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(content)
    return proj


_BASELINE_WF = {
    'wbs': [
        {'id': 'W1', 'name': '需求', 'role': 'ba', 'estimate': 5, 'start': '2026-01-01', 'end': '2026-01-10'},
        {'id': 'W2', 'name': '开发', 'estimate': 10, 'start': '2026-01-11', 'end': '2026-02-10', 'dependsOn': 'W1'},
    ],
    'metrics': {'evm': {'pv': 100}},
    'risks': [
        {'id': 'R1', 'likelihood': 2, 'impact': 2, 'score': 4, 'severity': '绿',
         'owner': '王五', 'mitigation': '提前评审'},
    ],
}

_WBS_WF = [
    {'id': 'W1', 'name': '需求', 'role': 'ba', 'estimate': 5, 'start': '2026-01-01', 'end': '2026-01-10'},
    {'id': 'W2', 'name': '开发', 'estimate': 10, 'start': '2026-01-11', 'end': '2026-02-10', 'dependsOn': 'W1'},
]


def fixture_waterfall_planning():
    """瀑布 planning 夹具：consistency 在 规划 态 exit 0，可用于 G1→2 硬门。"""
    data = {
        'project': {
            'id': 't-wf', 'name': '测试-瀑布', 'type': 'project', 'methodology': 'waterfall',
            'lifecycle_state': 'planning', 'phase': '规划', 'pm': '张三', 'sponsor': '李四',
        },
        'wbs': _WBS_WF,
        'risks': [
            {'id': 'R1', 'likelihood': 2, 'impact': 2, 'score': 4, 'severity': '绿',
             'owner': '王五', 'mitigation': '提前评审'},
        ],
        'metrics': {'evm': {'pv': 100}},
        'baseline': {'file': 'baselines/2026-01-01.yaml', 'on': '2026-01-01'},
        'artifacts': {},
    }
    return make_project('wf_plan', data,
                         extra={'baselines/2026-01-01.yaml': _dump(_BASELINE_WF)})


def fixture_waterfall_operational():
    """瀑布 operational 夹具：consistency 在 执行 态 exit 0 且 control_engine exit 0，用于 G3→4 硬门。"""
    data = {
        'project': {
            'id': 't-wf2', 'name': '测试-瀑布-运营', 'type': 'project', 'methodology': 'waterfall',
            'lifecycle_state': 'operational', 'phase': '执行', 'pm': '张三', 'sponsor': '李四',
        },
        'wbs': _WBS_WF,
        'risks': [
            {'id': 'R1', 'likelihood': 2, 'impact': 2, 'score': 4, 'severity': '绿',
             'owner': '王五', 'mitigation': '提前评审'},
        ],
        'metrics': {'evm': {'pv': 100, 'ev': 77, 'ac': 55}},
        'baseline': {'file': 'baselines/2026-01-01.yaml', 'on': '2026-01-01'},
        'actuals': {'as_of': '2026-02-01', 'ev': 77, 'ac': 55, 'wbs_progress': {'W1': 100, 'W2': 40}},
        'artifacts': {
            'closure_report': 'artifacts/closure_report.md',
            'lessons_learned': 'artifacts/lessons_learned.md',
        },
    }
    return make_project('wf_op', data, extra={
        'baselines/2026-01-01.yaml': _dump(_BASELINE_WF),
        'artifacts/closure_report.md': '# 验收交付物\n',
        'artifacts/lessons_learned.md': '# 经验教训\n',
    })


def fixture_agile_planning():
    data = {
        'project': {
            'id': 't-ag', 'name': '测试-敏捷', 'type': 'project', 'methodology': 'agile',
            'lifecycle_state': 'planning', 'phase': '规划', 'pm': '张三', 'sponsor': '李四',
        },
        'backlog': [
            {'id': 'B1', 'name': '登录', 'estimate': 3},
            {'id': 'B2', 'name': '列表', 'estimate': 5},
        ],
        'sprints': [
            {'id': 'S1', 'name': '冲刺1', 'tasks': [{'id': 'T1', 'name': '登录', 'estimate': 3}]},
        ],
        'risks': [],
        'artifacts': {},
    }
    return make_project('ag_plan', data)


def fixture_program_operational():
    data = {
        'project': {
            'id': 't-pg', 'name': '测试-项目群', 'type': 'program', 'methodology': 'waterfall',
            'lifecycle_state': 'operational', 'phase': '组合交付', 'pm': '张三', 'sponsor': '李四',
        },
        'wbs': _WBS_WF,
        'risks': [
            {'id': 'R1', 'likelihood': 2, 'impact': 2, 'score': 4, 'severity': '绿',
             'owner': '王五', 'mitigation': '提前评审'},
        ],
        'metrics': {'evm': {'pv': 100, 'ev': 77, 'ac': 55}},
        'baseline': {'file': 'baselines/2026-01-01.yaml', 'on': '2026-01-01'},
        'actuals': {'as_of': '2026-02-01', 'ev': 77, 'ac': 55, 'wbs_progress': {'W1': 100, 'W2': 40}},
        'program': {'benefits': [{'id': 'BN1', 'status': 'realized', 'owner': '赵六'}]},
        'artifacts': {
            'closure_report': 'artifacts/closure_report.md',
            'lessons_learned': 'artifacts/lessons_learned.md',
        },
    }
    return make_project('pg_op', data, extra={
        'baselines/2026-01-01.yaml': _dump(_BASELINE_WF),
        'artifacts/closure_report.md': '# 验收交付物\n',
        'artifacts/lessons_learned.md': '# 经验教训\n',
    })


def _dump(d):
    import yaml
    return yaml.safe_dump(d, allow_unicode=True, sort_keys=False)


# ------------------------------------------------------------------ #
# A. 纯函数 / 逻辑层
# ------------------------------------------------------------------ #
def test_logic_layer():
    print("\n[A] 纯函数 / 逻辑层")
    # GATES 表不变量
    for t, g in G.GATES.items():
        ok(f"GATES[{t}] 含必需键",
           all(k in g for k in ('requires_state', 'set_state', 'hard', 'approver', 'gate')),
           str(g))
    # 硬门必须是 执行/收尾/组合交付/组合收尾
    hard_targets = [t for t, g in G.GATES.items() if g['hard']]
    ok("硬门仅含控制门/收尾门",
       set(hard_targets) == {'执行', '收尾', '组合交付', '组合收尾'}, str(hard_targets))
    # 软门不得阻断（entry_criteria 对 启动/规划/监控 返回空准则）
    for soft in ('启动', '规划', '监控'):
        crit = G.entry_criteria(soft, {'project': {'methodology': 'waterfall'}}, 'x')
        ok(f"软门 {soft} 无硬准则", crit == [], str(crit))
    # phase_label_for_state：目标即合法 phase 时优先用目标（监控修复点）
    data_op = {'project': {'type': 'project'}}
    ok("执行→监控 写入 phase=监控（修复点）",
       G.phase_label_for_state(data_op, 'operational', '监控') == '监控')
    ok("规划→执行 写入 phase=执行",
       G.phase_label_for_state(data_op, 'operational', '执行') == '执行')
    # 项目群同义
    data_pg = {'project': {'type': 'program'}}
    ok("项目群 组合收尾→组合收尾",
       G.phase_label_for_state(data_pg, 'closed', '组合收尾') == '组合收尾')
    # 回退映射（target 非法时按 state 映射）
    ok("回退：operational→执行", G.phase_label_for_state(data_op, 'operational', 'ZZ') == '执行')
    ok("回退：closed→收尾", G.phase_label_for_state(data_op, 'closed', 'ZZ') == '收尾')
    ok("回退：planning→规划", G.phase_label_for_state(data_op, 'planning', 'ZZ') == '规划')
    # chk_* 助手
    ok("chk_baseline 有指针=True", G.chk_baseline({'baseline': {'file': 'x.yaml'}})[0] is True)
    ok("chk_baseline 无指针=False", G.chk_baseline({'baseline': {}})[0] is False)
    ok("chk_artifact 存在=True", G.chk_artifact({'artifacts': {'closure_report': 'p'}}, 'closure_report')[0] is True)
    ok("chk_artifact 缺失=False", G.chk_artifact({'artifacts': {}}, 'closure_report')[0] is False)
    ok("chk_program_benefits 非项目群=True", G.chk_program_benefits({'program': None})[0] is True)
    ok("chk_program_benefits 全部实现=True",
       G.chk_program_benefits({'program': {'benefits': [{'id': 'B1', 'status': 'realized'}]}})[0] is True)
    ok("chk_program_benefits 有未实现=False",
       G.chk_program_benefits({'program': {'benefits': [{'id': 'B1', 'status': 'open'}]}})[0] is False)
    # entry_criteria 分支：收尾缺交付物 → passed=False
    crit = G.entry_criteria('收尾', {'project': {'methodology': 'waterfall'}, 'artifacts': {}}, 'x')
    ok("收尾 缺 closure/lessons → 有未过准则", any(not ok_ for _, ok_, _ in crit), str(crit))
    # entry_criteria 分支：敏捷进执行免基线
    crit = G.entry_criteria('执行', {'project': {'methodology': 'agile'}}, 'x')
    names = [n for n, _, _ in crit]
    ok("敏捷进执行 不含『已冻结基线』准则", '已冻结基线' not in names, str(names))
    # 瀑布进执行 含『已冻结基线』准则
    crit = G.entry_criteria('执行', {'project': {'methodology': 'waterfall'}}, 'x')
    names = [n for n, _, _ in crit]
    ok("瀑布进执行 含『已冻结基线』准则", '已冻结基线' in names, str(names))


# ------------------------------------------------------------------ #
# B. CLI 集成层
# ------------------------------------------------------------------ #
def test_cli_layer():
    print("\n[B] CLI 集成层")

    # B1 软门 G0→1 启动→规划
    p = fixture_waterfall_planning()
    rc, out = run_gate(p, to='规划', approve='张三(PM)')
    ok("软门 规划 approve 成功(rc=0)", rc == 0, out)
    d = _load(p)
    ok("软门 规划 后 phase=规划", d['project']['phase'] == '规划', d['project']['phase'])
    ok("软门 规划 后 state 仍为 planning", d['project']['lifecycle_state'] == 'planning')
    ok("软门 规划 写入 stage_gates", len(d.get('governance', {}).get('stage_gates', [])) == 1)

    # B2 软门 G2→3 执行→监控（修复点：不能写成 执行）
    p = fixture_waterfall_operational()
    rc, out = run_gate(p, to='监控', approve='张三(PM)')
    ok("软门 监控 approve 成功(rc=0)", rc == 0, out)
    d = _load(p)
    ok("软门 监控 后 phase=监控（修复点）", d['project']['phase'] == '监控', d['project']['phase'])
    ok("软门 监控 后 state 仍为 operational", d['project']['lifecycle_state'] == 'operational')

    # B3 硬门 G1→2 瀑布 规划→执行（有基线+一致性）
    p = fixture_waterfall_planning()
    rc, out = run_gate(p, to='执行', approve='李四(sponsor)')
    ok("硬门 执行(瀑布,基线齐) 通过(rc=0)", rc == 0, out)
    d = _load(p)
    ok("硬门 执行 后 phase=执行", d['project']['phase'] == '执行', d['project']['phase'])
    ok("硬门 执行 后 state=operational", d['project']['lifecycle_state'] == 'operational')
    ok("硬门 执行 写入 stage_gates", len(d.get('governance', {}).get('stage_gates', [])) == 1)
    ok("硬门 执行 产出报告 docs/gate_reports", os.path.exists(
        os.path.join(os.path.dirname(p), 'docs', 'gate_reports')))

    # B4 硬门 G1→2 瀑布 缺基线 → 阻断(rc=1)
    p = fixture_waterfall_planning()
    # 移除 baseline 指针
    d = _load(p)
    d.pop('baseline', None)
    write_yaml(p, d)
    rc, out = run_gate(p, to='执行')
    ok("硬门 执行(瀑布,缺基线) 阻断(rc=1)", rc == 1, out)
    ok("硬门 执行 阻断信息含『基线』", '基线' in out or 'baseline' in out.lower(), out)
    d2 = _load(p)
    ok("硬门 执行 阻断后 phase 未变", d2['project']['phase'] == '规划', d2['project']['phase'])

    # B5 硬门 G1→2 敏捷 免基线 → 通过(rc=0)
    p = fixture_agile_planning()
    rc, out = run_gate(p, to='执行', approve='李四(sponsor)')
    ok("硬门 执行(敏捷,免基线) 通过(rc=0)", rc == 0, out)
    d = _load(p)
    ok("硬门 执行(敏捷) 后 phase=执行", d['project']['phase'] == '执行', d['project']['phase'])
    ok("硬门 执行(敏捷) state=operational", d['project']['lifecycle_state'] == 'operational')

    # B6 硬门 G3→4 收尾（交付物齐+control exit 0）
    p = fixture_waterfall_operational()
    rc, out = run_gate(p, to='收尾', approve='李四(sponsor)')
    ok("硬门 收尾(齐) 通过(rc=0)", rc == 0, out)
    d = _load(p)
    ok("硬门 收尾 后 phase=收尾", d['project']['phase'] == '收尾', d['project']['phase'])
    ok("硬门 收尾 后 state=closed", d['project']['lifecycle_state'] == 'closed')

    # B7 硬门 G3→4 收尾 缺交付物 → 阻断(rc=1)
    p = fixture_waterfall_operational()
    d = _load(p)
    d['artifacts'].pop('closure_report', None)
    write_yaml(p, d)
    rc, out = run_gate(p, to='收尾')
    ok("硬门 收尾(缺验收) 阻断(rc=1)", rc == 1, out)
    ok("硬门 收尾 阻断信息含 closure", 'closure' in out, out)
    d2 = _load(p)
    ok("硬门 收尾 阻断后 state 未变", d2['project']['lifecycle_state'] == 'operational')

    # B8 项目群 组合收尾（收益齐）
    p = fixture_program_operational()
    rc, out = run_gate(p, to='组合收尾', approve='李四(sponsor)')
    ok("硬门 组合收尾(收益齐) 通过(rc=0)", rc == 0, out)
    d = _load(p)
    ok("硬门 组合收尾 后 phase=组合收尾", d['project']['phase'] == '组合收尾', d['project']['phase'])
    ok("硬门 组合收尾 后 state=closed", d['project']['lifecycle_state'] == 'closed')

    # B9 项目群 组合收尾 收益未实现 → 阻断
    p = fixture_program_operational()
    d = _load(p)
    d['program']['benefits'][0]['status'] = 'open'
    write_yaml(p, d)
    rc, out = run_gate(p, to='组合收尾')
    ok("硬门 组合收尾(收益未实现) 阻断(rc=1)", rc == 1, out)
    ok("硬门 组合收尾 阻断信息含『收益』", '收益' in out, out)

    # B10 前置状态不符 → 拒绝(rc=1)
    p = fixture_waterfall_operational()  # operational
    rc, out = run_gate(p, to='规划')       # 规划 requires planning/review/baselined
    ok("前置状态不符 拒绝(rc=1)", rc == 1, out)
    ok("拒绝信息含『阶段门被拒』", '阶段门被拒' in out, out)

    # B11 未知目标 → 退出(rc=2)
    p = fixture_waterfall_planning()
    rc, out = run_gate(p, to='不存在的阶段')
    ok("未知目标 退出(rc=2)", rc == 2, out)

    # B12 dry-run 不落盘（phase/state/stage_gates 不变）
    p = fixture_waterfall_planning()
    before = _load(p)
    rc, out = run_gate(p, to='执行')  # 无 --approve
    ok("dry-run 评估成功(rc=0)", rc == 0, out)
    after = _load(p)
    ok("dry-run 前 phase=规划", before['project']['phase'] == '规划')
    ok("dry-run 后 phase 仍=规划（未落盘）", after['project']['phase'] == '规划')
    ok("dry-run 未写 stage_gates",
       len(after.get('governance', {}).get('stage_gates', [])) == 0)

    # B13 --status 正常输出
    p = fixture_waterfall_planning()
    rc, out = run_gate(p, status=True)
    ok("--status 成功(rc=0)", rc == 0, out)
    ok("--status 含 可走的门", '可走的门' in out, out)
    ok("--status 含 硬门/软门 标注", '硬门' in out and '软门' in out, out)


def _load(path):
    import yaml
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


# ------------------------------------------------------------------ #
def main():
    global _ROOT
    _ROOT = tempfile.mkdtemp(prefix='pm_gate_test_')
    print(f"临时根：{_ROOT}")
    try:
        test_logic_layer()
        test_cli_layer()
    finally:
        shutil.rmtree(_ROOT, ignore_errors=True)
    print(f"\n==== 结果：通过 {PASS} / 失败 {FAIL} ====")
    sys.exit(1 if FAIL else 0)


if __name__ == '__main__':
    main()
