简要回答：
好的，我将通过在 `GraphBuilder` 中引入控制依赖并在 `Engine` 中实现动态剪枝逻辑，来解决 Router 未选择分支被执行的资源浪费问题。

## [WIP] perf(runtime): 实现 Router 分支的动态剪枝机制

### 用户需求
当前 `cs.Router` 的实现是“急切”的，即无论 Selector 选择了哪个分支，所有备选分支（Routes）都会被调度执行。这在分支任务昂贵时造成了资源浪费。用户希望 `Engine` 能够智能地“剪枝”，即仅执行被选中的分支，跳过其他分支。

### 评论
这是一个重要的性能优化，它将 `cs.Router` 从简单的“结果选择器”升级为真正的“控制流结构”。这使得 `Cascade` 可以支持更复杂的条件工作流，如 A/B 测试路径或环境特定的部署流程，而无需担心副作用或资源消耗。

### 目标
1.  修改 `GraphBuilder`，强制 `Router` 的所有分支任务依赖于 `Selector` 任务，确保 `Selector` 优先执行。
2.  在 `Engine` 中实现剪枝逻辑：当 `Selector` 执行完成后，识别未被选中的分支任务，并将其标记为 `Skipped (RouterPruned)`。
3.  确保未选中分支的下游任务（如果只依赖该分支）也会被级联跳过。

### 基本原理
通过在图构建阶段添加隐式的控制依赖 (`IMPLICIT` 边)，我们利用 `Solver` 的拓扑排序保证了 `Selector` 在所有 `Route` 之前执行。这为 `Engine` 提供了一个时间窗口：在调度 `Route` 任务之前，`Selector` 的结果已经可用。`Engine` 利用这个结果动态地将不需要的任务 ID 加入跳过集合，从而阻断其执行。

### 标签
#intent/refine #intent/perf #flow/ready #priority/high
#comp/runtime #comp/graph #concept/routing #concept/executor
#scope/core
#task/domain/core #task/object/router #task/action/pruning
#task/state/begin #task/status/active

---

### Script

#### Acts 1: 修改 `GraphBuilder` 添加控制依赖

我们需要确保 `Selector` 在所有 `Routes` 之前执行。这是实现动态剪枝的前提。

~~~~~act
patch_file
src/cascade/graph/build.py
~~~~~
~~~~~python
                for route_result in value.routes.values():
                    route_node = self._visit(route_result)
                    # Implicit dependency edge for Router routes
                    imp_edge = Edge(
                        source=route_node,
                        target=target_node,
                        arg_name="_implicit_dependency", 
                        edge_type=EdgeType.IMPLICIT
                    )
                    self.graph.add_edge(imp_edge)
~~~~~
~~~~~python
                for route_result in value.routes.values():
                    route_node = self._visit(route_result)
                    # Implicit dependency edge for Router routes
                    imp_edge = Edge(
                        source=route_node,
                        target=target_node,
                        arg_name="_implicit_dependency", 
                        edge_type=EdgeType.IMPLICIT
                    )
                    self.graph.add_edge(imp_edge)

                    # NEW: Control dependency from selector to route
                    # This ensures the selector runs BEFORE the route, allowing the Engine
                    # to prune the route if it's not selected.
                    control_edge = Edge(
                        source=selector_node,
                        target=route_node,
                        arg_name="_router_control",
                        edge_type=EdgeType.IMPLICIT
                    )
                    self.graph.add_edge(control_edge)
~~~~~

#### Acts 2: 在 `Engine` 中实现动态剪枝逻辑

我们需要在 `Engine` 中添加识别 Router、构建映射以及在运行时执行剪枝的逻辑。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.runtime.resolvers import ArgumentResolver, ConstraintResolver


class Engine:
~~~~~
~~~~~python
from collections import defaultdict
from cascade.runtime.resolvers import ArgumentResolver, ConstraintResolver


class Engine:
~~~~~

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
        plan = self.solver.resolve(graph)  # Now returns List[List[Node]]
        results: Dict[str, Any] = {}
        skipped_node_ids: set[str] = set()

        # Inject params first (usually params are in the first stage or handled implicitly)
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
        plan = self.solver.resolve(graph)  # Now returns List[List[Node]]
        results: Dict[str, Any] = {}
        skipped_node_ids: set[str] = set()
        pruned_node_ids: set[str] = set()  # IDs explicitly pruned by Router logic

        # Pre-scan for routers to enable fast lookups during execution
        # Map: selector_node_id -> List[Router]
        selector_map = defaultdict(list)
        for edge in graph.edges:
            if edge.router:
                selector_map[edge.router.selector._uuid].append(edge.router)

        # Inject params first (usually params are in the first stage or handled implicitly)
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
                skip_reason = self._should_skip(node, graph, results, skipped_node_ids)
                if skip_reason:
                    skipped_node_ids.add(node.id)
                    self.bus.publish(
                        TaskSkipped(
                            run_id=run_id,
                            task_id=node.id,
                            task_name=node.name,
                            reason=skip_reason,
                        )
                    )
                    continue
                
                # Create coroutine for the node
~~~~~
~~~~~python
                skip_reason = self._should_skip(
                    node, graph, results, skipped_node_ids, pruned_node_ids
                )
                if skip_reason:
                    skipped_node_ids.add(node.id)
                    self.bus.publish(
                        TaskSkipped(
                            run_id=run_id,
                            task_id=node.id,
                            task_name=node.name,
                            reason=skip_reason,
                        )
                    )
                    continue
                
                # Create coroutine for the node
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
            for node, res in zip(runnable_nodes, stage_results):
                results[node.id] = res

        # Final check: Was the target task executed?
~~~~~
~~~~~python
            for node, res in zip(runnable_nodes, stage_results):
                results[node.id] = res

                # Check if this node drives any Routers
                if node.id in selector_map:
                    for router in selector_map[node.id]:
                        # The result of this node determines which route is active
                        selected_key = res
                        
                        # Identify active route UUID
                        active_route_uuid = None
                        if selected_key in router.routes:
                            active_route_uuid = router.routes[selected_key]._uuid
                        
                        # Prune all OTHER routes
                        for route_key, route_lazy in router.routes.items():
                            if route_lazy._uuid != active_route_uuid:
                                pruned_node_ids.add(route_lazy._uuid)

        # Final check: Was the target task executed?
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
    def _should_skip(
        self,
        node: Node,
        graph: Graph,
        results: Dict[str, Any],
        skipped_node_ids: set[str],
    ) -> Optional[str]:
        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]

        # 1. Cascade Skip: Check only DATA and IMPLICIT edges (i.e., actual inputs and router routes)
        for edge in incoming_edges:
            if edge.edge_type in (EdgeType.DATA, EdgeType.IMPLICIT):
                if edge.source.id in skipped_node_ids:
                    return "UpstreamSkipped"

        # 2. Condition Check
~~~~~
~~~~~python
    def _should_skip(
        self,
        node: Node,
        graph: Graph,
        results: Dict[str, Any],
        skipped_node_ids: set[str],
        pruned_node_ids: set[str],
    ) -> Optional[str]:
        # 0. Pruning Check
        if node.id in pruned_node_ids:
            return "RouterPruned"

        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]

        # 1. Cascade Skip: Check only DATA and IMPLICIT edges (i.e., actual inputs and router routes)
        for edge in incoming_edges:
            if edge.edge_type in (EdgeType.DATA, EdgeType.IMPLICIT):
                if edge.source.id in skipped_node_ids:
                    return "UpstreamSkipped"

        # 2. Condition Check
~~~~~

#### Acts 3: 添加剪枝测试

添加一个新的测试用例来验证剪枝逻辑是否按预期工作。

~~~~~act
write_file
tests/integration/test_router_pruning.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event, TaskSkipped, TaskExecutionFinished


class SpySubscriber:
    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def events_of_type(self, event_type):
        return [e for e in self.events if isinstance(e, event_type)]


@pytest.mark.asyncio
async def test_router_prunes_unselected_branch():
    """
    Verify that tasks in the unselected branch of a Router are NOT executed.
    """
    
    @cs.task
    def get_mode():
        return "fast"

    @cs.task
    def fast_task():
        return "FAST"

    @cs.task
    def slow_task():
        return "SLOW"

    @cs.task
    def process(val):
        return f"Processed: {val}"

    # Router: Selects 'fast' or 'slow'
    router = cs.Router(
        selector=get_mode(),
        routes={
            "fast": fast_task(),
            "slow": slow_task()
        }
    )

    flow = process(router)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    result = await engine.run(flow)

    assert result == "Processed: FAST"

    # Verify Events
    # 1. 'fast_task' should be executed
    finished = spy.events_of_type(TaskExecutionFinished)
    executed_names = {e.task_name for e in finished}
    assert "fast_task" in executed_names
    assert "process" in executed_names
    
    # 2. 'slow_task' should NOT be executed
    assert "slow_task" not in executed_names

    # 3. 'slow_task' should be SKIPPED with reason 'RouterPruned'
    skipped = spy.events_of_type(TaskSkipped)
    skipped_map = {e.task_name: e.reason for e in skipped}
    
    assert "slow_task" in skipped_map
    assert skipped_map["slow_task"] == "RouterPruned"


@pytest.mark.asyncio
async def test_router_prunes_cascade():
    """
    Verify that pruning cascades to downstream dependencies of the pruned branch.
    """
    
    @cs.task
    def selector():
        return "a"
    
    @cs.task
    def branch_a():
        return "A"
    
    @cs.task
    def branch_b_step1():
        return "B1"
    
    @cs.task
    def branch_b_step2(val):
        return f"{val}->B2"

    # Branch B has a chain: step1 -> step2
    chain_b = branch_b_step2(branch_b_step1())

    router = cs.Router(
        selector=selector(),
        routes={
            "a": branch_a(),
            "b": chain_b
        }
    )

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    await engine.run(router)

    skipped = spy.events_of_type(TaskSkipped)
    skipped_map = {e.task_name: e.reason for e in skipped}

    # step2 (the direct route result) is pruned explicitly
    assert skipped_map["branch_b_step2"] == "RouterPruned"
    
    # step1 is NOT pruned automatically because the Engine only prunes 
    # the *immediate* route result node (step2). 
    # step1 might still run if it has no dependency on selector.
    # 
    # WAIT: In the current implementation, we only prune the nodes directly in `router.routes`.
    # We do NOT prune the *upstream* of the pruned node (Reverse Pruning).
    # So `branch_b_step1` is expected to RUN, but its result is unused.
    #
    # Let's verify this behavior is consistent with implementation.
    # If we want to prevent step1 from running, step1 needs to depend on something that is pruned
    # OR we need a more advanced "demand-driven" execution model.
    #
    # For now, let's assert the current behavior: Step 2 is pruned.
    
    finished = spy.events_of_type(TaskExecutionFinished)
    executed = {e.task_name for e in finished}
    
    assert "branch_a" in executed
    assert "branch_b_step1" in executed  # This runs (wasted work, known limitation)
    assert "branch_b_step2" not in executed # This is pruned
~~~~~

### 下一步建议
我们已经实现了基本的 Router 剪枝，这是一个重要的性能提升。

**观察到的限制**:
在 `test_router_pruning.py` 的第二个测试中，我们注意到虽然 `branch_b_step2`（Router 直接引用的节点）被剪枝了，但它的上游 `branch_b_step1` 仍然执行了。这是因为目前的剪枝是**前向**的。要消除 `step1` 的浪费，我们需要一个**反向传播**的剪枝逻辑，或者让 `step1` 也隐式依赖于 `Selector`（但这很复杂）。

目前的实现已经解决了最痛的点（直接的分支任务），对于深层分支的优化可以作为未来的“技术债务”记录下来，或者作为下一次迭代的优化目标。

接下来，建议继续按照计划，关注 `Executor` 的增强或 `.map` 的实现。
