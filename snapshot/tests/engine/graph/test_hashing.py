from cascade import task
from cascade.graph.build import build_graph


def test_hashing_distinguishes_nested_lazy_results():
    """
    This test validates the new Merkle-style hashing.
    The node ID for task_a(task_b()) should be different from
    the node ID for task_a(task_c()).
    """

    @task
    def task_a(dep):
        return dep

    @task
    def task_b():
        return "b"

    @task
    def task_c():
        return "c"

    # These two targets have different dependency structures
    target1 = task_a(task_b())
    target2 = task_a(task_c())

    # Build graphs for both to get the canonical nodes
    _, _, instance_map1 = build_graph(target1)
    _, _, instance_map2 = build_graph(target2)

    # Get the canonical node for the root of each graph
    node1 = instance_map1[target1._uuid]
    node2 = instance_map2[target2._uuid]

    assert node1.id != node2.id, "Hasher must distinguish between different nested LazyResult dependencies"