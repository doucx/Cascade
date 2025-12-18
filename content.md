我已经完成了 `cascade-connector-mqtt` 包的实现，包括 LWT 机制。该连接器现在已全面符合 `Connector` 协议，并能够处理遥测输出和控制指令输入。

现在我将这个完整的功能单元作为一个独立的逻辑提交进行封装。

## [COMMIT] feat: Implement MqttConnector for external IO

### 用户需求
完成 `Cascade` 路线图第二阶段的核心功能，实现 `cascade-connector-mqtt` 包，以提供基于 MQTT 的遥测和控制反馈回路。

### 评论
这个提交标志着 Cascade 从一个纯粹的“单机/内存”工作流引擎，进化为一个“可观测、可控制”的系统。通过将 MQTT 连接器作为一个独立包实现，我们坚持了零强制依赖的原则。核心实现包括了非阻塞的 `publish`（遵循 Fail-Silent 原则）、基于异步迭代器的 `subscribe` 消息循环，以及确保系统状态可被外部监控的 LWT（遗言）机制。

### 目标
创建一个 Git 提交，包含 `MqttConnector` 的完整实现和所有相关的测试用例。

### 基本原理
现在连接器已经实现了 `connect`、`disconnect`、`publish` 和 `subscribe` 接口，并且 LWT 也已配置。这个功能块在逻辑上是完整的，适合作为一个主要的 `feat` 提交记录。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/sync #scope/api #scope/dx #ai/instruct #task/domain/runtime #task/object/mqtt-connector #task/action/implementation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 添加新文件和修改的文件到暂存区

将新创建的 `cascade-connector-mqtt` 包中的所有文件，以及修改过的 `cascade-py` 中的文件（如果有）添加到暂存区。由于本次修改集中在新包，我们主要添加新包的文件。

~~~~~act
git_add
packages/cascade-connector-mqtt/pyproject.toml
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/__init__.py
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/connector.py
packages/cascade-connector-mqtt/tests/test_connector.py
~~~~~

#### Acts 2: 执行提交

执行 Git 提交，并提供详细的 Commit Message。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(telemetry): Implement MqttConnector for external IO

Introduces the `cascade-connector-mqtt` package, providing a concrete implementation of the `Connector` protocol using the `aiomqtt` library.

This completes Phase 2 of the roadmap, enabling telemetry (observability) and command subscription (control).

Key implementation details:
- **Connector Protocol:** Full implementation of `connect`, `disconnect`, `publish`, and `subscribe`.
- **Fail-Silent Publish:** `publish` uses `asyncio.create_task` for non-blocking, fire-and-forget message sending, ensuring network errors do not block the core workflow execution.
- **LWT (Last Will and Testament):** Configured in `connect` to publish an "offline" status message (`cascade/status/{source_id}`) if the connection is unexpectedly lost.
- **Message Loop:** A background task is started on `connect` to continuously listen for and dispatch subscribed control messages, following the structured JSON payload convention.
~~~~~

### 下一步建议
我们已经完成了路线图的 **第二阶段 (Telemetry Implementation)**。现在系统具备了向外部发送状态的能力。

下一步是进入 **第三阶段：约束与环境感知 (Phase 3: Constraints & Environment Awareness)**。这要求我们实现一个反馈回路，使得外部系统可以通过 MQTT 约束来动态调节 `Engine` 的行为。

**初始任务将是：**
1.  在 `cascade-runtime` 中实现 `ConstraintManager` 组件。
2.  实现 `ConstraintResolver` 逻辑，处理动态约束（`LazyResult`）。

我建议我们从定义和集成 `ConstraintManager` 组件开始。
