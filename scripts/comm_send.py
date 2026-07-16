#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · 对外邮件审批门（Communication Send Gate）
====================================================
正式邮件是**对外、不可逆、安全敏感**动作。本脚本是发送前的**硬审批门 + 审计闸**：
读取安装期策略（技能根 config.yaml）与项目数据（project.yaml.communication），在真正委派给
邮件后端之前强制校验「是否启用 / 是否经审批 / 收件人是否在联络簿 / 外部邮件是否须 sponsor 会签」，
通过后才调用所选后端（agent-mail / himalaya / gog / smtp）实际发送，并写一条审计记录到
governance.communications[]。

分层（policy / data 分离，见 config.yaml 与 project-schema.md）：
  - 策略/护栏（安装期，不可被项目覆盖）：email.enabled / email.backend / email.default_from /
    email.requires_send_approval
  - 数据（项目期）：communication.contacts[]（联络簿）、communication.from、approval_override

安全默认：
  - requires_send_approval=true 且无 --approve  → exit 1（不发）
  - approval_override.require_sponsor_cosign=true 且含外部收件人，但 approver 不含 sponsor → exit 1
  - --dry-run：仅打印将要发送的邮件与后端命令、写审计（status=dry-run），**不真正外发**（便于测试/复核）

用法：
  # 按角色解析收件人（sponsor,pm → 查 communication.contacts[] 得邮箱），审批后发送
  python3 comm_send.py --project <项目>/project.yaml \\
      --to "sponsor,pm" --subject "里程碑 M2 达成" --body-file draft.md --approve "张三(PM)"

  #  dry-run 复核（不真正发送）
  python3 comm_send.py --project <项目>/project.yaml --to ops@corp.com \\
      --subject "周报" --body-file draft.md --approve "张三(PM)" --dry-run

  # 外部收件人 + 须 sponsor 会签
  python3 comm_send.py --project <项目>/project.yaml --to client@external.com \\
      --subject "验收通知" --body-file draft.md --approve "李四(sponsor)"
"""
import os
import sys
import argparse
import subprocess
import datetime
import tempfile

try:
    import yaml
except ImportError:
    yaml = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(os.path.dirname(SCRIPT_DIR), 'config.yaml')


def load(path):
    if yaml is None:
        raise RuntimeError("需要 PyYAML，请先 pip install pyyaml")
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def has(path):
    return os.path.exists(path)


def die(msg, code=1):
    print(f"✗ {msg}", file=sys.stderr)
    sys.exit(code)


# ---------- 收件人解析 ----------
def resolve_recipients(tokens, contacts):
    """tokens: 逗号分隔的角色名/姓名/邮箱。返回 (emails[], external_flags[])。"""
    emails = []
    external = []
    known = {(str(c.get('role', '')).strip().lower(),
              str(c.get('name', '')).strip().lower(),
              str(c.get('email', '')).strip().lower())
             for c in (contacts or [])}
    known_emails = {e for (_, _, e) in known}
    for tok in [t.strip() for t in tokens.split(',') if t.strip()]:
        low = tok.lower()
        if '@' in tok:                      # 显式邮箱
            emails.append(tok)
            external.append(tok.strip().lower() not in known_emails)
            continue
        hit = None
        for c in (contacts or []):
            if (str(c.get('role', '')).strip().lower() == low
                    or str(c.get('name', '')).strip().lower() == low):
                hit = c.get('email')
                break
        if hit:
            emails.append(hit)
            external.append(str(hit).strip().lower() not in known_emails)
        else:
            die(f"未知收件人（不在 communication.contacts[] 且非邮箱格式）：{tok}")
    if not emails:
        die("收件人为空")
    return emails, external


# ---------- 后端命令构造 ----------
def build_backend_cmd(backend, frm, to_csv, subject, body_file, smtp_cfg):
    """返回后端 CLI 命令列表（best-effort，具体 flag 以所装邮件技能为准）。"""
    if backend == 'agent-mail':
        return ['agentmail', 'send', '--to', to_csv, '--subject', subject, '--body-file', body_file]
    if backend == 'himalaya':
        return ['himalaya', 'mail', 'send', '--from', frm, '--to', to_csv,
                '--subject', subject, '--body-file', body_file]
    if backend == 'gog':
        return ['gog', 'mail', 'send', '--to', to_csv, '--subject', subject, '--body-file', body_file]
    if backend == 'smtp':
        if not (smtp_cfg or {}).get('host'):
            die("backend=smtp 但未在 config.yaml 配置 smtp.host")
        # 通用 SMTP 走 sendmail 风格不便内联；此处产出 EML 草稿交用户用邮件客户端发送
        return None
    die(f"未知邮件后端：{backend}（可选 agent-mail/himalaya/gog/smtp）")


def main():
    ap = argparse.ArgumentParser(description="PM Master 对外邮件审批门（Communication Send Gate）")
    ap.add_argument('--project', required=True)
    ap.add_argument('--to', required=True, help='收件人：角色名/姓名（解析自 communication.contacts[]）或邮箱，逗号分隔')
    ap.add_argument('--subject', required=True)
    ap.add_argument('--body', help='正文（内联字符串）')
    ap.add_argument('--body-file', help='正文（文件路径，推荐，支持多行）')
    ap.add_argument('--cc', default='', help='抄送，规则同 --to')
    ap.add_argument('--approve', metavar='APPROVER', default=None,
                    help='审批人（如 "张三(PM)"）。requires_send_approval=true 时必填')
    ap.add_argument('--dry-run', action='store_true', help='仅打印+审计，不真正外发')
    ap.add_argument('--config', default=DEFAULT_CONFIG, help='安装期策略文件（默认技能根 config.yaml）')
    a = ap.parse_args()

    # ---- 载入策略与数据 ----
    if not has(a.project):
        die(f"未找到 project.yaml: {a.project}")
    if not has(a.config):
        die(f"未找到安装期配置 config.yaml: {a.config}（请在技能根创建，定义 email.* 策略）")
    data = load(a.project)
    cfg = load(a.config) or {}
    email_cfg = cfg.get('email') or {}
    comm = data.get('communication') or {}

    # ---- 邮件内容 ----
    body = a.body
    if a.body_file:
        if not has(a.body_file):
            die(f"正文文件不存在: {a.body_file}")
        with open(a.body_file, 'r', encoding='utf-8') as f:
            body = f.read()
    if not body or not body.strip():
        die("邮件正文为空（需 --body 或 --body-file）")

    # ---- 护栏 1：能力开关 ----
    if not email_cfg.get('enabled', False):
        die("邮件功能未启用（config.email.enabled=false，安装期禁用）")

    # ---- 收件人解析 ----
    contacts = comm.get('contacts') or []
    to_emails, to_ext = resolve_recipients(a.to, contacts)
    cc_emails, cc_ext = ([], []) if not a.cc else resolve_recipients(a.cc, contacts)
    external_any = any(to_ext) or any(cc_ext)

    # ---- 护栏 2：强制审批 ----
    if email_cfg.get('requires_send_approval', True) and not a.approve:
        die("未经审批，禁止发送（config.email.requires_send_approval=true，须带 --approve <审批人>）")
    # ---- 护栏 3：外部邮件须 sponsor 会签（项目级仅可收紧）----
    ov = comm.get('approval_override') or {}
    if ov.get('require_sponsor_cosign') and external_any:
        if not (a.approve and 'sponsor' in a.approve.lower()):
            die("含外部收件人且 require_sponsor_cosign=true，审批人须含 sponsor（如 \"李四(sponsor)\"）")

    frm = comm.get('from') or email_cfg.get('default_from') or ''
    backend = email_cfg.get('backend', 'agent-mail')
    to_csv = ','.join(to_emails)
    cc_csv = ','.join(cc_emails)

    # ---- 打印草稿（呈现待批/复核）----
    print("=== 邮件草稿（Communication Send Gate）===")
    print(f"发件人 : {frm or '(未配置，使用后端默认)'}")
    print(f"收件人 : {to_csv}")
    if cc_csv:
        print(f"抄送   : {cc_csv}")
    print(f"主题   : {a.subject}")
    print(f"后端   : {backend}  | 审批人: {a.approve or '（无）'}")
    print("---- 正文 ----")
    print(body.strip())
    print("--------------")

    # ---- 审计记录 ----
    gov = data.setdefault('governance', {})
    log = gov.setdefault('communications', [])
    record = {
        'to': to_emails,
        'cc': cc_emails,
        'subject': a.subject,
        'on': datetime.date.today().isoformat(),
        'approved_by': a.approve,
        'backend': backend,
        'status': 'dry-run' if a.dry_run else 'pending',
    }

    # ---- dry-run：仅审计，不发送 ----
    if a.dry_run:
        record['status'] = 'dry-run'
        log.append(record)
        save(a.project, data)
        print("\n⚠ --dry-run：未真正外发；已写审计记录（governance.communications）。")
        sys.exit(0)

    # ---- 实际发送：委派后端 ----
    body_file = None
    try:
        tmp = tempfile.NamedTemporaryFile('w', suffix='.eml', delete=False, encoding='utf-8')
        tmp.write(body)
        tmp.close()
        body_file = tmp.name
        cmd = build_backend_cmd(backend, frm, to_csv, a.subject, body_file,
                                email_cfg.get('smtp'))
        if cmd is None:   # smtp 无 CLI：落盘 EML 草稿，交用户客户端发送
            draft = os.path.join(os.path.dirname(os.path.abspath(a.project)),
                                 'artifacts', f"draft_{a.subject[:20]}_{record['on']}.eml")
            os.makedirs(os.path.dirname(draft), exist_ok=True)
            with open(draft, 'w', encoding='utf-8') as f:
                f.write(f"From: {frm}\nTo: {to_csv}\nCc: {cc_csv}\nSubject: {a.subject}\n\n{body}")
            record['status'] = 'draft-saved'
            record['draft'] = os.path.relpath(draft, os.path.dirname(os.path.abspath(a.project)))
            log.append(record)
            save(a.project, data)
            print(f"\n✓ 已生成 EML 草稿（后端=smtp 无 CLI）：{record['draft']}；请经邮件客户端发送。")
            sys.exit(0)
        # 执行后端命令
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if p.returncode == 0:
            record['status'] = 'sent'
            log.append(record)
            save(a.project, data)
            print(f"\n✅ 邮件已发送（后端={backend}）；审计已写入 governance.communications。")
            sys.exit(0)
        else:
            record['status'] = 'failed'
            record['error'] = (p.stdout + p.stderr).strip()[:500]
            log.append(record)
            save(a.project, data)
            die(f"后端发送失败（{backend} exit={p.returncode}）：{record['error']}")
    except FileNotFoundError:
        record['status'] = 'failed'
        record['error'] = f'未找到后端 CLI：{backend}（请确认对应邮件技能已安装/连接）'
        log.append(record)
        save(a.project, data)
        die(record['error'])
    finally:
        if body_file and os.path.exists(body_file):
            try:
                os.remove(body_file)
            except OSError:
                pass


if __name__ == '__main__':
    main()
