from typing import Any
from typing import Any
from cascade.graph.build import build_graph
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.internal.inputs import _internal_gather
from .events import PlanAnalysisStarted, PlanNodeInspected, PlanAnalysisFinished


def dry_run(target: Any) -> None:
    """
    Builds the computation graph for a target and prints the execution plan
    without running any tasks.
    """
    bus = MessageBus()
    # Attach the console view
    DryRunConsoleSubscriber(bus)

    # Run the analysis logic
    _analyze_plan(target, bus)


def _analyze_plan(target: Any, bus: MessageBus) -> None:
    """
    Core logic for dry_run: builds the plan and emits events.
    Decoupled from any output mechanism.
    """
    if isinstance(target, (list, tuple)):
        if not target:
            # For empty list, emit a clean empty plan
            bus.publish(PlanAnalysisStarted(run_id="empty", target_node_id="empty"))
            bus.publish(PlanAnalysisFinished(run_id="empty", total_steps=0))
            return
        workflow_target = _internal_gather(*target)
    else:
        workflow_target = target

    # We use the default engine configuration to get the default solver
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())

    # 1. Build the graph statically
    graph, _ = build_graph(workflow_target)

    # 2. Resolve the execution plan (topological sort)
    plan = engine.solver.resolve(graph)
    # Calculate total nodes across all stages
    total_steps = sum(len(stage) for stage in plan)

    run_id = workflow_target._uuid
    bus.publish(PlanAnalysisStarted(run_id=run_id, target_node_id=run_id))

    current_index = 1
    for stage in plan:
        for node in stage:
            bus.publish(
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

    bus.publish(PlanAnalysisFinished(run_id=run_id, total_steps=total_steps))


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
        # Format input bindings for readability without extra quotes from repr
        bindings_repr = str(event.input_bindings)
        print(
            f"[{event.index}/{event.total_nodes}] {event.node_name} (Bindings: {bindings_repr})"
        )

    def on_finish(self, event: PlanAnalysisFinished):
        print("----------------------------------------")
