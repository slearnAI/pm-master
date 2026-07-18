#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · SOW 级启动会（Kick-off）批量生成器
-------------------------------------------------
修复「SOW 级 individual kick-off 没跑、没产出工件」：每个 SOW（工作说明书）级 summary 包
在规划期都应由本脚本产出一份 per-SOW 启动会工件（templates/common/sow_kickoff.md），
对齐范围/交付物/责任人/首批行动。

识别 SOW 级包：
  - 优先：wbs 中 `summary: true` 且 tier != 'program' 的行（即 SOW 级汇总包）；
  - 兜底：若没有显式 summary 标记，则取「顶层包」（id 不含 '.'，且存在以其为前缀的子包，
    如 'SOW1' 下有 'SOW1.1'）。

每个 SOW 包派生：
  - deliverables：其下叶子包（id 以 '<sow_id>.' 开头）的名称；
  - experts：叶子包去重后的 role；
  - participants：SOW owner + 领域专家 + PM + sponsor；
  - kickoff_date：project.start_date 或 '待定'。

输出：<项目根>/plans/kickoff/<sow_id>_kickoff.md，并把路径写回
      project.yaml 的 artifacts.sow_kickoffs（列表）。

用法：
  python3 build_sow_kickoff.py --project /workspace/<slug>/project.yaml
  python3 build_sow_kickoff.py --project <yaml> --out-dir /custom/kickoff
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


def _identify_sow_packages(wbs):
    """返回 SOW 级包的 id 列表。"""
    explicit = [w.get('id') for w in wbs
                if w.get('summary') and w.get('tier') != 'program' and w.get('id')]
    if explicit:
        return explicit
    # 兜底：顶层包且有子包
    ids = [w.get('id') for w in wbs if w.get('id')]
    sows = []
    for w in wbs:
        wid = w.get('id')
        if not wid or '.' in wid:
            continue
        has_child = any(i != wid and i.startswith(wid + '.') for i in ids)
        if has_child:
            sows.append(wid)
    return sows


def main():
    ap = argparse.ArgumentParser(description="PM Master · SOW 启动会批量生成器")
    ap.add_argument('--project', required=True, help="单一事实源 project.yaml")
    ap.add_argument('--out-dir', default=None, help="输出目录（缺省 <项目根>/plans/kickoff）")
    ap.add_argument('--template', default=None, help="启动会模板（缺省取技能内 templates/common/sow_kickoff.md）")
    a = ap.parse_args()

    if yaml is None:
        raise SystemExit("需要 PyYAML：请先 `pip install pyyaml`")

    data = _load(a.project)
    wbs = data.get('wbs') or []
    if not wbs:
        raise SystemExit("⚠ project.yaml 中未找到 wbs，无法生成 SOW 启动会（请先完成 WBS 拆解）。")

    sow_ids = _identify_sow_packages(wbs)
    if not sow_ids:
        print("[sow_kickoff] 未识别到 SOW 级包（summary: true 或带子包的顶层包），跳过。")
        return

    proj = data.get('project') or {}
    kickoff_date = proj.get('start_date') or '待定'
    pm = proj.get('pm') or '（待定）'
    sponsor = proj.get('sponsor') or '（待定）'

    tpl_path = a.template or os.path.join(SCRIPT_DIR, '..', 'templates', 'common', 'sow_kickoff.md')
    tpl_path = os.path.abspath(tpl_path)
    if not os.path.exists(tpl_path):
        raise SystemExit(f"启动会模板不存在：{tpl_path}")
    with open(tpl_path, 'r', encoding='utf-8') as f:
        tpl = f.read()
    from render import render

    root = os.path.dirname(os.path.abspath(a.project))
    out_dir = a.out_dir or os.path.join(root, 'plans', 'kickoff')
    os.makedirs(out_dir, exist_ok=True)

    if 'artifacts' not in data or not isinstance(data['artifacts'], dict):
        data['artifacts'] = {}
    data.setdefault('sow_kickoffs', [])

    produced = []
    for sow_id in sow_ids:
        sow = next((w for w in wbs if w.get('id') == sow_id), {})
        leaves = [w for w in wbs if str(w.get('id', '')).startswith(sow_id + '.')]
        deliverables = [{'id': w.get('id'), 'name': w.get('name', w.get('id'))} for w in leaves]
        experts = []
        for w in leaves:
            r = w.get('role')
            if r and r not in experts:
                experts.append(r)
        participants = [{'name': sow.get('owner') or '（待定）', 'role': 'SOW 责任人'}]
        for r in experts:
            participants.append({'name': f'（{r} 专家）', 'role': f'领域专家({r})'})
        participants.append({'name': pm, 'role': '项目经理(PM)'})
        participants.append({'name': sponsor, 'role': '发起人(Sponsor)'})

        ctx = {
            'project': proj,
            'sow': {
                'id': sow_id,
                'name': sow.get('name', sow_id),
                'domain': sow.get('domain') or '（待定）',
                'owner': sow.get('owner') or '（待定）',
                'objective': sow.get('deliverable') or sow.get('name', sow_id),
                'scope': sow.get('deliverable') or '（待定）',
            },
            'deliverables': deliverables,
            'experts': experts,
            'participants': participants,
            'kickoff_date': kickoff_date,
            'decisions': sow.get('kickoff_decisions')
                or [{'id': 1, 'item': '确认范围与交付物', 'conclusion': '（待定）'}],
            'assumptions': sow.get('assumptions') or ['（待定）'],
            'next_actions': sow.get('next_actions')
                or [{'action': '拆解并派发叶子工作包', 'owner': sow.get('owner') or '（待定）', 'due': '（待定）'}],
            'artifacts': sow.get('artifacts') or ['（待定）'],
            'status': sow.get('status') or '规划中',
        }
        rendered = render(tpl, ctx)
        slug = str(sow_id).replace('.', '_')
        out_path = os.path.join(out_dir, f'{slug}_kickoff.md')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(rendered)
        rel = os.path.relpath(out_path, root)
        produced.append(rel)
        print(f"[sow_kickoff] 已生成 {sow_id} 启动会：{out_path}")

    data['artifacts']['sow_kickoffs'] = produced
    _save(a.project, data)
    print(f"[sow_kickoff] 共 {len(produced)} 份 SOW 启动会，已写入 artifacts.sow_kickoffs")


if __name__ == '__main__':
    main()
