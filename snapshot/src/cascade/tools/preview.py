from ..spec.task import LazyResult
from ..graph.build import build_graph
from ..runtime.engine import Engine


def dry_run(target: LazyResult) -> None:
    """
    Builds the computation graph for a target and prints the execution plan
    without running any tasks.
    """
    engine = Engine()
    graph = build_graph(target)
    plan = engine.solver.resolve(graph)

    total_steps = len(plan)

    print("--- Cascade Execution Plan (Dry Run) ---")
    for i, node in enumerate(plan, 1):
        # Format literal inputs for readability
        literals_repr = {
            k: (f"<LazyResult of '{v.task.name}'>" if isinstance(v, LazyResult) else v)
            for k, v in node.literal_inputs.items()
        }

        print(f"[{i}/{total_steps}] {node.name} (Literals: {literals_repr})")

    print("----------------------------------------")