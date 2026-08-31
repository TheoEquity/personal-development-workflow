# 外部依赖

本仓库拥有并发布六个定制 Skill；下列 Superpowers Skill 是外部只读依赖。本仓库只记录依赖名称，不复制、不修改或重新发布其源码。

## 直接与条件依赖

- `writing-lean-plans`：编写唯一支持的正式 Lean Plan、执行独立计划 review 和交接。
- `using-git-worktrees`：在 SDD 明确开启后创建或确认隔离 worktree。
- `subagent-driven-development`：在一个 Full 实现 Worker 中按已采用 Lean Plan 连续执行默认 1–3 个垂直 Task，并保留逐 Task review 与最终整体 review。
- `executing-plans`：用户另行选择非 SDD 执行方式时使用。
- `test-driven-development`：定义 RED、GREEN、REFACTOR 与证据门禁。
- `verification-before-completion`：完成声明前取得新鲜验证证据。
- `finishing-a-development-branch`：事件完成后、用户另行授权集成时使用；个人工作流不会自动调用。

## 安装约定

在 Codex 中，可以从受信任的插件目录安装 Superpowers 插件 `superpowers@openai-curated-remote`，也可以使用 Superpowers 官方上游提供的等价安装方式。本仓库不代替这些来源，也不从未知地址下载依赖。

安装器在目标 Skill 根目录检查每个依赖目录及其 `SKILL.md`，并核对 YAML frontmatter 的 `name` 与所需依赖名称完全一致。任一依赖缺失或身份不一致时，安装器会列出缺口并停止，不下载替代副本，也不先安装部分定制 Skill。

当前 Superpowers Skill 分发不向本仓库提供统一的可锁定版本号，因此这里不伪造版本约束。依赖版本和更新由其原始安装渠道维护；安装完成后必须运行本仓库完整测试确认合同兼容。本仓库不冻结或 vendoring 这些外部源码，也不固定其内部角色使用的具体模型或推理档位。
