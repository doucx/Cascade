好的，测试失败了。正如预期的那样，我们对 `Engine` 强制实施依赖注入的改动，现在暴露了上层应用（`CascadeApp`）中的一个问题：它在没有提供所需 `strategy` 的情况下实例化了 `Engine`。

这是件好事，它迫使我们将架构变得更加清晰。应用层（`CascadeApp`）现在必须承担起构建和选择执行策略的责任，而不是把这个逻辑隐藏在核心运行时（`Engine`）里。

我将修复这个问题，并将您建议的 `use_vm` 参数集成进去，以便用户可以方便地从顶层 `run` 函数切换到实验性的 VM 后端。

## [WIP] fix(app): Inject execution strategy into Engine from CascadeApp

### 错误分析

在之前的重构中，`Engine.__init__` 方法被修改为必须接收一个 `strategy` 参数。然而，`cascade.app.CascadeApp` 在初始化时调用 `Engine()` 却没有提供这个必需的参数，导致了 `TypeError: Engine.__init__() missing 1 required positional argument: 'strategy'`。

### 用户需求

修复 `cascade-application` 包中的 `TypeError`，并通过在 `cascade.app.run` 函数中添加一个 `use_vm` 参数，来为用户提供一种选择执行后端的机制。

### 评论

这个修复是上一个架构重构的必然延续。它将策略（Strategy）的创建和组装逻辑从核心运行时（`Engine`）提升到了应用层（`CascadeApp`），这完全符合依赖倒置原则。现在，`Engine` 只关心执行一个策略，而 `CascadeApp` 负责决定“哪个”策略被执行。引入 `use_vm` 参数也为未来的后端实验提供了清晰的入口点。

### 目标

1.  向 `cascade.app.run` 全局函数和 `CascadeApp` 类的 `__init__` 方法中添加一个新的 `use_vm: bool = False` 参数。
2.  在 `CascadeApp` 的初始化逻辑中，根据 `use_vm` 参数或 `CASCADE_BACKEND` 环境变量来创建相应的 `ExecutionStrategy`（`GraphExecutionStrategy` 或 `VMExecutionStrategy`）。
3.  将创建好的 `strategy` 实例注入到 `Engine` 的构造函数中，解决 `TypeError`。

### 基本原理

我们将把之前在 `conftest.py` 中为测试构建的策略选择逻辑，移植到 `CascadeApp` 的构造函数中。`CascadeApp` 将首先检查 `use_vm` 标志。如果为 `True`，则使用 `VMExecutionStrategy`。否则，它会检查 `CASCADE_BACKEND` 环境变量。如果两者都未指定，则默认使用成熟的 `GraphExecutionStrategy`。这个过程涉及到组装 `NodeProcessor`、`ConstraintManager` 等图策略所需的依赖。最终，创建好的策略实例将被传递给 `Engine`，从而满足其新的构造函数契约。

### 标签

#intent/fix #flow/ready #priority/high #comp/runtime #scope/api #ai/instruct #task/domain/runtime #task/object/engine-instantiation #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 在 CascadeApp 中构建并注入执行策略

我将使用 `write_file` 全面更新 `packages/cascade-application/src/cascade/app/__init__.py` 文件。这次更新将引入必要的依赖，修改 `CascadeApp` 的构造函数以构建和注入策略，并向 `run` 函数添加 `use_vm` 参数。

~~~~~act
write_file
packages/cascade-application/src/cascade/app/__init__.py
~~~~~
~~~~~python
import asyncio
import os
from typing import Any, Dict, List, Tuple, Union, Optional, Callable

from cascade.spec.dsl.fluent import LazyResult
from cascade.spec.dsl.task import task
from cascade.spec.runtime import Connector, StateBackend, ExecutionStrategy

from cascade.execution.graph.model.build import build_graph
from cascade.execution.graph.model.model import Node, EdgeType

from cascade.runtime.host.instance import Engine
from cascade.runtime import EventBus, ResourceManager
from cascade.bus.events import (
    PlanAnalysisStarted,
    PlanNodeInspected,
    PlanAnalysisFinished,
)
from cascade.runtime.services.observability.subscribers import (
    HumanReadableLogSubscriber,
    TelemetrySubscriber,
)
from cascade.execution.graph.solvers.native import NativeSolver
from cascade.runtime.io.executors.local import LocalExecutor

from cascade.bus.feedback import bus
from cascade.common.renderers import CliRenderer, JsonRenderer

# Imports for Strategy construction
from cascade.runtime.services.constraints.manager import ConstraintManager
from cascade.runtime.services.resources.container import ResourceContainer
from cascade.execution.graph.logic.processor import NodeProcessor
from cascade.execution.graph.strategy import GraphExecutionStrategy
from cascade.runtime.strategies.vm import VMExecutionStrategy


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
        self.system_resources = system_resources
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

        # 4. Setup Engine Components
        self.solver = NativeSolver()
        self.executor = LocalExecutor()
        self.sb_factory = _create_state_backend_factory(state_backend)
        self.resource_manager = ResourceManager(capacity=self.system_resources)

        # 5. Create Execution Strategy based on user choice
        strategy: ExecutionStrategy
        backend_choice = (
            "vm" if use_vm else os.getenv("CASCADE_BACKEND", "graph").lower()
        )

        if backend_choice == "vm":
            strategy = VMExecutionStrategy(executor=self.executor, bus=self.event_bus)
        else:  # Default to 'graph'
            constraint_manager = ConstraintManager(self.resource_manager)
            wakeup_event = asyncio.Event()
            constraint_manager.set_wakeup_callback(wakeup_event.set)
            resource_container = ResourceContainer(self.event_bus)
            node_processor = NodeProcessor(
                executor=self.executor,
                bus=self.event_bus,
                resource_manager=self.resource_manager,
                constraint_manager=constraint_manager,
                solver=self.solver,
            )
            strategy = GraphExecutionStrategy(
                solver=self.solver,
                node_processor=node_processor,
                resource_container=resource_container,
                constraint_manager=constraint_manager,
                bus=self.event_bus,
                wakeup_event=wakeup_event,
            )

        # 6. Create Engine
        self.engine = Engine(
            solver=self.solver,
            executor=self.executor,
            bus=self.event_bus,
            strategy=strategy,
            resource_manager=self.resource_manager,
            system_resources=self.system_resources,
            connector=self.connector,
            state_backend_factory=self.sb_factory,
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

        # 2. Resolve Plan using the app's solver
        plan = self.solver.resolve(graph)
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

### 下一步建议

我们已经修复了应用层的 `Engine` 实例化问题，并提供了选择后端的机制。现在，我将再次运行测试套件。由于大量的测试用例都依赖于 `cascade.app.run` 或直接实例化 `Engine`（通过新的 fixture），这次测试应该能覆盖到我们的修改。如果还有其他地方直接实例化 `Engine` 而没有使用 fixture，测试将会再次失败，我将继续修复它们。
