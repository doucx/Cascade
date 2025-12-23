from cascade.spec.task import task
from cascade.graph.build import build_graph
from cascade.graph.model import EdgeType


@task
def leaf_task():
    return "leaf"


@task
def orchestrator(x: int):
    if x > 0:
        return leaf_task()
    return "done"


def test_build_graph_with_potential_tco():
    """
    Test that the graph builder detects the potential TCO call from
    orchestrator to leaf_task and creates a POTENTIAL edge.
    """
    workflow = orchestrator(10)
    graph, _ = build_graph(workflow)

    node_names = {n.name for n in graph.nodes}
    assert "orchestrator" in node_names
    assert "leaf_task" in node_names

    potential_edges = [e for e in graph.edges if e.edge_type == EdgeType.POTENTIAL]

    assert len(potential_edges) == 1
    edge = potential_edges[0]
    assert edge.source.name == "orchestrator"
    assert edge.target.name == "leaf_task"
    assert edge.arg_name == "<potential>"


def test_recursive_shadow_analysis():
    """
    Verify that the builder recursively analyzes potential TCO targets.
    """

    @task
    def task_c():
        return "C"

    @task
    def task_b():
        return task_c()

    @task
    def task_a():
        return task_b()

    workflow = task_a()
    graph, _ = build_graph(workflow)

    node_names = {n.name for n in graph.nodes}
    assert "task_a" in node_names
    assert "task_b" in node_names
    # task_c should now be present as a shadow node due to recursive analysis
    assert "task_c" in node_names

    # Verify edge chain: a -> b -> c
    potential_edges = [e for e in graph.edges if e.edge_type == EdgeType.POTENTIAL]
    assert len(potential_edges) == 2
    
    # a -> b
    assert any(e.source.name == "task_a" and e.target.name == "task_b" for e in potential_edges)
    # b -> c
    assert any(e.source.name == "task_b" and e.target.name == "task_c" for e in potential_edges)
