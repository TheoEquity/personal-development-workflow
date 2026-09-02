# 并行 Delivery

只有两个以上实现流能够独立修改、独立验证且没有未集成依赖时才启用。

## 拓扑

- 一个 Delivery Worktree 保存当前集成候选；
- 每个并行写入者使用独立 Worker Worktree；
- 一个 Worker Worktree 只绑定一个活动 CE 或一个明确的独立交付；
- Reviewer 默认只读固定 SHA，不成为额外写入者；
- 开发可以并行，集成始终串行。

## 集成

Worker 从 Delivery 的最新已验证 SHA 开始。完成后记录 Worker HEAD 和验证结果，在临时候选上串行合入并重新运行受影响验证。冲突、验证失败或 Delivery 基线已经移动时停止，不自动覆盖或扩大范围。

串行任务不得为了套用本文件而创建 Delivery + Worker 两层 Worktree。
