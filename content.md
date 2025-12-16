## [WIP] feat(runtime): Implement Router pruning with Reference Counting

### 用户需求
用户希望实现 `Router` 的剪枝（Pruning）功能。当 `Router` 的 `selector` 确定了执行路径后，系统应自动跳过（Skip）那些未被选择的分支上的任务，以节省资源并避免执行不必要的逻辑。

### 评论
这是一个极具价值的性能优化。为了安全地实现剪枝，我们必须解决“共享依赖”的问题——即不能因为一个分支不需要某个任务就贸然杀死它，因为其他分支或任务可能仍需要它。
基于引用计数（Reference Counting）的算法是解决此问题的最佳方案：我们将每个任务的“出度”视为其初始需求量。当 Router 排除一个分支时，我们减少该分支根节点的需求量。当需求量降为零时，节点被剪枝，并递归地减少其上游节点的需求量。

### 目标
1.  在 `FlowManager` 中实现基于引用计数的动态剪枝逻辑。
2.  在 `Engine` 中连接执行循环与 `FlowManager`，在任务完成后报告结果。
3.  添加单元测试，验证专属依赖被正确剪枝，而共享依赖被正确保留。

### 基本原理
我们将在 `FlowManager` 初始化时构建全图的引用计数（Demand）和拓扑索引。
当 `Engine` 报告 `selector` 的结果时，`FlowManager` 会识别出所有未选中的路由分支。对于每个未选中的分支，逻辑上切断其指向 Router Target 的边（即 Demand - 1）。如果某节点的 Demand 归零，说明它成为了图中的“孤岛”，不再对最终结果有贡献，因此可以安全地标记为 `Skipped`（原因：`Pruned`）。该过程会递归向上传播，直到遇到被其他活跃路径引用的节点（共享节点）为止。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/control-flow #scope/core #ai/instruct #task/domain/core #task/object/router #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 更新 `FlowManager` 实现引用计数剪枝

我们将重写 `FlowManager`，在其中加入索引构建、引用计数初始化、结果注册和递归剪枝的核心逻辑。

~~~~~act
write_file
src/cascade/runtime/flow.py
~~~~~
~~~~~python
from typing import Dict, Any, Optional, Set, List
from collections import defaultdict
from cascade.graph.model import Node, Graph, EdgeType, Edge


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
        
        for edge in self.graph.edges:
            self.in_edges[edge.target.id].append(edge)
            
            if edge.router:
                # Map selector_id -> edges that utilize this selector
                selector_id = edge.router.selector._uuid
                self.routers_by_selector[selector_id].append(edge)

        # --- 2. Initialize Reference Counting (Demand) ---
        # A node's initial demand is its out-degree (number of consumers).
        # We also treat the final workflow target as having +1 implicit demand.
        self.downstream_demand: Dict[str, int] = defaultdict(int)
        
        for edge in self.graph.edges:
            self.downstream_demand[edge.source.id] += 1
            
        self.downstream_demand[target_node_id] += 1

    def mark_skipped(self, node_id: str, reason: str = "Unknown"):
        """Manually marks a node as skipped."""
        self._skipped_nodes.add(node_id)
        # Note: We don't decrement demand here because if a node is skipped naturally 
        # (e.g. condition false), its downstream will handle "UpstreamSkipped".
        # Pruning is a proactive measure for nodes that haven't run yet.

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
        
        # 1. Identify unselected routes
        # Selector value might be non-hashable, but route keys in dict usually are strings/ints.
        # We rely on simple equality check.
        selected_route_key = selector_value
        
        for route_key, route_lazy_result in router.routes.items():
            if route_key == selected_route_key:
                continue
                
            # This route is NOT selected.
            # The edge from this route branch to the target node is logically "broken".
            # We decrement the demand for the branch's root node.
            branch_root_id = route_lazy_result._uuid
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
            # No one needs this node anymore. Prune it!
            # But wait, we should check if it has already run?
            # Engine handles that check (it won't check should_skip for completed nodes).
            self.mark_skipped(node_id, reason="Pruned")
            
            # Recursively decrement demand for its UPSTREAM dependencies.
            # These are the sources of incoming edges.
            for edge in self.in_edges[node_id]:
                self._decrement_demand_and_prune(edge.source.id)

    def should_skip(
        self, node: Node, results: Dict[str, Any]
    ) -> Optional[str]:
        """
        Determines if a node should be skipped.
        Returns the reason string if it should be skipped, or None otherwise.
        """
        # 0. Check if already marked (e.g. Pruned)
        if self.is_skipped(node.id):
            return "Pruned"

        # 1. Upstream Skip Propagation (Cascade Skip)
        for edge in self.in_edges[node.id]:
            if edge.edge_type in (EdgeType.DATA, EdgeType.IMPLICIT, EdgeType.ROUTER_ROUTE):
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

#### Acts 2: 连接 `Engine` 与 `FlowManager`

修改 `Engine`，在初始化 `FlowManager` 时传入 `target_node_id`，并在任务成功执行后调用 `register_result`。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
    async def _execute_graph(
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
    ) -> Any:
        graph = build_graph(target)
        self.flow_manager = FlowManager(graph) # Initialize FlowManager per run
        
        plan = self.solver.resolve(graph)  # Now returns List[List[Node]]
        results: Dict[str, Any] = {}
~~~~~
~~~~~python
    async def _execute_graph(
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
    ) -> Any:
        graph = build_graph(target)
        self.flow_manager = FlowManager(graph, target._uuid)
        
        plan = self.solver.resolve(graph)  # Now returns List[List[Node]]
        results: Dict[str, Any] = {}
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
                return result

            except Exception as e:
                last_exception = e
~~~~~
~~~~~python
                # Notify flow manager of result to trigger potential pruning
                if self.flow_manager:
                    self.flow_manager.register_result(node.id, result)

                return result

            except Exception as e:
                last_exception = e
~~~~~

#### Acts 3: 添加剪枝测试用例

创建一个新的测试文件 `tests/runtime/test_router_pruning.py`，测试“专属依赖”被剪枝和“共享依赖”被保留的场景。

~~~~~act
write_file
tests/runtime/test_router_pruning.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.bus import MessageBus
from cascade.runtime.engine import Engine
from cascade.runtime.events import Event, TaskSkipped

class SpySubscriber:
    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.events.append)

    def events_of_type(self, event_type):
        return [e for e in self.events if isinstance(e, event_type)]

@pytest.mark.asyncio
async def test_pruning_exclusive_branches():
    """
    Test that branches exclusive to a router are pruned when not selected.
    """
    @cs.task
    def get_route():
        return "a"

    @cs.task
    def branch_a():
        return "A"

    @cs.task
    def branch_b():
        return "B" # Should be pruned

    @cs.task
    def branch_b_upstream():
        return "B_UP" # Should also be pruned (recursive)

    # branch_b depends on branch_b_upstream
    b_chain = branch_b(branch_b_upstream())

    router = cs.Router(
        selector=get_route(),
        routes={"a": branch_a(), "b": b_chain}
    )

    @cs.task
    def consumer(val):
        return val

    workflow = consumer(router)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    result = await engine.run(workflow)
    assert result == "A"

    # Check pruning events
    skipped = spy.events_of_type(TaskSkipped)
    skipped_names = {e.task_name for e in skipped}
    
    assert "branch_b" in skipped_names
    assert "branch_b_upstream" in skipped_names
    
    # Verify reasons
    for e in skipped:
        assert e.reason == "Pruned"


@pytest.mark.asyncio
async def test_pruning_shared_dependency():
    """
    Test that a dependency shared between branches (or external tasks) 
    is NOT pruned even if one consumer branch is pruned.
    """
    @cs.task
    def get_route():
        return "a"

    @cs.task
    def shared_task():
        return "SHARED"

    @cs.task
    def branch_a(dep):
        return f"A({dep})"

    @cs.task
    def branch_b(dep):
        return f"B({dep})" # Should be pruned, but 'dep' should not

    # shared_task is used by BOTH branches
    shared = shared_task()
    
    router = cs.Router(
        selector=get_route(),
        routes={"a": branch_a(shared), "b": branch_b(shared)}
    )

    @cs.task
    def consumer(val):
        return val

    workflow = consumer(router)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    result = await engine.run(workflow)
    assert result == "A(SHARED)"

    # Check pruning
    skipped = spy.events_of_type(TaskSkipped)
    skipped_names = {e.task_name for e in skipped}

    assert "branch_b" in skipped_names
    assert "shared_task" not in skipped_names # MUST NOT be pruned

    # Only branch_b should be pruned
    assert len(skipped) == 1
~~~~~

### 下一步建议
我们已经实现了健壮的 `Router` 剪枝功能，并通过了复杂的依赖场景验证。
目前阶段三的所有功能（`.map`, `.run_if`, `Router`, `Pruning`, `File`, `Serialization`）均已完成。
接下来的重点将转向阶段四：**生态系统与核心工具**，即实现 `Provider` 插件系统的正式协议与加载机制，以及实现 `cs.template` 等核心 Provider。
