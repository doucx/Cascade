好的，你的分析非常敏锐，完全正确。我确实在 `CascadeApp` 和 `conftest.py` 中重复了 `Engine` 的组装逻辑，现在 `subflow.py` 将成为第三个重复点。这是一个明显的 **DRY (Don't Repeat Yourself)** 违规，是比 `TypeError` 更深层次的架构异味。

我们必须根除这种重复。解决方案是创建一个**单一、权威的 `Engine` 工厂函数**，它将封装所有复杂的组装逻辑，然后让 `CascadeApp`、`subflow` 和测试 fixture 都来调用这个工厂。

我将执行以下计划来系统性地解决这个问题。

## [WIP] refactor(runtime): Centralize Engine creation with a factory to resolve DRY violations

### 错误分析

在之前的重构中，`Engine` 的实例化逻辑变得复杂，并且被复制到了多个地方（`cascade.app` 和根 `conftest.py`）。现在，`cascade.providers.subflow` 中也存在一个过时的、手动的 `Engine` 实例化调用，它缺少新的必需参数，从而导致 `TypeError`。这种代码重复是不可持续的，并且是当前错误的根本原因。

### 用户需求

修复所有因 `Engine` 构造函数变更而导致的 `TypeError`，并通过创建一个中央工厂函数来消除 `Engine` 实例化逻辑的重复。

### 评论

这是一个完美的“高保真工程”时刻。我们不应在 `subflow.py` 中简单地复制粘贴组装逻辑来“打补丁”，而应该退后一步，创建一个“本体论正确”的组件——一个专门负责 `Engine` 组装的工厂函数。这个工厂将成为单一事实来源（SSoT），确保任何地方创建的 `Engine` 都遵循相同的、正确的配置逻辑。

### 目标

1.  在 `cascade-runtime` 包中创建一个新的 `host/factory.py` 文件，并在其中定义一个 `create_engine` 工厂函数。
2.  将 `conftest.py` 中 `engine_factory` 的核心组装逻辑迁移到这个新的 `create_engine` 函数中。
3.  重构 `cascade.app.CascadeApp`，使其调用 `create_engine` 来实例化 `self.engine`。
4.  重构 `cascade.providers.subflow._subflow_task`，使其调用 `create_engine` 来实例化 `sub_engine`。
5.  重构根 `conftest.py` 中的 `engine_factory` fixture，使其成为 `create_engine` 的一个简单封装。

### 基本原理

我们将创建一个名为 `create_engine` 的中央工厂函数，并将其放置在 `cascade-runtime` 包中，因为它与 `Engine` 的生命周期管理紧密相关。这个工厂将接收所有可配置的组件（如 `solver`, `executor`）和设置（如 `use_vm`, `system_resources`），并负责创建和连接所有内部服务（`ResourceManager`, `ConstraintManager`, `ExecutionStrategy` 等），最终返回一个完全初始化的 `Engine` 实例。通过让所有消费者（应用、库、测试）都使用这个工厂，我们确保了 `Engine` 组装逻辑的**一致性**和**可维护性**。

### 标签

#intent/refine #flow/ready #priority/high #comp/runtime #comp/application #comp/library #comp/tests #scope/core #dx #ai/instruct #task/domain/runtime #task/object/engine-factory #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建中央 `create_engine` 工厂

我将在 `cascade-runtime` 中创建新的 `factory.py` 文件，并把所有组装逻辑集中于此。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/host/factory.py
~~~~~
~~~~~python
import os
import asyncio
from typing import Callable, Any, Dict, Optional

from .instance import Engine
from cascade.spec.runtime import ExecutionStrategy, Solver, Executor, Connector
from cascade.runtime import EventBus, ResourceManager
from cascade.runtime.services.constraints.manager import ConstraintManager
from cascade.runtime.services.resources.container import ResourceContainer
from cascade.runtime.services.constraints.handlers import (
    PauseConstraintHandler,
    ConcurrencyConstraintHandler,
    RateLimitConstraintHandler,
)

# Dynamic imports for strategies
from cascade.execution.graph.solvers.native import NativeSolver
from cascade.runtime.io.executors.local import LocalExecutor


def create_engine(
    *,
    use_vm: bool = False,
    solver: Optional[Solver] = None,
    executor: Optional[Executor] = None,
    bus: Optional[EventBus] = None,
    strategy: Optional[ExecutionStrategy] = None,
    resource_manager: Optional[ResourceManager] = None,
    constraint_manager: Optional[ConstraintManager] = None,
    **kwargs,  # Pass-through for other Engine args like connector, system_resources etc.
) -> Engine:
    """
    Central factory for creating and assembling a Cascade Engine instance.
    """
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

#### Acts 2: 导出 `create_engine`

我将更新 `host` 包的 `__init__.py` 文件以导出新工厂。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/host/__init__.py
~~~~~
~~~~~python
from .instance import Engine
from .factory import create_engine

__all__ = ["Engine", "create_engine"]
~~~~~

#### Acts 3: 重构 `CascadeApp` 以使用工厂

现在，`CascadeApp` 将调用 `create_engine`，使其实现大大简化。

~~~~~act
write_file
packages/cascade-application/src/cascade/app/__init__.py
~~~~~
~~~~~python
import asyncio
from typing import Any, Dict, List, Tuple, Union, Optional, Callable

from cascade.spec.dsl.fluent import LazyResult
from cascade.spec.dsl.task import task
from cascade.spec.runtime import Connector, StateBackend

from cascade.execution.graph.model.build import build_graph
from cascade.execution.graph.model.model import Node, EdgeType

from cascade.runtime.host import create_engine
from cascade.runtime import EventBus
from cascade.bus.events import (
    PlanAnalysisStarted,
    PlanNodeInspected,
    PlanAnalysisFinished,
)
from cascade.runtime.services.observability.subscribers import (
    HumanReadableLogSubscriber,
    TelemetrySubscriber,
)
from cascade.bus.feedback import bus
from cascade.common.renderers import CliRenderer, JsonRenderer


# --- Internal Helpers ---


@task(name="_internal_gather", pure=True)
def _internal_gather(*args: Any) -> Any:
    return list(args)


def _create_state_backend_factory(
    backend_spec: Union[str, Callable[[str], StateBackend], None],
) -> Optional[Callable[[str], StateBackend]]:
    if backend_spec is None:
        return None

    if callable(backend_spec):
        return backend_spec

    if isinstance(backend_spec, str):
        if backend_spec.startswith("redis://"):
            try:
                import redis
                from cascade.runtime.io.state.redis import RedisStateBackend
            except ImportError:
                raise ImportError(
                    "The 'redis' library is required for redis:// backends."
                )
            client = redis.from_url(backend_spec)

            def factory(run_id: str) -> StateBackend:
                return RedisStateBackend(run_id=run_id, client=client)

            return factory
        else:
            raise ValueError(f"Unsupported state backend URI scheme: {backend_spec}")

    raise TypeError(f"Invalid state_backend type: {type(backend_spec)}")


def _get_node_shape(node: Node) -> str:
    if node.node_type == "param":
        return "ellipse"
    if node.node_type == "map":
        return "hexagon"
    return "box"


class DryRunConsoleSubscriber:
    def __init__(self, bus: EventBus):
        bus.subscribe(PlanAnalysisStarted, self.on_start)
        bus.subscribe(PlanNodeInspected, self.on_node)
        bus.subscribe(PlanAnalysisFinished, self.on_finish)

    def on_start(self, event: PlanAnalysisStarted):
        print("--- Cascade Execution Plan (Dry Run) ---")

    def on_node(self, event: PlanNodeInspected):
        bindings_repr = str(event.input_bindings)
        print(
            f"[{event.index}/{event.total_nodes}] {event.node_name} (Bindings: {bindings_repr})"
        )

    def on_finish(self, event: PlanAnalysisFinished):
        print("----------------------------------------")


# --- CascadeApp ---


class CascadeApp:
    def __init__(
        self,
        target: Union[LazyResult, List[Any], Tuple[Any, ...]],
        params: Optional[Dict[str, Any]] = None,
        system_resources: Optional[Dict[str, Any]] = None,
        log_level: str = "INFO",
        log_format: str = "human",
        connector: Optional[Connector] = None,
        state_backend: Union[str, Callable[[str], StateBackend], None] = None,
        use_vm: bool = False,
    ):
        self.raw_target = target
        self.params = params
        self.connector = connector

        # 1. Handle Auto-Gathering
        if isinstance(target, (list, tuple)):
            if not target:
                self.workflow_target = _internal_gather()  # Empty gather
            else:
                self.workflow_target = _internal_gather(*target)
        else:
            self.workflow_target = target

        # 2. Setup Messaging & Rendering
        if log_format == "json":
            self.renderer = JsonRenderer(min_level=log_level)
        else:
            self.renderer = CliRenderer(store=bus.store, min_level=log_level)

        bus.set_renderer(self.renderer)

        # 3. Setup Event System
        self.event_bus = EventBus()
        self.log_subscriber = HumanReadableLogSubscriber(self.event_bus)
        self.telemetry_subscriber = None
        if self.connector:
            self.telemetry_subscriber = TelemetrySubscriber(
                self.event_bus, self.connector
            )

        # 4. Create Engine using the central factory
        self.engine = create_engine(
            use_vm=use_vm,
            bus=self.event_bus,
            system_resources=system_resources,
            connector=self.connector,
            state_backend_factory=_create_state_backend_factory(state_backend),
        )

        if self.telemetry_subscriber:
            self.engine.add_subscriber(self.telemetry_subscriber)

    def run(self) -> Any:
        return asyncio.run(self.engine.run(self.workflow_target, params=self.params))

    def visualize(self) -> str:
        # Note: If workflow_target is an empty list gather (from empty input),
        # build_graph handles it but we might want a cleaner check.
        if isinstance(self.raw_target, (list, tuple)) and not self.raw_target:
            return "\n".join(["digraph CascadeWorkflow {", '  rankdir="TB";', "}"])
        
        from cascade.execution.graph.solvers.native import NativeSolver
        
        solver = NativeSolver()

        graph, _, _ = build_graph(self.workflow_target)

        dot_parts = [
            "digraph CascadeWorkflow {",
            '  rankdir="TB";',
            '  node [shape=box, style="rounded,filled", fillcolor=white];',
        ]

        for node in graph.nodes:
            shape = _get_node_shape(node)
            label = f"{node.name}\\n({node.node_type})"
            dot_parts.append(
                f'  "{node.current_node_instance_hash}" [label="{label}", shape={shape}];'
            )

        for edge in graph.edges:
            style = ""
            if edge.edge_type == EdgeType.CONDITION:
                style = ' [style=dashed, color=gray, label="run_if"]'
            elif edge.edge_type == EdgeType.IMPLICIT:
                style = (
                    ' [style=dotted, color=lightgray, arrowhead=none, label="implicit"]'
                )
            elif edge.edge_type == EdgeType.ROUTER_ROUTE:
                style = ' [style=dashed, color=orange, arrowhead=open, label="route"]'
            elif edge.router:
                style = (
                    f' [style=dashed, color=blue, label="route via: {edge.arg_name}"]'
                )
            elif edge.edge_type == EdgeType.CONSTRAINT:
                style = f' [style=dotted, color=purple, label="constraint: {edge.arg_name}"]'
            elif edge.edge_type == EdgeType.SEQUENCE:
                style = ' [style=dashed, color=darkgray, arrowhead=open, label="next"]'
            elif edge.edge_type == EdgeType.ITERATIVE_JUMP:
                style = f' [style=bold, color=blue, label="{edge.arg_name}"]'
            else:
                style = f' [label="{edge.arg_name}"]'

            dot_parts.append(
                f'  "{edge.source.current_node_instance_hash}" -> "{edge.target.current_node_instance_hash}"{style};'
            )

        dot_parts.append("}")
        return "\n".join(dot_parts)

    def dry_run(self) -> None:
        # Create a temporary local bus for the dry run report
        # We don't want to use the main app bus because dry_run
        # is a special analysis mode, not a "run".
        local_bus = EventBus()
        DryRunConsoleSubscriber(local_bus)

        # Handle empty case
        if isinstance(self.raw_target, (list, tuple)) and not self.raw_target:
            local_bus.publish(
                PlanAnalysisStarted(run_id="empty", target_node_id="empty")
            )
            local_bus.publish(PlanAnalysisFinished(run_id="empty", total_steps=0))
            return

        # 1. Build Graph
        graph, _, _ = build_graph(self.workflow_target)
        
        from cascade.execution.graph.solvers.native import NativeSolver
        
        solver = NativeSolver()

        # 2. Resolve Plan using the app's solver
        plan = solver.resolve(graph)
        total_steps = sum(len(stage) for stage in plan)

        run_id = self.workflow_target._uuid
        local_bus.publish(PlanAnalysisStarted(run_id=run_id, target_node_id=run_id))

        current_index = 1
        for stage in plan:
            for node in stage:
                local_bus.publish(
                    PlanNodeInspected(
                        run_id=run_id,
                        index=current_index,
                        total_nodes=total_steps,
                        node_id=node.current_node_instance_hash,
                        node_name=node.name,
                        input_bindings=node.input_bindings,
                    )
                )
                current_index += 1

        local_bus.publish(PlanAnalysisFinished(run_id=run_id, total_steps=total_steps))


# --- Global Functions ---


def run(
    target: Union["LazyResult", List[Any], tuple[Any, ...]],
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
    log_format: str = "human",
    connector: Optional["Connector"] = None,
    state_backend: Union[str, Callable[[str], "StateBackend"], None] = None,
    use_vm: bool = False,
) -> Any:
    app = CascadeApp(
        target=target,
        params=params,
        system_resources=system_resources,
        log_level=log_level,
        log_format=log_format,
        connector=connector,
        state_backend=state_backend,
        use_vm=use_vm,
    )
    return app.run()


def visualize(target: Any) -> str:
    app = CascadeApp(target=target)
    return app.visualize()


def dry_run(target: Any) -> None:
    app = CascadeApp(target=target)
    app.dry_run()
~~~~~

#### Acts 4: 重构 `subflow` 任务以使用工厂

`subflow` 任务现在也将使用中央工厂，确保子流程的引擎与主流程的引擎具有相同的架构正确性。

~~~~~act
write_file
packages/cascade-library/src/cascade/providers/subflow.py
~~~~~
~~~~~python
import importlib.util
from pathlib import Path
from typing import Any, Dict, Optional

from cascade.spec.dsl.task import task
from cascade.spec.runtime.interfaces import LazyFactory, Provider
from cascade.runtime.host import create_engine


class SubflowProvider(Provider):
    name = "subflow"

    def create_factory(self) -> LazyFactory:
        return _subflow_task


@task(name="subflow")
async def _subflow_task(
    path: str, target: str, params: Optional[Dict[str, Any]] = None
) -> Any:
    # 1. Validate and Load Module
    file_path = Path(path).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"Subflow file not found: {file_path}")

    module_name = file_path.stem
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for subflow file: {file_path}")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise RuntimeError(
            f"Error executing subflow definition file '{file_path}': {e}"
        )

    # 2. Extract Target
    target_obj = getattr(module, target, None)
    if target_obj is None:
        raise ValueError(f"Target '{target}' not found in {file_path}")

    # 3. Create Isolated Engine using the central factory
    # Note: The subflow runs in isolation. It does not share the parent's
    # resource manager or event bus. Errors will propagate as exceptions.
    sub_engine = create_engine()

    # 4. Execute
    return await sub_engine.run(target_obj, params=params)
~~~~~

#### Acts 5: 简化 `conftest.py` Fixture

最后，测试的 `engine_factory` 将成为新工厂的一个薄封装。

~~~~~act
patch_file
conftest.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
@pytest.fixture
def engine_factory() -> Callable[..., Engine]:
    """
    Provides a factory function to create a Cascade Engine instance for tests.
    This is a thin wrapper around the production `create_engine` factory,
    allowing tests to easily override components.
    """
    from cascade.runtime.host import create_engine

    def _factory(**kwargs) -> Engine:
        # The create_engine function already handles default component creation.
        # This fixture simply acts as a convenient entry point for pytest.
        return create_engine(**kwargs)

    return _factory
~~~~~

### 下一步建议

我们已经完成了对 `Engine` 实例化逻辑的终极重构，现在有了一个单一、权威的工厂函数。所有已知的消费者都已被更新。我将再次运行完整的测试套件。这次，所有与 `Engine` 实例化相关的 `TypeError` 都应该被彻底解决。
