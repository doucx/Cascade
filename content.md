## [WIP] feat(runtime): 引擎异步化与门面函数更新

### 用户需求
1.  将 `Engine.run` 改造为异步方法，以配合异步的 `Executor`。
2.  更新顶层 `cascade.run` 函数，使其能自动启动事件循环，对用户保持同步调用的便捷性。
3.  修复因异步改造而崩溃的集成测试。

### 评论
这是异步改造的收官之战。通过将 `Engine` 转变为异步，我们打通了整个调用链。虽然内部机制发生了翻天覆地的变化（从同步到异步），但在 `cascade.run` 这一层，我们通过 `asyncio.run` 保持了 API 的向后兼容性，这是一次优雅的重构。

### 目标
1.  修改 `src/cascade/runtime/engine.py`：将 `run` 方法改为 `async def`，并 `await` 执行器的结果。
2.  修改 `src/cascade/__init__.py`：在 `run` 函数中使用 `asyncio.run`。
3.  修复 `tests/test_end_to_end.py` 和 `tests/test_di_and_resources.py`：在直接使用 `Engine` 的测试中引入 `asyncio.run`。

### 基本原理
-   **全链路异步**: 只有当 `Engine` 也是异步的，它才能 `await` 异步的 `Executor`，从而正确获取结果而非协程对象。
-   **入口封装**: 对于库的使用者，特别是编写简单脚本的用户，`asyncio` 的复杂性被封装在 `cascade.run` 内部。
-   **测试适配**: 测试代码直接操作内部组件（Engine），因此必须显式管理事件循环。

### 标签
#intent/refine #flow/ready #priority/high
#comp/runtime #comp/tests #concept/async
#task/domain/core #task/object/async-support #task/action/implementation
#task/state/end #task/status/completed

---

### Script

#### Acts 1: Async Engine

将 `Engine.run` 转换为异步方法，并 `await` 执行器调用。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
    def override_resource_provider(self, name: str, new_provider: Any):
        # Unwrap ResourceDefinition if provided
        if isinstance(new_provider, ResourceDefinition):
            new_provider = new_provider.func
        self._resource_providers[name] = new_provider

    def run(self, target: LazyResult, params: Optional[Dict[str, Any]] = None) -> Any:
        run_id = str(uuid4())
        start_time = time.time()
~~~~~
~~~~~python
    def override_resource_provider(self, name: str, new_provider: Any):
        # Unwrap ResourceDefinition if provided
        if isinstance(new_provider, ResourceDefinition):
            new_provider = new_provider.func
        self._resource_providers[name] = new_provider

    async def run(
        self, target: LazyResult, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        run_id = str(uuid4())
        start_time = time.time()
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
                    self.bus.publish(start_event)

                    try:
                        result = self.executor.execute(
                            node, graph, results, active_resources
                        )
                        results[node.id] = result

                        task_duration = time.time() - task_start_time
~~~~~
~~~~~python
                    self.bus.publish(start_event)

                    try:
                        result = await self.executor.execute(
                            node, graph, results, active_resources
                        )
                        results[node.id] = result

                        task_duration = time.time() - task_start_time
~~~~~

#### Acts 2: Update Facade

更新 `cascade.run` 以使用 `asyncio.run`。

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
def run(target: LazyResult, params: Optional[Dict[str, Any]] = None) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.

    This is the primary entry point for users. It sets up a default
    engine with a human-readable logger.
    """
    bus = MessageBus()
    # Attach the default logger
    HumanReadableLogSubscriber(bus)

    engine = Engine(bus=bus)

    return engine.run(target, params=params)
~~~~~
~~~~~python
def run(target: LazyResult, params: Optional[Dict[str, Any]] = None) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.

    This is the primary entry point for users. It sets up a default
    engine with a human-readable logger.
    """
    bus = MessageBus()
    # Attach the default logger
    HumanReadableLogSubscriber(bus)

    engine = Engine(bus=bus)

    return asyncio.run(engine.run(target, params=params))
~~~~~

#### Acts 3: Fix DI Tests

修复 `tests/test_di_and_resources.py` 中的测试，使用 `asyncio.run`。

~~~~~act
patch_file
tests/test_di_and_resources.py
~~~~~
~~~~~python
def test_di_end_to_end():
    """Tests the full lifecycle: registration, injection, execution, teardown."""
    engine = cs.Engine()
    engine.register(config)
    engine.register(db_connection)

    result = engine.run(task_using_resource())

    assert result == "production_url"


def test_resource_events():
    """Tests that resource lifecycle events are emitted."""
    events = []
    bus = cs.MessageBus()
    bus.subscribe(Event, events.append)

    engine = cs.Engine(bus=bus)
    engine.register(config)
    engine.register(db_connection)

    engine.run(task_using_resource())

    # Check for ResourceAcquired events
~~~~~
~~~~~python
def test_di_end_to_end():
    """Tests the full lifecycle: registration, injection, execution, teardown."""
    import asyncio

    engine = cs.Engine()
    engine.register(config)
    engine.register(db_connection)

    result = asyncio.run(engine.run(task_using_resource()))

    assert result == "production_url"


def test_resource_events():
    """Tests that resource lifecycle events are emitted."""
    import asyncio

    events = []
    bus = cs.MessageBus()
    bus.subscribe(Event, events.append)

    engine = cs.Engine(bus=bus)
    engine.register(config)
    engine.register(db_connection)

    asyncio.run(engine.run(task_using_resource()))

    # Check for ResourceAcquired events
~~~~~

~~~~~act
patch_file
tests/test_di_and_resources.py
~~~~~
~~~~~python
    # Override the db_connection resource
    with cs.override_resource(engine, "db_connection", mock_db_connection):
        result = engine.run(task_using_resource())

    assert result == "mock_db_url"

    # After exiting the context, the original should be restored
    result_after = engine.run(task_using_resource())
    assert result_after == "production_url"
~~~~~
~~~~~python
    import asyncio

    # Override the db_connection resource
    with cs.override_resource(engine, "db_connection", mock_db_connection):
        result = asyncio.run(engine.run(task_using_resource()))

    assert result == "mock_db_url"

    # After exiting the context, the original should be restored
    result_after = asyncio.run(engine.run(task_using_resource()))
    assert result_after == "production_url"
~~~~~

#### Acts 4: Fix End-to-End Tests

修复 `tests/test_end_to_end.py` 中的测试，使用 `asyncio.run`。

~~~~~act
patch_file
tests/test_end_to_end.py
~~~~~
~~~~~python
    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    result = engine.run(final_greeting)

    assert result == "Hello, {name}!".format(name="Cascade")
~~~~~
~~~~~python
    import asyncio

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    result = asyncio.run(engine.run(final_greeting))

    assert result == "Hello, {name}!".format(name="Cascade")
~~~~~

~~~~~act
patch_file
tests/test_end_to_end.py
~~~~~
~~~~~python
    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    result = engine.run(r_d)
    assert result == 18
~~~~~
~~~~~python
    import asyncio

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    result = asyncio.run(engine.run(r_d))
    assert result == 18
~~~~~

~~~~~act
patch_file
tests/test_end_to_end.py
~~~~~
~~~~~python
    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    with pytest.raises(ValueError, match="Something went wrong"):
        engine.run(r3)

    assert spy.event_names() == [
~~~~~
~~~~~python
    import asyncio

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    with pytest.raises(ValueError, match="Something went wrong"):
        asyncio.run(engine.run(r3))

    assert spy.event_names() == [
~~~~~

### 下一步建议
运行测试。如果所有测试通过，则说明异步改造圆满完成。接下来，我们将进入 Cascade 阶段二的第三项任务：**缓存与重试机制**。这将进一步增强框架在不可靠环境下的健壮性。我们将首先从 **缓存协议与基础实现 (`FileExistenceCache`)** 开始。
