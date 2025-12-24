from unittest.mock import MagicMock
import pytest

from cascade.graph.model import Node, Edge, EdgeType
from cascade.spec.routing import Router
from cascade.spec.lazy_types import LazyResult
from cascade.runtime.flow import FlowManager
from cascade.adapters.state.in_memory import InMemoryStateBackend


def create_mock_node(name: str) -> Node:
    """Creates a mock Node with structural_id == name."""
    return Node(structural_id=name, name=name)


def create_mock_lazy_result(node_id: str) -> LazyResult:
    """Creates a mock LazyResult whose UUID matches the node ID for mapping."""
    lr = MagicMock(spec=LazyResult)
    lr._uuid = node_id
    return lr


@pytest.mark.asyncio
async def test_flow_manager_pruning_logic():
    """
    Test that FlowManager correctly prunes downstream nodes recursively.

    Graph Topology:
    S (Selector) -> chooses "a" or "b"

    Routes:
    - "a": A
    - "b": B -> B_UP (B depends on B_UP)

    Consumer C depends on Router(S)

    If S chooses "a":
    1. Route "b" (Node B) is not selected.
    2. B should be pruned.
    3. B_UP (only used by B) should be recursively pruned.
    """

    # 1. Setup Nodes
    nodes = [create_mock_node(n) for n in ["S", "A", "B", "B_UP", "C"]]
    n_map = {n.structural_id: n for n in nodes}

    # 2. Setup Router Objects
    lr_s = create_mock_lazy_result("S")
    lr_a = create_mock_lazy_result("A")
    lr_b = create_mock_lazy_result("B")

    router_obj = Router(selector=lr_s, routes={"a": lr_a, "b": lr_b})

    # 3. Setup Edges
    edges = [
        Edge(
            n_map["S"],
            n_map["C"],
            arg_name="x",
            edge_type=EdgeType.DATA,
            router=router_obj,
        ),
        Edge(n_map["B_UP"], n_map["B"], arg_name="dep", edge_type=EdgeType.DATA),
        Edge(
            n_map["A"], n_map["C"], arg_name="_route_a", edge_type=EdgeType.ROUTER_ROUTE
        ),
        Edge(
            n_map["B"], n_map["C"], arg_name="_route_b", edge_type=EdgeType.ROUTER_ROUTE
        ),
    ]

    graph = MagicMock()
    graph.nodes = nodes
    graph.edges = edges

    # Create a mock instance_map for the test
    instance_map = {
        lr_s._uuid: n_map["S"],
        lr_a._uuid: n_map["A"],
        lr_b._uuid: n_map["B"],
    }

    # 4. Initialize Manager & Backend
    manager = FlowManager(graph, target_node_id="C", instance_map=instance_map)
    state_backend = InMemoryStateBackend(run_id="test_run")

    # Initial state check
    assert manager.downstream_demand["B_UP"] == 1
    assert manager.downstream_demand["B"] == 1

    # 5. Simulate S completing and choosing "a"
    await state_backend.put_result("S", "a")
    await manager.register_result("S", "a", state_backend)

    # 6. Verify Pruning
    # Route "b" (Node B) was not selected and should be pruned.
    assert await state_backend.get_skip_reason("B") == "Pruned"
    # Node B_UP, which only B depends on, should be recursively pruned.
    assert await state_backend.get_skip_reason("B_UP") == "Pruned"
