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
"""
import os
import sys
import argparse
import json

try:
    import yaml
except ImportError:
    yaml = None

DEFAULT_PROJECT_YAML = "project.yaml"


def _load(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) if yaml else json.load(f) if path.endswith('.json') else {}


def _save(path, data):
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
    # 类型推断
    if value.startswith('[') or value.startswith('{'):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
    elif value.lower() in ('true', 'false', 'null'):
        value = {'true': True, 'false': False, 'null': None}[value.lower()]
    else:
        try:
            value = int(value)
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                pass
    cur[last] = value
    return data


def main():
    ap = argparse.ArgumentParser(description="PM Master 单一事实源读写")
    ap.add_argument('cmd', choices=['get', 'set', 'exists', 'show', 'init'])
    ap.add_argument('args', nargs='*', help="key / value / name 等")
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
    if a.cmd == 'init':
        if os.path.exists(path):
            print(f"[state] 已存在，跳过: {path}")
            return
        name = a.args[0] if a.args else '未命名项目'
        skeleton = {
            'schema_version': 1,
            'project': {
                'id': name.strip().lower().replace(' ', '-'),
                'name': name,
                'type': a.type,
                'methodology': a.methodology,
                'framework': a.framework if a.methodology == 'agile' else None,
                'phase': '启动' if a.type == 'project' else '组合定义',
                'status': '规划中',
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
            'program': {'projects': [], 'dependencies': [], 'benefits': []} if a.type == 'program' else None,
        }
        _save(path, skeleton)
        print(f"[state] 初始化 project.yaml: {path} (type={a.type}, methodology={a.methodology})")


if __name__ == '__main__':
    main()
