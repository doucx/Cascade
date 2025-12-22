## [WIP] fix: 修复 E2E 测试中因遥测关闭时序问题导致的断言失败

### 错误分析
`test_watch_local_uds_e2e` 测试中存在一个时序竞争：`Engine` 在关闭 `LocalConnector`（以及其 UDS 服务器）时，并未等待 `TelemetrySubscriber` 发送完最后一条 `ENGINE_STOPPED` 事件。这是因为测试没有将 `TelemetrySubscriber` 实例注册到 `Engine` 的生命周期管理器中，导致 `Engine` 的优雅关机逻辑未能覆盖到它。

### 用户需求
修复 `test_e2e_watch_local_uds_e2e` 测试中的 `AssertionError`，确保 `ENGINE_STOPPED` 事件能被可靠地接收。

### 评论
这是一个经典的异步系统关机时序问题。通过正确使用 `Engine` 提供的生命周期管理钩子 (`add_subscriber` 和 `shutdown`)，我们可以确保所有组件都能以正确的顺序、在正确的时机完成清理工作，从而保证了系统的健壮性和可测试性。

### 目标
1.  修改 `tests/cli/e2e/test_e2e_watch_local_backend.py` 文件。
2.  在测试设置中，将 `TelemetrySubscriber` 实例通过 `engine.add_subscriber()` 方法注册到 `Engine`。

### 基本原理
注册 `TelemetrySubscriber` 后，`engine.run()` 在其 `finally` 清理块中，会首先调用并等待 `subscriber.shutdown()` 完成。`TelemetrySubscriber.shutdown()` 会等待所有待处理的遥测消息（包括 `ENGINE_STOPPED`）都发送完毕。只有在这之后，`engine.run()` 才会继续执行 `connector.disconnect()`。这个顺序保证了最后一条消息一定会在连接关闭前被发送，从而解决了时序竞争问题。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #concept/sync #scope/core #ai/instruct #task/domain/testing #task/object/watch-local-backend #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 在测试中正确注册 TelemetrySubscriber

我们将修补测试文件，在 `Engine` 实例化后，添加对 `add_subscriber` 的调用。

~~~~~act
patch_file
tests/cli/e2e/test_e2e_watch_local_backend.py
~~~~~
~~~~~python
    # 2. Configure Engine with LocalConnector
    event_bus = MessageBus()
    connector = LocalConnector(db_path=str(db_path), telemetry_uds_path=uds_path)
    # We must attach TelemetrySubscriber manually as cs.run would do
    TelemetrySubscriber(event_bus, connector)

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=event_bus,
        connector=connector,
    )
~~~~~
~~~~~python
    # 2. Configure Engine with LocalConnector
    event_bus = MessageBus()
    connector = LocalConnector(db_path=str(db_path), telemetry_uds_path=uds_path)
    
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=event_bus,
        connector=connector,
    )

    # We must attach and REGISTER the TelemetrySubscriber so the engine manages its lifecycle
    subscriber = TelemetrySubscriber(event_bus, connector)
    engine.add_subscriber(subscriber)
~~~~~

### 下一步建议
这个修复应该能彻底解决测试失败的问题。在您确认后，请再次运行测试。如果一切顺利，我们就可以生成最终的 `[COMMIT]` 计划来结束这个宏大任务了。
