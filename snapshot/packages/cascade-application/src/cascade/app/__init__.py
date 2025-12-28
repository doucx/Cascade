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
    if node.node_type == "param":
        return "ellipse"
    if node.node_type == "map":
        return "hexagon"
    return "box"


# --- Tool Events (Scoped to Application Layer for now) ---


@dataclass(frozen=True)
class ToolEvent(Event):
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
    def __init__(self, bus: MessageBus):
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
            self.telemetry_subscriber = TelemetrySubscriber(
                self.event_bus, self.connector
            )

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
        return asyncio.run(self.engine.run(self.workflow_target, params=self.params))

    def visualize(self) -> str:
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
            dot_parts.append(
                f'  "{node.structural_id}" [label="{label}", shape={shape}];'
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
                f'  "{edge.source.structural_id}" -> "{edge.target.structural_id}"{style};'
            )

        dot_parts.append("}")
        return "\n".join(dot_parts)

    def dry_run(self) -> None:
        # Create a temporary local bus for the dry run report
        # We don't want to use the main app bus because dry_run
        # is a special analysis mode, not a "run".
        local_bus = MessageBus()
        DryRunConsoleSubscriber(local_bus)

        # Handle empty case
        if isinstance(self.raw_target, (list, tuple)) and not self.raw_target:
            local_bus.publish(
                PlanAnalysisStarted(run_id="empty", target_node_id="empty")
            )
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
