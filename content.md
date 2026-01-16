好的，分析完成。你的诊断非常准确，之前的重构虽然解耦了 `Engine` 和 `Strategy`，但没有将 `ConstraintManager` 的所有权也一并移出，导致 `Engine` 内部创建了一个 `ConstraintManager` 实例用于接收外部消息，而 `Strategy` 则使用了另一个在 `engine_factory` 中创建的实例来做决策，两者状态不通，因此所有基于外部消息的约束测试都失败了。

根本原因在于 **依赖关系不明确** 和 **责任分散**。`Engine` 不应该负责创建和配置像 `ConstraintManager` 这样的服务。它的职责应该是集成这些服务，并将它们连接在一起。

我将执行以下计划来修复这个问题：

1.  **重构 `Engine`**: 我将再次修改 `Engine` 的 `__init__` 方法，使其**必须**接收一个已经配置好的 `ConstraintManager` 和 `asyncio.Event` (用于唤醒)，彻底剥离其服务创建的职责。
2.  **增强 `engine_factory` Fixture**: 我会将服务（`ConstraintManager`）的创建、配置（注册 handlers）和连接（设置 wakeup callback）的全部责任都集中到 `conftest.py` 的 `engine_factory` 中。这个工厂现在将成为测试环境中所有核心运行时服务的“装配线”。

这个修复将确保在整个测试运行的生命周期中，只有一个 `ConstraintManager` 实例被创建和使用，从而保证状态的一致性，修复所有相关的约束测试失败。

## [WIP] fix(runtime): Ensure single ConstraintManager instance via DI

### 错误分析

测试在并发和暂停约束条件下失败，因为 `Engine` 实例和 `GraphExecutionStrategy` 实例使用了两个不同的 `ConstraintManager`。`Engine` 内部创建了一个用于接收 `connector` 消息的 `ConstraintManager`，而 `engine_factory` fixture 为 `GraphExecutionStrategy` 创建了另一个实例。因此，从连接器收到的约束更新从未应用到执行逻辑中。

### 用户需求

修复所有与约束相关的测试失败，通过重构确保 `Engine` 和其 `ExecutionStrategy` 共享同一个 `ConstraintManager` 实例。

### 评论

这是一个经典的依赖注入问题。通过将 `ConstraintManager` 的所有权从 `Engine` 转移到外部工厂（在此场景中是 `engine_factory` fixture），我们确保了整个运行时堆栈中该服务的单一实例。这不仅修复了当前的 bug，也让 `Engine` 的职责更加纯粹——它现在是一个服务集成器，而不是服务创建者，这使得系统更加模块化和可测试。

### 目标

1.  修改 `Engine` 的构造函数，使其接收 `constraint_manager` 和 `wakeup_event` 作为必需参数。
2.  从 `Engine` 中移除所有 `ConstraintManager` 的创建和配置逻辑。
3.  更新 `conftest.py` 中的 `engine_factory` fixture，让它负责创建和配置唯一的 `ConstraintManager` 实例，并将其注入到 `Engine` 和 `GraphExecutionStrategy` 中。

### 基本原理

我们将深化依赖注入模式的应用。`Engine` 将不再拥有或创建其核心服务。`engine_factory` 将作为依赖注入容器，在测试环境中负责组装整个运行时。它将：
1.  创建 `ResourceManager`。
2.  创建 `ConstraintManager` 并用 `ResourceManager` 对其进行初始化。
3.  在 `ConstraintManager` 上注册所有默认的约束处理器（`Pause`, `Concurrency`, `RateLimit`）。
4.  创建一个 `asyncio.Event` 作为唤醒信号，并将其回调设置到 `ConstraintManager`。
5.  将这同一个 `ConstraintManager` 和 `wakeup_event` 实例同时传递给 `GraphExecutionStrategy` 和 `Engine` 的构造函数。
这样，从 `connector` 进入 `Engine` 的约束消息和 `Strategy` 执行检查时所用的 `ConstraintManager` 将是同一个对象，确保了状态同步。

### 标签

#intent/fix #flow/ready #priority/critical #comp/runtime #comp/tests #scope/core #dx #ai/instruct #task/domain/testing #task/object/dependency-injection #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 重构 Engine，使其完全接受外部依赖

我将使用 `write_file` 更新 `instance.py`，移除 `Engine` 内部的服务创建逻辑。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/host/instance.py
~~~~~
~~~~~python
import os
import sys
import time
import asyncio
from typing import Any, Dict, Optional, Callable
from uuid import uuid4
from contextlib import ExitStack

from cascade.spec.dsl.resources import ResourceDefinition
from cascade.spec.dsl.constraint import GlobalConstraint
from cascade.spec.dsl.fluent import LazyResult, MappedLazyResult
from cascade.bus.core import EventBus
from cascade.spec import EventState
from cascade.bus.events import (
    RunStarted,
    RunFinished,
    ConnectorConnected,
    ConnectorDisconnected,
)
from cascade.spec.runtime import (
    Solver,
    Executor,
    StateBackend,
    Connector,
    ExecutionStrategy,
    ExecutionContext,
    ObjectStore,
)
from ..storage import InMemoryObjectStore
from ..services.resources.manager import ResourceManager
from ..services.constraints import ConstraintManager
from ..io.state import InMemoryStateBackend
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
                    object_store=self.object_store,
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

        except Exception as e:
            duration = time.time() - start_time
            self.bus.publish(
                RunFinished(
                    run_id=run_id,
                    status=EventState.FAILED,
                    duration=duration,
                    error=f"{type(e).__name__}: {e}",
                )
            )
            raise
        finally:
            # Gracefully shut down any managed subscribers BEFORE disconnecting the connector
            for sub in self._managed_subscribers:
                if hasattr(sub, "shutdown"):
                    await sub.shutdown()

            if self.connector:
                await self.connector.disconnect()
                self.bus.publish(ConnectorDisconnected(run_id=run_id))

    async def _on_constraint_update(self, topic: str, payload: Dict[str, Any]):
        try:
            # An empty payload, which becomes {}, signifies a cleared retained message (a resume command)
            if payload == {}:
                # Reconstruct scope from topic, e.g., cascade/constraints/task/api_call -> task:api_call
                scope_parts = topic.split("/")[2:]
                scope = ":".join(scope_parts)
                if scope:
                    self.constraint_manager.remove_constraints_by_scope(scope)
            else:
                # Basic validation, could be improved with a schema library
                constraint = GlobalConstraint(
                    id=payload["id"],
                    scope=payload["scope"],
                    type=payload["type"],
                    params=payload["params"],
                    expires_at=payload.get("expires_at"),
                )
                self.constraint_manager.update_constraint(constraint)
        except Exception as e:
            # In a real system, we'd use a proper logger.
            # For now, print to stderr to avoid crashing the engine.
            print(
                f"[Engine] Error processing constraint update on topic '{topic}': {e}",
                file=sys.stderr,
            )
        finally:
            # After any change (add, remove, or error), wake up the engine loop
            # if it's waiting.
            self._wakeup_event.set()
~~~~~

#### Acts 2: 集中化 `engine_factory` 的服务装配逻辑

现在，我将更新根 `conftest.py`，使其成为所有核心服务的唯一创建和配置点。

~~~~~act
write_file
conftest.py
~~~~~
~~~~~python
import pytest
from typing import Type
from cascade.vm.reactor import Reactor
from cascade.spec.vm.interfaces import ReactorProtocol

# Imports for new global fixtures
from cascade.runtime import EventBus
from cascade.test_utils.helpers import SpySubscriber

# Attempt to import LocalBusConnector for global cleanup
try:
    from cascade.connectors.local.bus import LocalBusConnector
except ImportError:
    LocalBusConnector = None


def pytest_addoption(parser):
    """Adds a command-line option to select the reactor backend."""
    parser.addoption(
        "--reactor-backend",
        action="store",
        default="python",
        help="Select reactor backend to test: python or rust",
    )


@pytest.fixture(scope="session")
def reactor_backend_factory(
    request,
) -> Type[ReactorProtocol]:
    """
    A session-scoped fixture that provides the Reactor class
    based on the --reactor-backend command-line option.
    """
    backend = request.config.getoption("--reactor-backend")

    if backend == "python":
        # Return the Python implementation
        return Reactor
    # elif backend == "rust":
    #     # Import the high-performance Rust implementation
    #     # from cascade_vm_js import JSReactor

    #     # return RustReactor
    #     return Reactor
    # elif backend == "js":
    #     # from cascade_vm_rs import RustReactor

    #     # return RustReactor
    #     return Reactor
    else:
        pytest.fail(
            f"Invalid reactor backend specified: '{backend}'. "
            "Choose from 'python'."
        )


@pytest.fixture(autouse=True)
def cleanup_local_bus():
    """
    Ensures that the memory broker state is completely cleared between tests.
    This prevents state leakage (retained messages/subscriptions) which
    causes unpredictable failures in E2E tests.
    """
    if LocalBusConnector:
        LocalBusConnector._reset_broker_state()
    yield
    if LocalBusConnector:
        LocalBusConnector._reset_broker_state()


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
from cascade.runtime.services.constraints.handlers import (
    PauseConstraintHandler,
    ConcurrencyConstraintHandler,
    RateLimitConstraintHandler,
)

# Default Components for VM Strategy
from cascade.runtime.strategies.vm import VMExecutionStrategy


@pytest.fixture
def engine_factory() -> Callable[..., Engine]:
    """
    Provides a factory function to create a Cascade Engine instance.

    This factory encapsulates the logic for selecting a default execution strategy
    and assembling all required services, decoupling the core Engine
    from specific strategy implementations and service construction.
    """

    def _factory(
        *,  # Force keyword arguments for clarity
        solver: Optional[Solver] = None,
        executor: Optional[Executor] = None,
        bus: Optional[EventBus] = None,
        strategy: Optional[ExecutionStrategy] = None,
        resource_manager: Optional[ResourceManager] = None,
        constraint_manager: Optional[ConstraintManager] = None,
        **kwargs,  # Pass-through for other Engine args like connector, system_resources etc.
    ) -> Engine:
        # 1. Provide sane defaults for core components
        _solver = solver or NativeSolver()
        _executor = executor or LocalExecutor()
        _bus = bus or EventBus()

        # 2. Create and configure shared services
        _resource_manager = resource_manager or ResourceManager(
            capacity=kwargs.get("system_resources")
        )
        _constraint_manager = constraint_manager or ConstraintManager(_resource_manager)
        _wakeup_event = asyncio.Event()

        # Register default handlers if the manager is newly created
        if not constraint_manager:
            _constraint_manager.register_handler(PauseConstraintHandler())
            _constraint_manager.register_handler(ConcurrencyConstraintHandler())
            _constraint_manager.register_handler(RateLimitConstraintHandler())

        _constraint_manager.set_wakeup_callback(_wakeup_event.set)

        # 3. Create strategy if not provided
        if strategy is None:
            backend_choice = os.getenv("CASCADE_BACKEND", "graph").lower()
            if backend_choice == "vm":
                strategy = VMExecutionStrategy(executor=_executor, bus=_bus)
            else:  # Default to 'graph'
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

        # 4. Construct Engine with all components
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

    return _factory


@pytest.fixture
def engine(engine_factory: Callable[..., Engine]) -> Engine:
    """Provides a default-configured Cascade Engine instance for simple tests."""
    return engine_factory()
~~~~~

### 下一步建议

我们已经完成了对 `Engine` 和测试 Fixture 的深度重构，现在依赖关系清晰，服务实例唯一。我将再次运行完整的测试套件。这次，所有与约束相关的测试都应该能够通过，因为消息传递和执行决策现在共享同一个 `ConstraintManager` 实例。如果仍有失败，那将表明问题存在于更深层次的逻辑中，而非架构接线问题。
