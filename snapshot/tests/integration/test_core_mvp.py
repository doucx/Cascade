from cascade.spec.task import task, LazyResult
from cascade.graph.build import build_graph


def test_task_decorator_and_lazy_result():
    @task
    def add(a, b):
        return a + b

    result = add(1, 2)
    assert isinstance(result, LazyResult)
    assert result.task.name == "add"
    assert result.args == (1, 2)
    assert result.kwargs == {}


def test_build_linear_graph():
    @task
    def t1():
        return 1

    @task
    def t2(x):
        return x + 1

    r1 = t1()
    r2 = t2(r1)

    graph = build_graph(r2)

    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1

    edge = graph.edges[0]
    assert edge.source.name == "t1"
    assert edge.target.name == "t2"
    assert edge.arg_name == "0"  # first positional arg


def test_build_diamond_graph():
    """
       A
      / \
     B   C
      \ /
       D
    """

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

    # Should have 4 nodes (A, B, C, D)
    assert len(graph.nodes) == 4

    # Should have 4 edges: A->B, A->C, B->D, C->D
    assert len(graph.edges) == 4

    # Verify A is reused (A->B and A->C)
    node_a = next(n for n in graph.nodes if n.name == "t_a")
    edges_from_a = [e for e in graph.edges if e.source == node_a]
    assert len(edges_from_a) == 2


def test_param_placeholder():
    from cascade.spec.task import Param

    p = Param("env", default="dev")
    assert p.name == "env"
    assert p.default == "dev"
