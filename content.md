好的，测试已经通过，确认任务级暂停与恢复功能已成功实现并验证。现在我们创建 Git 提交。

由于此前的操作涉及了多个包（`cascade-interfaces`, `cascade-connector-mqtt`, `cascade-runtime`, `cascade-cli-controller`, 以及测试文件），我们将把这些修改打包成一个逻辑上完整的工作单元进行提交。

## [COMMIT] feat(control): Implement task-level pause/resume via retained MQTT messages

### 用户需求
完成里程碑 3.1: 精准控制的开发。实现 `Engine` 对任务级暂停约束的响应，并为 `cs-controller` 添加 `resume` 功能，利用 MQTT 保留消息实现控制状态的持久化。

### 评论
本次提交是 Cascade 向“自适应执行环境”演进的关键一步。通过引入任务级的 `pause` 和 `resume`，我们极大地增强了系统的运行时可控性。核心设计是利用 MQTT 的保留消息作为**分布式状态存储**，保证了控制命令在执行者启动或重新连接时立即生效，实现了控制者和执行者之间的完全解耦。

### 目标
1.  **MqttConnector**: 增加对 `retain` 标志的支持。
2.  **ConstraintManager**: 增加 `remove_constraints_by_scope` 逻辑。
3.  **Engine**: 增强 `_on_constraint_update` 以识别空 payload（即 `resume` 命令），并清除对应的约束。
4.  **CLI Tooling**: 为 `cs-controller` 实现 `pause` (使用保留消息) 和 `resume` (清除保留消息) 命令。
5.  **Testing**: 增加集成测试以验证任务级暂停与恢复的端到端行为。

### 基本原理
我们基于 **MQTT 保留消息** 机制，将控制指令的持久化责任交给 Broker。一个带有 `retain=True` 的空消息是清除 Broker 上该主题保留消息的标准方法，这巧妙地实现了我们所需的 `resume` 功能。这种方法避免了在 `Engine` 或 `Controller` 中实现复杂的持久化状态存储逻辑。

### 标签
#intent/build #flow/ready #priority/high
#comp/runtime #comp/cli #comp/interfaces #comp/tests
#concept/executor #scope/api #scope/ux
#ai/instruct
#task/domain/control #task/object/constraint-system #task/action/implementation #task/state/end

---
### Script

#### Acts 1: 暂存所有已修改和新增的文件

~~~~~act
git_add
packages/cascade-interfaces/src/cascade/interfaces/protocols.py
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/connector.py
packages/cascade-runtime/src/cascade/runtime/constraints/manager.py
packages/cascade-runtime/src/cascade/runtime/constraints/handlers.py
packages/cascade-runtime/src/cascade/runtime/engine.py
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
packages/cascade-common/src/cascade/common/locales/en/cli_messages.json
tests/py/runtime/test_engine_constraints.py
~~~~~

#### Acts 2: 提交变更

~~~~~act
git_commit
~~~~~
~~~~~text
feat(control): Implement task-level pause/resume via retained MQTT messages

This implements Milestone 3.1, enabling precise, task-scoped control over running Cascade workflows via external control messages.

Key features and changes:

1.  **MqttConnector Enhancement:** Updated `publish` to support the `retain=True` flag for creating persistent control state messages on the broker.
2.  **Control Loop:**
    *   `Engine` now subscribes to `cascade/constraints/#`.
    *   It interprets an empty payload on a constraint topic as a `RESUME` command.
    *   `ConstraintManager` gains `remove_constraints_by_scope` to support dynamic constraint removal during runtime.
3.  **cs-controller Tooling:**
    *   `cs-controller pause` now publishes constraints with `retain=True`.
    *   A new `cs-controller resume` command publishes an empty retained message to the same topic, clearing the pause state on the broker and inside any connected `Engine`.
4.  **Scope Filtering:** `PauseConstraintHandler` correctly checks if a task matches a `task:<task_name>` scope.

This establishes the foundation for a truly adaptive and externally governable execution environment.
~~~~~

### 下一步建议
里程碑 3.1 (精准控制) 已完成。根据《Phase 3 (Refined) & Phase 4 并行开发路线图》：

我们下一步将进入 **里程碑 3.2: 并发管理 (Concurrency Management)**。这项工作的目标是利用 `ResourceManager`，通过外部指令限制特定任务的并发执行数量。

我建议先对 `ResourceManager` 进行必要的修改，使其能够处理动态的、由外部约束定义的容量限制，然后扩展 `ConstraintManager` 和 `ConstraintHandler`。
