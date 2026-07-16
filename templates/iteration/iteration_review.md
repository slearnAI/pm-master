# 迭代评审 · {{ project.name }}

> 迭代结束时向干系人演示成果、说明偏差，并向下迭代传递输入。

- **迭代编号**：{{ iteration.num }}

## 已完成（Completed）
{{#each review.completed}}
- {{this}}
{{/each}}

## 偏差说明（Deviation）
{{ review.deviation }}

## 演示结论（Demo）
{{ review.demo }}

## 下迭代输入（Next Input）
{{#each review.next_input}}
- {{this}}
{{/each}}

> 提示：偏差说明应关联根因，而非仅描述现象。
