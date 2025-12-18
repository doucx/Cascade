import pytest
from cascade.spec.task import task
from cascade.graph.build import build_graph
from cascade.adapters.solvers.csp import CSPSolver

# Skip tests if python-constraint is not installed
pytest.importorskip("constraint")


def test_csp_solver_init():
    """Test that CSPSolver can be initialized with resources."""
    solver = CSPSolver(system_resources={"cpu": 4, "ram": 16})
    assert solver.system_resources == {"cpu": 4, "ram": 16}


def test_csp_solver_missing_dependency(monkeypatch):
    """Test that meaningful error is raised if dependency is missing."""
    import cascade.adapters.solvers.csp as csp_module

    # Simulate missing dependency by setting constraint to None
    monkeypatch.setattr(csp_module, "constraint", None)

    with pytest.raises(ImportError, match="python-constraint"):
        CSPSolver(system_resources={})


def test_csp_solver_parallel_when_resources_sufficient():
    """
    Scenario: System has 10 CPU.
    Task A needs 4 CPU.
    Task B needs 4 CPU.
    No dependencies.

    Expected: Both run in Stage 0 (Parallel).
    """

    @task
    def t_a():
        pass

    @task
    def t_b():
        pass

    @task
    def gather(a, b):
        pass

    # Construct graph: A and B feed into Gather
    # But we want to test scheduling of A and B.
    # Let's just create a dummy gather to build the graph.
    node_a = t_a().with_constraints(cpu=4)
    node_b = t_b().with_constraints(cpu=4)
    target = gather(node_a, node_b)

    graph = build_graph(target)

    solver = CSPSolver(system_resources={"cpu": 10})
    plan = solver.resolve(graph)

    # Analyze plan
    # Gather depends on A and B, so Gather must be later.
    # A and B depend on nothing.

    # We expect minimum 2 stages: [A, B], [Gather]
    # Because A(4) + B(4) = 8 <= 10, they fit in one stage.

    assert len(plan) == 2

    first_stage_names = {n.name for n in plan[0]}
    assert "t_a" in first_stage_names
    assert "t_b" in first_stage_names
    assert len(plan[0]) == 2


def test_csp_solver_serial_when_resources_insufficient():
    """
    Scenario: System has 6 CPU.
    Task A needs 4 CPU.
    Task B needs 4 CPU.
    No dependencies.

    Expected: Run in separate stages (Serial) to respect limit.
    Plan should be 3 stages: [A], [B], [Gather] OR [B], [A], [Gather].
    """

    @task
    def t_a():
        pass

    @task
    def t_b():
        pass

    @task
    def gather(a, b):
        pass

    node_a = t_a().with_constraints(cpu=4)
    node_b = t_b().with_constraints(cpu=4)
    target = gather(node_a, node_b)

    graph = build_graph(target)

    # Limit system to 6 CPU
    solver = CSPSolver(system_resources={"cpu": 6})
    plan = solver.resolve(graph)

    # A(4) + B(4) = 8 > 6. Cannot run in parallel.
    # Must be split.
    # Gather is dependent on both, so it comes last.
    # Total stages should be 3.

    assert len(plan) == 3

    stage_0_names = {n.name for n in plan[0]}
    stage_1_names = {n.name for n in plan[1]}

    # One of them is in stage 0, the other in stage 1
    assert len(plan[0]) == 1
    assert len(plan[1]) == 1

    # Verify content
    assert stage_0_names.union(stage_1_names) == {"t_a", "t_b"}
    assert plan[2][0].name == "gather"
