from typing import Any
from ..spec.task import LazyResult
from ..graph.build import build_graph
from ..runtime.engine import Engine


def dry_run(target: LazyResult[Any]) -> None:
    """
    Builds the computation graph for a target and prints the execution plan
    without running any tasks.
    
    This tool instantiates a default Engine to access its Solver, ensuring
    the predicted order matches the actual execution order.
    """
    # We use the default engine configuration to get the default solver
    engine = Engine()
    
    # 1. Build the graph statically
    graph = build_graph(target)
    
    # 2. Resolve the execution plan (topological sort)
    plan = engine.solver.resolve(graph)

    total_steps = len(plan)

    print("--- Cascade Execution Plan (Dry Run) ---")
    for i, node in enumerate(plan, 1):
        # Format literal inputs for readability
        # If an input is a LazyResult, we show a reference to its task
        # Otherwise, we show the literal value
        literals_repr = {
            k: (f"<LazyResult of '{v.task.name}'>" if isinstance(v, LazyResult) else v)
            for k, v in node.literal_inputs.items()
        }

        print(f"[{i}/{total_steps}] {node.name} (Literals: {literals_repr})")

    print("----------------------------------------")