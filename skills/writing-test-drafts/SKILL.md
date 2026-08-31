---
name: writing-test-drafts
description: Use when the user asks Codex to write or update a test draft, run a specified test draft, perform acceptance testing, or produce an acceptance report from an actual test run.
---

# 测试稿与验收报告

## 核心原则

把用户提供的验收目标和验收方式与已确认 Spec 的验收基准直接写成 Codex 可以执行的测试稿。主动设计从开始状态到最终检查的具体操作，并为每个具名测试项写出可观察的预期结果。

测试稿是执行前的验收基准；实际结果、通过或失败状态以及证据属于每次运行后独立生成的验收报告。同一个 Skill 负责写测试稿，也负责按指定测试稿执行验收和输出报告，但不得把两类内容写进同一个文件。

Spec 不定义 `test_id`。Spec 负责验收条件；测试稿首次为可执行测试项分配稳定 ID；验收报告从所引用测试稿原样继承这些 ID，并根据真实执行结果生成机械状态。

## 唯一可执行语法

本 Skill 是测试稿与验收报告的唯一语义与 executable grammar 拥有者。验收报告落盘后，必须使用 `scripts/acceptance_report.py` 校验；总账、router 和其他消费者只能调用该 validator 并消费规范化结果，不得复制字段 grammar、Markdown 解析规则、状态推导或失败回传规则。

可导入入口为：

```python
validate_acceptance_report(
    test_text,
    report_text,
    expected_change_id,
    expected_test_ref,
    expected_code_ref,
    require_passed=False,
)
```

函数返回可 JSON 序列化的字典，包括 `overall_status`、`passed_test_ids`、`failed_test_ids`、`not_executed_ids`、`reused_automation_evidence`、`failure_handoff_required`、`failure_handoff_valid`、规范化测试项和失败回传。调用方把 `AcceptanceReportError` 视为报告无效；`require_passed=True` 只接受所有测试项均为 `passed` 的报告。

CLI 用法：

```text
python scripts/acceptance_report.py --test-file <test.md> --report-file <report.md> --change-id <CE-0001> --test-ref <tests/CE-0001.md@full-vault-sha> --code-ref <repository@full-sha> [--require-passed]
```

校验成功时 stdout 只输出规范化 JSON 且退出码为 `0`；校验失败时 stdout 为空、stderr 输出以 `acceptance report invalid:` 开头的明确错误且退出非零。validator 严格要求正式测试稿具有 `## 测试流程`，正式报告具有 `## 测试项结果`；frontmatter 绑定、测试项 ID 顺序、标题、原始预期、非空实际与证据、canonical 状态和总体结果必须一致。代码块内容在解析前排除，不能提供任何机械字段。

## 输入边界

- 个人工作流中必须接收总控提供的 `change_id`；它决定测试稿文件身份，不得由本 Skill 另行生成或替换。
- 用户提供的操作步骤、流程和预期结果优先，验收可以使用 UI、接口、命令、脚本、日志、数据库或混合方式。
- 用户未提供时，根据已确认 Spec 和只读核对过的系统入口主动生成操作、流程和预期结果。Spec 不能证明具体入口时停止并指出缺口，不得虚构页面、接口、命令或环境。
- 以已确认的 Spec 确定应该出现什么结果和验收边界。
- 初次编写测试稿不依赖 Plan；测试稿必须在 Plan 和编码之前形成。后续修正已有测试稿时，如已评审 Plan 提供了仍符合 Spec 的可观察业务顺序，可以用它核对操作可执行性，但不得把文件清单、任务拆分或逐行实现复制成验收步骤。
- 以变更内容和必要的当前系统事实确定实际操作对象、环境、测试数据和证据来源。
- 执行验收时以已提交的 `code_ref=<repository>@<full-code-commit-sha>` 确定受测代码；SHA 必须是 Git 返回的完整、精确 commit object ID，不接受 7 位或其他缩写。编写测试稿时不要求绑定某个代码版本。
- 讨论稿不属于测试稿输入；Spec 与已有正式材料冲突、引用无效或代码事实已经漂移时停止，不自行选择或静默修补。
- 无论用户是否给出大致验收方式，都由 Codex 按上述优先级补全具体测试路径、操作对象、测试数据和观察点；不要要求用户逐步设计测试。
- 遵守当前项目的文档位置、命名和安全边界。

## 写测试稿

- 提取测试开始状态、用户指定的验收方式和最终必须验证的功能效果。
- 按用户提供的流程或 Spec 定义的可观察业务顺序组织测试项，并让每个关键业务动作紧邻其可观察预期。每个测试项使用唯一且能说明目的的标题，例如“创建批注”或“检查 GitLab Issue 同步”。
- 每个测试项必须同时包含唯一 `test_id`，格式为 `T-001`、`T-002`。编号只用于同一测试稿及其验收报告间稳定关联，不替代说明目的的标题。
- 更新已经发布的测试稿时保留已有 ID；标题可以修改，但 ID 不变。新增测试项使用下一个未用编号；删除测试项后不复用旧编号，也不为排序变化重编号。
- 每个测试项包含两部分：**操作**写明 Codex 对什么对象执行什么动作并使用什么输入；**预期结果**写明完成后立即可观察的界面、响应、日志、数据或状态。
- 一个测试项可以包含若干连续操作。需要引用其他测试项的产物时，直接使用测试项标题作为关联依据。
- 用最后一个或多个测试项检查验收目标是否真正达成，并覆盖用户明确要求检查的重复、丢失、错误状态或副作用。
- 将完整内容直接写到用户指定或项目既有的测试稿位置。没有可确定的文件位置时，在当前回复中给出完整测试稿。此流程不增加预览或确认环节，也不执行测试。
- 作为 Spec Vault 正式材料保存时，测试稿固定使用 `tests/<change_id>.md`；这一路径与总控提供的 `change_id` 以及总账 `test_ref` 的机械校验一致。

## 测试稿输出格式

```markdown
# 测试稿：<名称>

## 验收目标

<本次最终需要验证的效果>

## 前置条件

- <执行测试前必须满足的条件>

## 测试流程

### T-001 <唯一测试项名称>

test_id: T-001

操作：

1. <具体动作>

预期结果：

- <完成本测试项后可以观察到的结果>

### T-002 <另一个唯一测试项名称>

test_id: T-002

操作：

1. <具体动作>

预期结果：

- <完成本测试项后可以观察到的结果>
```

## 测试稿示例

用户要求：“调用接口创建任务，再到管理后台确认任务已经出现。”

```markdown
### T-001 调用接口创建任务

test_id: T-001

操作：

1. 使用指定测试账号调用创建任务接口，任务名称填写为 `验收任务-001`。

预期结果：

- 接口返回创建成功响应。
- 响应中包含新任务的稳定标识，任务名称为 `验收任务-001`。

### T-002 在管理后台查看任务

test_id: T-002

操作：

1. 打开管理后台的任务列表。
2. 使用“调用接口创建任务”测试项返回的任务标识搜索任务。

预期结果：

- 列表中只显示一条对应任务。
- 任务名称和状态与创建接口返回的数据一致。
```

## 执行测试稿并生成验收报告

用户要求执行或验收测试稿时，读取总控指定的完整 `test_ref=tests/<change_id>.md@<full-vault-commit-sha>`，逐项核对已有有效证据或实际操作，并生成一份新的验收报告。正式验收报告必须绑定同一 `change_id`；没有事件身份时停止生成正式报告并请求上游提供，不能写“未提供”冒充绑定。

开始第一个测试项前，必须确认目标 Git SHA 是完整 object ID 且精确解析为该 commit、实际运行内容与代码版本完全一致，并通过只读检查确认本次变更相关文件没有会改变受测行为的未提交改动。不得用旧 `HEAD`、“当前工作区”或暂存区状态代替已提交的 `code_ref`。仓库存在无关的用户改动不构成阻塞，也不得清理或提交这些无关改动。无法证明代码快照一致时，停止在验收前置检查，不执行测试项、不声称已经生成验收结果，并请求上游重新验证和形成已授权的本地代码 commit。

自动化成功证据的精确复用键是 `code_sha + command + environment_fingerprint + input_fingerprint`。总控提供的证据只有在四项与当前 `code_ref`、命令、环境和输入完全一致，且同时记录非空 `scope`、`result=passed` 与 `produced_by` 时才有效；完全相同的成功自动化证据不得重跑。任一维度变化就使对应证据失效并重新执行。验收只实际执行尚未覆盖的手工、外部环境或真实服务步骤，以及没有有效自动化证据的测试项。

复用证据仍是本次验收对精确证据的真实核对；复用不是 `not_executed`。若该证据足以证明测试项预期，测试项写 `status: passed`，在“实际结果”中说明已核对的结果和绑定键，在“证据”中使用一行 `复用自动化证据：<compact-json>`。JSON 必须且只能包含字符串字段 `code_sha`、`command`、`environment_fingerprint`、`input_fingerprint`、`scope`、`result`、`produced_by`；其中 `code_sha` 必须等于当前 `code_ref` 的完整 SHA、`result` 必须是 `passed`、`produced_by` 必须是 `delivery`，同一报告不得重复四元复用键。validator 会解析并返回 `reused_automation_evidence`，版本不符、缺字段、附加字段或自由文本占位都会使报告无效。只有既未复用也未执行的项目才是 `not_executed`。实际新执行的项目继续按原证据格式记录。本规则不新增报告类型或机械状态。

验收报告必须：

- 在文件开头的 YAML frontmatter 逐字写入本次 `change_id`、完整 `test_ref`、实际 `code_ref` 和 canonical `overall_status`；代码版本必须是本次真实执行所对应的 `repository@<full-git-sha>`。
- 保留测试稿中的每个测试项、原始 `test_id` 和标题，逐项记录预期结果、实际结果、状态和证据；报告 ID 集合必须与测试稿完全一致，不得遗漏、增加或重编号。
- 每个测试项机械状态的固定值为 `passed` / `failed` / `not_executed`，分别写成 `status: passed`、`status: failed` 或 `status: not_executed`；人类可读文字对应使用“通过”“失败”“未执行”。
- `test_id` 只接受 `T-001` 形式；每项必须保留同 ID 标题、原始预期结果，并提供非空实际结果、证据和唯一 canonical `status`。中文机械状态、“pass”等缩写、占位符和空壳项目无效。机械字段必须写在普通 Markdown 正文，代码块中的示例或伪字段不计入报告结构。
- 当前测试项失败但后续测试项可独立执行时，继续执行后续测试项。
- 当前测试项导致后续测试项无法执行时，仍保留后续测试项，标记为 `未执行` 并写明原因。
- 记录本次验收真实执行或核对复用证据所得的结果；不得修改测试稿中的预期结果来匹配实际结果。
- 每次验收核对新建一份报告，不覆盖旧报告，也不回填测试稿。
- 总体结果为“失败”时，在同一报告中增加“失败回传”，逐项提取失败事实和脱敏日志/证据，供上游工作流判断回到 Spec、Plan、代码、测试稿或验收环境；报告本身不判断根因或返回阶段，也不另建失败文档。

涉及真实远端写入、删除或其他受控操作时，先遵守项目安全边界并取得所需授权。证据中不得包含密码、Token、Cookie 或其他凭据。

### 总体结果

| 条件 | 总体结果 |
|---|---|
| 所有测试项均通过 | 通过 |
| 至少一个测试项失败 | 失败 |
| 没有失败，但至少一个测试项未执行 | 未完成 |

报告 frontmatter 同时写入机械字段 `overall_status`。固定值为 `passed` / `failed` / `incomplete`，由测试项机械状态推导：

- 全部测试项都是 `passed`：`overall_status: passed`；
- 任一测试项是 `failed`：`overall_status: failed`；
- 没有 `failed`，但存在 `not_executed`：`overall_status: incomplete`。

不得手写与测试项状态不一致的总体状态。`change_id`、`test_ref`、`code_ref` 必须逐字复制本次事件、实际执行的测试稿版本和受测代码版本；旧测试稿的报告不能绑定新 `test_ref`。

### 验收报告输出格式

```markdown
---
change_id: <CE-0001>
test_ref: tests/<change_id>.md@<full-vault-commit-sha>
code_ref: <repository>@<full-code-commit-sha>
overall_status: passed
---

# 验收报告：<名称>

- 变更事件：<change_id>
- 测试稿版本：tests/<change_id>.md@<full-vault-commit-sha>
- 代码版本：<repository>@<full-code-commit-sha>
- 验收环境：<环境名称或地址>
- 开始时间：<ISO 8601 时间>
- 结束时间：<ISO 8601 时间>
- 总体结果：通过 / 失败 / 未完成

## 测试项结果

### T-001 <测试稿中的测试项标题>

test_id: T-001
status: passed

预期结果：

- <测试稿中的原始预期>

实际结果：

- <真实观察结果>

证据：

- <带时间的证据位置或摘要>

### T-002 <另一个测试项标题>

test_id: T-002
status: not_executed

预期结果：

- <测试稿中的原始预期>

实际结果：

- <未执行原因>

证据：

- 无

## 结果汇总

- 通过：<数量>
- 失败：<数量>
- 未执行：<数量>
- 结论：<本次运行结论>

## 失败回传

> 仅在总体结果为“失败”时保留本节。

| test_id | 失败测试项 | 预期结果 | 实际结果 | 错误摘要 | 证据与日志 |
|---|---|---|---|---|---|
| <T-001> | <失败测试项标题> | <原预期> | <真实结果> | <脱敏后的错误、异常或偏差摘要；没有错误消息时说明可观察偏差> | <带时间的日志、截图、命令或 URL 引用> |
```

证据使用简洁格式：

```text
<ISO 8601 时间> | <screenshot / command / log / url> | <文件路径、页面地址或输出摘要>
```

`overall_status: failed` 时必须有且仅有一个“失败回传”；表格必须包含全部且仅有状态为 `failed` 的测试项，并按报告顺序让 `test_id`、标题、预期、实际和证据与对应测试项逐项完全匹配。一个单元格需要表达原字段的多行内容时，按原顺序用 `<br>` 分隔；单元格内作为内容的竖线写成 `\|`。错误摘要必须是非空的脱敏失败事实。`passed` 或 `incomplete` 报告不得保留“失败回传”，因此 `incomplete` 不能伪装成 `failed`。保留必要的错误消息和定位信息，但不要复制整份日志，也不要包含密码、Token、Cookie 或其他凭据。上游流程使用 validator 返回的规范化 `change_id`、测试稿版本、代码版本、预期、实际和证据进行回环。

以下旧格式缺少 `change_id` 与 `test_ref`，只是拒绝示例，不是报告模板；其中字段位于代码块，也不能充当报告机械字段：

```markdown
---
overall_status: passed
code_ref: <repository>@<code-git-sha>
---
```

### 验收报告示例

```markdown
---
overall_status: failed
change_id: CE-0001
test_ref: tests/CE-0001.md@<full-vault-commit-sha>
code_ref: forentx-frontend@<full-code-commit-sha>
---

- 总体结果：失败

## 测试项结果

### T-001 创建批注

test_id: T-001
status: passed

预期结果：

- 页面显示一条新批注。

实际结果：

- 页面显示一条新批注。

证据：

- 2026-08-17T14:30:01Z | screenshot | acceptance/CE-0001/T-001.png

### T-002 检查 Issue

test_id: T-002
status: failed

预期结果：

- 只创建一个映射 Issue。

实际结果：

- 创建了两个 Issue。

证据：

- 2026-08-17T14:30:02Z | url | GitLab Issue 列表

### T-003 检查反向同步

test_id: T-003
status: not_executed

预期结果：

- Issue 状态回显到原批注。

实际结果：

- 因 T-002 失败而无法继续。

证据：

- 无

## 失败回传

| test_id | 失败测试项 | 预期结果 | 实际结果 | 错误摘要 | 证据与日志 |
|---|---|---|---|---|---|
| T-002 | 检查 Issue | 只创建一个映射 Issue。 | 创建了两个 Issue。 | 观察到重复 Issue。 | 2026-08-17T14:30:02Z \| url \| GitLab Issue 列表 |
```

将报告写到 `acceptance/<change_id>/<YYYY-MM-DD-HHmmss>.md`，确保沿用同一变更身份且每次运行文件名唯一；不得覆盖旧报告。这一路径角色与总账 `evidence_ref` 的机械校验一致。

## 快速检查

| 检查项 | 合格标准 |
|---|---|
| 测试方式 | 与用户指定的方法一致 |
| 操作 | Codex 可以据此实际执行 |
| 逐项预期 | 每个测试项都有立即可观察的结果 |
| 稳定关联 | 测试稿每项有唯一稳定 `test_id`；报告原样继承且集合完全一致 |
| 最终检查 | 能判断验收目标是否达成 |
| 测试稿性质 | 只写执行前基准，不写实际运行结果 |
| 代码快照 | 实际运行内容与报告 `code_ref` 完全一致，相关改动均已包含在该 commit 中 |
| 报告覆盖 | 测试稿的每个测试项及其原始标题都出现在验收报告中 |
| 机械绑定 | frontmatter 的 `change_id`、完整 `test_ref`、完整 `code_ref` 与本次运行逐字一致 |
| 机械状态 | `overall_status`、每项 canonical `status` 完整且与人类可读结果一致 |
| 真实结果 | 实际结果、状态和证据来自本次执行或对精确复用证据的核对 |
| 失败回传 | 失败报告逐项给出预期、实际、错误摘要和脱敏证据；不自行判断返回阶段 |
| 运行隔离 | 每次运行新建报告，不覆盖旧报告或测试稿 |

## 常见错误

| 错误 | 修正方式 |
|---|---|
| 写成“分析需求、拆分场景”的测试设计元流程 | 写成实际要执行的测试项和操作 |
| 把所有验收都限定为 UI 点击 | 严格沿用用户指定的验收方式 |
| 让用户补写每个测试项和预期 | Codex 根据目标、方法和确认资料主动设计 |
| 等待 Plan 后才首次编写测试稿 | 初次测试稿在 Spec 确认后立即生成；用户输入优先，否则从 Spec 与可验证入口生成 |
| 只用顺序编号或只用标题关联测试项 | 同时使用稳定 `test_id` 和说明目的的标题；报告按 ID 继承 |
| 先发预览并等待确认 | 直接生成正式测试稿 |
| 用“结果正常”描述预期 | 写明可观察的具体界面、响应、日志、数据或状态 |
| 在测试稿填写实际结果和证据 | 将这些内容留给独立验收报告 |
| 验收失败后省略剩余测试项 | 保留测试项，能继续则执行，不能继续则标记未执行并写明原因 |
| 用预期结果代替实际结果 | 记录本次真正观察到的结果 |
| 用旧 `HEAD`、工作区或暂存区状态填写代码版本 | 验收前形成并核对包含实际受测代码的本地 commit |
| 因仓库存在无关脏文件而拒绝验收或擅自清理 | 只检查本次变更相关文件，无关用户改动保持不动 |
| 相关代码在验收前又发生未提交变化 | 停止验收，重新验证并形成新的代码 SHA |
| 失败报告只有自由文本结论，无法向前传递 | 增加固定“失败回传”表，逐项给出失败事实和脱敏证据 |
| 报告只写中文“通过/失败” | 同时写机械 `status`，并由全部测试项推导 `overall_status` |
| 把机械字段放进代码块或只保留 ID/状态空壳 | 在普通正文逐项写同 ID 标题、原始预期、实际、证据和 canonical 状态 |
| 用旧测试稿的报告绑定新 `test_ref` | frontmatter 逐字复制本次实际执行的完整 `test_ref` |
| 让验收报告猜测根因或决定回到哪个阶段 | 报告只传事实；由个人工作流入口判断路由 |
| 重复验收时覆盖旧报告 | 每次验收核对生成新的验收报告文件 |
