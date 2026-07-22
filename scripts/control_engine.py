#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · 运营控制引擎（Operational Control Engine）

进入 operational 阶段后，按 control.cadence 周期性对照**基线**运行既定检查，
确保项目按基线预期运行；任一控制项突破阈值即升级告警（exit 1，可挂定时任务）。

对照对象：baselines/<date>.yaml（由 baseline.py 冻结）
输入（project.yaml）：baseline 指针 + actuals（最新实际进展）+ control（阈值/频次/收件人）

控制项：
  1. 进度 Schedule    : 各 WBS 包 按计划% vs 实际% 偏差 / 逾期天数
  2. 成本 EVM         : SPI=EV/PV, CPI=EV/AC, EAC/ETC/VAC
  3. 风险漂移 Risk    : 当前评分 vs 基线评分；新增红/严重风险
  4. 里程碑 Milestone : 里程碑逾期未完成
  5. 问题 Issue       : RAID 问题 overdue 未关闭
  6. 变更 Change      : 未决变更请求数量
  7. 数据完整性       : 重跑 consistency_check

用法：
  python3 control_engine.py --project /workspace/<slug>/project.yaml [--as-of 2026-08-12] [--json]
"""
import os
import sys
import json
import subprocess
import datetime
import argparse

try:
    import yaml
except ImportError:
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))


def load_config():
    """读取安装期 config.yaml（operational_control / quality_gate 等旋钮）。"""
    for cand in (os.path.join(HERE, '..', 'config.yaml'),
                 os.path.join(HERE, 'config.yaml')):
        if os.path.exists(cand):
            try:
                with open(cand, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                return {}
    return {}
RENDER = os.path.join(HERE, 'render.py')
CONSISTENCY = os.path.join(HERE, 'consistency_check.py')

# ---- 统一状态常量（避免各支柱内联 hardcode 导致 '已降降' 类错字）----
DONE_STATES = {'done', 'complete', 'completed', '完成', '已完成'}
CLOSED_STATES = {'closed', '已关闭', '关闭', 'resolved', '已解决',
                 'retired', '已退役', '退役'}
CANCELLED_STATES = {'cancelled', 'canceled', '已取消', '取消',
                    'descoped', '已降级', '移出范围', 'out-of-scope',
                    'terminated', '已终止', '终止', 'deferred', '已延期搁置'}
NOT_OVERDUE_STATES = DONE_STATES | CLOSED_STATES | CANCELLED_STATES
NON_WORKING_STATES = CANCELLED_STATES
RISK_INACTIVE_STATES = CLOSED_STATES | CANCELLED_STATES | DONE_STATES


def _norm_status(v):
    """状态归一：小写 + 兼容中英文同义词。"""
    if v is None:
        return ''
    s = str(v).strip().lower()
    if s in ('已取消',):
        return 'cancelled'
    if s in ('取消', '移出范围'):
        return 'descoped'
    if s in ('终止', '已终止'):
        return 'terminated'
    return s


def load(path):
    if yaml is None:
        raise RuntimeError("需要 PyYAML，请先 pip install pyyaml")
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def run(cmd):
    return subprocess.run([sys.executable] + cmd, capture_output=True, text=True)


def parse_date(s):
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%Y/%m/%d'):
        try:
            return datetime.datetime.strptime(str(s), fmt).date()
        except ValueError:
            continue
    return None


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def collect_risks(data):
    seen = {}
    for r in (data.get('risks') or []):
        if r.get('id'):
            seen[r['id']] = r
    for r in ((data.get('raid') or {}).get('risks') or []):
        if r.get('id') and r['id'] not in seen:
            seen[r['id']] = r
    return list(seen.values())


SEV_TO_BAND = {'绿': 'low', '黄': 'medium', '橙': 'high', '红': 'critical',
               'green': 'low', 'yellow': 'medium', 'orange': 'high', 'red': 'critical'}


def norm_sev(s):
    return SEV_TO_BAND.get(str(s).strip().lower()) if s else None


def compute(data, bdata, as_of):
    controls = []
    escalations = []
    cfg = data.get('control') or {}
    thr = cfg.get('thresholds') or {}
    spi_warn = float(thr.get('spi_warn', 0.95))
    cpi_warn = float(thr.get('cpi_warn', 0.95))
    slip_pct = float(thr.get('schedule_slip_pct', 15))
    open_change_high = int(thr.get('open_change_high', 2))

    actuals = data.get('actuals') or {}
    have_actuals = bool(data.get('actuals'))
    wbs_progress = actuals.get('wbs_progress') or {}
    ev_reported = actuals.get('ev')
    ac = actuals.get('ac')

    bl_wbs = bdata.get('wbs') or []
    # 项目群层级：仅以里程碑级（tier != 'component'）行计算进度，
    # 避免把组件叶子细节摊到项目群报告；组件层级按自身 wbs 全部计算。
    bl_wbs_all = bl_wbs
    if str((data.get('project') or {}).get('type', '')).lower() == 'program':
        bl_wbs = [w for w in bl_wbs if w.get('tier') != 'component']
    proj_type = str((data.get('project') or {}).get('type', '')).lower()
    bl_evm = (bdata.get('metrics') or {}).get('evm') or {}
    bac = bl_evm.get('bac') or bl_evm.get('pv') or 0
    # 若基线带 pv 作为总计划值且未给 bac，用 pv 当作完工预算近似值
    if not bac and bl_evm.get('pv'):
        bac = bl_evm.get('pv')

    # ---------- 1. 进度 Schedule ----------
    # 结构化进度明细：每行一个工作包/里程碑，分别记录 计划% / 实际% / 偏差% / 状态。
    # 项目群层级：baseline.wbs 仅含各 SOW 里程碑汇总包 → 自然聚合成里程碑级明细；
    # 组件层级：baseline.wbs 含叶子包 → 明细到叶子级。二者共用同一渲染逻辑。
    sched_msgs = []
    total_est = 0.0
    planned_wsum = 0.0
    actual_wsum = 0.0
    overdue_pkgs = []
    schedule_rows = []
    for w in bl_wbs:
        # 汇总包(summary)是标签行，其估算是子叶子的 rollup；纳入会重复计数，跳过。
        if w.get('summary'):
            continue
        # 已取消/降级/终止/移出范围的包不计入进度控制（非在办工作，不算逾期）。
        if _norm_status(w.get('status')) in NON_WORKING_STATES:
            continue
        est = w.get('estimate') or 0
        try:
            est = float(est)
        except (TypeError, ValueError):
            est = 0
        s = parse_date(w.get('start'))
        e = parse_date(w.get('end'))
        planned_pct = 0.0
        if s and e and e >= s:
            if as_of <= s:
                planned_pct = 0.0
            elif as_of >= e:
                planned_pct = 100.0
            else:
                planned_pct = (as_of - s).days / max((e - s).days, 1) * 100.0
        if isinstance(wbs_progress, dict):
            actual_pct = float(wbs_progress.get(w.get('id'), 0) or 0)
        else:
            # 容错：若 wbs_progress 传入标量（整体完成%），则统一套用到各工作包
            try:
                actual_pct = float(wbs_progress or 0)
            except (TypeError, ValueError):
                actual_pct = 0.0
        total_est += est
        planned_wsum += est * planned_pct
        actual_wsum += est * actual_pct
        variance = actual_pct - planned_pct
        # 行级状态：落后超阈值→告警；逾期未完成→红；否则绿
        if actual_pct < planned_pct - slip_pct:
            row_status = 'RED' if (e and as_of > e and actual_pct < 100) else 'AMBER'
        else:
            row_status = 'GREEN'
        schedule_rows.append({
            'id': w.get('id'), 'name': w.get('name'),
            'planned': round(planned_pct, 1), 'actual': round(actual_pct, 1),
            'variance': round(variance, 1), 'status': row_status,
        })
        if e and as_of > e and actual_pct < 100:
            overdue_pkgs.append({'id': w.get('id'), 'name': w.get('name'),
                                 'overdue_days': (as_of - e).days})
        if actual_pct < planned_pct - slip_pct:
            sched_msgs.append(f"{w.get('id')} 实际 {actual_pct:.0f}% 落后计划 {planned_pct:.0f}% "
                             f"(差 {planned_pct-actual_pct:.0f}%)")
    overall_planned = (planned_wsum / total_est) if total_est else 0.0
    overall_actual = (actual_wsum / total_est) if total_est else 0.0
    # 整体状态由行级状态聚合：任一 RED→红；任一 AMBER→黄；否则绿
    row_statuses = [r['status'] for r in schedule_rows]
    if 'RED' in row_statuses:
        sched_status = 'RED'
    elif 'AMBER' in row_statuses or sched_msgs:
        sched_status = 'AMBER'
    else:
        sched_status = 'GREEN'
    if overdue_pkgs:
        sched_status = 'RED'
    sched_detail = (f"整体进度 计划 {overall_planned:.0f}% / 实际 {overall_actual:.0f}%。"
                    + (f" 滞后 {len(sched_msgs)} 个，逾期 {len(overdue_pkgs)} 个。"
                       if (sched_msgs or overdue_pkgs) else " 进度受控。"))
    controls.append({'name': '进度控制 Schedule', 'status': sched_status,
                     'detail': sched_detail, 'key': 'schedule'})
    if sched_status == 'RED':
        escalations.append('schedule_slip')

    # ---------- 2. 成本 EVM ----------
    # 统一 EVM 货币基准：PV/EV/AC 必须同口径。本引擎以 BAC(货币) 为唯一基准，
    # 不再引用 metrics.evm.pv（历史存的是人天，已废弃）。
    # 固定费率(fixed-fee)工作：EV 应以「计费里程碑达成(billing milestone done)」计量，
    # 而非物理完成%——在首个计费里程碑确认前，物理% 会系统性低估 EV，CPI 不宜判红。
    proj_start = parse_date((data.get('project') or {}).get('start_date'))
    pre_start = bool(proj_start and as_of < proj_start)

    # 计费里程碑（固定费率）及其完成状态（来自 actuals.milestone_status 或 wbs_progress 的里程碑行）
    def _milestone_done(mid):
        ms = (actuals.get('milestone_status') or {}) if isinstance(actuals, dict) else {}
        st = ms.get(mid)
        if st in ('done', 'complete', 'signed-off', 'signed_off', 100):
            return True
        wp = wbs_progress.get(mid) if isinstance(wbs_progress, dict) else None
        try:
            return float(wp or 0) >= 100
        except (TypeError, ValueError):
            return False

    fixed_milestones = []
    for w in (bdata.get('wbs') or []):
        b = w.get('billing') or {}
        fee = b.get('fee_inr') or b.get('fee')
        if w.get('milestone') and b.get('fee_type') == 'fixed' and fee:
            try:
                fixed_milestones.append((w.get('id'), float(fee)))
            except (TypeError, ValueError):
                pass
    evm_method = 'physical'
    ev_fixed = 0.0
    pv_fixed = 0.0
    if fixed_milestones:
        evm_method = 'milestone'
        for mid, fee in fixed_milestones:
            if _milestone_done(mid):
                ev_fixed += fee
            # PV(固定费率): 里程碑计划完成（as_of 已过其 end）即计入计划值
            s = parse_date(({w.get('id'): w for w in (bdata.get('wbs') or [])}.get(mid) or {}).get('end'))
            if s and as_of >= s:
                pv_fixed += fee

    if pre_start:
        # 基线起始前不应产生挣值；PV=EV=AC=0，EVM 置 N/A，不误报 SPI=1.0
        pv = ev = ac_v = 0.0
        spi = cpi = 1.0
        eac = etc = vac = 0.0
        evm_status = 'N/A'
        evm_detail = (f"EVM 不适用：as_of {as_of.isoformat()} 早于项目起始 {proj_start.isoformat()}"
                      f"；基线起始前不产生挣值（PV=EV=AC=0）。")
    else:
        if evm_method == 'milestone':
            # 固定费率部分用里程碑计量；非固定(BAC - 固定总额)部分用物理% 计量
            fixed_total = sum(f for _, f in fixed_milestones)
            tm_base = max(bac - fixed_total, 0.0)
            ev_tm = tm_base * overall_actual / 100.0 if tm_base else 0.0
            pv_tm = tm_base * overall_planned / 100.0 if tm_base else 0.0
            ev = ev_fixed + ev_tm
            pv = pv_fixed + pv_tm
            ac_v = float(ac) if isinstance(ac, (int, float)) else 0.0
            # 首个计费里程碑确认前，CPI 用物理% 估算，仅作 AMBER 提示，不判红升级
            if ev_fixed <= 0 and ac_v > 0:
                cpi = (ev / ac_v) if ac_v > 0 else 1.0
                spi = (ev / pv) if pv > 0 else 1.0
                eac = etc = vac = 0.0  # 计费里程碑未确认前不推算 EAC/VAC（避免误报偏差）
                evm_status = 'AMBER'
                evm_detail = (f"SPI={spi:.2f} CPI={cpi:.2f}（估算，首个计费里程碑未确认前用物理%）| "
                              f"PV={pv:.1f} EV={ev:.1f} AC={ac_v:.1f} | 固定费率 BAC={fixed_total:.0f} 已确认 EV={ev_fixed:.0f}"
                              f"\n  ⚠ 注意：固定费率 SOW 在首个 Wave Design Document 签署确认前，CPI 不具真实超支含义，"
                              f"请勿据此上报 EAC/VAC 偏差。")
                # 不 append 'cpi' 升级（避免误报 RED）
                if spi < spi_warn:
                    escalations.append('spi')
            else:
                cpi = (ev / ac_v) if ac_v > 0 else 1.0
                spi = (ev / pv) if pv > 0 else 1.0
                eac = (bac / cpi) if cpi > 0 else bac
                etc = max(eac - ac_v, 0.0)
                vac = bac - eac
                evm_status = 'GREEN'
                if cpi < cpi_warn or spi < spi_warn:
                    evm_status = 'RED'
                elif cpi < 1.0 or spi < 1.0:
                    evm_status = 'AMBER'
                evm_detail = (f"SPI={spi:.2f} CPI={cpi:.2f}（里程碑计量）| PV={pv:.1f} EV={ev:.1f} AC={ac_v:.1f} | "
                              f"EAC={eac:.1f} ETC={etc:.1f} VAC={vac:.1f} (BAC={bac:.1f}) | 已确认固定费率 EV={ev_fixed:.0f}")
                if cpi < cpi_warn:
                    escalations.append('cpi')
                if spi < spi_warn:
                    escalations.append('spi')
        else:
            pv = bac * overall_planned / 100.0 if bac else 0.0
            ev = float(ev_reported) if isinstance(ev_reported, (int, float)) else (bac * overall_actual / 100.0 if bac else 0.0)
            ac_v = float(ac) if isinstance(ac, (int, float)) else 0.0
            spi = (ev / pv) if pv > 0 else 1.0
            cpi = (ev / ac_v) if ac_v > 0 else 1.0
            eac = (bac / cpi) if cpi > 0 else bac
            etc = max(eac - ac_v, 0.0)
            vac = bac - eac
            evm_status = 'GREEN'
            if cpi < cpi_warn or spi < spi_warn:
                evm_status = 'RED'
            elif cpi < 1.0 or spi < 1.0:
                evm_status = 'AMBER'
            evm_detail = (f"SPI={spi:.2f} CPI={cpi:.2f} | PV={pv:.1f} EV={ev:.1f} AC={ac_v:.1f} | "
                          f"EAC={eac:.1f} ETC={etc:.1f} VAC={vac:.1f} (BAC={bac:.1f})")
            if cpi < cpi_warn:
                escalations.append('cpi')
            if spi < spi_warn:
                escalations.append('spi')

    controls.append({'name': '成本/挣值 EVM', 'status': evm_status,
                     'detail': evm_detail, 'key': 'evm'})

    # ---------- 3. 风险漂移 Risk ----------
    bl_risks = {r.get('id'): r for r in (bdata.get('risks') or [])}
    cur_risks = collect_risks(data)
    risk_msgs = []
    risk_red = False
    for r in cur_risks:
        rid = r.get('id')
        if _norm_status(r.get('status')) in RISK_INACTIVE_STATES:
            continue  # 已关闭/已解决/已取消的风险不算活跃漂移
        bl = bl_risks.get(rid)
        if bl and isinstance(r.get('score'), (int, float)) and isinstance(bl.get('score'), (int, float)):
            if r['score'] > bl['score']:
                risk_msgs.append(f"{rid} 评分 {bl['score']}→{r['score']} 升级")
                risk_red = True
        if norm_sev(r.get('severity')) == 'critical':
            risk_msgs.append(f"{rid} 为红/严重风险(当前)")
            risk_red = True
        if rid not in bl_risks and norm_sev(r.get('severity')) in ('high', 'critical'):
            risk_msgs.append(f"{rid} 基线后新增高/严重风险")
            risk_red = True
    risk_status = 'RED' if risk_red else ('AMBER' if risk_msgs else 'GREEN')
    controls.append({'name': '风险漂移 Risk Drift', 'status': risk_status,
                     'detail': ('; '.join(risk_msgs) if risk_msgs else '与基线相比无风险升级'), 'key': 'risk'})
    if risk_red:
        escalations.append('new_red_risk' if any('新增' in m for m in risk_msgs) else 'risk_upgrade')

    # ---------- 4. 里程碑 Milestone ----------
    # 里程碑来源：优先用顶层 milestones[]，否则从 wbs 的 milestone 包派生（SKILL 单一事实源）。
    ms_top = data.get('milestones') or bdata.get('milestones') or []
    if not ms_top:
        wbs_all = (data.get('wbs') or []) + (bdata.get('wbs') or [])
        seen = set()
        for w in wbs_all:
            if w.get('milestone') and w.get('id') not in seen:
                seen.add(w.get('id'))
                wp = (wbs_progress.get(w.get('id')) if isinstance(wbs_progress, dict) else None)
                try:
                    done = float(wp or 0) >= 100
                except (TypeError, ValueError):
                    done = False
                ms_top.append({
                    'id': w.get('id'), 'name': w.get('name'),
                    'date': w.get('start') or w.get('end'),
                    'status': 'done' if done else (w.get('status') or 'open'),
                })
    ms = ms_top
    ms_overdue = []
    for m in ms:
        d = parse_date(m.get('date'))
        st = str(m.get('status', '')).lower()
        if d and as_of > d and st not in ('done', 'complete', '完成', 'closed', '关闭'):
            ms_overdue.append(m.get('id') or m.get('name'))
    ms_status = 'RED' if ms_overdue else 'GREEN'
    controls.append({'name': '里程碑 Milestone', 'status': ms_status,
                     'detail': ('逾期未完成: ' + ', '.join(ms_overdue)) if ms_overdue else '无逾期里程碑',
                     'key': 'milestone'})
    if ms_overdue:
        escalations.append('overdue_milestone')

    # ---------- 5. 问题 RAID Issues ----------
    issues = (data.get('raid') or {}).get('issues') or []
    iss_overdue = []
    for i in issues:
        d = parse_date(i.get('due'))
        st = str(i.get('status', '')).lower()
        if d and as_of > d and st not in ('done', 'complete', '完成', 'closed', '关闭'):
            iss_overdue.append(i.get('id'))
    iss_status = 'RED' if iss_overdue else 'GREEN'
    controls.append({'name': '问题 RAID Issues', 'status': iss_status,
                     'detail': ('逾期未关闭: ' + ', '.join(iss_overdue)) if iss_overdue else '无逾期问题',
                     'key': 'issue'})
    if iss_overdue:
        escalations.append('overdue_issue')

    # ---------- 6. 变更 Change ----------
    changes = data.get('changes') or (data.get('raid') or {}).get('changes') or []
    # 兼容 change_log 表
    clog = data.get('change_log') or []
    if isinstance(clog, list):
        changes = clog
    open_changes = [c for c in changes
                    if str(c.get('status', '')).lower() in ('open', 'pending', '待审', '进行中')]
    ch_status = 'RED' if len(open_changes) >= open_change_high else ('AMBER' if open_changes else 'GREEN')
    controls.append({'name': '变更 Change', 'status': ch_status,
                     'detail': f"未决变更请求 {len(open_changes)} 个（阈值≥{open_change_high} 升级）",
                     'key': 'change'})
    if len(open_changes) >= open_change_high:
        escalations.append('open_change_high')

    # ---------- 6b. 控制门纪律（lifecycle_state 技术强制）----------
    # 贴合 lifecycle.md §5：waterfall/hybrid 须 planning→baselined→operational 强制串行。
    # 控制引擎只在 operational 下做正式巡检；未进入则告警（AMBER），不误报为 RED 升级。
    ls = str((data.get('project') or {}).get('lifecycle_state') or 'planning').lower()
    # 已收尾终态：程序/项目已通过收尾门正式关闭，已超过运营控制阶段，不应再报 gate_not_operational。
    TERMINAL_LS = {'closed', 'closeout', '收尾', '已关闭', '终止', 'terminated',
                   'cancelled', 'archived', '已归档'}
    if ls == 'operational':
        gate_status = 'GREEN'
        gate_detail = '已通过控制门，处于运营控制阶段（lifecycle_state=operational），控制引擎正常巡检。'
    elif ls in TERMINAL_LS:
        gate_status = 'GREEN'
        gate_detail = (f'已进入终态（lifecycle_state={ls}）：项目/程序已经收尾门正式关闭，'
                       '已超过运营控制阶段；本次仅为历史对照，不再要求 operational。')
    elif ls == 'baselined':
        gate_status = 'AMBER'
        gate_detail = ('已基线化但未置 lifecycle_state=operational；本次仍按基线对照，'
                       '但正式运营控制须先经控制门将 lifecycle_state 置为 operational。')
    else:
        gate_status = 'AMBER'
        gate_detail = (f'当前 lifecycle_state={ls}，尚未进入运营控制阶段；'
                       f'控制引擎应在 operational 下运行'
                       f'（先 baseline.py --freeze → 控制门 → operational）。')
    controls.append({'name': '控制门 Gate', 'status': gate_status,
                     'detail': gate_detail, 'key': 'gate'})
    if ls not in ({'operational'} | TERMINAL_LS):
        escalations.append('gate_not_operational')

    # ---------- 7. 数据完整性 Integrity ----------
    chk = run([CONSISTENCY, '--project', project_path_global])
    int_status = 'GREEN' if chk.returncode == 0 else 'RED'
    controls.append({'name': '数据完整性 Integrity', 'status': int_status,
                     'detail': ('一致性门禁通过' if chk.returncode == 0
                                else '一致性门禁失败，详情见 consistency_check 输出'), 'key': 'integrity'})
    if int_status == 'RED':
        escalations.append('integrity')

    # 未填报实际进展：进度/EVM 无法对照基线，应记为 AMBER（运营缺口）而非误报 RED 升级
    if not have_actuals:
        for c in controls:
            if c['key'] in ('schedule', 'evm'):
                c['status'] = 'AMBER'
                c['detail'] = ('未填报实际进展(actuals)，无法对照基线计算'
                               + ('进度偏差' if c['key'] == 'schedule' else 'EVM')
                               + '；请按 control.cadence 更新 actuals 后巡检')
        for r in schedule_rows:
            r['status'] = 'N/A'
            r['variance'] = None
        escalations = [e for e in escalations if e not in ('schedule_slip', 'cpi', 'spi')]

    order = {'GREEN': 0, 'AMBER': 1, 'RED': 2, 'N/A': 0}
    overall = 'GREEN'
    for c in controls:
        if order[c['status']] > order[overall]:
            overall = c['status']
    return {
        'as_of': as_of.isoformat(),
        'overall_status': overall,
        'controls': controls,
        'escalations': escalations,
        'schedule_table': schedule_rows,
        'schedule_slip_pct': slip_pct,
        'metrics': {'bac': round(bac, 1), 'pv': round(pv, 1), 'ev': round(ev, 1),
                    'ac': round(ac_v, 1), 'spi': round(spi, 3),
                    'cpi': round(cpi, 3), 'eac': round(eac, 1), 'etc': round(etc, 1),
                    'vac': round(vac, 1),
                    'planned_pct': round(overall_planned, 1), 'actual_pct': round(overall_actual, 1)},
    }


project_path_global = None


def main():
    global project_path_global
    ap = argparse.ArgumentParser(description="PM Master 运营控制引擎")
    ap.add_argument('--project', required=True)
    ap.add_argument('--as-of', default=None, help="巡检基准日 ISO，默认今天")
    ap.add_argument('--json', action='store_true', help="仅输出 JSON")
    ap.add_argument('--call-evm', action='store_true',
                    help="P1-3: 用 evm.py.compute 交叉校验 EVM 数值（独立模块复用）")
    a = ap.parse_args()
    project_path_global = os.path.abspath(a.project)
    data = load(project_path_global)
    proj = data.get('project', {}) or {}
    bl = data.get('baseline') or {}
    blfile = bl.get('file')
    if not blfile:
        print("✗ 控制引擎中止：项目尚未基线化（无 baseline 指针）。请先运行 baseline.py --freeze。",
              file=sys.stderr)
        sys.exit(3)
    bpath = blfile if os.path.isabs(blfile) else os.path.join(os.path.dirname(project_path_global), blfile)
    if not os.path.exists(bpath):
        print(f"✗ 控制引擎中止：基线文件不存在：{bpath}", file=sys.stderr)
        sys.exit(3)
    bdata = load(bpath)
    as_of = (parse_date((data.get('actuals') or {}).get('as_of'))
             or parse_date(a.as_of) or datetime.date.today())

    # 配置化阈值（M3）：把安装期 config.operational_control 注入 data.control.thresholds，
    # compute() 会优先读取；项目级 control.thresholds 可进一步覆盖（收紧优先）。
    cfg = load_config() if 'load_config' in globals() else {}
    oc = (cfg.get('operational_control') or {}) if isinstance(cfg, dict) else {}
    if isinstance(oc, dict) and oc:
        ctrl = data.setdefault('control', {})
        cthr = ctrl.setdefault('thresholds', {})
        for k in ('spi_warn', 'cpi_warn', 'schedule_slip_warn_pct', 'open_change_high'):
            if k in oc and k not in cthr:
                try:
                    cthr[k] = float(oc[k])
                except (ValueError, TypeError):
                    pass

    result = compute(data, bdata, as_of)

    # ---- OAG：运营期交付物护栏（交付物漂移检测） ----
    oag_violation = False
    try:
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        from artifact_guard import check_artifacts as _chk_art
        _ok, _viol, _ = _chk_art(project_path_global, data)
        if _ok:
            result['controls'].append({'name': '交付物漂移 (OAG)',
                                       'status': 'OK',
                                       'detail': '全部交付物与事实源一致'})
        else:
            _msg = '；'.join(_viol[:3]) + (' …' if len(_viol) > 3 else '')
            result['controls'].append({'name': '交付物漂移 (OAG)',
                                       'status': 'RED',
                                       'detail': f'{len(_viol)} 项交付物未随事实源刷新：{_msg}'})
            result.setdefault('escalations', []).append('交付物护栏违规(OAG)')
            oag_violation = True
    except Exception as _e:
        print(f"[OAG] 检查跳过: {_e}")

    # ---- P1-3: 用 evm.py 交叉校验 EVM 数值 ----
    if a.call_evm:
        try:
            import importlib.util as _ilu
            esp = os.path.join(HERE, 'evm.py')
            spec = _ilu.spec_from_file_location('evm_mod', esp)
            evm_mod = _ilu.module_from_spec(spec); spec.loader.exec_module(evm_mod)
            m = result.get('metrics') or {}
            cross = evm_mod.compute(m.get('pv', 0), m.get('ev', 0), m.get('ac', 0), m.get('bac', 0))
            print("[call-evm] evm.py 交叉校验:", json.dumps(cross, ensure_ascii=False))
        except Exception as _e:
            print(f"[call-evm] 校验跳过: {_e}")

    out_root = os.path.dirname(project_path_global)
    arts = data.get('artifacts', {}) or {}
    crep = arts.get('control_report') or 'artifacts/control_report.md'
    # 渲染控制报告
    tmp = {'project': proj, 'as_of': result['as_of'], 'overall_status': result['overall_status'],
           'controls': result['controls'], 'escalations': result['escalations'],
           'schedule_table': result['schedule_table'],
           'schedule_slip_pct': result['schedule_slip_pct'],
           'schedule_note': f"巡检基准日 {result['as_of']}；偏差告警阈值 ±{result['schedule_slip_pct']:.0f}%。"
                            f"{'项目群层级：按各 SOW 里程碑汇总。' if str(proj.get('type','')).lower()=='program' else '组件层级：明细到叶子工作包。'}",
           'metrics': result['metrics'], 'baseline_on': bl.get('on'),
           'baseline_file': bl.get('file')}
    tmp_path = os.path.join(out_root, '.control_tmp.yaml')
    with open(tmp_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(tmp, f, allow_unicode=True, sort_keys=False)
    run([RENDER, '--template',
         os.path.join(HERE, '..', 'templates', 'common', 'control_report.md'),
         '--data', tmp_path, '--out', os.path.join(out_root, crep)])
    try:
        os.remove(tmp_path)
    except OSError:
        pass

    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"=== 运营控制报告（as_of {result['as_of']}）===")
        print(f"整体状态: {result['overall_status']}  | 基线: {bl.get('on')}")
        print(f"进度 {result['metrics']['planned_pct']}%→{result['metrics']['actual_pct']}%  "
              f"SPI={result['metrics']['spi']} CPI={result['metrics']['cpi']}")
        for c in result['controls']:
            print(f"  [{c['status']:>5}] {c['name']}: {c['detail']}")
        if result['escalations']:
            print(f"⚠ 升级项: {', '.join(result['escalations'])}")
        print(f"报告已渲染: {crep}")
    # 巡检落盘时间戳（E4：避免重复巡检）
    data['last_control_check'] = as_of.isoformat() if hasattr(as_of, 'isoformat') else str(as_of)
    # 同步回 control 块，便于向后兼容
    (data.setdefault('control', {}))['last_control_check'] = data['last_control_check']
    with open(project_path_global, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
    # 退出码：任一 RED 升级 或 交付物护栏违规 → 1（可挂定时任务告警）
    sys.exit(1 if (result['overall_status'] == 'RED' or oag_violation) else 0)


if __name__ == '__main__':
    main()
