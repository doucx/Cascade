from cascade.spec.task import task
from cascade.graph.build import build_graph


def test_impure_tasks_have_unique_identities():
    """
    Verifies that default tasks (Impure) have unique structural identities.

    Scenario:
    The same task is called twice, even with identical arguments.

    Expected Behavior (CP-006):
    The system should treat them as two separate nodes in the graph, each
    with a different structural_id.

    Previous Behavior (Fixed):
    The system would merge them into a single node via hash-consing.
    """

    @task  # Defaults to pure=False
    def random_int():
        return 42

    # Create two instances
    a = random_int()
    b = random_int()

    # Build graphs for each instance
    graph_a, instance_map_a = build_graph(a)
    graph_b, instance_map_b = build_graph(b)

    node_a = instance_map_a[a._uuid]
    node_b = instance_map_b[b._uuid]

    # Assert: For side-effecting tasks, even if the function and arguments are
    # identical, they are distinct entities.
    assert node_a.structural_id != node_b.structural_id, (
        "Impure tasks (default) must have unique structural IDs to avoid incorrect deduplication."
    )


def test_pure_tasks_are_deduplicated():
    """
    Verifies that pure tasks are correctly deduplicated.
    """

    @task(pure=True)
    def add(x, y):
        return x + y

    a = add(1, 2)
    b = add(1, 2)

    graph_a, instance_map_a = build_graph(a)
    graph_b, instance_map_b = build_graph(b)

    node_a = instance_map_a[a._uuid]
    node_b = instance_map_b[b._uuid]

    # Assert: Pure tasks should be content-addressable.
    assert node_a.structural_id == node_b.structural_id, (
        "Pure tasks must be deduplicated based on their content (function + args)."
    )
