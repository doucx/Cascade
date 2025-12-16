import asyncio
from cascade.adapters.executors.local import LocalExecutor
from cascade.graph.model import Node, Graph, Edge


def test_local_executor():
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