# 变更事件登记阶段

只在 `current_stage=register_change` 时完整读取。

## 输入与身份

输入必须是当前对话已经确认的完整“最终总体方案（需求层）”。新需求或来自外部用户、客户、独立测试方、生产使用、已交付功能的反馈建立新事件；当前事件内部 TDD、自测或验收失败继续使用原 `change_id`。

总控调用 `managing-change-ledger next-id` 取得唯一 `change_id`，并把同一值原样用于全部正式材料。子 Skill、Worker 和文件名不得自行生成身份。

## 登记

1. 形成登记版 `changes/<change_id>/change.md`，记录背景、分类、影响范围、Spec 处理和已确认最终总体方案。
2. 保存并提交登记版，取得 `changes/<change_id>/change.md@<完整 Git SHA>` 的 `change_ref`。
3. 创建总账行，并把当前游标一次性绑定到同一 `change_id`。
4. 验证 Git 对象、总账行和绑定身份后，把阶段设为 `writing_spec`，然后立即停止。

`change.md` 登记时创建一次、完成时更新一次。Spec、测试稿、Plan、代码与证据推进时，中间阶段只更新各自的 SQLite 引用，不修改登记版 `change.md` 或 `change_ref`。新事件登记并绑定后固定把阶段设为 `writing_spec`；只有 `spec_ref` 与 `test_ref` 都有效后才能进入 Plan。不得跳过事件直接调用 `writing-specs`。

## 停止信号

- 最终总体方案未由用户确认；
- 事件分类或 `change_id` 不唯一；
- 登记版 Git 引用、总账或游标绑定不一致；
- 正准备在同一轮进入 `writing_spec`，或为内部失败建立新事件。
