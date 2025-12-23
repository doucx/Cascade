from typing import Any
from cascade.spec.lazy_types import LazyResult  # NEW
from cascade.graph.build import build_graph
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from .events import PlanAnalysisStarted, PlanNodeInspected, PlanAnalysisFinished


def dry_run(target: LazyResult[Any]) -> None:
    """
    Builds the computation graph for a target and prints the execution plan
    without running any tasks.
    """
    bus = MessageBus()
    # Attach the console view
    DryRunConsoleSubscriber(bus)

    # Run the analysis logic
    _analyze_plan(target, bus)


def _analyze_plan(target: LazyResult[Any], bus: MessageBus) -> None:
    """
    Core logic for dry_run: builds the plan and emits events.
    Decoupled from any output mechanism.
    """
    # We use the default engine configuration to get the default solver
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())

    # 1. Build the graph statically
    graph, _ = build_graph(target)

    # 2. Resolve the execution plan (topological sort)
    plan = engine.solver.resolve(graph)
    # Calculate total nodes across all stages
    total_steps = sum(len(stage) for stage in plan)

    bus.publish(PlanAnalysisStarted(run_id=target._uuid, target_node_id=target._uuid))

    current_index = 1
    for stage in plan:
        for node in stage:
            # Filter out non-literal dependencies from the inputs for cleaner output
            from cascade.spec.lazy_types import LazyResult, MappedLazyResult

            literals = {
                k: v
                for k, v in node.literal_inputs.items()
                if not isinstance(v, (LazyResult, MappedLazyResult))
            }

            bus.publish(
                PlanNodeInspected(
                    run_id=target._uuid,
                    index=current_index,
                    total_nodes=total_steps,
                    node_id=node.id,
                    node_name=node.name,
                    literal_inputs=literals,
                )
            )
            current_index += 1

    bus.publish(PlanAnalysisFinished(run_id=target._uuid, total_steps=total_steps))


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
        # Format literal inputs for readability
        literals_repr = {
            k: (f"<LazyResult of '{v.task.name}'>" if isinstance(v, LazyResult) else v)
            for k, v in event.literal_inputs.items()
        }
        print(
            f"[{event.index}/{event.total_nodes}] {event.node_name} (Literals: {literals_repr})"
        )

    def on_finish(self, event: PlanAnalysisFinished):
        print("----------------------------------------")
