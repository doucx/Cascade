from unittest.mock import MagicMock
from cascade.graph.model import Node, Edge, EdgeType
from cascade.runtime.flow import FlowManager
from cascade.adapters.state import InMemoryStateBackend
from cascade.spec.lazy_types import LazyResult
from cascade.spec.routing import Router


def create_mock_node(id):
    return Node(id=id, name=id)


def create_mock_lazy_result(uuid):
    lr = MagicMock(spec=LazyResult)
    lr._uuid = uuid
    return lr


def test_flow_manager_pruning_logic():
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
    n_map = {n.id: n for n in nodes}

    # 2. Setup Router Objects
    lr_s = create_mock_lazy_result("S")
    lr_a = create_mock_lazy_result("A")
    lr_b = create_mock_lazy_result("B")

    router_obj = Router(selector=lr_s, routes={"a": lr_a, "b": lr_b})

    # 3. Setup Edges
    edges = [
        # S is used by C as the router selector
        # Edge from Selector to Consumer
        Edge(
            n_map["S"],
            n_map["C"],
            arg_name="x",
            edge_type=EdgeType.DATA,
            router=router_obj,
        ),
        # B depends on B_UP
        Edge(n_map["B_UP"], n_map["B"], arg_name="dep", edge_type=EdgeType.DATA),
        # Router implicitly links Routes to Consumer (ROUTER_ROUTE edges would exist in real graph)
        # But FlowManager uses routers_by_selector map mostly.
        # However, for demand counting, we need edges representing usage.
        # In build_graph, we add edges from Route Result to Consumer.
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
    instance_map = {"S": n_map["S"], "A": n_map["A"], "B": n_map["B"]}

    # 4. Initialize Manager & Backend
    manager = FlowManager(graph, target_node_id="C", instance_map=instance_map)
    state_backend = InMemoryStateBackend(run_id="test_run")

    # Initial state check
    # B_UP demand should be 1 (from B)
    assert manager.downstream_demand["B_UP"] == 1
    # B demand should be 1 (from C)
    assert manager.downstream_demand["B"] == 1

    # 5. Simulate S completing and choosing "a"
    state_backend.put_result("S", "a")
    manager.register_result("S", "a", state_backend)

    # 6. Verify Pruning
    # Route "b" (Node B) was not selected.
    # It should be marked skipped.
    assert state_backend.get_skip_reason("B") == "Pruned"

    # Recursion: Since B is skipped, B_UP's demand should drop to 0 and be skipped too.
    assert state_backend.get_skip_reason("B_UP") == "Pruned"

    # Route "a" (Node A) should NOT be skipped.
    assert state_backend.get_skip_reason("A") is None
