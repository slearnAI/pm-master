#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · 单一事实源读写（project.yaml）
-------------------------------------------------
每个项目/项目群一个 project.yaml，主控 Agent 与子 Agent 都通过本脚本读写，
保证状态一致、跨会话/跨 Agent 连续。

命令：
  get  <key>            读取（支持点路径，如 project.name）
  set  <key> <value>    写入（自动按类型推断；list/dict 用 JSON 串）
  exists                判断 project.yaml 是否存在
  show                  打印整份 yaml
  init <name> [--type project|program] [--methodology ...] [--framework ...]
                        （仅当文件不存在时）初始化骨架
  migrate               v1.x -> v2 平滑迁移（补 _checkpoint / schema_version=2 / last_control_check）
  checkpoint [<step>]   读取当前工作流检查点；传 <step> 则写回并更新 last_step_at
  config [<key>]        读取安装期 config.yaml（如 execution.subagent_mode）

设计：v2 在 v1 基础上引入 Agent 层检查点(_checkpoint)，用于防跳步与跨会话续跑。
"""
import os
import sys
import argparse
import json
import datetime

try:
    import yaml
except ImportError:
    yaml = None

DEFAULT_PROJECT_YAML = "project.yaml"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _load(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) if yaml else {}


def _backup(path):
    """Take a timestamped backup before any destructive write (defense against data loss)."""
    if os.path.exists(path):
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        bak = f"{path}.bak_{ts}"
        try:
            import shutil
            shutil.copy2(path, bak)
        except Exception:
            pass
        return bak
    return None


def _save(path, data, _backup_ok=True):
    # Hard guard: never write an empty/skeleton dict over a non-empty file.
    if isinstance(data, dict) and len(data) == 0 and os.path.exists(path):
        try:
            existing = _load(path)
        except Exception:
            existing = {}
        if isinstance(existing, dict) and len(existing) > 0:
            print(f"✗ 拒绝写入：将用空数据覆盖非空 project.yaml（疑似 PyYAML/加载失败）。"
                  f" 已中止，未改动原文件。", file=sys.stderr)
            sys.exit(5)
    if _backup_ok:
        _backup(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)) if os.path.dirname(path) else '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        if yaml:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        else:
            json.dump(data, f, ensure_ascii=False, indent=2)


def _get(data, key):
    cur = data
    for part in key.split('.'):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _set(data, key, value):
    parts = key.split('.')
    cur = data
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
        if not isinstance(cur, dict):
            raise ValueError(f"路径 {part} 不是 dict")
    last = parts[-1]
    if isinstance(value, str) and (value.startswith('[') or value.startswith('{')):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
    elif isinstance(value, str) and value.lower() in ('true', 'false', 'null'):
        value = {'true': True, 'false': False, 'null': None}[value.lower()]
    else:
        try:
            value = int(value)
        except (ValueError, TypeError):
            try:
                value = float(value)
            except (ValueError, TypeError):
                pass
    cur[last] = value
    return data


def load_config():
    """读取安装期 config.yaml（skills 目录下的策略/护栏层）。
    优先顺序：env PM_MASTER_CONFIG -> <SKILL_DIR>/../config.yaml -> 内建默认。"""
    req = os.environ.get('PM_MASTER_CONFIG')
    candidates = []
    if req:
        candidates.append(req)
    candidates.append(os.path.join(SCRIPT_DIR, '..', 'config.yaml'))
    candidates.append(os.path.join(SCRIPT_DIR, 'config.yaml'))
    for c in candidates:
        if c and os.path.exists(c):
            try:
                with open(c, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) if yaml else {}, c
            except Exception:
                continue
    return {}, None


def main():
    ap = argparse.ArgumentParser(description="PM Master 单一事实源读写")
    ap.add_argument('cmd', choices=['get', 'set', 'exists', 'show', 'init', 'migrate', 'checkpoint', 'config'])
    ap.add_argument('args', nargs='*', help="key / value / name / step 等")
    ap.add_argument('--file', default=DEFAULT_PROJECT_YAML)
    ap.add_argument('--type', default='project')
    ap.add_argument('--methodology', default='agile')
    ap.add_argument('--framework', default='scrum')
    a = ap.parse_args()

    path = a.file

    if a.cmd == 'exists':
        print('true' if os.path.exists(path) else 'false')
        return

    if a.cmd == 'show':
        data = _load(path)
        print(yaml.safe_dump(data, allow_unicode=True, sort_keys=False) if yaml else json.dumps(data, ensure_ascii=False, indent=2))
        return

    if a.cmd == 'config':
        cfg, src = load_config()
        if not a.args:
            print(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False) if yaml else json.dumps(cfg, ensure_ascii=False, indent=2))
            return
        val = _get(cfg, a.args[0])
        print('' if val is None else (json.dumps(val, ensure_ascii=False) if isinstance(val, (list, dict)) else val))
        return

    if a.cmd == 'get':
        if not a.args:
            print("用法: get <key>", file=sys.stderr); sys.exit(2)
        val = _get(_load(path), a.args[0])
        print('' if val is None else (json.dumps(val, ensure_ascii=False) if isinstance(val, (list, dict)) else val))
        return

    if a.cmd == 'set':
        if len(a.args) < 2:
            print("用法: set <key> <value>", file=sys.stderr); sys.exit(2)
        data = _load(path)
        _set(data, a.args[0], a.args[1])
        _save(path, data)
        print(f"[state] set {a.args[0]}")
        return

    if a.cmd == 'checkpoint':
        data = _load(path)
        cp = data.setdefault('_checkpoint', {})
        if a.args:
            step = a.args[0]
            cp['step'] = step
            cp['last_step_at'] = datetime.date.today().isoformat()
            _save(path, data)
            print(f"[checkpoint] -> {step}")
        else:
            print(cp.get('step') or 'none')
        return

    if a.cmd == 'migrate':
        if not os.path.exists(path):
            print(f"✗ 未找到 project.yaml: {path}", file=sys.stderr); sys.exit(2)
        data = _load(path)
        ver = data.get('schema_version', 1)
        if ver >= 2:
            print(f"[migrate] 已是最新 schema (v{ver})，无需迁移")
            return
        data['schema_version'] = 2
        cp = data.setdefault('_checkpoint', {})
        if 'step' not in cp:
            cp['step'] = 'init'
            cp['last_step_at'] = datetime.date.today().isoformat()
        if 'last_control_check' not in data:
            data['last_control_check'] = None
        _save(path, data)
        print(f"[migrate] v{ver} -> v2 完成（补 _checkpoint / last_control_check，schema_version=2）")
        return

    if a.cmd == 'init':
        if os.path.exists(path):
            print(f"[state] 已存在，跳过: {path}")
            return
        name = a.args[0] if a.args else '未命名项目'
        skeleton = {
            'schema_version': 2,
            '_checkpoint': {'step': 'init', 'last_step_at': datetime.date.today().isoformat()},
            'last_control_check': None,
            'project': {
                'id': name.strip().lower().replace(' ', '-'),
                'name': name,
                'type': a.type,
                'methodology': a.methodology,
                'framework': a.framework if a.methodology == 'agile' else None,
                'phase': '启动' if a.type == 'project' else '组合定义',
                'status': '规划中',
                'lifecycle_state': 'planning',
                'baselined_on': None,
                'domain': '',
                'product': '',
                'start_date': None,
                'target_end': None,
                'objectives': [],
                'scope': '',
                'out_of_scope': '',
                'sponsor': '',
                'pm': '',
                'team': [],
            },
            'governance': {'stage_gates': [], 'cadence': ''},
            'artifacts': {},
            'raid': {'risks': [], 'assumptions': [], 'issues': [], 'dependencies': []},
            'metrics': {'evm': {}, 'burndown': []},
            'wbs': [],
            'milestones': [],
            'actuals': {},
            'control': {},
            'program': {'projects': [], 'dependencies': [], 'benefits': []} if a.type == 'program' else None,
        }
        _save(path, skeleton)
        print(f"[state] 初始化 project.yaml: {path} (type={a.type}, methodology={a.methodology}, schema=v2)")


if __name__ == '__main__':
    main()
