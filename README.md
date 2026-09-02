# Personal Development Workflow

这是一个面向 Codex 的轻量个人开发工作流。它用同一套控制面处理小修复、普通功能和从零开发完整系统，并把过程约束集中在少数真正需要持久化或机械验证的边界上。

## 核心结构

任务深度使用 `direct / light / full`：

- `direct`：恢复已有行为或局部维护，直接实现和验证；
- `light`：明确、低风险的行为变化，先写短 Spec；
- `full`：架构、公共契约、数据、安全或大范围变化，使用完整 Spec，必要时增加里程碑 Plan 和正式验收。

执行拓扑独立选择：

- **单 Worktree 串行**：默认，一个 CE 从定义到验证都在同一个 Worktree 完成；
- **多 Worktree 并行**：只有两个以上实现流能够独立修改、独立验证时启用。

Full 不自动等于并行，Direct/Light 也不绕过代码隔离。

## 工作流

```text
选择 direct / light / full
→ 创建或恢复 CE
→ 创建并绑定 Worktree
→ 必要时写 Spec 和里程碑 Plan
→ 实现
→ 在同一 Worktree 验证实际候选
→ 记录完成摘要和 code_ref
```

持久阶段只有：

```text
define → implement → verify → done
```

阶段用于跨会话恢复，不记录模型内部推理、TDD 子步骤、临时 reviewer 或聊天确认状态。

## Worktree 防串

所有代码修改默认在 Worktree 中进行。

- 一个活动 CE 默认绑定一个 Worktree；
- 一个 Worktree 同时只有一个写入者；
- 已经位于 linked/Codex-managed Worktree 时不得嵌套创建；
- 测试、构建、提交和 `code_ref` 必须来自绑定的同一个 Worktree；
- Worktree 根目录、Git common directory、稳定仓库名和绑定时 HEAD 由总账脚本读取并保存；
- 写入、测试和提交前可以用 `workflow-assert-worktree` 机械复核；
- 多个 Agent 不得并发写入同一个 Permanent Worktree。

Worktree 不隔离端口、数据库、Docker project 和仓库外目录。项目使用这些共享资源时，应按 Worktree 分配独立 namespace。ignored 但运行必需的文件使用 `.worktreeinclude` 明确复制。

## 从零开发完整系统

完整系统使用一个长期目标保持整体方向，由系统级 Spec 保存架构边界和关键不变量，再拆成多个可独立验收的纵向 CE。每个 CE 交付一个可运行增量，后续从最新已验证基线继续。

Plan 只覆盖当前里程碑。只有真正独立的实现流才创建 Worker Worktree；开发可以并行，集成必须串行。

## Spec 和验收

- Direct 不写 Spec；
- Light 使用包含问题、触发、期望行为、范围和完成条件的短 Spec；
- Full 使用与风险相称的完整行为和架构合同；
- 正式验收按需启用，适用于系统里程碑、迁移、安全、关键数据流程或用户明确要求逐项验收的场景；
- 其他任务使用轻量验证清单，但验证始终必需。

TDD 是按问题选择的方法，不是统一门禁。适合稳定复现的 Bug、核心逻辑和关键状态转换时优先测试先行；无论采用什么开发方法，完成前都必须运行真实验证。

## 总账

项目配置示例位于 `examples/personal-development-workflow.json.example`。SQLite 保存：

- CE 身份、flow、状态、来源和摘要；
- 可选 Spec/证据引用与实际代码引用；
- 四阶段游标；
- Worktree 与仓库绑定。

Plan 和测试稿可以作为 Full 的项目材料，但不是总账的固定字段门禁。已完成 CE 和已关闭游标不可修改。旧数据库初始化时会保留历史引用，并把旧阶段映射到四阶段。

## Skill

- `using-personal-development-workflow`：薄总控和路由；
- `managing-change-ledger`：CE、阶段和 Worktree 绑定；
- `exploring-and-grilling-requirements`：按需处理实质歧义和高风险选择；
- `writing-specs`：Light/Full 行为合同；
- `writing-test-drafts`：按需正式验收。

## 全局 Skill 触发范围

`config/global-skill-trigger-overrides.json` 保存七个可选外部 Skill 的轻量触发描述，覆盖 TDD、系统化调试、详细计划、代码审查、并行 Agent、Subagent 开发和计划执行。普通任务不再仅因为属于功能、Bug、多步骤或待合并状态而自动进入这些重流程；只有用户明确要求，或 Full/高风险任务满足配置中的条件时才触发。

安装器只修改目标 Skill 的 `description`，不复制或接管它们的执行正文。目标 Skill 未安装时直接跳过；修改前的 `SKILL.md` 会进入 `.personal-development-workflow-backups`。因此这些覆盖是可恢复的全局集成，不是五个自有 Skill 的运行依赖。

## 权限

本地读取、编辑、测试和当前 CE 范围内的本地 commit 属于正常实现动作。Push、MR/PR、部署、删除 Worktree、删除远端分支和其他外部写入仍需用户明确授权。

安装、测试和可选外部能力见 [DEPENDENCIES.md](DEPENDENCIES.md)。
