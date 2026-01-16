好的，分析完毕。这是一个典型的因“便利性”而破坏架构分层的循环依赖问题。`Engine` 作为底层运行时，为了方便用户（尤其是测试）直接实例化，而对自己本不应感知的上层策略实现 `GraphExecutionStrategy` 产生了依赖。

正确的做法是坚持依赖注入（DI）原则：`Engine` 只接受一个抽象的 `ExecutionStrategy`，而不关心其具体实现。具体的策略实例由更高层的应用或测试代码来创建和注入。

我将执行以下计划来解决这个问题：

1.  **净化 `Engine`**: 我将修改 `cascade.runtime.host.instance.py` 中的 `Engine` 类。
    *   移除所有动态加载策略的内部方法 (`_resolve_default_strategy`, `_load_vm_strategy`, `_load_graph_strategy`)。
    *   将 `__init__` 方法中的 `strategy` 参数设为必需项，彻底切断对 `cascade-execution-graph` 的隐式依赖。
    *   移除 `run` 方法中已废弃的 `use_vm` 参数。
2.  **创建测试 Fixture**: 我将在根目录的 `conftest.py` 中添加一个新的 `engine_factory` pytest fixture。
    *   这个工厂将封装之前存在于 `Engine` 中的默认策略选择逻辑（即检查 `CASCADE_BACKEND` 环境变量）。
    *   它将负责创建和组装所有必要的组件（如 `NodeProcessor`, `ResourceManager` 等），并实例化一个完整的 `Engine`。
    *   同时，我还会提供一个简单的 `engine` fixture，它直接使用这个工厂来创建一个默认配置的 `Engine` 实例，以便现有的大量测试可以无缝迁移。

这个重构将使 `cascade-runtime` 成为一个纯粹的、无上层依赖的核心库，同时将测试和应用配置的复杂性隔离在它们应该在的地方。

## [WIP] refactor(runtime): Decouple Engine from execution strategies via DI

### 用户需求

解决 `cascade-runtime` 和 `cascade-execution-graph` 之间的循环依赖问题。`Engine` 类不应直接依赖于任何具体的 `ExecutionStrategy` 实现。

### 评论

这是一个关键的架构重构。通过强制使用依赖注入，我们恢复了正确的依赖方向（`execution-graph` -> `runtime`），消除了循环依赖，并使 `Engine` 的职责更加清晰。将策略的构建逻辑移至测试 fixture 中，既能保持测试代码的简洁，又遵循了“关注点分离”的原则。

### 目标

1.  修改 `Engine` 类，使其 `__init__` 方法必须接收一个 `ExecutionStrategy` 实例。
2.  移除 `Engine` 内部所有用于动态加载默认策略的代码。
3.  在根 `conftest.py` 文件中创建一个 `engine_factory` fixture，用于在测试中构建带有默认策略的 `Engine` 实例。
4.  添加一个简单的 `engine` fixture 以简化大多数测试用例。

### 基本原理

我们将遵循依赖注入（Dependency Injection）原则。`Engine` 将不再负责创建或选择其 `ExecutionStrategy`。这个责任被转移给 `Engine` 的调用者。对于测试，我们利用 Pytest 的 fixture 机制来提供一个中央工厂 (`engine_factory`)，该工厂封装了构建 `Engine` 及其默认策略（如图策略或VM策略）的复杂性。这使得核心库 (`cascade-runtime`) 保持了对上层实现的无知，从而打破了循环依赖。

### 标签

#intent/refine #flow/ready #priority/high #comp/runtime #comp/tests #scope/core #dx #ai/instruct #task/domain/testing #task/object/engine-fixture #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 重构 Engine 以强制依赖注入

首先，我们将修改 `Engine` 类，移除其内部的策略选择逻辑，并要求在构造时必须传入一个策略实例。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/host/instance.py
~~~~~
~~~~~python.old
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
        object_store: Optional[ObjectStore] = None,
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
        self.object_store = object_store or InMemoryObjectStore()

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
            self.strategy = self._resolve_default_strategy()

        self._managed_subscribers = []

    def _resolve_default_strategy(self) -> ExecutionStrategy:
        backend_choice = os.getenv("CASCADE_BACKEND", "graph").lower()
        if backend_choice == "vm":
            return self._load_vm_strategy()
        else:
            return self._load_graph_strategy()

    def _load_vm_strategy(self) -> ExecutionStrategy:
        from cascade.runtime.strategies.vm import VMExecutionStrategy

        return VMExecutionStrategy(executor=self.executor, bus=self.bus)

    def _load_graph_strategy(self) -> ExecutionStrategy:
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
        self._managed_subscribers.append(subscriber)

    def register(self, resource_def: ResourceDefinition):
        self.resource_container.register(resource_def)

    def _is_simple_task(self, lr: Any) -> bool:
        if not isinstance(lr, LazyResult):
            return False
        if lr._condition or (lr._constraints and not lr._constraints.is_empty()):
            return False

        def _has_lazy(obj):
            if isinstance(obj, (LazyResult, MappedLazyResult)):
                return True
            if isinstance(obj, (list, tuple)):
                return any(_has_lazy(x) for x in obj)
            if isinstance(obj, dict):
                return any(_has_lazy(v) for v in obj.values())
            return False

        # Check args and kwargs recursively
        for arg in lr.args:
            if _has_lazy(arg):
                return False

        for v in lr.kwargs.values():
            if _has_lazy(v):
                return False

        return True

    def get_resource_provider(self, name: str) -> Callable:
        return self.resource_container.get_provider(name)

    def override_resource_provider(self, name: str, new_provider: Any):
        self.resource_container.override_provider(name, new_provider)

    async def run(
        self,
        target: Any,
        use_vm: bool = False,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
~~~~~
~~~~~python.new
class Engine:
    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: EventBus,
        strategy: ExecutionStrategy,
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

        # Setup constraint manager with default handlers
        self.constraint_manager = ConstraintManager(self.resource_manager)
        self.constraint_manager.register_handler(PauseConstraintHandler())
        self.constraint_manager.register_handler(ConcurrencyConstraintHandler())
        self.constraint_manager.register_handler(RateLimitConstraintHandler())

        self._wakeup_event = asyncio.Event()
        self.constraint_manager.set_wakeup_callback(self._wakeup_event.set)

        self.resource_container = ResourceContainer(self.bus)

        self._managed_subscribers = []

    def add_subscriber(self, subscriber: Any):
        self._managed_subscribers.append(subscriber)

    def register(self, resource_def: ResourceDefinition):
        self.resource_container.register(resource_def)

    def _is_simple_task(self, lr: Any) -> bool:
        if not isinstance(lr, LazyResult):
            return False
        if lr._condition or (lr._constraints and not lr._constraints.is_empty()):
            return False

        def _has_lazy(obj):
            if isinstance(obj, (LazyResult, MappedLazyResult)):
                return True
            if isinstance(obj, (list, tuple)):
                return any(_has_lazy(x) for x in obj)
            if isinstance(obj, dict):
                return any(_has_lazy(v) for v in obj.values())
            return False

        # Check args and kwargs recursively
        for arg in lr.args:
            if _has_lazy(arg):
                return False

        for v in lr.kwargs.values():
            if _has_lazy(v):
                return False

        return True

    def get_resource_provider(self, name: str) -> Callable:
        return self.resource_container.get_provider(name)

    def override_resource_provider(self, name: str, new_provider: Any):
        self.resource_container.override_provider(name, new_provider)

    async def run(
        self,
        target: Any,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
~~~~~

#### Acts 2: 在 conftest.py 中提供 Engine 工厂 Fixture

现在，我们将之前移除的逻辑重新实现在测试基础设施中，为测试提供便利的 `engine_factory` 和 `engine` fixture。

~~~~~act
patch_file
conftest.py
~~~~~
~~~~~python.old
@pytest.fixture
def bus_and_spy():
    """Provides a runtime EventBus instance and an attached SpySubscriber."""
    bus = EventBus()
    spy = SpySubscriber(bus)
    return bus, spy
~~~~~
~~~~~python.new
@pytest.fixture
def bus_and_spy():
    """Provides a runtime EventBus instance and an attached SpySubscriber."""
    bus = EventBus()
    spy = SpySubscriber(bus)
    return bus, spy


# --- Engine Fixtures for Decoupled Testing ---

import os
import asyncio
from typing import Callable, Any, Dict, Optional

# Core Engine & Interfaces
from cascade.runtime.host.instance import Engine
from cascade.spec.runtime import ExecutionStrategy, Solver, Executor
from cascade.runtime import ResourceManager

# Default Components for Graph Strategy
from cascade.execution.graph.solvers.native import NativeSolver
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.execution.graph.logic.processor import NodeProcessor
from cascade.execution.graph.strategy import GraphExecutionStrategy
from cascade.runtime.services.constraints.manager import ConstraintManager
from cascade.runtime.services.resources.container import ResourceContainer

# Default Components for VM Strategy
from cascade.runtime.strategies.vm import VMExecutionStrategy


@pytest.fixture
def engine_factory() -> Callable[..., Engine]:
    """
    Provides a factory function to create a Cascade Engine instance.

    This factory encapsulates the logic for selecting a default execution strategy
    based on the CASCADE_BACKEND environment variable, decoupling the core Engine
    from specific strategy implementations.
    """

    def _factory(
        *,  # Force keyword arguments for clarity
        solver: Optional[Solver] = None,
        executor: Optional[Executor] = None,
        bus: Optional[EventBus] = None,
        strategy: Optional[ExecutionStrategy] = None,
        resource_manager: Optional[ResourceManager] = None,
        **kwargs,  # Pass-through for other Engine args like connector, system_resources etc.
    ) -> Engine:
        # 1. Provide sane defaults for core components
        _solver = solver or NativeSolver()
        _executor = executor or LocalExecutor()
        _bus = bus or EventBus()

        # 2. Manage shared ResourceManager dependency
        # If a manager is passed in, use it. Otherwise, create one from system_resources kwarg.
        _resource_manager = resource_manager or ResourceManager(
            capacity=kwargs.get("system_resources")
        )

        # 3. Create strategy if not provided
        if strategy is None:
            backend_choice = os.getenv("CASCADE_BACKEND", "graph").lower()
            if backend_choice == "vm":
                strategy = VMExecutionStrategy(executor=_executor, bus=_bus)
            else:  # Default to 'graph'
                # build graph strategy with shared components
                constraint_manager = ConstraintManager(_resource_manager)
                wakeup_event = asyncio.Event()
                constraint_manager.set_wakeup_callback(wakeup_event.set)
                resource_container = ResourceContainer(_bus)
                node_processor = NodeProcessor(
                    executor=_executor,
                    bus=_bus,
                    resource_manager=_resource_manager,
                    constraint_manager=constraint_manager,
                    solver=_solver,
                )
                strategy = GraphExecutionStrategy(
                    solver=_solver,
                    node_processor=node_processor,
                    resource_container=resource_container,
                    constraint_manager=constraint_manager,
                    bus=_bus,
                    wakeup_event=wakeup_event,
                )

        # 4. Construct Engine with all components
        return Engine(
            solver=_solver,
            executor=_executor,
            bus=_bus,
            strategy=strategy,
            resource_manager=_resource_manager,
            **kwargs,  # Pass through system_resources, connector etc.
        )

    return _factory


@pytest.fixture
def engine(engine_factory: Callable[..., Engine]) -> Engine:
    """Provides a default-configured Cascade Engine instance for simple tests."""
    return engine_factory()
~~~~~

### 下一步建议

现在我们已经完成了核心重构。下一步是运行完整的测试套件 (`pytest`)。由于我们引入了 `engine_factory` 和 `engine` fixture 来替代旧的 `Engine()` 调用方式，可能会有一些测试文件需要更新以使用新的 fixture。如果测试失败，我将生成修复这些测试的计划。
