好的，我明白了。上一轮的修复引入了一个更深层次的架构问题，而这些测试失败是其直接症状。

所有失败的根本原因都是同一个：**`Engine` 和 `GraphExecutionStrategy` 之间存在状态隔离**。

具体来说：

1.  **`ResourceContainer` 的分裂**: 我们在 `Engine` 内部创建了一个 `ResourceContainer` 实例，并在 `run()` 方法中用它来注册内部资源（如 `_internal_connector`）。然而，我们传递给 `GraphExecutionStrategy` 的是**另一个** `ResourceContainer` 实例（在 `engine_factory` 中创建）。
2.  **状态不一致**:
    *   当测试调用 `engine.register(sqlite_db)` 时，资源被注册到了 `Engine` 的 `ResourceContainer` 中。
    *   当 `engine.run()` 调用 `strategy.execute()` 时，`Strategy` 使用它自己的、**空的** `ResourceContainer` 来扫描和设置资源。
    *   因此，当 `Strategy` 寻找 `sqlite_db` 或 `_internal_connector` 时，它在自己的容器里找不到，从而抛出 `NameError`。
3.  **`AssertionError` 的根源**: `test_recv_blocks_and_wakes_up` 的 `AssertionError: Engine finished prematurely` 是 `NameError` 的副作用。因为 `_internal_connector` 资源未找到导致 `run()` 提前异常退出，所以 `engine_task` 立即结束了，触发了断言失败。

我们之前解决了 `ConstraintManager` 的分裂问题，现在必须对 `ResourceContainer` 应用同样的修复。

我们将再次深化依赖注入模式，将 `ResourceContainer` 也提升为一个由外部创建并注入到 `Engine` 中的核心服务。

1.  **修改 `Engine.__init__`**: 使其接收一个 `ResourceContainer` 实例，而不是在内部创建它。
2.  **更新 `create_engine` 工厂**: 让工厂函数负责创建唯一的 `ResourceContainer` 实例，并将其同时注入到 `Engine` 和 `GraphExecutionStrategy` 中。

这样，`engine.register()` 和 `strategy.execute()` 将操作同一个 `ResourceContainer` 实例，确保了状态的完全一致。

## [WIP] fix(runtime): Unify ResourceContainer instance via dependency injection

### 错误分析

`Engine` 和 `GraphExecutionStrategy` 各自持有一个独立的 `ResourceContainer` 实例。这导致了 `engine.register()` 注册的资源（如 `sqlite_db`）或 `engine.run()` 内部注册的资源（如 `_internal_connector`）对于 `GraphExecutionStrategy` 来说是不可见的，从而在资源扫描阶段引发 `NameError`。

### 用户需求

修复所有因 `NameError: Resource ... not registered` 导致的测试失败，并确保整个运行时共享一个统一的 `ResourceContainer` 实例。

### 评论

这是对我们依赖注入架构的最后一次关键修正。通过将 `ResourceContainer` 的所有权也移出 `Engine` 并交由工厂管理，我们最终实现了一个纯粹的、无状态的服务容器 `Engine`。现在，所有的核心服务（`Strategy`, `ConstraintManager`, `ResourceContainer`）都是可替换、可共享的，这使得系统架构更加健壮和清晰。

### 目标

1.  修改 `Engine` 的构造函数，使其接收一个 `resource_container` 作为必需参数。
2.  更新 `cascade.runtime.host.factory.create_engine` 函数，让它创建 `ResourceContainer` 并将其注入到 `Engine` 和 `GraphExecutionStrategy` 中。

### 基本原理

我们将遵循与 `ConstraintManager` 相同的修复模式。`create_engine` 工厂将创建 `EventBus`，然后用这个 `EventBus` 实例来创建 `ResourceContainer`。接着，这个唯一的 `ResourceContainer` 实例将被传递给 `GraphExecutionStrategy`（用于资源扫描）和 `Engine`（用于内部资源注册）。这将保证任何通过 `engine.register()` 添加的资源对执行策略都是可见的，从而解决 `NameError`。

### 标签

#intent/fix #flow/ready #priority/critical #comp/runtime #scope/core #dx #ai/instruct #task/domain/runtime #task/object/dependency-injection #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 重构 Engine 以接收 ResourceContainer

我将修改 `instance.py`，使 `Engine` 依赖于外部提供的 `ResourceContainer`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/host/instance.py
~~~~~
~~~~~python.old
from ..services.resources.container import ResourceContainer


class Engine:
    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: EventBus,
        strategy: ExecutionStrategy,
        constraint_manager: ConstraintManager,
        wakeup_event: asyncio.Event,
        state_backend_factory: Optional[Callable[[str], StateBackend]] = None,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
        cache_backend: Optional[Any] = None,
        resource_manager: Optional[ResourceManager] = None,
        object_store: Optional[ObjectStore] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.strategy = strategy
        self.constraint_manager = constraint_manager
        self._wakeup_event = wakeup_event
        self.connector = connector
        # Default to InMemory factory if none provided
        self.state_backend_factory = state_backend_factory or (
            lambda run_id: InMemoryStateBackend(run_id)
        )
        self.cache_backend = cache_backend
        self.object_store = object_store or InMemoryObjectStore()

        if resource_manager:
            self.resource_manager = resource_manager
            # If system_resources is also provided, we update the injected manager
            if system_resources:
                self.resource_manager.set_capacity(system_resources)
        else:
            self.resource_manager = ResourceManager(capacity=system_resources)

        self.resource_container = ResourceContainer(self.bus)
        self._managed_subscribers = []
~~~~~
~~~~~python.new
from ..services.resources.container import ResourceContainer


class Engine:
    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: EventBus,
        strategy: ExecutionStrategy,
        constraint_manager: ConstraintManager,
        resource_container: ResourceContainer,
        wakeup_event: asyncio.Event,
        state_backend_factory: Optional[Callable[[str], StateBackend]] = None,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
        cache_backend: Optional[Any] = None,
        resource_manager: Optional[ResourceManager] = None,
        object_store: Optional[ObjectStore] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.strategy = strategy
        self.constraint_manager = constraint_manager
        self.resource_container = resource_container
        self._wakeup_event = wakeup_event
        self.connector = connector
        # Default to InMemory factory if none provided
        self.state_backend_factory = state_backend_factory or (
            lambda run_id: InMemoryStateBackend(run_id)
        )
        self.cache_backend = cache_backend
        self.object_store = object_store or InMemoryObjectStore()

        if resource_manager:
            self.resource_manager = resource_manager
            # If system_resources is also provided, we update the injected manager
            if system_resources:
                self.resource_manager.set_capacity(system_resources)
        else:
            self.resource_manager = ResourceManager(capacity=system_resources)

        self._managed_subscribers = []
~~~~~

#### Acts 2: 更新 `create_engine` 工厂以管理 `ResourceContainer`

现在，我将更新中央工厂函数，让它创建并注入 `ResourceContainer`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/host/factory.py
~~~~~
~~~~~python.old
    if strategy is None:
        backend_choice = "vm" if use_vm else os.getenv("CASCADE_BACKEND", "graph").lower()

        if backend_choice == "vm":
            from cascade.runtime.strategies.vm import VMExecutionStrategy
            strategy = VMExecutionStrategy(executor=_executor, bus=_bus)
        else:  # Default to 'graph'
            from cascade.execution.graph.logic.processor import NodeProcessor
            from cascade.execution.graph.strategy import GraphExecutionStrategy

            resource_container = ResourceContainer(_bus)
            node_processor = NodeProcessor(
                executor=_executor,
                bus=_bus,
                resource_manager=_resource_manager,
                constraint_manager=_constraint_manager,
                solver=_solver,
            )
            strategy = GraphExecutionStrategy(
                solver=_solver,
                node_processor=node_processor,
                resource_container=resource_container,
                constraint_manager=_constraint_manager,
                bus=_bus,
                wakeup_event=_wakeup_event,
            )

    # 4. Construct Engine with all assembled components
    return Engine(
        solver=_solver,
        executor=_executor,
        bus=_bus,
        strategy=strategy,
        resource_manager=_resource_manager,
        constraint_manager=_constraint_manager,
        wakeup_event=_wakeup_event,
        **kwargs,
    )
~~~~~
~~~~~python.new
    _resource_container = ResourceContainer(_bus)

    # 3. Create strategy if not provided
    if strategy is None:
        backend_choice = "vm" if use_vm else os.getenv("CASCADE_BACKEND", "graph").lower()

        if backend_choice == "vm":
            from cascade.runtime.strategies.vm import VMExecutionStrategy
            strategy = VMExecutionStrategy(executor=_executor, bus=_bus)
        else:  # Default to 'graph'
            from cascade.execution.graph.logic.processor import NodeProcessor
            from cascade.execution.graph.strategy import GraphExecutionStrategy

            node_processor = NodeProcessor(
                executor=_executor,
                bus=_bus,
                resource_manager=_resource_manager,
                constraint_manager=_constraint_manager,
                solver=_solver,
            )
            strategy = GraphExecutionStrategy(
                solver=_solver,
                node_processor=node_processor,
                resource_container=_resource_container,
                constraint_manager=_constraint_manager,
                bus=_bus,
                wakeup_event=_wakeup_event,
            )

    # 4. Construct Engine with all assembled components
    return Engine(
        solver=_solver,
        executor=_executor,
        bus=_bus,
        strategy=strategy,
        resource_manager=_resource_manager,
        constraint_manager=_constraint_manager,
        resource_container=_resource_container,
        wakeup_event=_wakeup_event,
        **kwargs,
    )
~~~~~

#### Acts 3: 更新 `CascadeApp` 以适应新的工厂签名

`CascadeApp` 不需要显式传递 `resource_container`，因为它被 `create_engine` 内部管理。但是，为了保持一致性，我需要检查 `create_engine` 的调用签名。我的上一个修复中，`CascadeApp` 调用 `create_engine` 时，并未传入 `constraint_manager` 和 `wakeup_event`，因为它们在工厂内部创建。新工厂仍然如此，所以 `CascadeApp` 的代码无需更改。太好了。

同样，`conftest.py` 中的 `engine_factory` 也不需要更改，因为它只是 `create_engine` 的一个薄封装。

### 下一步建议

现在，我们已经将 `ResourceContainer` 的创建和注入逻辑集中到了 `create_engine` 工厂中，彻底解决了 `Engine` 和 `Strategy` 之间的状态分裂问题。所有依赖此工厂的消费者（包括 `CascadeApp` 和所有测试）都将自动获得正确的、共享的服务实例。

我将再次运行完整的测试套件。我非常有信心，这次所有与资源注册相关的 `NameError` 和连锁导致的 `AssertionError` 都将得到解决。
