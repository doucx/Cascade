好的，我已经掌握了 SDK 中现有工具的源代码。现在我们可以开始执行 ADR-013 的第三阶段：将 `visualize` 和 `dry_run` 迁移到 `CascadeApp`。

## [WIP] feat(arch): 统一 API 入口点 (阶段三)

### 用户需求
执行 ADR-013 阶段三：将 `visualize` 和 `dry_run` 的核心逻辑从 `cascade-sdk` 迁移到 `CascadeApp` 中，实现统一的 API 入口点。

### 评论
当前，`cs.run`, `cs.visualize`, `cs.dry_run` 的图构建和预处理逻辑（如自动汇合）分散在不同的函数中。通过将它们作为 `CascadeApp` 的方法实现，我们可以复用 `__init__` 中已经统一的 `workflow_target` 处理逻辑，从而确保所有操作都基于完全相同的图结构。这不仅消除了代码重复，还增强了系统的行为一致性。

### 目标
1.  在 `CascadeApp` 中实现 `visualize` 方法。这需要移植 `_get_node_shape` 等辅助函数。
2.  在 `CascadeApp` 中实现 `dry_run` 方法。这需要移植 `DryRunConsoleSubscriber` 和 `_analyze_plan` 的逻辑。
3.  为了支持 `dry_run`，我们需要将 `ToolEvent` 及其子类从 `cascade-sdk` 迁移到 `cascade-application`（或者在 `application` 中重新定义，如果不希望引入对 SDK 的反向依赖）。考虑到 `ToolEvent` 实际上是运行时的一部分，在 `application` 层定义它们是合理的。

### 基本原理
我们将采用“重新实现”的策略，将 SDK 中的逻辑复制并适配到 `CascadeApp` 的方法中。由于 `CascadeApp` 已经处理了 `target` 的标准化（`_internal_gather`），新的实现将直接操作 `self.workflow_target`，从而简化了代码。

### 标签
#intent/refine #flow/ready #priority/high #comp/application #scope/api #scope/dx #ai/instruct #task/domain/architecture #task/object/cascade-app #task/action/unify-api #task/state/continue

---

### Script

#### Acts 1: 在 CascadeApp 中实现 visualize 和 dry_run

我们将更新 `packages/cascade-application/src/cascade/app/__init__.py`，填入 `visualize` 和 `dry_run` 的具体实现，并添加必要的辅助类和事件定义。

为了保持文件整洁，我将把 `ToolEvent` 相关定义放在同一个文件中（或作为私有类），因为它们目前仅被 `dry_run` 使用。

~~~~~act
write_file
packages/cascade-application/src/cascade/app/__init__.py
~~~~~
~~~~~python
import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple, Union, Optional, Callable

from cascade.spec.lazy_types import LazyResult
from cascade.spec.task import task
from cascade.spec.protocols import Connector, StateBackend

from cascade.graph.build import build_graph
from cascade.graph.model import Node, EdgeType

from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event
from cascade.runtime.subscribers import HumanReadableLogSubscriber, TelemetrySubscriber
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer, JsonRenderer


# --- Internal Helpers ---

@task(name="_internal_gather", pure=True)
def _internal_gather(*args: Any) -> Any:
    """An internal pure task used to gather results from a list."""
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
                from cascade.adapters.state.redis import RedisStateBackend
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
    """Returns the Graphviz shape for a given node type."""
    if node.node_type == "param":
        return "ellipse"
    if node.node_type == "map":
        return "hexagon"
    return "box"


# --- Tool Events (Scoped to Application Layer for now) ---

@dataclass(frozen=True)
class ToolEvent(Event):
    """Base class for all events emitted by developer tools."""
    pass

@dataclass(frozen=True)
class PlanAnalysisStarted(ToolEvent):
    target_node_id: str = ""

@dataclass(frozen=True)
class PlanNodeInspected(ToolEvent):
    index: int = 0
    total_nodes: int = 0
    node_id: str = ""
    node_name: str = ""
    input_bindings: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PlanAnalysisFinished(ToolEvent):
    total_steps: int = 0


class DryRunConsoleSubscriber:
    """
    Listens to plan analysis events and prints a human-readable report.
    """
    def __init__(self, bus: MessageBus):
        bus.subscribe(PlanAnalysisStarted, self.on_start)
        bus.subscribe(PlanNodeInspected, self.on_node)
        bus.subscribe(PlanAnalysisFinished, self.on_finish)

    def on_start(self, event: PlanAnalysisStarted):
        print("--- Cascade Execution Plan (Dry Run) ---")

    def on_node(self, event: PlanNodeInspected):
        bindings_repr = str(event.input_bindings)
        print(f"[{event.index}/{event.total_nodes}] {event.node_name} (Bindings: {bindings_repr})")

    def on_finish(self, event: PlanAnalysisFinished):
        print("----------------------------------------")


# --- CascadeApp ---

class CascadeApp:
    """
    The central manager for a workflow's lifecycle, encapsulating all
    infrastructure, configuration, and top-level operations.
    """

    def __init__(
        self,
        target: Union[LazyResult, List[Any], Tuple[Any, ...]],
        params: Optional[Dict[str, Any]] = None,
        system_resources: Optional[Dict[str, Any]] = None,
        log_level: str = "INFO",
        log_format: str = "human",
        connector: Optional[Connector] = None,
        state_backend: Union[str, Callable[[str], StateBackend], None] = None,
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
        self.event_bus = MessageBus()
        self.log_subscriber = HumanReadableLogSubscriber(self.event_bus)
        
        self.telemetry_subscriber = None
        if self.connector:
            self.telemetry_subscriber = TelemetrySubscriber(self.event_bus, self.connector)

        # 4. Setup Engine Components
        self.solver = NativeSolver()
        self.executor = LocalExecutor()
        self.sb_factory = _create_state_backend_factory(state_backend)

        # 5. Create Engine
        self.engine = Engine(
            solver=self.solver,
            executor=self.executor,
            bus=self.event_bus,
            system_resources=self.system_resources,
            connector=self.connector,
            state_backend_factory=self.sb_factory,
        )

        if self.telemetry_subscriber:
            self.engine.add_subscriber(self.telemetry_subscriber)

    def run(self) -> Any:
        """
        Executes the workflow and returns the final result.
        """
        return asyncio.run(
            self.engine.run(self.workflow_target, params=self.params)
        )

    def visualize(self) -> str:
        """
        Generates and returns a Graphviz DOT string of the workflow.
        """
        # Note: If workflow_target is an empty list gather (from empty input), 
        # build_graph handles it but we might want a cleaner check.
        if isinstance(self.raw_target, (list, tuple)) and not self.raw_target:
             return "\n".join(["digraph CascadeWorkflow {", '  rankdir="TB";', "}"])

        graph, _ = build_graph(self.workflow_target)

        dot_parts = [
            "digraph CascadeWorkflow {",
            '  rankdir="TB";',
            '  node [shape=box, style="rounded,filled", fillcolor=white];',
        ]

        for node in graph.nodes:
            shape = _get_node_shape(node)
            label = f"{node.name}\\n({node.node_type})"
            dot_parts.append(f'  "{node.structural_id}" [label="{label}", shape={shape}];')

        for edge in graph.edges:
            style = ""
            if edge.edge_type == EdgeType.CONDITION:
                style = ' [style=dashed, color=gray, label="run_if"]'
            elif edge.edge_type == EdgeType.IMPLICIT:
                style = ' [style=dotted, color=lightgray, arrowhead=none, label="implicit"]'
            elif edge.edge_type == EdgeType.ROUTER_ROUTE:
                style = ' [style=dashed, color=orange, arrowhead=open, label="route"]'
            elif edge.router:
                style = f' [style=dashed, color=blue, label="route via: {edge.arg_name}"]'
            elif edge.edge_type == EdgeType.CONSTRAINT:
                style = f' [style=dotted, color=purple, label="constraint: {edge.arg_name}"]'
            elif edge.edge_type == EdgeType.SEQUENCE:
                style = ' [style=dashed, color=darkgray, arrowhead=open, label="next"]'
            elif edge.edge_type == EdgeType.ITERATIVE_JUMP:
                style = f' [style=bold, color=blue, label="{edge.arg_name}"]'
            else:
                style = f' [label="{edge.arg_name}"]'

            dot_parts.append(
                f'  "{edge.source.structural_id}" -> "{edge.target.structural_id}"{style};'
            )

        dot_parts.append("}")
        return "\n".join(dot_parts)

    def dry_run(self) -> None:
        """
        Builds and prints the execution plan without running any tasks.
        """
        # Create a temporary local bus for the dry run report
        # We don't want to use the main app bus because dry_run 
        # is a special analysis mode, not a "run".
        local_bus = MessageBus()
        DryRunConsoleSubscriber(local_bus)

        # Handle empty case
        if isinstance(self.raw_target, (list, tuple)) and not self.raw_target:
             local_bus.publish(PlanAnalysisStarted(run_id="empty", target_node_id="empty"))
             local_bus.publish(PlanAnalysisFinished(run_id="empty", total_steps=0))
             return

        # 1. Build Graph
        graph, _ = build_graph(self.workflow_target)

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
                        node_id=node.structural_id,
                        node_name=node.name,
                        input_bindings=node.input_bindings,
                    )
                )
                current_index += 1

        local_bus.publish(PlanAnalysisFinished(run_id=run_id, total_steps=total_steps))
~~~~~

### 下一步建议
阶段三已完成。`CascadeApp` 现在是一个全功能的入口点，涵盖了 `run`, `visualize`, `dry_run`。

接下来的**阶段四**是确保向后兼容性。我们需要修改 `packages/cascade-sdk/src/cascade/__init__.py`，将原有的全局函数重构为使用 `CascadeApp` 的包装器。同时，我们需要更新 SDK 的依赖，确保它包含 `cascade-application`。

在进行阶段四之前，我建议先**安装**新的 `cascade-application` 包，以确保环境处于正确状态。

请指示是否进行安装和阶段四。
