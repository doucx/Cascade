Excellent. The tests failed with the expected `AttributeError`, confirming our test suite is correctly identifying the problem. We are now in a clear "RED" state.

The traceback shows the error occurs deep inside the engine's graph execution strategy, which correctly received a `list` where it expected a `LazyResult`. This is exactly the scenario our new logic in `cs.run` will prevent.

I will now generate the plan to implement the auto-gathering feature, turning our tests from RED to GREEN.

## [WIP] feat: Implement auto-gathering for cs.run

### 用户需求
根据提案 CP-011，`cs.run()` 函数需要被扩展，以接受 `LazyResult` 对象的列表或元组作为其 `target` 参数。当接收到此类输入时，它应自动将这些任务并行执行，并返回一个包含所有结果的列表。

### 评论
这个功能是提升开发者体验（DX）的关键一步。通过在 API 入口层处理可迭代对象，我们向 Python 开发者熟悉的 `asyncio.gather` 模式看齐，消除了不必要的样板代码，使得并行工作流的定义更加直观和简洁。

### 目标
1.  在 `cascade.internal.inputs` 中创建一个新的内部任务 `_internal_gather`, 它应被标记为 `pure=True`，并能接收任意数量的位置参数，将它们作为列表返回。
2.  修改 `cascade.run` 函数的逻辑：
    *   检测 `target` 参数是否为列表或元组。
    *   如果是，则将 `target` 包装在一个对 `_internal_gather` 的 `LazyResult` 调用中。
    *   处理空列表的边缘情况，直接返回一个空列表以避免不必要的引擎启动。
    *   将包装后的 `LazyResult` (或原始 `target`) 传递给引擎执行。

### 基本原理
我们将在 `cs.run` 这个面向用户的 API 门面中实现转换逻辑。通过检查 `target` 的类型，我们可以无缝地将 `[task_a, task_b]` 这样的用户输入，转换为引擎可以理解的单一根节点 `_internal_gather(task_a, task_b)`。由于 `_internal_gather` 是一个纯任务，它不会引入任何执行开销，同时又能确保图构建器和求解器能正确地处理依赖关系，从而以最小的架构侵入性实现这个强大的语法糖。

### 标签
#intent/build #flow/ready #priority/high #comp/sdk #scope/api #scope/dx #ai/instruct #task/domain/sdk #task/object/auto-gathering #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 定义内部 `_internal_gather` 任务

首先，我们在 `internal/inputs.py` 中创建这个核心的、纯粹的汇合任务。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/internal/inputs.py
~~~~~
~~~~~python
# 这个任务的职责是从 OS 环境中获取值。
@task(name="_get_env_var")
def _get_env_var(name: str) -> Optional[str]:
    return os.getenv(name)
~~~~~
~~~~~python
# 这个任务的职责是从 OS 环境中获取值。
@task(name="_get_env_var")
def _get_env_var(name: str) -> Optional[str]:
    return os.getenv(name)


@task(name="_internal_gather", pure=True)
def _internal_gather(*args: Any) -> Any:
    """An internal pure task used by cs.run to gather results from a list."""
    return list(args)
~~~~~

#### Acts 2: 在 `cs.run` 中实现自动汇合逻辑

现在，我们修改 `cs.run` 函数，使其能够处理列表和元组输入。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python
# --- Main Run Entrypoint ---


def _create_state_backend_factory(
    backend_spec: Union[str, Callable[[str], StateBackend], None],
):
    """
    Helper to create a factory function from a backend specification (URI or object).
    """
    if backend_spec is None:
        return None  # Engine defaults to InMemory

    if callable(backend_spec):
        return backend_spec

    if isinstance(backend_spec, str):
        if backend_spec.startswith("redis://"):
            try:
                import redis
                from cascade.adapters.state.redis import RedisStateBackend
            except ImportError:
                raise ImportError(
                    "The 'redis' library is required for redis:// backends."
                )

            # Create a shared client pool
            client = redis.from_url(backend_spec)

            def factory(run_id: str) -> StateBackend:
                return RedisStateBackend(run_id=run_id, client=client)

            return factory
        else:
            raise ValueError(f"Unsupported state backend URI scheme: {backend_spec}")

    raise TypeError(f"Invalid state_backend type: {type(backend_spec)}")


def run(
    target: LazyResult,
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
    log_format: str = "human",
    connector: Optional[Connector] = None,
    state_backend: Union[str, Callable[[str], StateBackend], None] = None,
) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.

    Args:
        state_backend: A URI string (e.g. "redis://localhost") or a factory function
                       that accepts a run_id and returns a StateBackend.
    """
    # 1. Setup the messaging renderer
    if log_format == "json":
        renderer = JsonRenderer(min_level=log_level)
    else:
        renderer = CliRenderer(store=bus.store, min_level=log_level)
    bus.set_renderer(renderer)

    # 2. Setup the event system
    event_bus = MessageBus()
    # Attach the human-readable log translator
    HumanReadableLogSubscriber(event_bus)
    # Attach the telemetry publisher if a connector is provided
    if connector:
        TelemetrySubscriber(event_bus, connector)

    # 3. Assemble the default Engine
    solver = NativeSolver()
    executor = LocalExecutor()

    sb_factory = _create_state_backend_factory(state_backend)

    engine = Engine(
        solver=solver,
        executor=executor,
        bus=event_bus,
        system_resources=system_resources,
        connector=connector,
        state_backend_factory=sb_factory,
    )

    return asyncio.run(engine.run(target, params=params))
~~~~~
~~~~~python
# --- Main Run Entrypoint ---


def _create_state_backend_factory(
    backend_spec: Union[str, Callable[[str], StateBackend], None],
):
    """
    Helper to create a factory function from a backend specification (URI or object).
    """
    if backend_spec is None:
        return None  # Engine defaults to InMemory

    if callable(backend_spec):
        return backend_spec

    if isinstance(backend_spec, str):
        if backend_spec.startswith("redis://"):
            try:
                import redis
                from cascade.adapters.state.redis import RedisStateBackend
            except ImportError:
                raise ImportError(
                    "The 'redis' library is required for redis:// backends."
                )

            # Create a shared client pool
            client = redis.from_url(backend_spec)

            def factory(run_id: str) -> StateBackend:
                return RedisStateBackend(run_id=run_id, client=client)

            return factory
        else:
            raise ValueError(f"Unsupported state backend URI scheme: {backend_spec}")

    raise TypeError(f"Invalid state_backend type: {type(backend_spec)}")


def run(
    target: Union[LazyResult, List[Any], tuple[Any, ...]],
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
    log_format: str = "human",
    connector: Optional[Connector] = None,
    state_backend: Union[str, Callable[[str], StateBackend], None] = None,
) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.

    Args:
        target: The LazyResult to execute, or a list/tuple of LazyResults
                and literals to execute in parallel.
        state_backend: A URI string (e.g. "redis://localhost") or a factory function
                       that accepts a run_id and returns a StateBackend.
    """
    # 1. Setup the messaging renderer
    if log_format == "json":
        renderer = JsonRenderer(min_level=log_level)
    else:
        renderer = CliRenderer(store=bus.store, min_level=log_level)
    bus.set_renderer(renderer)

    # 2. Setup the event system
    event_bus = MessageBus()
    # Attach the human-readable log translator
    HumanReadableLogSubscriber(event_bus)
    # Attach the telemetry publisher if a connector is provided
    if connector:
        TelemetrySubscriber(event_bus, connector)

    # 3. Handle Auto-Gathering
    from .internal.inputs import _internal_gather

    if isinstance(target, (list, tuple)):
        # Handle edge case of empty list
        if not target:
            return []
        # Wrap the iterable in the internal gather task
        workflow_target = _internal_gather(*target)
    else:
        workflow_target = target

    # 4. Assemble the default Engine
    solver = NativeSolver()
    executor = LocalExecutor()

    sb_factory = _create_state_backend_factory(state_backend)

    engine = Engine(
        solver=solver,
        executor=executor,
        bus=event_bus,
        system_resources=system_resources,
        connector=connector,
        state_backend_factory=sb_factory,
    )

    return asyncio.run(engine.run(workflow_target, params=params))
~~~~~

### 下一步建议

我们已经成功地将 RED 状态转换为实现代码。现在，请重新运行 `tests/sdk/integration/test_auto_gathering.py` 中的测试。我预期所有测试都将通过，将我们的 TDD 周期推进到 GREEN 状态。
