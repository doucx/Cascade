from cascade import task
from cascade.graph.build import build_graph


@task(mode="compute")
def compute_task():
    return 1


@task(mode="blocking")
def blocking_task():
    return 2


@task
def default_task():
    return 3


def test_execution_mode_is_passed_to_node():
    """
    Verifies that the `mode` parameter from the @task decorator
    is correctly propagated to the `execution_mode` attribute of the
    corresponding Node in the graph.
    """
    # 1. Define a simple workflow
    ct = compute_task()
    bt = blocking_task()
    dt = default_task()

    # We need a target to build the graph
    target = [ct, bt, dt]

    # 2. Build the graph
    # NOTE: We are building from a list, which is not a valid final target for
    # the engine, but it is sufficient for build_graph to explore all dependencies.
    # The build_graph function does not require a single root LazyResult.
    graph, instance_map = build_graph(target)

    # 3. Find the nodes in the graph
    compute_node = instance_map[ct._uuid]
    blocking_node = instance_map[bt._uuid]
    default_node = instance_map[dt._uuid]

    # 4. Assert the execution modes
    assert (
        compute_node.execution_mode == "compute"
    ), "Node for compute_task should have mode 'compute'"
    assert (
        blocking_node.execution_mode == "blocking"
    ), "Node for blocking_task should have mode 'blocking'"
    assert (
        default_node.execution_mode == "blocking"
    ), "Node for default_task should have the default mode 'blocking'"
