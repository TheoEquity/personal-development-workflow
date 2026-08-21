# Stage Worker Contract

本文件是个人工作流中 Spec Worker、Plan Worker 和 Implementation Coordinator 的统一上下文隔离与交接合同。阶段内容仍由各自 Skill 拥有；本合同只定义谁调用、输入如何冻结、完整结果保存在哪里，以及主 Agent 如何安全消费。

## 角色和阶段

| `stage` | `role` | 内容 Skill |
|---|---|---|
| `writing_spec` | `spec_worker` | `writing-specs`，确认后调用 `writing-test-drafts` |
| `writing_plan` | `plan_worker` | 已选择的 `writing-lean-plans` 或 `writing-plans`，以及对应独立 reviewer |
| `implementation` | `implementation_coordinator` | `subagent-driven-development` |

阶段 Worker 不是新的工作流、变更事件、游标、正式材料类型或权限来源。它们不得修改 SQLite；`workflow_id`、`change_id`、用户确认、正式材料采用、总账写入和阶段推进始终由主 Agent 负责。

## 新鲜上下文

- 每个阶段派发一个新的 Worker；Plan Worker 不复用 Spec Worker，Implementation Coordinator 不复用 Plan Worker。
- 平台支持时使用 `fork_turns=none`。不得继承完整主会话，也不得粘贴累计聊天记录、代码搜索输出或上一个阶段的推理过程。
- 派发只包含角色模板、当前 `workflow_id`、`change_id`、绝对配置路径、正式材料路径与不可变引用、当前阶段所需基线和已经确认的决策。
- 下一阶段直接读取正式材料，不读取上一 Worker 的聊天记录。用户要求修改候选时，只传确认的修改项和原 handoff 路径。
- Plan 基线确认后，为了让 writer 和 reviewer 读取同一精确 Git tree，可以创建或复用**规划用只读 worktree**；它不允许编辑、测试生成、commit 或后续实现，也不获得 SDD 权限。SDD 明确开启后仍须按执行合同另行创建或验证开发 worktree。

## 持久工作区

使用 `scripts/stage_worker_handoff.py init` 创建：

```text
<spec_vault>/.local/stage-workers/<workflow_id>/<change_id>/<stage>/
└─ run-<input_fingerprint>/
   ├─ handoff.json
   ├─ handoff.lock
   ├─ candidate.md
   ├─ report.md
   ├─ authorization-offer.json   # 仅 Implementation
   └─ execution-contract.json    # 仅 Implementation
```

完整内容写入文件，并按阶段区分：Spec 的 `candidate.md` 保存完整待确认草案；Plan 的 `candidate.md` 是候选清单，只记录精确的不可变候选 `plan_ref`、profile、基线和 review 结果，Plan 正文位于该 Git 引用指向的 `plans/<change_id>.md`；Implementation 的 `candidate.md` 保留不用。Plan 在 reviewer、主 Agent 和用户三重门禁完成前只是**待采用候选**，即使已经形成 Spec Vault Git 引用也不是总账中的正式 Plan。长调查、完整 review 和执行历史写 `report.md`，身份和短结果写 `handoff.json`。

`handoff.json.summary` 必须包含阶段结论；Plan 还要列出 review 结论及全部简短**非阻塞建议**，`blockers` 只保存未解决阻塞。完整报告默认不灌回主 Agent；出现异常、用户明确要求审计或短摘要无法支撑决策时，主 Agent 才按需读取 `report.md`。Worker 在聊天中只返回短交接：

```text
状态：<status>
交接文件：<absolute handoff.json>
候选或报告：<absolute path>
待决策：<无或简短列表>
阻塞：<无或简短列表>
```

不得把完整候选、调查日志、diff、review 报告或逐任务历史直接返回主 Agent。主 Agent 在需要审核时只读取对应文件一次。

## Handoff 身份

`handoff.json` 固定包含：

```json
{
  "schema_version": 2,
  "config_path": "<absolute current config>",
  "spec_vault": "<absolute vault>",
  "workflow_id": "<workflow_id>",
  "change_id": "<change_id>",
  "stage": "<writing_spec | writing_plan | implementation>",
  "role": "<spec_worker | plan_worker | implementation_coordinator>",
  "status": "<status>",
  "revision": 0,
  "input_refs": {},
  "candidate_path": "<absolute path>",
  "report_path": "<absolute path>",
  "candidate_sha256": null,
  "authorization_offer_path": null,
  "execution_contract_path": null,
  "authorization_offer_sha256": null,
  "execution_contract_sha256": null,
  "artifact_ref": null,
  "review_status": null,
  "summary": [],
  "needs_user_decision": [],
  "blockers": []
}
```

其中 `schema_version` 当前为 `2`。当前配置路径、Spec Vault、`workflow_id`、`change_id`、`stage`、`role` 和 `input_refs` 在 `init` 后冻结，并共同生成 `input_fingerprint`。同一输入幂等复用同一 run；任一输入引用变化都会创建新的 run，旧 handoff 原样保留。helper 从配置和 fingerprint 反向推导唯一 run 路径，拒绝 run 外 handoff、重定向的 candidate/report、符号链接和未在配置中声明的仓库。

Worker 只用 helper 的 `write --config <当前配置路径> --expected-revision <当前 revision>` 更新结果字段。每次合法写入把 `revision` 加一；helper 持有文件锁并执行 compare-and-swap，旧 Worker 的陈旧 `expected_revision` 不能覆盖新状态。状态只按 helper 的允许转移推进，`published` 和 `complete` 是终态。主 Agent 消费前使用带同一配置路径的 `validate`，对当前游标、事件、阶段、角色、全部输入引用、固定路径、内容摘要和 revision 逐项验证。任何不一致都停止，不得采用旧 Worker 的候选或结果。

Spec/Plan 进入候选状态时，helper 读取固定 `candidate.md` 并写入 `candidate_sha256`；此后 `validate` 会重新计算，文件变化即失败。主 Agent 审核和用户确认必须绑定该精确摘要。Spec 发布时 Worker 还必须把主 Agent 转交的确认摘要作为 `confirmed_candidate_sha256` 交给 helper；不匹配时不得发布。Plan 的正文由不可变 Git `artifact_ref` 绑定，`candidate.md` 还必须明确写出同一引用。

### 阶段必填输入

helper 会机械检查下列 `input_refs` 键存在，并校验 profile、来源、绝对路径和完整 SHA。它还用只读 Git 命令确认 Spec Vault 与配置仓库是真实 worktree root、formal ref 的 `<sha>:<path>` 存在、代码/基线 SHA 是 commit，并确认规划来源 worktree 与实现 worktree 的 Git common directory 属于配置仓库。列表或对象采用稳定排序的紧凑 JSON；内容过长时使用不可变文件引用或内容摘要，不粘贴正文。

| 阶段 | 必填键 |
|---|---|
| Spec | `change_ref`、`repository_path`、`code_sha`、`related_formal_refs`、`acceptance_steps_ref` |
| Plan | `change_ref`、`spec_ref`、`test_ref`、`plan_profile`、`repository_path`、`base_source`、`base_locator`、`base_sha`、`baseline_details`、`agents_inventory`、`workspace_differences` |
| Implementation | `change_ref`、`spec_ref`、`plan_ref`、`test_ref`、`repository_path`、`workspace_path`、`authorization_offer`、`execution_contract` |

`baseline_details` 是稳定 JSON：远程来源至少含 `base_remote`、`base_branch`；本地来源至少含 `base_worktree`、`base_local_branch`、`base_detached_sha`、`pushed_status`、`dirty_exclusions`。helper 会规范化 JSON、路径和 SHA 后再计算 fingerprint，并验证 formal ref 与当前 `change_id` 一致。

Implementation 的 `authorization_offer` 和 `execution_contract` 是执行合同定义的完整规范化 JSON 对象，不是任意标签或聊天摘要。helper 机械验证字段集合、当前 `plan_ref`、配置仓库、实际 worktree、TDD/commit/finishing 边界及二者派生关系，然后把原样内容写入 run 内的 `authorization-offer.json`、`execution-contract.json` 并保存各自 SHA-256。Coordinator 只读取这两个 helper 生成的不可变文件；任一逐字节或摘要变化都会使 `validate` 失败。Plan handoff 写成 `approved` 时，helper 还会要求 `artifact_ref=plans/<change_id>.md@<40-char-sha>`、`review_status=Approved`、`blockers` 为空且候选清单包含同一引用。

## 恢复

进入阶段时先查找并验证当前身份的 handoff：

- 有效且 `candidate_ready`、`waiting_user` 或 `approved`：恢复对应确认或采用门禁，不重新调查。
- 有效且 `working`：优先恢复仍可用的原 Worker；不可恢复时，新 Worker 读取 handoff、candidate/report 和正式输入继续。
- `published` 或 `complete`：再用正式引用或 Git 事实验证，不能只相信 handoff。
- 身份、输入引用或正式材料已经变化：旧 handoff 只保留作临时记录，创建匹配新输入的工作区；不得就地改写冻结字段。

Durable handoff 只恢复阶段位置和工作结果，不恢复用户授权。新的对话仍必须重新满足当前阶段要求的用户确认或 SDD 权限门禁。

## 主 Agent 审核边界

主 Agent必须审核 Worker 的正式候选和异常，但不重复 Worker 的完整调查：

- Spec：读取候选一次，核对行为合同和来源，然后在对话中完整展示。
- Plan：读取经独立 reviewer `Approved` 的精确 `artifact_ref` 候选一次，核对 Spec、基线、profile、短 review 摘要和阻塞状态，然后提交用户确认；完整 review 只在异常或用户要求高审计时读取。
- Implementation：读取短 handoff、SDD ledger、最终 review 和验证证据，核对提交范围后更新 `code_ref`。

主 Agent不亲自修正文档或代码。用户反馈由对应 Worker 修正并重新经过该阶段原有 reviewer 或验证合同。
