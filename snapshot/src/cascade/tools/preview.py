from typing import Any
from ..spec.task import LazyResult
from ..graph.build import build_graph
from ..runtime.engine import Engine
from ..runtime.bus import MessageBus
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
    engine = Engine()

    # 1. Build the graph statically
    graph = build_graph(target)

    # 2. Resolve the execution plan (topological sort)
    plan = engine.solver.resolve(graph)
    total_steps = len(plan)

    bus.publish(PlanAnalysisStarted(run_id=target._uuid, target_node_id=target._uuid))

    for i, node in enumerate(plan, 1):
        bus.publish(
            PlanNodeInspected(
                run_id=target._uuid,
                index=i,
                total_nodes=total_steps,
                node_id=node.id,
                node_name=node.name,
                literal_inputs=node.literal_inputs,
            )
        )

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
