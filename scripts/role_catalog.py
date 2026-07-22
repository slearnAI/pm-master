#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Master · 领域 + 专家角色目录（单一事实源 / single source of truth）

设计目标
--------
1. **域无关（domain-agnostic）**：开箱即用的默认不再偏向数据域。任何技术项目
   （软件研发 / 云与基础设施 / 数据平台 / AI·ML / 安全 / 产品 / 测试 / 集成 / ERP / BI）
   都能从本目录取得合适的专家角色。
2. **从合同/SOW 抽取自动对齐**：`infer_domain(text)` 从 SOW/合同文本推断技术域；
   `infer_role(name, domain)` 结合域专属关键词 + 跨域关键词给出角色；
   `align_from_sow(spec)` 输出整份 SOW 的 {domain, product, role 建议}，供
   `parse_sow.py` 写入、供 `dispatch.py` / `consistency_check.py` 复用。
3. **单一事实源**：`dispatch.py` 与 `consistency_check.py` 共享本文件，消除漂移。

角色 ID 采用「能力（capability）」命名，跨域通用；域特化名在 `role_labels` 中生成，
由 `specialize()` 按 project.domain / project.product 代入，绝不硬编码客户/厂商标识。
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# 跨域角色（适用于任意技术域）
# ---------------------------------------------------------------------------
CROSS_ROLES = {
    'ba': ['需求', '用户故事', '规格', 'requirement', 'story', 'brd', 'prd', '需求分析'],
    'qa-lead': ['测试', 'uat', '质量', 'test', 'quality', 'qa'],
    'change-manager': ['变更', 'ccb', 'change', '影响评估', 'change control'],
    'solution-architect': ['蓝图', '集成', '方案', 'blueprint', 'integration', 'solution',
                            '架构设计', 'architecture', '总体设计'],
    'enablement-lead': ['培训', '赋能', '课程', 'training', 'enable', '知识转移', 'kt'],
    'infra-engineer': ['基础设施', '安装', '环境', 'infra', 'install', 'env', '部署', '容量规划',
                        'capacity'],
    'domain-sme': ['sme', '业务知识', '源系统', '领域支持', '业务规则', '业务顾问'],
    'project-manager': ['项目经理', 'pmo', '进度管理', '沟通计划', 'stakeholder mgmt'],
}

# ---------------------------------------------------------------------------
# 技术域目录
# 每个域：keywords（域识别信号）、roles（{role_id: [关键词]}）、
#         role_labels（{role_id: 特化名模板，支持 {domain}/{product}}）
# ---------------------------------------------------------------------------
DOMAINS = {
    'data-platform': {
        'keywords': ['数据湖', '数仓', 'datalake', 'data lake', 'data warehouse', 'warehouse',
                      'etl', '数据建模', '数据迁移', '主数据', '元数据', '血缘',
                      'data platform', 'lakehouse', '数据管道'],
        'roles': {
            'data-architect': ['建模', '模型', '主题域', 'schema', 'erd', '数据模型',
                                'datamodel', 'logical model', '物理模型'],
            'etl-engineer': ['迁移', '历史加载', '抽取', 'etl', '加载', '接入', 'migration',
                              'load', 'pipeline', '数据管道'],
            'data-governance-lead': ['治理', '元数据', '血缘', '审计', 'governance', 'meta',
                                      'audit', '主数据管理', 'mdm'],
            'data-security-engineer': ['脱敏', '掩码', '隐私', 'pii', '令牌', '加密', 'mask',
                                        'privacy', '合规'],
            'data-scientist': ['分析', '特征', 'ml', 'modelops', '用例', 'analytic', '统计分析'],
        },
        'role_labels': {
            'data-architect': '{domain} 数据架构师',
            'etl-engineer': '{domain} ETL/数据工程师',
            'data-governance-lead': '{domain} 数据治理负责人',
            'data-security-engineer': '{domain} 数据安全/合规工程师',
            'data-scientist': '{domain} 数据分析/建模工程师',
        },
    },
    'software-dev': {
        'keywords': ['软件开发', '应用开发', '后端', '前端', '微服务', 'software',
                      'application development', 'backend', 'frontend', 'microservice',
                      'app development', '应用系统'],
        'roles': {
            'software-architect': ['架构设计', '模块设计', '模块划分', 'architecture', '系统设计'],
            'backend-engineer': ['后端', '服务端', 'backend', 'api 实现', 'service 实现'],
            'frontend-engineer': ['前端', '界面', 'frontend', 'web', 'ui 实现'],
            'fullstack-engineer': ['全栈', 'fullstack', 'full stack'],
            'mobile-engineer': ['移动端', 'mobile', 'ios', 'android', 'app 端'],
        },
        'role_labels': {
            'software-architect': '{domain} 软件架构师',
            'backend-engineer': '{domain} 后端工程师',
            'frontend-engineer': '{domain} 前端工程师',
            'fullstack-engineer': '{domain} 全栈工程师',
            'mobile-engineer': '{domain} 移动端工程师',
        },
    },
    'cloud-infra': {
        'keywords': ['云', 'cloud', 'kubernetes', 'k8s', 'terraform', '容器', '容器化', 'iac',
                      'infrastructure as code', 'aws', 'azure', 'gcp', '私有云', '云原生'],
        'roles': {
            'cloud-architect': ['云架构', '云方案', 'cloud architecture', '云蓝图'],
            'sre-engineer': ['可靠性', 'sre', '稳定性', '可用性', 'oncall', '容灾'],
            'platform-engineer': ['平台工程', 'platform', '内部平台', 'devops 平台'],
            'devops-engineer': ['devops', 'ci/cd', '流水线', '自动化部署', 'pipeline 工程'],
            'network-engineer': ['网络', 'network', 'vpc', 'dns', '负载均衡', 'lb'],
        },
        'role_labels': {
            'cloud-architect': '{domain} 云架构师',
            'sre-engineer': '{domain} SRE 工程师',
            'platform-engineer': '{domain} 平台工程师',
            'devops-engineer': '{domain} DevOps 工程师',
            'network-engineer': '{domain} 网络工程师',
        },
    },
    'ai-ml': {
        'keywords': ['大模型', 'llm', '机器学习', 'machine learning', 'ai', '深度学习',
                      'deep learning', '模型训练', '推理', 'inference', 'genai', '生成式'],
        'roles': {
            'ml-engineer': ['模型训练', '特征工程', 'ml', '机器学习', 'model training', '建模'],
            'llm-engineer': ['大模型', 'llm', 'prompt', 'rag', '微调', 'fine-tune', '推理优化'],
            'mlops-engineer': ['mlops', '模型部署', '模型监控', 'model serving', '模型上线'],
            'ai-product-manager': ['ai 产品', 'ai product', '算法产品', '模型产品'],
            'data-scientist': ['分析', '特征', '用例', 'analytic', '统计分析'],
        },
        'role_labels': {
            'ml-engineer': '{domain} ML 工程师',
            'llm-engineer': '{domain} 大模型/LLM 工程师',
            'mlops-engineer': '{domain} MLOps 工程师',
            'ai-product-manager': '{domain} AI 产品经理',
            'data-scientist': '{domain} 数据科学工程师',
        },
    },
    'cybersecurity': {
        'keywords': ['安全', 'security', '渗透', 'pentest', '攻防', '合规安全', '零信任',
                      'zero trust', 'vulnerability', '漏洞', '等保'],
        'roles': {
            'security-engineer': ['安全设计', '安全加固', 'security', '防护', 'hardening', '安全架构'],
            'privacy-engineer': ['隐私', 'pii', '脱敏', 'privacy', '个保', 'gdpr', 'pipl', '数据合规'],
            'secops-engineer': ['安全运营', 'soc', 'siem', '威胁检测', 'incident', '应急响应'],
            'appsec-engineer': ['应用安全', 'appsec', '代码安全', 'sast', 'dast'],
        },
        'role_labels': {
            'security-engineer': '{domain} 安全工程师',
            'privacy-engineer': '{domain} 隐私/合规工程师',
            'secops-engineer': '{domain} 安全运营工程师',
            'appsec-engineer': '{domain} 应用安全工程师',
        },
    },
    'product': {
        'keywords': ['产品', 'product', 'roadmap', '产品规划', '需求管理', 'backlog 规划',
                      '产品策略'],
        'roles': {
            'product-manager': ['产品规划', 'roadmap', 'product', '商业分析', '产品策略'],
            'product-owner': ['po', 'backlog', '产品待办', '产品负责人'],
            'ux-designer': ['用户体验', 'ux', 'ui 设计', '交互', '原型'],
        },
        'role_labels': {
            'product-manager': '{domain} 产品经理',
            'product-owner': '{domain} 产品负责人(PO)',
            'ux-designer': '{domain} 体验/交互设计师',
        },
    },
    'qa': {
        'keywords': ['质量', 'quality', '测试工程', '自动化测试', '性能测试', 'qa engineering'],
        'roles': {
            'qa-engineer': ['测试', 'test', '测试用例', 'uat', '功能测试'],
            'test-automation-engineer': ['自动化测试', 'test automation', 'selenium', '自动化框架'],
            'performance-engineer': ['性能测试', 'performance', '压测', '负载测试'],
        },
        'role_labels': {
            'qa-engineer': '{domain} 测试工程师',
            'test-automation-engineer': '{domain} 自动化测试工程师',
            'performance-engineer': '{domain} 性能测试工程师',
        },
    },
    'integration': {
        'keywords': ['集成', 'integration', 'esb', '中间件', 'middleware', 'api 网关',
                      'api gateway', '消息队列', '对接'],
        'roles': {
            'integration-engineer': ['集成', 'esb', '中间件', '对接', 'interface', '系统对接'],
            'api-engineer': ['api 设计', 'api 网关', 'api gateway', '接口', 'api 实现'],
        },
        'role_labels': {
            'integration-engineer': '{domain} 集成工程师',
            'api-engineer': '{domain} API 工程师',
        },
    },
    'erp': {
        'keywords': ['erp', 'sap', 'oracle ebs', '财务系统', 'hr 系统', '企业资源',
                      'enterprise resource', '财务模块'],
        'roles': {
            'erp-consultant': ['erp 实施', 'erp 咨询', 'sap', '业务流程', 'erp blueprint'],
            'erp-developer': ['erp 开发', 'abap', '二次开发', '表单开发'],
            'erp-functional': ['erp 功能', '财务模块', 'hr 模块', '功能顾问'],
        },
        'role_labels': {
            'erp-consultant': '{domain} ERP 实施顾问',
            'erp-developer': '{domain} ERP 开发工程师',
            'erp-functional': '{domain} ERP 功能顾问',
        },
    },
    'biz-analytics': {
        'keywords': ['bi', '商业智能', 'business intelligence', '报表平台', '数据分析平台',
                      '看板', 'dashboard 平台'],
        'roles': {
            'bi-engineer': ['报表', 'dashboard', 'bi', '可视化', 'olap', '看板'],
            'analytics-engineer': ['分析工程', 'analytics engineering', '指标', 'metrics', '指标体系'],
        },
        'role_labels': {
            'bi-engineer': '{domain} BI/报表工程师',
            'analytics-engineer': '{domain} 分析工程师',
        },
    },
}

# 通用/中立回退（难以消歧的词 -> 中立角色，避免偏向数据域）
GLOBAL_FALLBACK = {
    'model': 'solution-architect', '建模': 'solution-architect',
    'design': 'solution-architect', '设计': 'solution-architect',
    '开发': 'software-architect', 'develop': 'software-architect',
}

PM_GENERALIST = {'planner', 'scheduler', 'risk', 'stakeholder', 'reporter', 'program',
                 'project-manager'}

# 向后兼容：仅当用户 project.domain 精确等于以下已知域时才启用特化名，
# 不再作为「默认」偏向数据域。新项目默认走上方 DOMAINS 的 role_labels 或
# 中性回退 role（domain）。
LEGACY_SPECIALIZATION = {
    'insurance-data-lake': {
        'data-architect': '保险主题域数据架构师',
        'etl-engineer': 'MPP 数仓 TPT/ETL 工程师',
        'data-security-engineer': '个保法/PII 合规工程师',
        'data-scientist': '保险精算/分析建模工程师',
        'governance-lead': '保险数据治理与审计负责人',
        'dr-bcp-engineer': '保险 BC/DR 工程师',
        'infra-engineer': 'MPP 数仓/平台工程师',
    },
    'payments': {
        'data-architect': '支付领域架构师',
        'etl-engineer': '支付 ETL 工程师',
        'data-security-engineer': 'PCI-DSS 安全工程师',
        'data-scientist': '反欺诈/风控建模工程师',
    },
    'ecommerce': {
        'data-architect': '电商域建模师',
        'data-scientist': '推荐/搜索 ML 工程师',
        'etl-engineer': '电商数据工程师',
    },
    'fintech-core': {
        'data-architect': '核心银行领域架构师',
        'etl-engineer': '账务/清算工程师',
        'data-security-engineer': '监管报送工程师',
    },
}


# ---------------------------------------------------------------------------
# 核心函数
# ---------------------------------------------------------------------------
def list_domains():
    return list(DOMAINS.keys())


def infer_domain(text):
    """从 SOW/合同文本推断技术域。无信号返回 'generic'。"""
    if not text:
        return 'generic'
    t = text.lower()
    best, best_score = 'generic', 0
    for dk, d in DOMAINS.items():
        score = sum(1 for kw in d['keywords'] if kw.lower() in t)
        if score > best_score:
            best, best_score = dk, score
    return best if best_score > 0 else 'generic'


def infer_role(name, domain=None, explicit_role=None):
    """推断工作包角色。优先级：显式 role > 域专属关键词 > 跨域关键词 > 全局中立回退 > None。"""
    if explicit_role:
        return explicit_role
    n = (name or '').lower()
    dom = (domain or '').lower()
    if dom in DOMAINS:
        for rid, kws in DOMAINS[dom]['roles'].items():
            if any(k in n for k in kws):
                return rid
    for rid, kws in CROSS_ROLES.items():
        if any(k in n for k in kws):
            return rid
    for k, rid in GLOBAL_FALLBACK.items():
        if k in n:
            return rid
    return None


def is_domain_activity(role, name, domain):
    if role in PM_GENERALIST:
        return False
    if role:
        return True
    n = (name or '').lower()
    if any(k in n for _, kws in CROSS_ROLES.items() for k in kws):
        return True
    for d in DOMAINS.values():
        if any(k in n for kws in d['roles'].values() for k in kws):
            return True
    if domain:
        return True
    return False


def specialize(role, domain, product):
    """生成领域特化的专家名（域无关，不出现客户/厂商标识）。"""
    if not role:
        return None
    d = DOMAINS.get(domain)
    if d and role in d.get('role_labels', {}):
        return d['role_labels'][role].format(domain=domain or '', product=product or '')
    # 向后兼容：仅精确匹配用户既有项目域时启用旧特化名
    if domain in LEGACY_SPECIALIZATION and role in LEGACY_SPECIALIZATION[domain]:
        return LEGACY_SPECIALIZATION[domain][role]
    if product:
        return f"{role}（{product}）"
    if domain and domain != 'generic':
        return f"{role}（{domain}）"
    return role


def align_from_sow(spec):
    """从 SOW 理解记录(spec dict) 抽取 domain + product + 每个包的推荐 role。
    返回 {domain, product, default_role, pkg_roles:{id:role_id}}。
    """
    text = " ".join([
        str(spec.get('objective', '') or ''),
        str(spec.get('scope', '') or ''),
        str(spec.get('out_of_scope', '') or ''),
        " ".join(str(x) for x in (spec.get('assumptions', []) or [])),
        " ".join(str(x) for x in (spec.get('roles', []) or [])),
    ])
    domain = spec.get('domain') or infer_domain(text)
    product = spec.get('product') or spec.get('name')
    # 显式角色（保留 spec 中明确给出的角色）
    pkg_roles = {}
    for r in (spec.get('roles') or []):
        if isinstance(r, dict):
            pkg_roles[r.get('id')] = r.get('role')
    return {
        'domain': domain,
        'product': product,
        'default_role': 'solution-architect' if domain in (None, 'generic') else None,
        'pkg_roles': pkg_roles,
    }


if __name__ == '__main__':
    # 简易自测
    samples = {
        '数据湖建模与 ETL 迁移': 'data-platform',
        '微服务后端与前端应用开发': 'software-dev',
        'Kubernetes 容器化与 Terraform 云架构': 'cloud-infra',
        '大模型 RAG 与模型训练': 'ai-ml',
        '渗透测试与零信任安全加固': 'cybersecurity',
        '产品 roadmap 与 backlog 规划': 'product',
        '自动化测试与性能压测': 'qa',
        'SAP ERP 财务模块实施': 'erp',
        'BI 报表与指标体系': 'biz-analytics',
    }
    for txt, exp in samples.items():
        got = infer_domain(txt)
        print(f"[{'OK' if got == exp else 'XX'}] {txt!r:40} -> {got} (expect {exp})")
    print("role infer (数据湖逻辑模型, data-platform):",
          infer_role('逻辑模型设计', 'data-platform'))
    print("role infer (后端服务实现, software-dev):",
          infer_role('后端 API 实现', 'software-dev'))
    print("specialize (data-architect, data-platform, 客户数仓):",
          specialize('data-architect', 'data-platform', '云数仓'))
