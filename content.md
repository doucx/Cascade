## [WIP] fix(runtime): Fix FlowManager pruning logic and Param ID resolution

### 用户需求
1.  **修复 Router 剪枝导致的误判**: 之前的实现中，`FlowManager` 会因为某个未被选中的路由分支被标记为 Skipped，而错误地将目标节点（Consumer）也标记为 Skipped（原因是 `UpstreamSkipped`）。必须修正 `should_skip` 逻辑，使其忽略未被选中分支的 Skip 状态。
2.  **修复 Param ID 解析错误**: `FlowManager` 无法处理 `Param` 类型的 Selector，因为 `Param` 对象没有 `_uuid` 属性。需要统一 ID 获取逻辑。

### 评论
这是一个关键的逻辑修复。通过在 `FlowManager` 内部构建 `Route Source Map`，我们可以精确地知道哪条 `ROUTER_ROUTE` 边对应哪个 Key。结合运行时的 Selector 结果，我们可以实现精准的“条件性依赖检查”，即只关心被选中分支的健康状况。

### 目标
1.  在 `FlowManager` 中增加 `_get_obj_id` 辅助方法，统一处理 `Param` 和 `LazyResult`。
2.  在 `FlowManager` 初始化时构建 `consumer -> {source_id: route_key}` 的映射。
3.  重写 `should_skip` 逻辑，对于 `ROUTER_ROUTE` 类型的边，仅当其对应的 Key 与 Selector 结果一致时，才检查 Skip 状态。

### 基本原理
Consumer 节点虽然在图结构上依赖所有 Route 分支，但在运行时逻辑上，它只依赖被选中的那一个。`FlowManager` 作为控制流的大脑，必须体现这种运行时逻辑，屏蔽掉图结构带来的“虚假”依赖失败。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/control-flow #scope/core #ai/instruct #task/domain/core #task/object/flow-manager #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 修正 `FlowManager`

我们将对 `FlowManager` 进行全面的逻辑增强。

~~~~~act
write_file
src/cascade/runtime/flow.py
~~~~~
~~~~~python
from typing import Dict, Any, Optional, Set, List
from collections import defaultdict
from cascade.graph.model import Node, Graph, EdgeType, Edge
from cascade.spec.common import Param
from cascade.spec.lazy_types import LazyResult


class FlowManager:
    """
    Manages the control flow of the execution, implementing logic for
    skipping tasks (Conditions) and pruning branches (Router).
    """

    def __init__(self, graph: Graph, target_node_id: str):
        self.graph = graph
        self.target_node_id = target_node_id
        self._skipped_nodes: Set[str] = set()
        
        # --- 1. Build Topology Indices ---
        self.in_edges: Dict[str, List[Edge]] = defaultdict(list)
        self.routers_by_selector: Dict[str, List[Edge]] = defaultdict(list)
        
        # Mapping: consumer_id -> { source_node_id -> route_key }
        # Used to identify which route key a ROUTER_ROUTE edge corresponds to.
        self.route_source_map: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        for edge in self.graph.edges:
            self.in_edges[edge.target.id].append(edge)
            
            if edge.router:
                # Map selector_id -> edges that utilize this selector
                selector_id = self._get_obj_id(edge.router.selector)
                self.routers_by_selector[selector_id].append(edge)
                
                # Build the route source map for the consumer (edge.target)
                for key, route_result in edge.router.routes.items():
                    route_source_id = self._get_obj_id(route_result)
                    self.route_source_map[edge.target.id][route_source_id] = key

        # --- 2. Initialize Reference Counting (Demand) ---
        # A node's initial demand is its out-degree (number of consumers).
        # We also treat the final workflow target as having +1 implicit demand.
        self.downstream_demand: Dict[str, int] = defaultdict(int)
        
        for edge in self.graph.edges:
            self.downstream_demand[edge.source.id] += 1
            
        self.downstream_demand[target_node_id] += 1

    def _get_obj_id(self, obj: Any) -> str:
        """Helper to get ID from LazyResult or Param."""
        if isinstance(obj, LazyResult):
            return obj._uuid
        elif isinstance(obj, Param):
            return obj.name
        # Fallback, though graph building should ensure these types
        return str(obj)

    def mark_skipped(self, node_id: str, reason: str = "Unknown"):
        """Manually marks a node as skipped."""
        self._skipped_nodes.add(node_id)

    def is_skipped(self, node_id: str) -> bool:
        return node_id in self._skipped_nodes

    def register_result(self, node_id: str, result: Any):
        """
        Notify FlowManager of a task completion. 
        Triggers pruning if the node was a Router selector.
        """
        if node_id in self.routers_by_selector:
            for edge_with_router in self.routers_by_selector[node_id]:
                self._process_router_decision(edge_with_router, result)

    def _process_router_decision(self, edge: Edge, selector_value: Any):
        router = edge.router
        
        selected_route_key = selector_value
        
        for route_key, route_lazy_result in router.routes.items():
            if route_key == selected_route_key:
                continue
                
            # This route is NOT selected. Prune it.
            branch_root_id = self._get_obj_id(route_lazy_result)
            self._decrement_demand_and_prune(branch_root_id)

    def _decrement_demand_and_prune(self, node_id: str):
        """
        Decrements demand for a node. If demand hits 0, marks it pruned 
        and recursively processes its upstreams.
        """
        if self.is_skipped(node_id):
            return

        self.downstream_demand[node_id] -= 1
        
        if self.downstream_demand[node_id] <= 0:
            self.mark_skipped(node_id, reason="Pruned")
            
            for edge in self.in_edges[node_id]:
                self._decrement_demand_and_prune(edge.source.id)

    def should_skip(
        self, node: Node, results: Dict[str, Any]
    ) -> Optional[str]:
        """
        Determines if a node should be skipped.
        Returns the reason string if it should be skipped, or None otherwise.
        """
        if self.is_skipped(node.id):
            return "Pruned"

        # Determine active route key if this node is a Router consumer
        active_route_key = None
        # Find the edge carrying the Router definition
        router_edge = next((e for e in self.in_edges[node.id] if e.router), None)
        if router_edge:
            selector_id = self._get_obj_id(router_edge.router.selector)
            # If selector result is available, we know the active key
            if selector_id in results:
                active_route_key = results[selector_id]
            # If selector is missing/skipped, we can't determine active key yet.
            # But standard DATA dependency check below will handle missing selector.

        # 1. Upstream Skip Propagation
        for edge in self.in_edges[node.id]:
            # Special handling for ROUTER_ROUTE edges
            if edge.edge_type == EdgeType.ROUTER_ROUTE:
                # If we know the active route, we only care about that one.
                if active_route_key is not None:
                    # Look up which key this edge corresponds to
                    edge_key = self.route_source_map[node.id].get(edge.source.id)
                    # If this edge is NOT the active route, ignore its skip status
                    if edge_key != active_route_key:
                        continue
                
                # If active_route_key is unknown (shouldn't happen if selector ran),
                # or if this IS the active route, check if it's skipped.
                if self.is_skipped(edge.source.id):
                    return "UpstreamSkipped"

            elif edge.edge_type in (EdgeType.DATA, EdgeType.IMPLICIT):
                if self.is_skipped(edge.source.id):
                    return "UpstreamSkipped"

        # 2. Condition Check (run_if)
        for edge in self.in_edges[node.id]:
            if edge.edge_type == EdgeType.CONDITION:
                if edge.source.id not in results:
                    return "ConditionMissing"
                
                condition_result = results.get(edge.source.id)
                if not condition_result:
                    return "ConditionFalse"

        return None
~~~~~

### 下一步建议
通过这次修复，我们解决了 Router 剪枝逻辑中的核心缺陷。`FlowManager` 现在不仅能正确地剪枝未选中的分支，还能正确地保护 Consumer 免受“无辜”分支被剪枝的影响。
可以运行测试以验证修复结果。验证通过后，我们将继续推进生态系统的建设。
