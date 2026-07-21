#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · 机密性扫描器（Confidentiality Scanner）
--------------------------------------------------
对 skill 包做一次穿透式扫描，覆盖「所有文件的内容」，而不仅限文件路径/文件名。
包括：
  - 文本文件（.py / .md / .yaml / .json / templates / references / examples / 任意文本）
  - 二进制 / 缓存文件（如 __pycache__/*.pyc，其字节码内嵌 co_filename 绝对路径，
    仅扫文件名/文本会漏掉这类泄露）

用途：在上架 / 发布（push 到共享分支）前确认包内不含真实客户 / 厂商标识或
本机绝对路径泄露。这是对「每次发布前的机密性评审」的自动化固化。

敏感令牌（HIGH，命中即视为泄露 -> exit 1）：
  LIC / Teradata / Vertica / Vantage / FSAS / lic-datalake /
  /Users/ / /home/ / C:\\Users / qclaw / Stephen Lau

白名单（不报警，已在评审中确认安全）：
  - 脱敏占位符：示例客户 / 示例数据湖项目 / MPP数仓
  - 通用示例角色：nos-architect（方法论示例角色，非客户系统 NOS）
  - 通用示例邮箱：*@corp.com / *@external.com / *@example.com
  - 通用示例货币占位：示例 ₹ 金额 / ₹XX.XM（明确标注为示例，非真实金额）

用法：
  python3 confidentiality_check.py --pack <skill_root>   # 默认 = 脚本上级的上级目录
  python3 confidentiality_check.py                        # 自动定位 skill 根
返回：发现 HIGH 泄露 -> exit 1；全清 -> exit 0。
"""
import argparse
import os
import re
import sys


# ---- HIGH 敏感令牌：命中即泄露 ----
HIGH_PATTERNS = [
    (r'\bLIC\b', 'LIC (客户缩写)'),
    (r'Teradata', 'Teradata (厂商)'),
    (r'Vertica', 'Vertica (厂商)'),
    (r'Vantage', 'Vantage (Teradata Vantage)'),
    (r'\bFSAS\b', 'FSAS (客户系统)'),
    (r'lic-datalake', 'lic-datalake (客户项目 slug)'),
    (r'/Users/', '绝对路径 /Users/ (泄露本机用户名)'),
    (r'/home/', '绝对路径 /home/ (泄露本机用户名)'),
    (r'C:\\Users', '绝对路径 C:\\Users (泄露本机用户名)'),
    (r'qclaw', 'qclaw (历史工作区路径)'),
    (r'Stephen Lau', 'Stephen Lau (真实人名)'),
]

# ---- 已在评审中确认安全的白名单片段（仅用于报告提示，不报警）----
REVIEW_NOTES = [
    ('示例客户', '脱敏占位符（非真实客户名）'),
    ('示例数据湖项目', '脱敏占位符（非真实项目名）'),
    ('MPP数仓', '脱敏占位符（非真实厂商名）'),
    ('nos-architect', '通用方法论示例角色（非客户系统 NOS）'),
    ('示例 ₹ 金额', '通用示例货币占位（非真实金额）'),
    ('₹XX.XM', '通用示例货币占位（非真实金额）'),
]


def _scan_text(text, patterns):
    """在已解码文本上逐行匹配，返回 [(line_no, label, snippet)]。"""
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        for pat, label in patterns:
            if re.search(pat, line):
                hits.append((i, label, line.strip()[:160]))
    return hits


def _scan_bytes(raw, patterns):
    """对二进制（如 .pyc）做字节级扫描，返回 [(offset, label, snippet)]。"""
    hits = []
    for pat, label in patterns:
        for m in re.finditer(pat.encode('utf-8'), raw):
            start = max(0, m.start() - 30)
            end = min(len(raw), m.end() + 30)
            snippet = raw[start:end].decode('latin-1', errors='replace').replace('\n', ' ')
            hits.append((m.start(), label, snippet[:80]))
    return hits


# 扫描器自身文件名（含定义中的敏感令牌样例），必须排除自匹配
SELF_NAMES = {os.path.basename(__file__), 'confidentiality_check.py'}


def scan_pack(pack_root):
    high = []        # (relpath, location, label, snippet)
    reviewed = set() # 报告里提示的已评审安全片段
    for dirpath, dirnames, filenames in os.walk(pack_root):
        # 跳过 git 元数据
        if '.git' in dirnames:
            dirnames.remove('.git')
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, pack_root)
            # 跳过扫描器自身（其源码含待查令牌样例，会自匹配误报）
            if fn in SELF_NAMES:
                continue
            try:
                with open(full, 'rb') as f:
                    raw = f.read()
            except OSError:
                continue
            # 先尝试以 utf-8 文本解码；失败则按二进制扫字节
            try:
                text = raw.decode('utf-8')
                is_text = True
            except UnicodeDecodeError:
                text = None
                is_text = False
            if is_text:
                for ln, label, snip in _scan_text(text, HIGH_PATTERNS):
                    high.append((rel, f'L{ln}', label, snip))
            else:
                for off, label, snip in _scan_bytes(raw, HIGH_PATTERNS):
                    high.append((rel, f'@{off}', label, snip))
            # 收集白名单片段用于提示
            sample = text if text is not None else raw.decode('latin-1', errors='replace')
            for token, note in REVIEW_NOTES:
                if token in sample:
                    reviewed.add(f'{token} -> {note}')
    return high, reviewed


def main():
    ap = argparse.ArgumentParser(description="PM Master · 机密性穿透扫描")
    here = os.path.dirname(os.path.abspath(__file__))
    default_pack = os.path.dirname(here)
    ap.add_argument('--pack', default=default_pack, help='skill 根目录（默认脚本上级目录）')
    a = ap.parse_args()

    pack = os.path.abspath(a.pack)
    if not os.path.isdir(pack):
        raise SystemExit(f'包目录不存在：{pack}')

    high, reviewed = scan_pack(pack)

    print('=' * 64)
    print(f'PM Master · 机密性扫描  ->  {pack}')
    print('=' * 64)
    if high:
        print(f'\n[FAIL] 发现 {len(high)} 处 HIGH 敏感令牌泄露：\n')
        for rel, loc, label, snip in high:
            print(f'  • {rel} ({loc})  [{label}]')
            print(f'      {snip}')
        print('\n这些命中必须脱敏后才能发布。')
    else:
        print('\n[PASS] 未在任何文件内容（含二进制/字节码）中发现 HIGH 敏感令牌。')

    if reviewed:
        print('\n[INFO] 已评审确认安全的占位/示例片段（不报警）：')
        for r in sorted(reviewed):
            print(f'  - {r}')

    print('\n' + '=' * 64)
    return 1 if high else 0


if __name__ == '__main__':
    sys.exit(main())
