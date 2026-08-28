# 变更事件登记阶段

只在 `current_stage=register_change` 时完整读取。

## 输入与身份

输入必须是当前对话已经确认的完整“最终总体方案（需求层）”。新需求或来自外部用户、客户、独立测试方、生产使用、已交付功能的反馈建立新事件；当前事件内部 TDD、自测或验收失败继续使用原 `change_id`。

总控调用 `managing-change-ledger next-id` 取得唯一 `change_id`，并把同一值原样用于全部正式材料。子 Skill、Worker 和文件名不得自行生成身份。

## 登记

1. 形成登记版 `changes/<change_id>/change.md`，记录背景、分类、影响范围、Spec 处理和已确认最终总体方案；新 Bug 来自已完成 CE 时增加 `source_ce`，但不修改旧 CE。`source_ce` 没有来源时写 `null`，完成版必须原样保留。
2. 保存并提交登记版，取得 `changes/<change_id>/change.md@<完整 Git SHA>` 的 `change_ref`。
3. 创建总账行，并把当前游标一次性绑定到同一 `change_id`。`flow` 只写入 `workflow_state`，不复制到不可变登记版 `change.md`。
4. 验证 Git 对象、总账行和绑定身份后按 `flow` 进入下一门禁：`direct → tdd_coding`，`light/full → writing_spec`，然后按 `review_mode` 决定停止或继续。

`change.md` 登记时创建一次、完成时更新一次。Spec、测试稿、Plan、代码与证据推进时，中间阶段只更新各自的 SQLite 引用，不修改登记版 `change.md` 或 `change_ref`。`direct` 不调用 `writing-specs`；`light` 只有 `spec_ref` 有效后才能进入编码；`full` 只有 `spec_ref` 与 `test_ref` 都有效后才能进入 Plan。不得跳过事件直接生成材料或编码。

## 停止信号

- 最终总体方案未由用户确认；
- 事件分类或 `change_id` 不唯一；
- 登记版 Git 引用、总账或游标绑定不一致；
- 正准备在同一轮进入 `writing_spec`，或为内部失败建立新事件。
