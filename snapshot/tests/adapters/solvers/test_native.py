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

    assert len(plan) == 4

    # Node A must be first
    assert plan[0].name == "t_a"
    # Node D must be last
    assert plan[-1].name == "t_d"

    # Nodes B and C can be in any order in between
    middle_names = {plan[1].name, plan[2].name}
    assert middle_names == {"t_b", "t_c"}
