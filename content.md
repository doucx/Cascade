我将执行 Phase 3：引擎解耦。这将消除 `Engine` 对遗留图执行器代码的静态依赖，转而使用依赖注入或动态加载。这会将 `cascade-runtime` 转变为一个纯粹的宿主环境。

## [WIP] refactor(runtime): 解耦 Engine 与遗留图执行器

### 用户需求
实施重构路线图的 Phase 3：Engine Decoupling。
核心目标是修改 `Engine` 类，使其不再硬编码依赖 `GraphExecutionStrategy` 和 `NodeProcessor`，而是通过构造函数注入 `ExecutionStrategy`，或在未提供时动态加载默认策略（即旧的图执行器）。

### 评论
这是一个关键的架构转折点。它将“怎么跑（Strategy）”从“跑在哪里（Host）”中物理剥离。
这也为未来引入 `VMExecutionStrategy` 扫清了障碍，并允许 `cascade-runtime` 在没有遗留代码包的情况下独立运行。
目前 `Engine.run` 方法中的 `use_vm` 参数逻辑将被简化，策略的选择权上移至 Engine 的初始化阶段。

### 目标
1.  修改 `cascade/runtime/host/instance.py`。
2.  移除对 `cascade.execution.graph.*` 和 `cascade.runtime.legacy.*` 的顶层导入。
3.  更新 `Engine.__init__` 以接受可选的 `strategy` 参数。
4.  实现 `_load_default_strategy` 方法以动态加载旧的图执行器（保持向后兼容）。
5.  更新 `Engine.run` 以使用配置好的策略。

### 基本原理
通过将具体的执行策略（Strategy）作为依赖注入或动态插件，`Engine` 变成了通用的工作流宿主，不再受限于特定的执行模型。这符合“Host-Plugin”架构模式。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/runtime #task/object/engine #task/action/decouple #task/state/continue

---

### Script

#### Acts 1: 解耦 Engine

我们将修改 `instance.py`，移除静态依赖并实现动态加载逻辑。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/host/instance.py
~~~~~
~~~~~python.old
from cascade.runtime.services.constraints.handlers import (
    PauseConstraintHandler,
    ConcurrencyConstraintHandler,
    RateLimitConstraintHandler,
)
from cascade.runtime.io.state import InMemoryStateBackend
from cascade.execution.graph.logic.processor import NodeProcessor
from cascade.runtime.services.resources.container import ResourceContainer
from cascade.runtime.legacy.strategies import (
    GraphExecutionStrategy,
)
from cascade.spec.runtime import ExecutionContext


class Engine:
    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: EventBus,
        state_backend_factory: Optional[Callable[[str], StateBackend]] = None,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
        cache_backend: Optional[Any] = None,
        resource_manager: Optional[ResourceManager] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.connector = connector
        # Default to InMemory factory if none provided
        self.state_backend_factory = state_backend_factory or (
            lambda run_id: InMemoryStateBackend(run_id)
        )
        self.cache_backend = cache_backend

        if resource_manager:
            self.resource_manager = resource_manager
            # If system_resources is also provided, we update the injected manager
            if system_resources:
                self.resource_manager.set_capacity(system_resources)
        else:
            self.resource_manager = ResourceManager(capacity=system_resources)

        # Setup constraint manager with default handlers
        self.constraint_manager = ConstraintManager(self.resource_manager)
        self.constraint_manager.register_handler(PauseConstraintHandler())
        self.constraint_manager.register_handler(ConcurrencyConstraintHandler())
        self.constraint_manager.register_handler(RateLimitConstraintHandler())

        self._wakeup_event = asyncio.Event()
        self.constraint_manager.set_wakeup_callback(self._wakeup_event.set)

        self.resource_container = ResourceContainer(self.bus)

        # Delegate node execution logic to NodeProcessor
        self.node_processor = NodeProcessor(
            executor=self.executor,
            bus=self.bus,
            resource_manager=self.resource_manager,
            constraint_manager=self.constraint_manager,
            solver=self.solver,
        )

        # Initialize Strategies
        self.graph_strategy = GraphExecutionStrategy(
            solver=self.solver,
            node_processor=self.node_processor,
            resource_container=self.resource_container,
            constraint_manager=self.constraint_manager,
            bus=self.bus,
            wakeup_event=self._wakeup_event,
        )
        self.vm_strategy = self.graph_strategy  # for future

        self._managed_subscribers = []

    def add_subscriber(self, subscriber: Any):
~~~~~
~~~~~python.new
from cascade.runtime.services.constraints.handlers import (
    PauseConstraintHandler,
    ConcurrencyConstraintHandler,
    RateLimitConstraintHandler,
)
from cascade.runtime.io.state import InMemoryStateBackend
from cascade.runtime.services.resources.container import ResourceContainer
from cascade.spec.runtime import ExecutionContext
from cascade.runtime.strategies import ExecutionStrategy


class Engine:
    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: EventBus,
        state_backend_factory: Optional[Callable[[str], StateBackend]] = None,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
        cache_backend: Optional[Any] = None,
        resource_manager: Optional[ResourceManager] = None,
        strategy: Optional[ExecutionStrategy] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.connector = connector
        # Default to InMemory factory if none provided
        self.state_backend_factory = state_backend_factory or (
            lambda run_id: InMemoryStateBackend(run_id)
        )
        self.cache_backend = cache_backend

        if resource_manager:
            self.resource_manager = resource_manager
            # If system_resources is also provided, we update the injected manager
            if system_resources:
                self.resource_manager.set_capacity(system_resources)
        else:
            self.resource_manager = ResourceManager(capacity=system_resources)

        # Setup constraint manager with default handlers
        self.constraint_manager = ConstraintManager(self.resource_manager)
        self.constraint_manager.register_handler(PauseConstraintHandler())
        self.constraint_manager.register_handler(ConcurrencyConstraintHandler())
        self.constraint_manager.register_handler(RateLimitConstraintHandler())

        self._wakeup_event = asyncio.Event()
        self.constraint_manager.set_wakeup_callback(self._wakeup_event.set)

        self.resource_container = ResourceContainer(self.bus)

        if strategy:
            self.strategy = strategy
        else:
            self.strategy = self._load_default_strategy()

        self._managed_subscribers = []

    def _load_default_strategy(self) -> ExecutionStrategy:
        """
        Dynamically loads the legacy GraphExecutionStrategy if available.
        This provides backward compatibility without hard compile-time dependencies.
        """
        try:
            # Dynamic imports to break hard dependency
            from cascade.execution.graph.logic.processor import NodeProcessor
            from cascade.execution.graph.strategy import GraphExecutionStrategy

            # Reconstruct the legacy stack
            node_processor = NodeProcessor(
                executor=self.executor,
                bus=self.bus,
                resource_manager=self.resource_manager,
                constraint_manager=self.constraint_manager,
                solver=self.solver,
            )

            return GraphExecutionStrategy(
                solver=self.solver,
                node_processor=node_processor,
                resource_container=self.resource_container,
                constraint_manager=self.constraint_manager,
                bus=self.bus,
                wakeup_event=self._wakeup_event,
            )
        except ImportError:
            raise RuntimeError(
                "No execution strategy provided and 'cascade-execution-graph' package not found. "
                "Please install 'cascade-execution-graph' or provide a custom strategy."
            )

    def add_subscriber(self, subscriber: Any):
~~~~~

#### Acts 2: 更新 Engine.run 方法

移除 `use_vm` 的逻辑（因为现在由构造函数决定），并使用 `self.strategy`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/host/instance.py
~~~~~
~~~~~python.old
    async def run(
        self,
        target: Any,
        use_vm: bool = False,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        # Handle Auto-Gathering
        from cascade.reflection import _internal_gather

        if isinstance(target, (list, tuple)):
            if not target:
                return []
            workflow_target = _internal_gather(*target)
        else:
            workflow_target = target

        run_id = str(uuid4())
        start_time = time.time()

        # Robustly determine initial target name for logging
        target_name = "unknown"
        if isinstance(target, LazyResult):
            target_name = getattr(target.task, "name", "unknown")
        elif isinstance(target, MappedLazyResult):
            target_name = f"map({getattr(target.factory, 'name', 'unknown')})"

        # Initialize State Backend using the factory
        state_backend = self.state_backend_factory(run_id)

        try:
            # 1. Establish Infrastructure Connection FIRST
            if self.connector:
                await self.connector.connect()
                self.bus.publish(ConnectorConnected(run_id=run_id))
                await self.connector.subscribe(
                    "cascade/constraints/#", self._on_constraint_update
                )

            # 2. Publish Lifecycle Event
            self.bus.publish(
                RunStarted(
                    run_id=run_id, target_tasks=[target_name], params=params or {}
                )
            )

            # 3. Select Strategy
            # The explicit `use_vm` flag takes precedence.
            # Otherwise, fall back to the environment variable for testing/experimental runs.
            should_use_vm = use_vm or os.getenv("CASCADE_BACKEND") == "vm"
            strategy = self.vm_strategy if should_use_vm else self.graph_strategy

            # 4. Execute
            # The global stack holds "run" scoped resources
            with ExitStack() as run_stack:
                # Register the engine's connector as a special internal resource
                if self.connector:
                    from cascade.spec.dsl.resources import ResourceDefinition

                    # We define the provider and then explicitly wrap it in a ResourceDefinition
                    # because the @resource decorator doesn't work as expected on closures
                    # defined inside another function for some type checkers.
                    def _connector_provider():
                        yield self.connector

                    connector_res_def = ResourceDefinition(
                        func=_connector_provider,
                        name="_internal_connector",
                        scope="run",
                    )
                    self.register(connector_res_def)

                active_resources: Dict[str, Any] = {}

                context = ExecutionContext(
                    run_id=run_id,
                    state_backend=state_backend,
                    run_stack=run_stack,
                    active_resources=active_resources,
                    params=params or {},
                )

                final_result = await strategy.execute(
                    target=workflow_target, context=context
                )

            duration = time.time() - start_time
            self.bus.publish(
                RunFinished(
                    run_id=run_id, status=EventState.SUCCEEDED, duration=duration
                )
            )
            return final_result
~~~~~
~~~~~python.new
    async def run(
        self,
        target: Any,
        use_vm: bool = False,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        # Handle Auto-Gathering
        from cascade.reflection import _internal_gather

        if isinstance(target, (list, tuple)):
            if not target:
                return []
            workflow_target = _internal_gather(*target)
        else:
            workflow_target = target

        run_id = str(uuid4())
        start_time = time.time()

        # Robustly determine initial target name for logging
        target_name = "unknown"
        if isinstance(target, LazyResult):
            target_name = getattr(target.task, "name", "unknown")
        elif isinstance(target, MappedLazyResult):
            target_name = f"map({getattr(target.factory, 'name', 'unknown')})"

        # Initialize State Backend using the factory
        state_backend = self.state_backend_factory(run_id)

        try:
            # 1. Establish Infrastructure Connection FIRST
            if self.connector:
                await self.connector.connect()
                self.bus.publish(ConnectorConnected(run_id=run_id))
                await self.connector.subscribe(
                    "cascade/constraints/#", self._on_constraint_update
                )

            # 2. Publish Lifecycle Event
            self.bus.publish(
                RunStarted(
                    run_id=run_id, target_tasks=[target_name], params=params or {}
                )
            )

            # 3. Select Strategy
            # NOTE: `use_vm` is deprecated. Strategy is now selected at Engine init.
            # We use the configured strategy.
            strategy = self.strategy

            # 4. Execute
            # The global stack holds "run" scoped resources
            with ExitStack() as run_stack:
                # Register the engine's connector as a special internal resource
                if self.connector:
                    from cascade.spec.dsl.resources import ResourceDefinition

                    # We define the provider and then explicitly wrap it in a ResourceDefinition
                    # because the @resource decorator doesn't work as expected on closures
                    # defined inside another function for some type checkers.
                    def _connector_provider():
                        yield self.connector

                    connector_res_def = ResourceDefinition(
                        func=_connector_provider,
                        name="_internal_connector",
                        scope="run",
                    )
                    self.register(connector_res_def)

                active_resources: Dict[str, Any] = {}

                context = ExecutionContext(
                    run_id=run_id,
                    state_backend=state_backend,
                    run_stack=run_stack,
                    active_resources=active_resources,
                    params=params or {},
                )

                final_result = await strategy.execute(
                    target=workflow_target, context=context
                )

            duration = time.time() - start_time
            self.bus.publish(
                RunFinished(
                    run_id=run_id, status=EventState.SUCCEEDED, duration=duration
                )
            )
            return final_result
~~~~~

### 下一步建议
我们已经完成了 Phase 3。现在 Engine 已经解耦。
接下来的步骤是 **Phase 4: 依赖清理与配置 (Dependency Cleanup)**。我们需要从 `cascade-runtime/pyproject.toml` 中移除 `python-constraint` 依赖，并将其仅保留在 `cascade-execution-graph` 中（虽然目前 workspace 配置可能已经分开了，但需要确认清理）。
