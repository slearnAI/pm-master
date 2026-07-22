#!/usr/bin/env python3
"""rollup_subprojects.py — 跨子项目汇总（milestones/subprojects 分割架构）。

读取每个子项目的 project.yaml（位于 <program>/subprojects/<sowN>/project.yaml），
汇总里程碑状态、健康指标与 EAC/成本，生成项目群级视图。

用法:
  python3 rollup_subprojects.py --program <program_dir> [--json]
"""
import argparse
import os
import sys
import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def _status_from_control(ctrl):
    """从 control_engine 输出或 metrics 推断整体状态（GREEN/AMBER/RED）。"""
    if not isinstance(ctrl, dict):
        return 'UNKNOWN'
    for k in ('overall', 'status'):
        v = ctrl.get(k)
        if v in ('GREEN', 'AMBER', 'RED'):
            return v
    return 'UNKNOWN'


def rollup(program_dir):
    subs = []
    sub_root = os.path.join(program_dir, 'subprojects')
    if not os.path.isdir(sub_root):
        sub_root = program_dir  # 也可能直接传入含多个 project.yaml 的目录
    for name in sorted(os.listdir(sub_root)):
        py = os.path.join(sub_root, name, 'project.yaml')
        if not os.path.isfile(py):
            continue
        try:
            d = _load(py)
        except Exception:
            subs.append({'id': name, 'error': '解析失败'})
            continue
        proj = d.get('project') or {}
        metrics = d.get('metrics') or {}
        evm = metrics.get('evm') or {}
        actuals = d.get('actuals') or {}
        wbs = d.get('wbs') or []
        # 里程碑统计（从 wbs 派生）
        ms_done = ms_total = 0
        for w in wbs:
            if w.get('milestone'):
                ms_total += 1
                wp = actuals.get('wbs_progress', {}).get(w.get('id'))
                try:
                    if float(wp or 0) >= 100:
                        ms_done += 1
                except (TypeError, ValueError):
                    pass
        subs.append({
            'id': proj.get('id') or name,
            'name': proj.get('name') or name,
            'lifecycle': proj.get('lifecycle_state'),
            'type': proj.get('type'),
            'start': proj.get('start_date'),
            'target_end': proj.get('target_end'),
            'milestones': {'done': ms_done, 'total': ms_total},
            'bac': evm.get('bac') or 0,
            'ev': evm.get('ev') or actuals.get('ev') or 0,
            'ac': actuals.get('ac') or 0,
            'eac': evm.get('eac') or 0,
            'cpi': evm.get('cpi'),
            'spi': evm.get('spi'),
            'status': _status_from_control(metrics.get('control')),
        })
    # 汇总
    tot_bac = sum(s.get('bac', 0) or 0 for s in subs)
    tot_ev = sum(s.get('ev', 0) or 0 for s in subs)
    tot_ac = sum(s.get('ac', 0) or 0 for s in subs)
    tot_eac = sum(s.get('eac', 0) or 0 for s in subs)
    roll = {
        'subprojects': subs,
        'summary': {
            'count': len(subs),
            'bac': tot_bac,
            'ev': tot_ev,
            'ac': tot_ac,
            'eac': tot_eac,
            'cpi': (tot_ev / tot_ac) if tot_ac else None,
            'eac_vs_bac_var': (tot_bac - tot_eac) if tot_eac else None,
        },
    }
    return roll


def main():
    ap = argparse.ArgumentParser(description="跨子项目汇总")
    ap.add_argument('--program', required=True, help="项目群目录（含 subprojects/）")
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    roll = rollup(a.program)
    if a.json:
        print(yaml.safe_dump(roll, allow_unicode=True, sort_keys=False))
        return
    print(f"=== 子项目汇总（{roll['summary']['count']} 个）===")
    print(f"{'ID':<10}{'里程碑':>10}{'BAC':>14}{'EV':>14}{'AC':>14}{'EAC':>14}{'状态':>8}")
    for s in roll['subprojects']:
        m = s.get('milestones', {})
        print(f"{str(s['id']):<10}{str(m.get('done',0))+'/'+str(m.get('total',0)):>10}"
              f"{s.get('bac',0) or 0:>14.0f}{s.get('ev',0) or 0:>14.0f}"
              f"{s.get('ac',0) or 0:>14.0f}{s.get('eac',0) or 0:>14.0f}{'':>3}{s.get('status','')}")
    sm = roll['summary']
    print(f"{'合计':<10}{'':>10}{sm['bac']:>14.0f}{sm['ev']:>14.0f}{sm['ac']:>14.0f}{sm['eac']:>14.0f}")
    if sm.get('cpi') is not None:
        var = sm.get('eac_vs_bac_var')
        var_txt = f"{var:.0f}" if isinstance(var, (int, float)) else 'n/a'
        print(f"项目群 CPI(估算)={sm['cpi']:.3f}  EAC vs BAC 偏差={var_txt}")


if __name__ == '__main__':
    main()
