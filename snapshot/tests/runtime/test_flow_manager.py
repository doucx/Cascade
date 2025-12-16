import pytest
from unittest.mock import MagicMock
from cascade.graph.model import Node, Edge, EdgeType
from cascade.runtime.flow import FlowManager

def create_mock_node(id):
    return Node(id=id, name=id)

def test_flow_manager_pruning_logic():
    """测试 FlowManager 的动态剪枝算法。"""
    
    nodes = [create_mock_node(n) for n in ["S", "A", "B", "C"]]
    n_map = {n.id: n for n in nodes}
    
    edges = [
        # S->A (route=a), S->B (route=b) via ROUTER_ROUTE
        Edge(n_map["S"], n_map["A"], arg_name="x", edge_type=EdgeType.ROUTER_ROUTE),
        Edge(n_map["S"], n_map["B"], arg_name="x", edge_type=EdgeType.ROUTER_ROUTE),
        
        # C 依赖 A (DATA)
        Edge(n_map["A"], n_map["C"], arg_name="arg_a", edge_type=EdgeType.DATA),
        # C 依赖 B (DATA)
        Edge(n_map["B"], n_map["C"], arg_name="arg_b", edge_type=EdgeType.DATA),
    ]
    
    graph = MagicMock()
    graph.nodes = nodes
    graph.edges = edges
    
    # 初始化 FlowManager
    manager = FlowManager(graph, target_node_id="C")
    
    # 模拟 Router 决定：S 完成，选择了 Route "A"，因此剪枝 B
    # 假设我们有一个内部方法 _decrement_demand_and_prune(node_id)
    if hasattr(manager, "_decrement_demand_and_prune"):
        manager._decrement_demand_and_prune("B")
        
        # 断言 B 被标记为 Skipped/Pruned
        assert manager.is_skipped("B")
        
        # C 强依赖 B，所以 C 也应该被剪枝
        assert manager.is_skipped("C")