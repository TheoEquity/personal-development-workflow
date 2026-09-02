---
name: managing-change-ledger
description: Use when a personal-workflow change or cursor must be created, queried, advanced, bound to a worktree, or completed in local SQLite.
---

# 管理轻量变更总账

## 职责

SQLite 只保存可恢复状态和必要引用，不复制 Spec、Plan、测试稿或 Git 历史。正式文档由项目仓库保存，代码事实由 Git 保存。

总账记录：

- `change_id`、`flow`、`status` 和可选 `source_ce`；
- 简短目标或完成摘要；
- 可选 `spec_ref`、必需 `code_ref`、可选 `evidence_ref`；
- 工作流的 `define`、`implement`、`verify`、`done` 阶段；
- 活动 CE 的 worktree、仓库身份、Git common directory 和绑定时 HEAD。

Plan 和测试稿不是总账门禁。需要时由 Full 流程生成并在 CE 文档中引用；总账不解析它们的 Markdown 结构。

## 基本命令

统一通过 `scripts/change_ledger.py` 操作，不手写 SQL：

```text
init
next-id
create --flow direct|light|full --summary <text> [--source-ce <CE>]
set-ref <CE> --field spec_ref|code_ref|evidence_ref|change_ref --value <ref>
show <CE>
list [--status in_progress|completed]
complete <CE> --summary <text>
```

工作流游标：

```text
workflow-create --flow direct|light|full
workflow-bind-change <WF> <CE>
workflow-set-stage <WF> define|implement|verify
workflow-bind-worktree <WF> --worktree <path>
workflow-assert-worktree <WF> --worktree <path>
workflow-show <WF>
workflow-list [--state active|closed]
workflow-status <WF>
```

## 门禁

- Light/Full 从 `define` 进入 `implement` 前必须有 `spec_ref`；Direct 不需要。
- 进入 `verify` 前必须已经绑定 Worktree 并写入真实 `code_ref`。
- 完成前必须处于 `verify`，存在 `code_ref`，并提供非空完成摘要。
- `complete` 原子把 CE 标为 completed，并把绑定游标写为 `done/closed`。
- 已完成 CE 和已关闭游标不可修改。

## Worktree 绑定

`workflow-bind-worktree` 从 Git 实际读取顶层、common directory 和 HEAD，并通过项目配置中的 `repositories` 映射稳定仓库名。同一个活动 Worktree 只能有一个绑定。`workflow-assert-worktree` 在写入、测试或提交前复核实际路径和仓库身份；不一致时停止。

Worktree 绑定不等于 Push、MR、部署或删除授权，也不允许从一个路径跳到另一个 checkout。删除 Worktree 前必须先完成或明确终止工作流，并取得用户授权。

## 兼容

初始化旧数据库时保留既有 CE、正式引用和完成状态；旧阶段映射到四阶段。旧 Plan/Test 引用可以作为历史列继续存在，但新流程不再更新或依赖它们。
