# 需求讨论阶段

只在 `current_stage=requirement_discussion`、`research` 或 `prototype` 时完整读取。本阶段只决定需求，不读取后续阶段规则或正式项目 Markdown。

## 需求讨论

每个新需求或外部反馈都使用 `exploring-and-grilling-requirements`。输入看起来完整、已有实现、用户要求跳过或时间紧，都不能让总控替代该 Skill 作出清晰度判定；个人工作流中不改用普通 `brainstorming`。

只读取用户输入和决定目标、触发、行为、输出、状态或边界所必需的产品事实。不得读取 Worker 合同、执行合同、规划规则、TDD 规则、验收规则、branch finishing、集线或 worktree 回收规则，也不得读取尚未建立的正式材料正文。

没有实质未决项时直接生成行为校验和；存在会改变用户可观察行为或边界的未决项时，才发散 2–3 个方向并使用决策包 Grill。frontier 为空后完整打印“最终总体方案（需求层）”，至少整合：

- 功能目标；
- 用户场景与触发；
- 总体行为、输出与状态变化；
- 边界和行为校验和。

打印后输出“阶段状态：等待确认”，确认前保持 `current_stage=requirement_discussion` 并停止。状态卡摘要不能代替已确认的最终总体方案。只有用户在当前对话明确确认刚展示的完整方案，且讨论 Skill 输出“阶段状态：已完成”后，确认后才把 `current_stage` 更新为 `register_change`；更新后立即停止，不在同一轮登记事件。

## Research 与 Prototype

外部事实未知且会影响契约或范围时建议 Research；交互、复杂状态或陌生服务必须经体验或实验才能决定时建议 Prototype。两者不是总账正式材料，其结论返回需求讨论并纳入最终总体方案。

进入发现活动时把阶段设为 `research` 或 `prototype` 并停止；下一轮只加载本 reference 和已获授权的发现能力。Prototype 修改任何文件前必须取得具体授权，并与正式实现隔离。发现结束后返回 `requirement_discussion` 并停止；方案仍须完整打印和确认。

## 停止信号

- 正准备因为需求简单、时间紧或用户催促而跳过专用讨论 Skill；
- 最终总体方案尚未完整打印或未确认，却准备登记事件；
- 正准备加载或引用任一后续阶段规则、讨论稿以外的正式材料，或开始实现；
- Research/Prototype 结论未返回最终总体方案，或 Prototype 未授权写入。
