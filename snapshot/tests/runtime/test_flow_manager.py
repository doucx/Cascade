import pytest
from unittest.mock import MagicMock
from cascade.graph.model import Node, Edge, EdgeType
from cascade.runtime.flow import FlowManager

def create_mock_node(id):
    return Node(id=id, name=id)

def test_flow_manager_pruning_logic():
    """Test that FlowManager correctly prunes downstream nodes."""
    
    # Graph Topology:
    #       S
    #      / \
    #     A   B (to be pruned)
    #      \ /
    #       C
    
    # Note: In a real router scenario, S would be the selector, and there would be
    # implicit edges. Here we simulate the pruning mechanism directly.
    
    nodes = [create_mock_node(n) for n in ["S", "A", "B", "C"]]
    n_map = {n.id: n for n in nodes}
    
    edges = [
        # S -> A
        Edge(n_map["S"], n_map["A"], arg_name="x", edge_type=EdgeType.DATA),
        # S -> B
        Edge(n_map["S"], n_map["B"], arg_name="x", edge_type=EdgeType.DATA),
        
        # A -> C
        Edge(n_map["A"], n_map["C"], arg_name="a", edge_type=EdgeType.DATA),
        # B -> C
        Edge(n_map["B"], n_map["C"], arg_name="b", edge_type=EdgeType.DATA),
    ]
    
    graph = MagicMock()
    graph.nodes = nodes
    graph.edges = edges
    
    manager = FlowManager(graph, target_node_id="C")
    
    # Initial state: C has demand 2 (from A and B) + 1 (target) = 3?
    # No, demand is out-degree.
    # S: 2 (A, B)
    # A: 1 (C)
    # B: 1 (C)
    # C: 1 (Target implicit)
    
    # We simulate pruning B.
    # B's demand is 1. If we prune it, we simulate that its demand drops to 0?
    # No, pruning means we decided B shouldn't run.
    # The method _decrement_demand_and_prune(node_id) does:
    # demand[node_id] -= 1
    # if demand <= 0: mark_skipped; recursively decrement demand for upstreams (inputs to node_id)
    
    # Wait, the pruning logic usually works backward from unselected routes?
    # Or forward?
    # In flow.py:
    # _process_router_decision:
    #   for unselected route:
    #     branch_root_id = ...
    #     _decrement_demand_and_prune(branch_root_id)
    
    # So if S is a Router, and it selects A.
    # Then B is unselected.
    # We call decrement(B).
    # B's demand is 1 (C depends on B). 
    # Decrementing it makes it 0. So B is pruned.
    # Then B's inputs (S) are decremented? 
    #   for edge in in_edges[B]: decrement(S)
    
    # C depends on B. But C also depends on A.
    # If B is pruned, does C get pruned?
    # C's demand is 1 (target).
    # Pruning B doesn't affect C's demand (C is downstream of B).
    # Pruning usually propagates UPSTREAM (reducing demand for parents).
    
    # Ah, Router logic is: "This branch is not needed".
    # But C needs B?
    # If C needs B, and B is pruned, C will fail with DependencyMissing unless C handles it.
    
    # The logic in flow.py seems to imply:
    # If a node is not needed by anyone (demand=0), prune it.
    
    # In this test, if we call decrement(B):
    # demand[B] becomes 0. B is skipped.
    # B's input is S. demand[S] becomes 1 (was 2). S is NOT skipped.
    
    # Check if B is skipped.
    manager._decrement_demand_and_prune("B")
    assert manager.is_skipped("B")
    assert not manager.is_skipped("A")
    assert not manager.is_skipped("S")
    assert not manager.is_skipped("C")