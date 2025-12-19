出色的工作。通过这次深入的分析和修复，我们不仅解决了最初的遥测丢失问题和更隐蔽的启动竞态条件（通过调整 `Engine` 顺序和实现 `TelemetrySubscriber` 关机），还顺带发现并修复了测试线束中关键的 MQTT 通配符缺陷。现在我们的 E2E 测试基础设施更加健壮了。

我将把所有这些逻辑上相关的修改打包成一个原子提交。

## [COMMIT] fix(runtime, test): 修复启动竞态条件并增强遥测可靠性

### 用户需求
1.  修复 `Engine` 启动时，`RunStarted` 遥测事件在连接建立前发送导致丢失的问题。
2.  解决因事件发布异步性导致的关闭竞态条件，确保所有遥测消息在连接断开前发送。
3.  修复 E2E 测试线束中的 MQTT `+` 通配符匹配缺陷，以使遥测 E2E 测试能正确路由消息。

### 评论
这个提交解决了 Cascade 运行时中最关键的一类并发和时序缺陷。通过将 Engine 的连接和订阅逻辑提升到 `RunStarted` 事件之前，消除了启动时的竞态。同时，在 `TelemetrySubscriber` 中实现了优雅关机逻辑，确保了所有异步发布的任务在 `Connector` 断开之前被刷新。最后，修复了测试线束中的通配符匹配缺陷，为所有控制面和遥测 E2E 测试提供了坚实的基础。

### 目标
将以下功能性修复和测试改进整合为一个提交：
1.  调整 `Engine.run()` 中的初始化顺序：先连接/订阅，后发布 `RunStarted`。
2.  为 `TelemetrySubscriber` 添加任务追踪和 `shutdown` 方法，并更新 `Engine` 以在 `finally` 块中调用该方法。
3.  修复 `InProcessConnector._topic_matches` 以正确支持 MQTT `+` 通配符。
4.  更新 `test_startup_telemetry.py`，正确注册 `TelemetrySubscriber` 和 `Engine` 的管理。

### 基本原理
这些变更虽然分散在运行时代码和测试代码中，但它们共同构成了对 **"Engine 启动时序和遥测可靠性"** 这个核心问题的完整解决方案。因此，它们应作为一个原子工作单元被提交。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #comp/tests #concept/telemetry #concept/lifecycle #scope/core #scope/dx #ai/instruct #task/domain/runtime #task/object/engine-startup #task/action/reorder #task_state/continue

---

### Script

#### Acts 1: 暂存所有已修改文件

我们将所有受影响的文件添加到 Git 暂存区。

~~~~~act
git_add
packages/cascade-runtime/src/cascade/runtime/subscribers.py
packages/cascade-runtime/src/cascade/runtime/engine.py
tests/py/e2e/harness.py
tests/py/e2e/test_startup_telemetry.py
tests/py/e2e/test_harness_connector.py
~~~~~

#### Acts 2: 提交变更

~~~~~act
git_commit
~~~~~
~~~~~text
fix(runtime, test): Enhance telemetry reliability and fix startup race conditions

This commit implements a suite of fixes to address reliability issues in the engine's startup sequence and telemetry publishing mechanisms.

Key fixes:
1.  **Engine Startup Order:** `Engine.run()` now connects to the external `Connector` (and subscribes to control constraints via retained messages) *before* publishing the `RunStarted` internal event. This prevents the `RunStarted` telemetry from being lost due to a race condition where the `TelemetrySubscriber` attempts to publish before the connector is fully connected.
2.  **Telemetry Flush on Shutdown:** Introduced `async def shutdown()` to `TelemetrySubscriber` to wait for all fire-and-forget publish tasks to complete. `Engine` now calls this method in its `finally` block before disconnecting the connector, ensuring all scheduled telemetry is successfully flushed, resolving a shutdown race condition for fast workflows.
3.  **Test Harness Bugfix:** Fixed a critical bug in `tests/py/e2e/harness.py:InProcessConnector._topic_matches` where the MQTT single-level wildcard (`+`) was not correctly supported. This was preventing many E2E telemetry and control tests from correctly routing messages.

New dedicated tests (`test_startup_telemetry.py`, `test_harness_connector.py`) confirm the success of these fixes.
~~~~~

### 下一步建议
我们已经完成了路线图中的 **步骤 3: [绿灯] 修复引擎的启动逻辑**，并且解决了相关的测试基础设施缺陷。

现在，我们回到路线图的 **步骤 4: [红灯] 为运行时控制延迟编写一个失败的测试**，以解决在工作流执行中途无法响应 `pause` 命令的问题。

我建议继续执行路线图的下一步。
