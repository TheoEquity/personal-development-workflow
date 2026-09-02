---
name: using-personal-development-workflow
description: Use when the user explicitly opens, resumes, continues, closes, or asks for the status of their personal development workflow.
---

# 使用个人开发工作流

## 目标

用同一套轻量控制面处理小修复、普通功能和从零开发完整系统。工作流只保存任务身份、当前阶段、必要材料和可验证事实；具体实现交给当前强模型完成，不固定角色链、逐步推理方式或多层交接协议。

## 两个独立维度

任务深度：`direct | light | full`。

- `direct`：恢复已有行为的 Bug，或不改变正式行为的局部维护；登记 CE 后实现和验证，不写 Spec 或 Plan。
- `light`：新增或改变明确、低风险的行为；先用 `writing-specs` 写短 Spec，再实现和验证。
- `full`：需求存在重要选择，或涉及架构、公共契约、数据迁移、安全和较大影响面；使用完整 Spec，必要时形成里程碑级 Lean Plan，并按风险启用正式验收。

执行拓扑只有两种：

- **单 Worktree 串行**：默认。Direct、Light 和没有独立并行流的 Full 都只使用一个 Worktree。
- **多 Worktree 并行**：只有两个以上任务能够独立修改、独立验证并在之后串行集成时使用。

任务深度不决定是否并行。Full 可以串行，Direct/Light 也不因为简单而绕过隔离。

## 从零开发完整系统

使用一个长期系统目标维持整体方向，把可独立验收的纵向能力拆成多个纵向 CE。系统级 Spec 保存整体行为、架构边界和关键不变量；每个 CE 只承担当前纵向交付。Plan 只覆盖当前里程碑，不一次展开整个系统的文件级微步骤。

每完成一个纵向 CE，就取得可运行、可验证的系统增量。后续 CE 从最新已验证基线继续。只有真正独立的实现流才启用多 Worktree 并行。

## 可恢复阶段

持久阶段固定为：

```text
define → implement → verify → done
```

- `define`：确认 flow、分配或恢复 CE；Light/Full 形成所需 Spec，Full 必要时形成 Plan。
- `implement`：在绑定 Worktree 中修改代码并运行聚焦检查。
- `verify`：对实际候选代码执行与风险相称的完整验证；必要时使用 `writing-test-drafts`。
- `done`：记录最终摘要和代码引用，关闭活动游标。

需求变化但仍属于同一交付时回到 `define` 更新必要材料；成为新的独立交付时新建 CE。内部测试失败留在原 CE 中修复。

## 启动与恢复

1. 从当前目录向上定位项目配置 `.codex/personal-development-workflow.json`。
2. 使用 `managing-change-ledger workflow-list --state active` 查找活动游标。
3. 若存在唯一活动游标，读取它绑定的 CE、flow、阶段和 Worktree；事实冲突时停止并报告。
4. 若不存在，创建 `define` 阶段游标，选择 flow，并登记最小 CE 摘要。
5. 只加载当前阶段需要的 Skill 或参考文件。

清晰任务直接判断 flow；需求存在实质歧义时才调用 `exploring-and-grilling-requirements`。不得为了显得严谨而强制进行需求拷打。

## Worktree 默认策略

所有代码写入默认在 Worktree 中进行。进入 `implement` 前读取 [worktree-safety.md](references/worktree-safety.md)，绑定并机械核对当前 Worktree。

- 一个活动 CE 默认绑定一个 Worktree。
- 一个 Worktree 同时只有一个写入者。
- 当前已经位于 Codex-managed 或 linked Worktree 时直接复用，不得嵌套创建。
- Reviewer 可以读取固定提交，但不得与实现者并发写同一个 Worktree。
- 测试、构建和代码引用必须来自绑定的同一个 Worktree。
- 命令不得跳转到原始 checkout 或使用硬编码的机器路径。

并行条件满足时才读取 [parallel-delivery.md](references/parallel-delivery.md)。

## 实现与验证

TDD 是按风险选择的方法，不是所有修改的固定仪式。适合稳定复现的 Bug、纯逻辑、算法和关键状态转换时优先测试先行；配置、UI 调整、探索性实现或已有测试充分覆盖时，可以实现后立即验证。

验证始终必需。完成前必须：

1. 确认测试命令在绑定 Worktree 中运行；
2. 记录被验证的实际 `code_ref`；
3. 运行与修改风险相称的聚焦测试和必要回归；
4. 对无法自动化的关键行为给出可复核证据；
5. 如实报告失败、未执行项和环境限制。

Direct/Light 默认使用轻量验证清单。Full 在系统里程碑、迁移、安全、关键数据流程或用户要求逐项验收时，按需调用 `writing-test-drafts`；正式验收不是 Full 的无条件门禁。

## 权限边界

本地读取、编辑、测试和本次 CE 范围内的本地 commit 属于正常实现动作。Push、创建或合并 MR/PR、部署、删除 Worktree、删除远端分支以及其他外部写入仍需用户明确授权。旧对话、Plan、总账状态和用户沉默不能替代授权。

## 完成输出

完成版 CE 只记录：问题或目标、最终行为、主要修改、验证结果、`code_ref` 和必要证据。详细实现由 Git 保存，不重复生成最终逻辑稿。完成后的新需求或外部 Bug 建立新 CE，并可用 `source_ce` 关联历史。

## 停止条件

- 需求歧义会改变用户可观察行为且无法安全判断；
- Worktree 身份、绑定 CE、仓库或实际命令目录不一致；
- 发现另一个写入者正在使用同一 Worktree；
- 修改范围扩大到新的独立交付；
- 验证失败或关键步骤无法执行；
- 即将执行尚未授权的远端、部署或删除操作。
