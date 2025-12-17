好的，我们来修复这些回归问题。

主要原因是 `FlowManager` 在之前的重构中丢失了“递归修剪”的能力。在 v2.0 的无状态设计中，`FlowManager` 虽然不存储任务结果，但它仍然需要维护本次运行的**控制流拓扑状态**（如节点的剩余下游需求数），以便在分支被修剪时能够向上递归地取消不再需要的上游任务。

这个计划将分三步：
1.  **恢复核心逻辑**：在 `FlowManager` 中重新引入引用计数（Demand Counting）机制，实现递归修剪。
2.  **修正测试断言**：更新 `test_control_flow.py` 以匹配新的、更精确的错误码。
3.  **重构白盒测试**：重写 `test_flow_manager.py`，使其适应新的、依赖 `StateBackend` 的架构。

## [WIP] fix(flow): 恢复递归修剪逻辑并修复测试套件

### 用户需求
1.  修复 `test_control_flow.py` 中的断言错误，适配新的 `UpstreamSkipped_Data` 错误码。
2.  修复 `test_router_pruning.py` 中的失败，确保当 Router 选择分支时，未被选择分支的上游依赖（如果不再被其他节点需要）也能被正确地递归修剪。
3.  修复 `test_flow_manager.py`，使其与当前的 `FlowManager` 实现对齐。

### 评论
这次修复不仅仅是“让测试通过”，更是对无状态 `FlowManager` 职责的一次明确。虽然它不存储“结果数据”，但它必须管理“执行拓扑的动态状态”。引用计数（Demand）属于后者，因此应该由 `FlowManager` 在其实例生命周期内维护。

### 目标
1.  修改 `src/cascade/runtime/flow.py`，在 `__init__` 中初始化 `downstream_demand`，并实现 `_decrement_demand_and_prune` 方法。
2.  修改 `tests/runtime/test_control_flow.py`，更新断言字符串。
3.  重写 `tests/runtime/test_flow_manager.py`，使用 Mock 的 `StateBackend` 来验证修剪逻辑。

### 基本原理
1.  **递归修剪算法**:
    *   **初始化**: 计算所有节点的初始“需求数”（即静态出度）。
    *   **触发**: 当 Router 决定不走某条路时，该路由节点的需求归零（或视为被满足）。
    *   **传播**: 对该路由节点的所有上游依赖，将其需求数减 1。
    *   **递归**: 如果某上游节点的需求数降为 0（意味着没人需要它了），则将其标记为 Skipped，并对其上游继续重复此过程。
2.  **测试适配**: 之前的白盒测试直接调用了被删除的私有方法。现在的测试应模拟 `StateBackend` 和 `Graph`，通过调用公共接口 `register_result` 来触发内部的修剪逻辑，验证 `state_backend.mark_skipped` 是否被正确调用。

### 标签
#intent/fix #flow/ready #priority/high
#comp/engine #concept/flow #scope/core
#ai/instruct
#task/domain/architecture #task/object/flow-manager #task/action/bug-fix #task/state/continue #task/status/active

---

### Script

#### Acts 1: 恢复 FlowManager 的递归修剪逻辑

我们将引用计数逻辑带回 `FlowManager`。

~~~~~act
write_file
src/cascade/runtime/flow.py
~~~~~
~~~~~python
from typing import Dict, Any, Optional, List
from collections import defaultdict
from cascade.graph.model import Node, Graph, EdgeType, Edge
from cascade.spec.common import Param
from cascade.spec.lazy_types import LazyResult
from cascade.runtime.protocols import StateBackend


class FlowManager:
    """
    Manages the control flow of the execution, implementing logic for
    skipping tasks (Conditions) and pruning branches (Router).
    """

    def __init__(self, graph: Graph, target_node_id: str):
        self.graph = graph
        self.target_node_id = target_node_id
        
        self.in_edges: Dict[str, List[Edge]] = defaultdict(list)
        self.routers_by_selector: Dict[str, List[Edge]] = defaultdict(list)
        self.route_source_map: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        # Reference counting for pruning
        # Initial demand = Out-degree (number of consumers)
        self.downstream_demand: Dict[str, int] = defaultdict(int)

        for edge in self.graph.edges:
            self.in_edges[edge.target.id].append(edge)
            self.downstream_demand[edge.source.id] += 1
            
            if edge.router:
                selector_id = self._get_obj_id(edge.router.selector)
                self.routers_by_selector[selector_id].append(edge)
                
                for key, route_result in edge.router.routes.items():
                    route_source_id = self._get_obj_id(route_result)
                    self.route_source_map[edge.target.id][route_source_id] = key

        # The final target always has at least 1 implicit demand (the user wants it)
        self.downstream_demand[target_node_id] += 1

    def _get_obj_id(self, obj: Any) -> str:
        if isinstance(obj, LazyResult):
            return obj._uuid
        elif isinstance(obj, Param):
            return obj.name
        return str(obj)

    def register_result(self, node_id: str, result: Any, state_backend: StateBackend):
        """
        Notifies FlowManager of a task completion. 
        Triggers pruning if the node was a Router selector.
        """
        if node_id in self.routers_by_selector:
            for edge_with_router in self.routers_by_selector[node_id]:
                self._process_router_decision(edge_with_router, result, state_backend)

    def _process_router_decision(
        self, edge: Edge, selector_value: Any, state_backend: StateBackend
    ):
        router = edge.router
        selected_route_key = selector_value
        
        for route_key, route_lazy_result in router.routes.items():
            if route_key != selected_route_key:
                branch_root_id = self._get_obj_id(route_lazy_result)
                # This branch is NOT selected. 
                # We decrement its demand. If it drops to 0, it gets pruned.
                # Note: In the Router model, the "edge" carrying the router implies a demand
                # from the consumer (edge.target) to the route (branch_root).
                # Since we decided NOT to use this route, that demand is effectively gone.
                self._decrement_demand_and_prune(branch_root_id, state_backend)

    def _decrement_demand_and_prune(self, node_id: str, state_backend: StateBackend):
        """
        Decrements demand for a node. If demand hits 0, marks it pruned 
        and recursively processes its upstreams.
        """
        # If already skipped/pruned, no need to do anything further
        if state_backend.get_skip_reason(node_id):
            return

        self.downstream_demand[node_id] -= 1
        
        if self.downstream_demand[node_id] <= 0:
            state_backend.mark_skipped(node_id, "Pruned")
            
            # Recursively reduce demand for inputs of the pruned node
            for edge in self.in_edges[node_id]:
                # Special case: If the edge is from a Router, do we prune the Router selector?
                # No, the selector might be used by other branches.
                # Standard dependency logic applies: reduce demand on source.
                self._decrement_demand_and_prune(edge.source.id, state_backend)

    def should_skip(
        self, node: Node, state_backend: StateBackend
    ) -> Optional[str]:
        """
        Determines if a node should be skipped based on the current state.
        Returns the reason string if it should be skipped, or None otherwise.
        """
        # 1. Check if already skipped (e.g., by router pruning)
        if reason := state_backend.get_skip_reason(node.id):
            return reason

        # 2. Condition Check (run_if)
        for edge in self.in_edges[node.id]:
            if edge.edge_type == EdgeType.CONDITION:
                if not state_backend.has_result(edge.source.id):
                    # Propagate skip if condition source was skipped
                    if state_backend.get_skip_reason(edge.source.id):
                        return "UpstreamSkipped_Condition"
                    return "ConditionMissing"
                
                condition_result = state_backend.get_result(edge.source.id)
                if not condition_result:
                    return "ConditionFalse"
        
        # 3. Upstream Skip Propagation
        active_route_key = None
        router_edge = next((e for e in self.in_edges[node.id] if e.router), None)
        if router_edge:
            selector_id = self._get_obj_id(router_edge.router.selector)
            if state_backend.has_result(selector_id):
                active_route_key = state_backend.get_result(selector_id)

        for edge in self.in_edges[node.id]:
            if edge.edge_type == EdgeType.ROUTER_ROUTE:
                if active_route_key is not None:
                    edge_key = self.route_source_map[node.id].get(edge.source.id)
                    if edge_key != active_route_key:
                        continue
                
                if state_backend.get_skip_reason(edge.source.id):
                    return "UpstreamSkipped_Route"
            
            elif edge.edge_type in (EdgeType.DATA, EdgeType.IMPLICIT):
                if state_backend.get_skip_reason(edge.source.id):
                    return "UpstreamSkipped_Data"
        
        return None
~~~~~

#### Acts 2: 修正 test_control_flow.py 的错误码断言

~~~~~act
patch_file
tests/runtime/test_control_flow.py
~~~~~
~~~~~python
    assert reason_a == "ConditionFalse"
    assert reason_b == "UpstreamSkipped"
~~~~~
~~~~~python
    assert reason_a == "ConditionFalse"
    assert reason_b == "UpstreamSkipped_Data"
~~~~~

#### Acts 3: 重写 test_flow_manager.py

该测试原先依赖具体的内部实现，现在我们需要根据新的架构重写它，使用 Mock 的 `StateBackend` 来验证逻辑。

~~~~~act
write_file
tests/runtime/test_flow_manager.py
~~~~~
~~~~~python
import pytest
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
    
    router_obj = Router(
        selector=lr_s,
        routes={"a": lr_a, "b": lr_b}
    )
    
    # 3. Setup Edges
    edges = [
        # S is used by C as the router selector
        # Edge from Selector to Consumer
        Edge(n_map["S"], n_map["C"], arg_name="x", edge_type=EdgeType.DATA, router=router_obj),
        
        # B depends on B_UP
        Edge(n_map["B_UP"], n_map["B"], arg_name="dep", edge_type=EdgeType.DATA),
        
        # Router implicitly links Routes to Consumer (ROUTER_ROUTE edges would exist in real graph)
        # But FlowManager uses routers_by_selector map mostly.
        # However, for demand counting, we need edges representing usage.
        # In build_graph, we add edges from Route Result to Consumer.
        Edge(n_map["A"], n_map["C"], arg_name="_route_a", edge_type=EdgeType.ROUTER_ROUTE),
        Edge(n_map["B"], n_map["C"], arg_name="_route_b", edge_type=EdgeType.ROUTER_ROUTE),
    ]
    
    graph = MagicMock()
    graph.nodes = nodes
    graph.edges = edges
    
    # 4. Initialize Manager & Backend
    manager = FlowManager(graph, target_node_id="C")
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
~~~~~

### 下一步建议
如果这个计划成功执行，`test_router_pruning.py`（集成测试）和新的 `test_flow_manager.py`（单元测试）都应该通过。这将确认我们在保留了 v2.0 状态解耦架构的同时，成功恢复了 v1.x 的核心流控功能。

接下来，我们将回到原定的轨道：**更新和完善集成测试**。特别是那些可能受到架构变更影响的 E2E 测试和资源调度测试。
