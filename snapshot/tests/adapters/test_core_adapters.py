from cascade.spec.task import task
from cascade.graph.build import build_graph
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.graph.model import Node, Graph, Edge


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


def test_local_executor():
    import asyncio

    def add(x: int, y: int) -> int:
        return x + y

    # Manually construct graph for clarity
    node_x = Node(id="x", name="provide_x", callable_obj=lambda: 5)
    node_y = Node(id="y", name="provide_y", callable_obj=lambda: 10)
    node_add = Node(id="add", name="add", callable_obj=add)

    edge1 = Edge(source=node_x, target=node_add, arg_name="0")  # positional x
    edge2 = Edge(source=node_y, target=node_add, arg_name="y")  # keyword y

    graph = Graph(nodes=[node_x, node_y, node_add], edges=[edge1, edge2])

    # Simulate upstream results
    upstream_results = {"x": 5, "y": 10}

    executor = LocalExecutor()
    result = asyncio.run(
        executor.execute(node_add, graph, upstream_results, resource_context={})
    )

    assert result == 15
