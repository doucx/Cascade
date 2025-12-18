这是一个关键的里程碑。我们将所有解决遥测、控制和测试稳定性问题的修复合并为一个完整的逻辑提交。

## [COMMIT] fix(telemetry): 正确实现异步桥接和通配符主题匹配

### 用户需求
解决 Cascade 引擎的遥测流 (Telemetry Stream) 中的一系列架构和实现问题，确保 `cs-observer` 和 `cs-controller` 能够稳定地进行实时观测和动态控制。

### 评论
这个提交解决了阻碍我们验证 Phase 2 和 Phase 3 核心功能的一系列问题：
1.  **架构遵守**: 修复了 `Engine` 内部直接调用日志总线（`self.bus.info`）的违规行为，转而使用 `ConnectorConnected/Disconnected` 事件。
2.  **异步桥接**: 解决了 `TelemetrySubscriber` 中的同步/异步调用错误，保证了遥测数据的发送。
3.  **连接器功能**: 修正了 `MqttConnector` 对通配符订阅的支持，使得 `cs-observer` 可以正确接收消息。

这些修复共同使得 Cascade 首次实现了完全可用的、基于 MQTT 的远程遥测和控制能力。

### 目标
创建一个单一的 Git 提交，包含所有为了实现稳定遥测和控制所做的架构和 Bug 修复。

### 基本原理
将所有针对同一宏观目标（Telemetry System Activation）的修改进行原子化提交，以保持 Git 历史的清晰和可追溯性。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #comp/connector #comp/cli #concept/events #scope/core #ai/instruct #task/domain/telemetry #task/object/observer #task/action/fix #task/state/end

---

### Script

#### Acts 1: 提交所有核心遥测与控制修复

将所有修改过的文件添加到暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
packages/cascade-runtime/src/cascade/runtime/subscribers.py
packages/cascade-runtime/src/cascade/runtime/engine.py
packages/cascade-runtime/src/cascade/runtime/events.py
packages/cascade-common/src/cascade/common/locales/en/runtime_events.json
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/connector.py
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
tests/cli-controller/test_controller_app.py
tests/py/runtime/test_engine_constraints.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(telemetry): Correctly implement async bridge and wildcard topic matching

This commit resolves several critical bugs that prevented the telemetry system (cs-observer) from receiving or displaying real-time data from the Engine, fully validating Phase 2 and 3 observability and control.

Key fixes include:
1. Async/Sync Bridge Fix: TelemetrySubscriber.on_event was incorrectly defined as an async method, leading to a RuntimeWarning and failed execution. It is now a sync wrapper that correctly schedules asyncio.create_task for publishing. Also added the missing `import asyncio`.
2. Architecture Compliance: Replaced direct `self.bus.info()` calls in `Engine` with new `ConnectorConnected/Disconnected` events, adhering to the Event Bus separation principle.
3. MQTT Wildcard Support: Implemented `_topic_matches` logic in `MqttConnector` to correctly route messages from the broker to wildcard subscriptions (e.g., `cascade/telemetry/#`), enabling `cs-observer` to function.
4. Observer Parsing Fix: Corrected a schema mismatch in `cs-observer`'s `on_message`, which now correctly reads `run_id` directly from the flat JSON payload.
5. Test Stability: Enhanced `test_engine_constraints.py` to use deterministic waiting for connector subscriptions, fixing previous flakiness.
6. Minor Fix: Corrected missing 'asyncio' import in TelemetrySubscriber and fixed controller test signatures.
~~~~~

### 下一步建议
我们已经完成了对 Telemetry 和 Control 系统的核心激活。根据 [Cascade 架构演进技术路线图 (v2.0).md] 中的 Phase 3 和 Phase 4，所有功能已基本实现。

下一步应该继续在测试套件中实施我们的测试原则，并完成 Phase 3.4 中剩下的“系统健壮性”目标，例如：
1.  **为 `cs-controller` 添加 `--ttl` 功能** (尽管基础实现已经有了，但需全面测试)。
2.  **实现更丰富的遥测事件**：例如 `ConstraintApplied` 和 `TaskDeferredByConstraint`，以提高 `cs-observer` 的洞察力。

我建议先从**增强 `cs-observer` 对约束事件的展示**开始。
