#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · 模板渲染引擎（契约脚本）
-------------------------------------------------
把带占位符的 Markdown 模板 + YAML/JSON 数据，渲染为最终 Markdown 产物。

支持的模板语法（mini-Jinja，足够 PM 文档使用）：
  1. 变量：      {{ project.name }}  或  {{ this.id }}
  2. 循环：      {{#each risks}} ... {{this.description}} ... {{/each}}
  3. 循环变量：  {{@index}} / {{@first}} / {{@last}}（循环内可用，常用于拼接逗号数组）
  4. 条件：      {{#if framework == "scrum"}} ... {{else}} ... {{/if}}
                  （也兼容 {{#else}} 写法，二者等价）
  5. 比较运算：  ==  /  !=  （用于 #if）
  6. 字面量：    "文本"  /  '文本'  /  true / false / null / 数字
  7. 列表索引：  {{ burndown.[0].remaining }}（支持 arr.[n] 形式）
  8. 字段拼接：  {{ join(burndown, ", ", "day") }} -> 1, 2, 3（单行拼接，用于 mermaid 数组）

数据合并：循环体内通过 `this` 引用当前元素；支持一层嵌套循环（this 会按层覆盖）。
缺失变量输出空串，不抛错（便于部分数据渲染）。
"""
import os
import sys
import argparse
import re

try:
    import yaml
except ImportError:
    yaml = None


# ---------- 表达式求值 ----------
def _resolve(path, ctx):
    """按 '.' 路径从 ctx 取值，支持 dict / list 索引（含 arr.[0] 形式）。"""
    cur = ctx
    for part in str(path).split('.'):
        # 支持 list 索引段：arr.[0] -> 0
        if len(part) >= 3 and part.startswith('[') and part.endswith(']'):
            part = part[1:-1]
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return cur


def _resolve_or_literal(tok, ctx):
    tok = tok.strip()
    if len(tok) >= 2 and ((tok[0] == '"' and tok[-1] == '"') or (tok[0] == "'" and tok[-1] == "'")):
        return tok[1:-1]
    low = tok.lower()
    if low in ('true', 'false', 'null'):
        return {'true': True, 'false': False, 'null': None}[low]
    try:
        return int(tok)
    except ValueError:
        pass
    try:
        return float(tok)
    except ValueError:
        pass
    return _resolve(tok, ctx)


def _eval(expr, ctx):
    expr = expr.strip()
    for op in ('==', '!='):
        if op in expr:
            left, right = expr.split(op, 1)
            l = _resolve_or_literal(left, ctx)
            r = _resolve_or_literal(right, ctx)
            return (l == r) if op == '==' else (l != r)
    return _resolve_or_literal(expr, ctx)


def _split_args(s):
    """按逗号切分，忽略引号内的逗号（用于 join() 参数解析）。"""
    out = []
    cur = []
    in_q = None
    for ch in s:
        if in_q:
            cur.append(ch)
            if ch == in_q:
                in_q = None
        elif ch in ('"', "'"):
            in_q = ch
            cur.append(ch)
        elif ch == ',':
            out.append(''.join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append(''.join(cur))
    return [p.strip() for p in out]


def _join_call(tag, ctx):
    """支持 join(listExpr, "sep", "field") 形式的字段拼接（单行、无换行）。

    例：{{ join(burndown, ", ", "day") }} -> 1, 2, 3
    用于生成 mermaid xychart 等需要逗号数组的图表。
    """
    m = re.match(r'^\s*join\s*\((.*)\)\s*$', tag, re.S)
    if not m:
        return None
    args = _split_args(m.group(1))
    if len(args) < 2:
        return ''
    lst = _resolve(args[0], ctx)
    if not isinstance(lst, (list, tuple)):
        return ''
    sep = args[1]
    if len(sep) >= 2 and ((sep[0] == '"' and sep[-1] == '"') or (sep[0] == "'" and sep[-1] == "'")):
        sep = sep[1:-1]
    field = args[2] if len(args) > 2 else ''
    if len(field) >= 2 and ((field[0] == '"' and field[-1] == '"') or (field[0] == "'" and field[-1] == "'")):
        field = field[1:-1]
    items = []
    for it in lst:
        if not field or field == 'this':
            items.append('' if it is None else str(it))
        else:
            v = _resolve(field, it)
            items.append('' if v is None else str(v))
    return sep.join(items)


def _slug_call(tag, ctx):
    """支持 slug(text) 生成 mermaid 安全节点 ID（空格/非常规字符 -> 下划线，保留中文）。

    例：{{ slug this.from }} -> 订单服务 / M1_交易闭环
    用于 flowchart 节点 ID（mermaid 不允许 ID 含空格）。
    """
    m = re.match(r'^\s*slug\s*\((.*)\)\s*$', tag, re.S)
    if not m:
        # 兼容文档示例中的无括号写法：{{ slug this.from }}
        m = re.match(r'^\s*slug\s+(.+?)\s*$', tag, re.S)
    if not m:
        return None
    inner = m.group(1).strip()
    val = _resolve_or_literal(inner, ctx)
    if val is None:
        return ''
    s = re.sub(r'\s+', '_', str(val))
    # 仅保留 字母/数字/下划线/连字符/中日韩汉字，其余去除
    s = re.sub(r'[^0-9A-Za-z_\-\u4e00-\u9fff]', '', s)
    return s


# ---------- 块匹配 ----------
def _find_block(text, start, open_marker, close_marker):
    """从 start 起，找到与 open_marker 匹配的 close_marker，返回 (内部文本, close之后索引)。"""
    depth = 1
    i = start
    L = len(text)
    while i < L and depth > 0:
        oi = text.find(open_marker, i)
        ci = text.find(close_marker, i)
        if ci == -1:
            raise ValueError(f"未匹配的块标记: {open_marker}")
        if oi != -1 and oi < ci:
            depth += 1
            i = oi + len(open_marker)
        else:
            depth -= 1
            i = ci + len(close_marker)
            if depth == 0:
                return text[start:ci], i
    return text[start:i], i


def _split_else(body):
    """在 #if 体内找到顶层（depth==1）的 {{else}} 或 {{#else}} 作为 then/else 分界。

    两种写法等价：{{else}} 与 {{#else}}。
    """
    depth = 1
    i = 0
    L = len(body)
    while i < L:
        oi = body.find('{{#if ', i)
        oe = body.find('{{#each ', i)
        e1 = body.find('{{else}}', i)
        e2 = body.find('{{#else}}', i)
        ci = body.find('{{/if}}', i)
        ce = body.find('{{/each}}', i)
        cands = []
        if oi != -1:
            cands.append((oi, 'if'))
        if oe != -1:
            cands.append((oe, 'each'))
        if e1 != -1:
            cands.append((e1, 'else'))
        if e2 != -1:
            cands.append((e2, 'else2'))
        if ci != -1:
            cands.append((ci, 'ifc'))
        if ce != -1:
            cands.append((ce, 'eachc'))
        if not cands:
            break
        p, t = min(cands)
        if t == 'if':
            depth += 1; i = p + 6
        elif t == 'each':
            depth += 1; i = p + 8
        elif t == 'ifc':
            depth -= 1; i = p + 7
        elif t == 'eachc':
            depth -= 1; i = p + 9
        elif t in ('else', 'else2'):
            marker_len = len('{{else}}') if t == 'else' else len('{{#else}}')
            if depth == 1:
                return body[:p], body[p + marker_len:]
            i = p + marker_len
    return body, ''


# ---------- 递归渲染 ----------
def _parse(text, ctx):
    out = []
    i = 0
    L = len(text)
    while i < L:
        idx = text.find('{{', i)
        if idx == -1:
            out.append(text[i:]); break
        out.append(text[i:idx])
        end = text.find('}}', idx)
        if end == -1:
            out.append(text[idx:]); break
        tag = text[idx + 2:end].strip()
        if tag.startswith('#each '):
            expr = tag[6:].strip()
            body, ni = _find_block(text, end + 2, '{{#each ', '{{/each}}')
            val = _eval(expr, ctx)
            chunk = []
            if isinstance(val, (list, tuple)):
                n = len(val)
                for idx, item in enumerate(val):
                    sub = dict(ctx)
                    sub['this'] = item
                    sub['@index'] = idx
                    sub['@first'] = (idx == 0)
                    sub['@last'] = (idx == n - 1)
                    rendered = _parse(body, sub)
                    # 去掉循环体首尾换行，避免连续行之间出现空行（保持每行一个换行）
                    stripped = rendered.lstrip('\n').rstrip('\n')
                    # 仅当循环体本身含换行（如表格行）才补换行；
                    # 行内 each（如甘特图依赖链）不补，避免打断同一行。
                    chunk.append(stripped + '\n' if '\n' in rendered else stripped)
            out.append(''.join(chunk))
            i = ni
        elif tag.startswith('#if '):
            expr = tag[4:].strip()
            body, ni = _find_block(text, end + 2, '{{#if ', '{{/if}}')
            then_b, else_b = _split_else(body)
            branch = then_b if _truthy(_eval(expr, ctx)) else else_b
            out.append(_parse(branch, ctx))
            i = ni
        else:
            res = _join_call(tag, ctx)
            if res is None:
                res = _slug_call(tag, ctx)
            if res is not None:
                out.append(res)
            else:
                val = _eval(tag, ctx)
                if isinstance(val, list):
                    val = ', '.join(str(x) for x in val)
                out.append('' if val is None else str(val))
            i = end + 2
    return ''.join(out)


def _truthy(v):
    if isinstance(v, (list, dict, str)):
        return len(v) > 0
    return bool(v)


def render(text, data):
    return _parse(text, data if isinstance(data, dict) else {})


# ---------- CLI ----------
def load_data(path):
    with open(path, 'r', encoding='utf-8') as f:
        raw = f.read()
    if path.endswith(('.yaml', '.yml')):
        if yaml is None:
            raise SystemExit("需要 PyYAML：请先 `pip install pyyaml`")
        return yaml.safe_load(raw)
    return __import__('json').loads(raw)


def main():
    ap = argparse.ArgumentParser(description="PM Master 模板渲染引擎")
    ap.add_argument('--template', required=True, help="模板 .md 路径")
    ap.add_argument('--data', required=True, help="数据 .yaml/.json 路径")
    ap.add_argument('--out', required=True, help="输出 .md 路径")
    args = ap.parse_args()

    with open(args.template, 'r', encoding='utf-8') as f:
        tpl = f.read()
    data = load_data(args.data)
    result = render(tpl, data)

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        f.write(result)
    print(f"[render] {args.template} + {args.data}  ->  {args.out}  ({len(result)} chars)")


if __name__ == '__main__':
    main()
