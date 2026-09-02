# Worktree 安全合同

Worktree 是代码写入的默认隔离层。它隔离工作目录和 index，但不自动隔离 Git refs、端口、数据库、Docker project、系统临时目录或仓库外路径。

## 建立绑定

进入实现前，使用总账的 `workflow-bind-worktree` 从实际路径读取并保存：

- `change_id`；
- 稳定仓库名；
- Worktree 根目录；
- Git common directory；
- 绑定时完整 HEAD。

同一个活动 Worktree 不得绑定多个工作流。已经在 linked/Codex-managed Worktree 时复用当前目录，不再创建第二层 Worktree。

## 写入前检查

每个会修改文件、暂存、提交、构建或测试的执行单元先调用 `workflow-assert-worktree`。检查必须证明：

1. 实际 Git 顶层等于绑定的 Worktree 根目录；
2. 实际 Git common directory 等于绑定仓库；
3. 当前活动工作流仍绑定同一 CE；
4. Worktree 没有被另一个活动写入者绑定；
5. 命令工作目录位于该 Worktree 内。

失败时停止，不通过 `cd`、绝对路径或复制文件绕过检查。

## 运行时隔离

只有项目实际使用共享运行资源时才配置额外隔离：不同端口、数据库文件或 schema、Docker Compose project、日志/PID 目录。Worktree 所需的 ignored 配置使用 `.worktreeinclude` 明确复制；不要把 tracked 文件列入其中，也不要把凭据写入仓库。

## 完成

测试和代码引用必须来自同一个绑定 Worktree。完成集成后关闭工作流，释放绑定；删除 Worktree 仍需要用户明确授权。
