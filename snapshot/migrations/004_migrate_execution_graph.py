from pathlib import Path
from stitcher.refactor.migration import MigrationSpec, Move, MoveDir


def upgrade(spec: MigrationSpec):
    # Define absolute base paths for source and destination packages
    runtime_base = Path("packages/cascade-runtime/src/cascade/runtime").absolute()
    graph_base = Path(
        "packages/cascade-execution-graph/src/cascade/execution/graph"
    ).absolute()

    # ==========================================
    # 1. Model Layer
    # ==========================================
    # Move the entire graph model directory
    # packages/cascade-runtime/src/cascade/runtime/graph -> .../execution/graph/model
    spec.add(MoveDir(runtime_base / "graph", graph_base / "model"))

    # ==========================================
    # 2. Solvers
    # ==========================================
    # Move the solvers directory
    # packages/cascade-runtime/src/cascade/runtime/kernel/solvers -> .../execution/graph/solvers
    spec.add(MoveDir(runtime_base / "kernel/solvers", graph_base / "solvers"))

    # ==========================================
    # 3. Logic Layer (Splitting 'legacy' folder)
    # ==========================================
    # Move individual logic files to a new 'logic' subdirectory
    spec.add(
        Move(
            runtime_base / "legacy/processor.py", graph_base / "logic/processor.py"
        )
    )
    spec.add(Move(runtime_base / "legacy/flow.py", graph_base / "logic/flow.py"))
    spec.add(
        Move(
            runtime_base / "legacy/resolvers.py", graph_base / "logic/resolvers.py"
        )
    )

    # ==========================================
    # 4. Strategy
    # ==========================================
    # Move the graph execution strategy implementation
    spec.add(
        Move(
            runtime_base / "legacy/strategies/graph.py",
            graph_base / "strategy.py",
        )
    )

    # ==========================================
    # 5. Shared Errors
    # ==========================================
    # Move errors.py as it contains DependencyMissingError used by logic
    spec.add(Move(runtime_base / "errors.py", graph_base / "errors.py"))