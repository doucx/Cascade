好的，测试通过，证明 `cs-controller pause` 的核心逻辑已经正确实现，并且满足了我们关于测试分离和 Mock Intent 的所有原则。

现在我们来创建这次实现的提交。

## [COMMIT] feat(cli): Implement cs-controller pause command

### 用户需求
提交 `cs-controller` 的核心功能：发布 `pause` 约束。

### 评论
该提交完成了对 `cs-controller` 命令行工具的实现。它现在能够连接到 MQTT Broker，构造符合 `GlobalConstraint` 规范的 JSON 报文，并将其发布到正确的控制主题上。为了便于测试，核心异步逻辑被提取到 `_publish_pause` 函数中，并且新的测试套件验证了发布行为的正确性。这是实现 Cascade 自适应控制能力的第一块外部工具。

### 目标
1.  提交 `cs-controller/app.py` 中 `pause` 命令的实现。
2.  提交 `tests/cli-controller/test_app.py` 测试文件。
3.  更新 `cli_messages.json` 包含所有必需的控制器消息。

### 基本原理
遵循 `d3-constraint-quipu-plan-script-rules-D3-P2` 约束，本次计划用于提交前一个步骤中已完成的代码。

### 标签
#intent/build #flow/ready #priority/high #comp/cli #concept/control-loop #scope/ux #ai/instruct #task/domain/cli #task/object/controller-tool #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交 Controller 逻辑、测试和消息模板

将所有与 `cs-controller` 实现相关的修改添加到暂存区，并执行提交。

~~~~~act
git_add
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
packages/cascade-common/src/cascade/common/locales/en/cli_messages.json
tests/cli-controller/test_app.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(cli): Implement cs-controller pause command

Introduces the first functional command for the `cs-controller` CLI, enabling external control over running Cascade workflows.

The `pause` command:
1. Connects to the MQTT broker using `MqttConnector`.
2. Constructs a `GlobalConstraint` payload with `type="pause"`.
3. Publishes the constraint to a structured topic (`cascade/constraints/{scope_path}`).

Refactoring: The core asynchronous logic was extracted into `_publish_pause` to ensure high testability. Dedicated tests were added to verify correct topic generation and payload contents for different scopes (e.g., 'global' vs. 'task:api_call').
~~~~~

---
## 当前位置与后续路线图分析

我们正在执行 **Cascade 架构演进技术路线图 (v2.0)** 的 **第三阶段 (约束与环境感知)** 和 **第四阶段 (生态工具链)** 的并行开发。

### 已完成：

| 里程碑 | 目标 | 状态 |
| :--- | :--- | :--- |
| **Phase 2.0** | 遥测系统实现 | **DONE** |
| **Phase 3.4** | 约束同步（Engine 接收 MQTT） | **DONE** (在 `engine.py` 中实现 `_on_constraint_update`) |
| **Phase 4.1** | `cs-observer` 基础实现 | **DONE** (完成消息处理逻辑和测试) |
| **Phase 4.2** | `cs-controller pause` 实现 | **DONE** |

### 下一步聚焦：Phase 3.1 和 Phase 3.2

尽管我们实现了 `cs-controller`，但在 `Engine` 内部，我们只实现了最基本的**全局暂停**检查（即 `ConstraintManager.check_permission` 中的硬编码逻辑）。

路线图要求我们实现更精细的控制：

| 里程碑 | 目标 (Engine Capability) | 对应的 CLI 命令 |
| :--- | :--- | :--- |
| **3.1** | **精准控制**：支持基于 `scope` 的任务级暂停。 | `cs-controller pause --task <name>` |
| **3.2** | **并发管理**：实现基于动态资源的并发数限制。 | `cs-controller set-limit --concurrency <limit>` |

目前，我们的 `ConstraintManager` 尚未实现 **Scope 匹配**和 **约束过期** 逻辑，也未实现 **并发限制**。

### 建议的下一步

我们将从 **里程碑 3.1** 开始，增强 `ConstraintManager` 的逻辑，使其能够识别和应用不同作用域的约束，并清理已过期的约束。

**新任务**: 增强 `ConstraintManager`，实现 Scope 匹配和约束过期功能。

如果你同意，我将生成实现这个内部增强的计划。
