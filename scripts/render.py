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
  8. 字段拼接：  {{ join(burndown, ", ", "day") }} -> 1, 2, 3（单行拼接，用于 mermaid 数组；None 回退为 0 防崩溃）
9. mermaid 安全辅助：
   - {{ mid(text) }}      -> mermaid 节点/task 安全 ID（空格/点/非常规字符 -> 下划线，保证非空、不以数字开头）
   - {{ mlabel(text) }}   -> mermaid 标签文本（转义双引号、折叠空白，用于 ["..."] 内）
   - {{ gname(text) }}    -> 甘特图任务显示名（标签安全 + 冒号转全角，避免破坏 `name :id` 分隔）
10. 色标辅助（风险登记册等）：
   - {{ sev_icon(text) }} / {{ risk_icon(text) }} -> 把严重度(绿/黄/橙/红 或 green/yellow/orange/red 或
     low/medium/high/critical)映射为颜色 emoji：🟢 绿 / 🟡 黄 / 🟠 橙 / 🔴 红；未知 -> ⚪

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
    # 支持 #if 内的辅助函数调用，如 (eq granularity "fortnight") / (sev_cell x y)
    if expr.startswith('(') and expr.endswith(')'):
        inner = expr[1:-1].strip()
        if re.match(r'^\w+[(\s]', inner):
            hres = _call_helper(inner, ctx)
            if hres is not None:
                return hres
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
            # None -> '0'：用于 mermaid xychart 等数值数组，避免 [1, , 3] 语法错误
            items.append('0' if it is None else str(it))
        else:
            v = _resolve(field, it)
            items.append('0' if v is None else str(v))
    return sep.join(items)


def _mermaid_id(val):
    """生成 mermaid 安全的节点/task ID。

    - 空格 -> 下划线
    - 点(.) -> 下划线（mermaid gantt/flowchart 的 ID 不允许含 '.'，
      原 slug 直接删点会丢失层级并可能造成重复 ID 而报错）
    - 其余非常规字符 -> 下划线
    - 保证非空（空值回退到稳定的 node_<hash>），且不以数字开头（前缀 '_'）
    例：{{ mid this.id }} -> SOW1_1 （输入 'SOW1.1'）
    """
    if val is None:
        return ''
    s = re.sub(r'\s+', '_', str(val).strip())
    # 保留：单词字符 \w（含字母/数字/下划线/中日韩等 unicode 字母）与连字符 '-'；
    # 其余（点号/标点）-> 下划线。mermaid 接受 unicode 节点/task ID，
    # 故保留中文，仅把 '.' 等非常规字符转为 '_'（同时避免 gantt 非法 task id）。
    s = re.sub(r'[^\w-]', '_', s)
    if s == '' or s == '_':
        h = abs(hash(str(val))) % 1000000
        return f'node_{h:06d}'
    if s[0].isdigit():
        s = '_' + s
    return s


def _mermaid_label(val):
    """mermaid 标签文本（用于 ["..."] / "..." 内）。

    - 双引号 '"' -> 单引号 "'"（避免破坏双引号字符串）
    - 折叠连续空白/换行为单个空格并去首尾空白
    例：{{ mlabel this.from }} -> 订单服务（即使原文含引号/换行也安全）
    """
    if val is None:
        return ''
    s = str(val).replace('"', "'")
    # 注意：'\n' 是字面量反斜杠+n，不被 \s 匹配，故节点内换行仍保留
    s = re.sub(r'[ \t\r\f\v]+', ' ', s).strip()
    return s


def _gantt_name(val):
    """甘特图任务显示名（':' 分隔符之前的文本）。

    在 gantt 行 `任务名 :taskId, start, end` 中，任务名里的冒号会破坏分隔，
    故把 ':' 换成全角 '：'；`&` 是 mermaid 多任务同行运算符，需转义，
    否则未转义的 '&' 会让解析器把后续 token 当作无日期任务 -> 'undefined.endTime' 报错。
    同时复用标签安全处理（引号/空白）。
    """
    s = _mermaid_label(val)
    # gantt 中 ':' 是任务/ID 分隔符，'&' 是多任务同行运算符；
    # 两者都会破坏标签，必须转义。'&' 换成全角 '＆'(U+FF06)，
    # 视觉仍是 & 但不会被当作运算符，避免 'undefined.endTime' 报错。
    s = s.replace(':', '：').replace('&', '＆')
    return s


def _severity_icon(val):
    """把严重度映射为颜色 emoji，用于风险登记册等色标展示。

    接受中文色字（绿/黄/橙/红）、英文 band（green/yellow/orange/red）、
    英文等级（low/medium/high/critical）或其任意组合文本。未知 -> ⚪。
    例：{{ sev_icon this.severity }} -> 🔴（输入 '红' / 'red' / 'critical'）
    """
    if not val:
        return ''
    s = str(val).strip().lower()
    if s in ('绿', 'green', 'low'):
        return '🟢'
    if s in ('黄', 'yellow', 'medium'):
        return '🟡'
    if s in ('橙', 'orange', 'high'):
        return '🟠'
    if s in ('红', 'red', 'critical'):
        return '🔴'
    # 子串兜底（如 "10 橙"、"15 orange"）
    if '绿' in s or 'green' in s:
        return '🟢'
    if '黄' in s or 'yellow' in s:
        return '🟡'
    if '橙' in s or 'orange' in s:
        return '🟠'
    if '红' in s or 'red' in s:
        return '🔴'
    return '⚪'


def _slug_call(tag, ctx):
    """兼容旧写法：slug(x) / slug x 等价于 mid(x)（mermaid 安全 ID）。"""
    m = re.match(r'^\s*slug\s*\((.*)\)\s*$', tag, re.S)
    if not m:
        m = re.match(r'^\s*slug\s+(.+?)\s*$', tag, re.S)
    if not m:
        return None
    return _mermaid_id(_resolve_or_literal(m.group(1).strip(), ctx))


def _severity_band_from_score(score):
    """按 5×5 校准矩阵把 score 映射为颜色 emoji（缺 severity 时回退用）。

    色带：🟢 绿 1–4 ｜ 🟡 黄 5–9 ｜ 🟠 橙 10–15 ｜ 🔴 红 16–25。
    无法解析 -> ⚪。
    """
    if score is None:
        return '⚪'
    try:
        sc = float(str(score).strip())
    except (ValueError, AttributeError):
        return '⚪'
    if sc <= 4:
        return '🟢'
    if sc <= 9:
        return '🟡'
    if sc <= 15:
        return '🟠'
    return '🔴'


def _severity_cell(sev, score=None):
    """优先用 severity 显式色标，缺失时用 score 推导，保证色标永远显示。

    用法：{{ sev_cell this.severity this.score }} -> 🔴
    """
    icon = _severity_icon(sev)
    if icon and icon != '⚪':
        return icon
    return _severity_band_from_score(score)


def _call_helper(tag, ctx):
    """分发已知辅助函数调用：slug / mid / mlabel / gname / join。

    返回 None 表示这不是一个可识别的辅助调用（交由通用变量求值处理）。
    """
    m = re.match(r'^\s*(\w+)\s*\((.*)\)\s*$', tag, re.S)
    if m:
        name = m.group(1)
        arg = m.group(2).strip()
        if name in ('slug', 'mid'):
            return _mermaid_id(_resolve_or_literal(arg, ctx))
        if name == 'mlabel':
            return _mermaid_label(_resolve_or_literal(arg, ctx))
        if name == 'gname':
            return _gantt_name(_resolve_or_literal(arg, ctx))
        if name in ('sev_icon', 'risk_icon'):
            return _severity_icon(_resolve_or_literal(arg, ctx))
        if name in ('sev_cell', 'sev_band'):
            # sev_cell(severity, score) / sev_band(score)  -- 支持逗号或空格分隔
            inner = re.match(r'^\s*(.*?)\s*[,\s]\s*(.*)\s*$', arg, re.S)
            if name == 'sev_band':
                return _severity_band_from_score(_resolve_or_literal(arg, ctx))
            if inner and inner.group(2).strip():
                a = _resolve_or_literal(inner.group(1).strip(), ctx)
                b = _resolve_or_literal(inner.group(2).strip(), ctx)
                return _severity_cell(a, b)
            return _severity_cell(_resolve_or_literal(arg, ctx), None)
        if name == 'join':
            return _join_call(tag, ctx)
        if name == 'eq':
            # eq(a, b) 或 eq a b -> 相等返回 b 的字面值（truthy），否则 ''（falsy），供 {{#if (eq ..)}} 使用
            a_raw, b_raw = None, None
            inner = re.match(r'^\s*(.*?)\s*,\s*(.*)\s*$', arg, re.S)
            if inner:
                a_raw, b_raw = inner.group(1).strip(), inner.group(2).strip()
            else:
                # 空格分隔（兼容引号包裹字面量）：eq granularity "fortnight"
                m2 = re.match(r'^\s*(\S+)\s+"([^"]*)"\s*$', arg, re.S)
                if m2:
                    a_raw, b_raw = m2.group(1).strip(), '"' + m2.group(2) + '"'
                else:
                    parts = arg.split(None, 1)
                    if len(parts) == 2:
                        a_raw, b_raw = parts[0].strip(), parts[1].strip()
            if a_raw is not None and b_raw is not None:
                a = _resolve_or_literal(a_raw, ctx)
                b = _resolve_or_literal(b_raw, ctx)
                return b if str(a) == str(b) else ''
            return ''
        return None
    # 兼容文档示例中的无括号写法：{{ slug this.from }} 与 {{ eq a b }}
    if tag.startswith('slug '):
        return _slug_call(tag, ctx)
    if tag.startswith('eq '):
        inner = tag[3:].strip()
        # 转成 eq(a, b) 形式重新进入解析（支持引号字面量）
        m2 = re.match(r'^(\S+)\s+"([^"]*)"\s*$', inner, re.S)
        if m2:
            return _call_helper('eq(%s, "%s")' % (m2.group(1), m2.group(2)), ctx)
        parts = inner.split(None, 1)
        if len(parts) == 2:
            return _call_helper('eq(%s, %s)' % (parts[0], parts[1].strip('"')), ctx)
        return ''
    return None


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
            res = _call_helper(tag, ctx)
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
