# RACI 责任分配矩阵 · {{ project.name }}

> RACI 矩阵（Responsible 执行 / Accountable 负责 / Consulted 咨询 / Informed 告知）厘清每项活动由谁执行、谁担责、需咨询谁、需告知谁，避免职责不清与决策真空。

| 活动 | 执行(R) | 负责(A) | 咨询(C) | 告知(I) |
|------|---------|---------|---------|---------|
{{#each raci}}
| {{this.activity}} | {{this.responsible}} | {{this.accountable}} | {{this.consulted}} | {{this.informed}} |
{{/each}}

_生成于 PM Master · RACI 矩阵模板_
