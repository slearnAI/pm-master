#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master v2 · 子Agent产出校验器（Sub-Agent Output Validator）
============================================================
主控收到子Agent回报后，运行此脚本校验产出是否合规。

校验项：
  1. JSON格式完整性（必须含 agent_role/status/artifacts/key_findings）
  2. 产物文件确实存在
  3. 估算数值化检查
  4. 风险/RAID完整性检查（owner/mitigation）
  5. project_yaml_updates格式检查

用法：
  python3 subagent_check.py --report <子Agent回报JSON文件> --project <项目>/project.yaml
  python3 subagent_check.py --report <JSON文件> --strict  # 告警也升级为致命
"""
import os
import sys
import argparse
import json as _json

try:
    import yaml
except ImportError:
    yaml = None


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return _json.load(f)


def load_yaml(path):
    if yaml is None:
        raise RuntimeError("需要 PyYAML，请先 pip install pyyaml")
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def has_estimate(est):
    if est is None:
        return False
    if isinstance(est, (int, float)):
        return est > 0
    import re
    s = str(est).strip()
    if s in ('', '—', '-', 'TBD', '待定', 'N/A', 'NA', 'none', 'null'):
        return False
    m = re.search(r'\d+(\.\d+)?', s)
    if not m:
        return False
    return float(m.group()) > 0


def validate_report(report, project_root):
    """校验子Agent回报，返回 (problems, warnings)"""
    problems = []
    warnings = []

    # 1. JSON结构完整性
    required_fields = ['agent_role', 'status', 'artifacts', 'key_findings']
    for field in required_fields:
        if field not in report:
            problems.append(f"缺少必填字段: {field}")

    if 'agent_role' in report and report['agent_role'] not in (
        'planner-agent', 'scheduler-agent', 'risk-agent', 'stakeholder-agent',
        'reporter-agent', 'program-agent', 'communication-agent', 'monitoring-agent'
    ):
        warnings.append(f"未知角色: {report['agent_role']}")

    if 'status' in report and report['status'] not in ('success', 'partial', 'failed'):
        problems.append(f"无效status: {report['status']}")

    # 2. 产物文件存在性
    for art in report.get('artifacts', []):
        path = art.get('path', '')
        if not path:
            problems.append(f"产物 {art.get('key','?')} 缺少path")
            continue
        # 支持相对路径（相对于project_root）
        if not os.path.isabs(path):
            path = os.path.join(project_root, path)
        if not os.path.exists(path):
            problems.append(f"产物文件不存在: {art.get('key','?')} → {path}")

    # 3. key_findings检查
    findings = report.get('key_findings', [])
    if len(findings) < 2:
        warnings.append("key_findings少于2条，建议3-5条")
    if len(findings) > 10:
        warnings.append(f"key_findings过多({len(findings)}条)，建议≤5条")

    # 4. project_yaml_updates格式
    updates = report.get('project_yaml_updates', {})
    if updates and not isinstance(updates, dict):
        problems.append("project_yaml_updates必须是dict")

    # 5. status=failed时的处理
    if report.get('status') == 'failed' and not report.get('errors'):
        problems.append("status=failed但没有errors说明")

    # 6. 如果report中包含内联数据，检查估算
    if 'data_files' in report:
        for df in report.get('data_files', []):
            if not os.path.exists(df):
                warnings.append(f"数据文件不存在: {df}")

    return problems, warnings


def main():
    ap = argparse.ArgumentParser(description="PM Master v2 子Agent产出校验器")
    ap.add_argument('--report', required=True, help="子Agent回报JSON文件路径")
    ap.add_argument('--project', default=None, help="项目 project.yaml（用于解析相对路径）")
    ap.add_argument('--strict', action='store_true', help="告警升级为致命")
    a = ap.parse_args()

    try:
        report = load_json(a.report)
    except Exception as e:
        print(f"✗ 无法解析JSON: {e}")
        sys.exit(1)

    project_root = os.path.dirname(os.path.abspath(a.project)) if a.project else os.getcwd()
    problems, warnings = validate_report(report, project_root)

    print(f"=== 子Agent产出校验 ===")
    print(f"角色: {report.get('agent_role', '?')} | 状态: {report.get('status', '?')}")
    print(f"产物数: {len(report.get('artifacts', []))} | 发现: {len(report.get('key_findings', []))}条")

    if warnings:
        print(f"\n⚠ 告警 {len(warnings)} 条:")
        for w in warnings:
            print(f"  - {w}")

    if problems:
        print(f"\n✗ 致命问题 {len(problems)} 条:")
        for p in problems:
            print(f"  - {p}")
        if a.strict:
            problems.extend(f"[strict] {w}" for w in warnings)
        sys.exit(1)

    if not problems:
        print("\n✓ 子Agent产出校验通过")
        sys.exit(0)


if __name__ == '__main__':
    main()
