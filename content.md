好的，`cs-observer status` 功能已实现并准备提交。

## [COMMIT] feat(cli): Implement 'cs-observer status' command to query active constraints

### 用户需求
实现 `cs-observer status` 命令，允许用户连接到 MQTT Broker 并查询当前所有通过保留消息发布的、处于激活状态的约束（如 `pause`, `concurrency`, `rate_limit`）。

### 评论
这个新命令是操作工具链的关键组成部分。它通过利用 MQTT 的保留消息机制，为操作员提供了一个快速、可靠的系统控制状态快照。特别是在引入 TTL 功能后，`status` 命令可以清晰地显示每个约束的剩余生命周期，从而极大地提升了系统的可观测性和运维体验。

### 目标
创建一个 Git 提交，包含 `cs-observer` 中 `status` 命令的实现和相关导入的修改。

### 基本原理
`cs-observer status` 通过订阅通配符主题 `cascade/constraints/#` 来接收所有保留约束。它通过 `asyncio.sleep(0.5)` 策略等待 Broker 完成同步推送，然后优雅地断开连接，将收集到的 `GlobalConstraint` 对象列表格式化为 `rich.Table` 输出。这种模式保证了命令的原子性（一次性状态获取）和准确性（基于 Broker 的持久化状态）。

### 标签
#intent/build #flow/done #priority/high 
#comp/cli #concept/config #concept/ui #scope/ux #scope/dx 
#ai/instruct 
#task/domain/cli #task/object/cs-observer #task/action/feature-enhancement 
#task/state/end

---

### Script

#### Acts 1: 暂存并提交 `cs-observer` 的变更

将 `app.py` 文件的修改添加到暂存区，并执行提交。

~~~~~act
git_add
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(cli): Implement 'cs-observer status' command to query active constraints

Introduces the `cs-observer status` command, fulfilling a key requirement of the Phase 4 tooling roadmap.

This command connects to the configured MQTT broker, subscribes to the `cascade/constraints/#` topic, and utilizes the Retained Message feature to retrieve all active `GlobalConstraint` objects (pause, concurrency, rate limits).

The constraints are parsed and displayed in a readable `rich.Table` format, including the dynamic calculation of remaining Time-To-Live (TTL) when applicable.

This greatly improves the operator's ability to monitor the runtime control state.
~~~~~

### 下一步建议
我们已经完成了 Phase 4 的第一个目标。下一步是继续增强 `cs-observer` 的**实时**观测能力，以更好地支持对动态约束行为的调试和理解。

- **路线图**: **里程碑 3.4 (系统健壮性与完善)** 要求我们在 `Engine` 中增加遥测事件：`ConstraintApplied` 和 `TaskDeferredByConstraint`。
- **目标**: 下一步计划应首先在 `cascade-runtime` 中实现这两个新的事件，为 `cs-observer` 的增强做好数据源准备。

如果你同意，我将生成下一个计划来实现 `ConstraintApplied` 和 `TaskDeferredByConstraint` 事件。
