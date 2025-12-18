from cascade.spec.task import task
from cascade.graph.build import build_graph
from cascade.adapters.solvers.native import NativeSolver


def test_native_solver_diamond_graph():
    @task
    def t_a():
        return 1

    @task
    def t_b(x):
        return x + 1

    @task
    def t_c(x):
        return x * 2

    @task
    def t_d(y, z):
        return y + z

    r_a = t_a()
    r_b = t_b(r_a)
    r_c = t_c(r_a)
    r_d = t_d(r_b, z=r_c)

    graph = build_graph(r_d)
    solver = NativeSolver()
    plan = solver.resolve(graph)

    # Should have 3 stages: [A], [B, C], [D]
    assert len(plan) == 3

    # Stage 0: A
    assert len(plan[0]) == 1
    assert plan[0][0].name == "t_a"

    # Stage 1: B and C (Parallel)
    assert len(plan[1]) == 2
    middle_names = {n.name for n in plan[1]}
    assert middle_names == {"t_b", "t_c"}

    # Stage 2: D
    assert len(plan[2]) == 1
    assert plan[2][0].name == "t_d"
