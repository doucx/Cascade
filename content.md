这是一个非常敏锐的洞察。

目前的 `Router` 实现确实存在结构性的缺陷：**它将“路由逻辑”推迟到了“参数解析”阶段（即任务执行前一刻）才处理**。这太晚了。为了实现剪枝，我们需要在**上游选择器（Selector）完成的那一刻**，就立即介入并决策下游分支的命运。

这意味着我们需要将“控制流逻辑”从 `Engine` 的巨型循环和 `ArgumentResolver` 中剥离出来，提升为一个独立的、响应式的组件。

以下是针对 `Router` 剪枝准备的重构计划。

## [WIP] refactor(runtime): Extract `FlowManager` and refine edge types for routing

### 用户需求
用户指出当前 `Router` 实现存在结构性问题，无法支持“未选择分支的剪枝”这一关键优化。需要对 `Engine`、`Graph` 模型和构建逻辑进行重构，为后续实现基于选择器的动态剪枝（Pruning）奠定架构基础。

### 评论
当前的实现中，`Router` 的路由逻辑隐式地散落在 `GraphBuilder`（作为 `IMPLICIT` 边）和 `ArgumentResolver`（在最后一刻解析）中。这种“懒惰”处理导致 `Engine` 无法在运行时感知路由的决策。
我们需要将“控制流”提升为一等公民。通过引入 `FlowManager` 和明确的 `ROUTER_ROUTE` 边类型，我们可以让 `Engine` 在 `Selector` 任务完成时立即触发路由计算，从而有机会在调度器调度那些昂贵的分支任务之前将其“杀死”。

### 目标
1.  **模型清晰化**: 在 `EdgeType` 中引入 `ROUTER_ROUTE`，将路由分支边与普通的隐式依赖区分开。
2.  **逻辑集中化**: 创建 `src/cascade/runtime/flow.py`，引入 `FlowManager` 类。
3.  **解耦**: 将 `_should_skip` 等零散的跳过逻辑从 `Engine` 移入 `FlowManager`。
4.  **事件驱动准备**: 为 `FlowManager` 设计钩子，使其能在任务完成时评估对图状态的影响（这是未来实现剪枝的切入点）。

### 基本原理
1.  **明确的语义**: `Solver` 和 `Engine` 目前无法区分“因为依赖而必须先运行”和“因为是路由候选项而必须先运行”。`EdgeType.ROUTER_ROUTE` 解决了这种歧义。
2.  **关注点分离**: `Engine` 负责“怎么跑”（调度、资源、执行），`FlowManager` 负责“跑什么”（跳过、剪枝、条件判断）。这种分离降低了 `Engine.run` 循环的复杂度。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/graph #concept/control-flow #scope/core #ai/instruct #task/domain/core #task/object/router #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 扩展图模型与边类型

首先，我们需要在图模型中明确区分“路由分支”边。目前它们被混淆在 `IMPLICIT` 类型中。

~~~~~act
patch_file
src/cascade/graph/model.py
~~~~~
~~~~~python
class EdgeType(Enum):
    """Defines the semantic type of a dependency edge."""
    DATA = auto()           # A standard data dependency (the output of Source is an input to Target)
    CONDITION = auto()      # A control dependency for the run_if condition
    CONSTRAINT = auto()     # An implicit dependency for resolving dynamic constraints
    IMPLICIT = auto()       # An implicit structural dependency (e.g., from Router routes)
~~~~~
~~~~~python
class EdgeType(Enum):
    """Defines the semantic type of a dependency edge."""
    DATA = auto()           # A standard data dependency (the output of Source is an input to Target)
    CONDITION = auto()      # A control dependency for the run_if condition
    CONSTRAINT = auto()     # An implicit dependency for resolving dynamic constraints
    IMPLICIT = auto()       # An implicit structural dependency
    ROUTER_ROUTE = auto()   # A potential dependency branch for a Router
~~~~~

#### Acts 2: 更新图构建逻辑

更新 `GraphBuilder`，在处理 `Router` 时使用新的边类型。这将使图结构携带足够的语义信息供运行时决策。

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
                for route_key, route_result in value.routes.items():
                    route_node = self._visit(route_result)
                    # Specific edge type for Router routes, allowing dynamic pruning later
                    imp_edge = Edge(
                        source=route_node,
                        target=target_node,
                        arg_name=f"_route_{route_key}", 
                        edge_type=EdgeType.ROUTER_ROUTE
                    )
                    self.graph.add_edge(imp_edge)
~~~~~

#### Acts 3: 创建 `FlowManager`

创建一个新的模块 `flow.py`，并将原本散落在 `Engine` 中的跳过逻辑（Skip Logic）迁移至此。同时，我们为其增加处理 `Router` 的基础结构。

~~~~~act
write_file
src/cascade/runtime/flow.py
~~~~~
~~~~~python
from typing import Dict, Any, Optional, Set, List
from cascade.graph.model import Node, Graph, EdgeType
from cascade.runtime.exceptions import DependencyMissingError


class FlowManager:
    """
    Manages the control flow of the execution, determining which tasks
    should be skipped based on conditions (run_if) or routing logic (Router).
    """

    def __init__(self, graph: Graph):
        self.graph = graph
        self._skipped_nodes: Set[str] = set()

    def mark_skipped(self, node_id: str):
        """Manually marks a node as skipped."""
        self._skipped_nodes.add(node_id)

    def is_skipped(self, node_id: str) -> bool:
        return node_id in self._skipped_nodes

    def should_skip(
        self, node: Node, results: Dict[str, Any]
    ) -> Optional[str]:
        """
        Determines if a node should be skipped.
        Returns the reason string if it should be skipped, or None otherwise.
        """
        # 1. Upstream Skip Propagation (Cascade Skip)
        # Check DATA, IMPLICIT, and ROUTER_ROUTE edges
        incoming_edges = [edge for edge in self.graph.edges if edge.target.id == node.id]
        
        for edge in incoming_edges:
            if edge.edge_type in (EdgeType.DATA, EdgeType.IMPLICIT, EdgeType.ROUTER_ROUTE):
                # If an upstream dependency was skipped, we must skip this node too.
                # Note: For Router, if the *selected* branch was skipped, we skip.
                # Pruning logic (skipping unselected branches) handles the other case 
                # before we get here.
                if edge.source.id in self._skipped_nodes:
                    return "UpstreamSkipped"

        # 2. Condition Check (run_if)
        for edge in incoming_edges:
            if edge.edge_type == EdgeType.CONDITION:
                if edge.source.id not in results:
                    # Condition task didn't run? Should be caught by UpstreamSkipped,
                    # but double check safety.
                    return "ConditionMissing"
                
                condition_result = results.get(edge.source.id)
                if not condition_result:
                    return "ConditionFalse"

        return None
~~~~~

#### Acts 4: 重构 `Engine` 以使用 `FlowManager`

修改 `Engine`，移除内部的 `_should_skip` 方法，转而使用 `FlowManager`。这使得 `Engine` 的代码更加清晰，专注于编排。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.resolvers import ArgumentResolver, ConstraintResolver


class Engine:
~~~~~
~~~~~python
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.resolvers import ArgumentResolver, ConstraintResolver
from cascade.runtime.flow import FlowManager


class Engine:
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver()

    def register(self, resource_def: ResourceDefinition):
~~~~~
~~~~~python
        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver()
        self.flow_manager: Optional[FlowManager] = None

    def register(self, resource_def: ResourceDefinition):
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
        for edge in incoming_edges:
            if edge.edge_type == EdgeType.CONDITION:
                condition_result = results.get(edge.source.id)
                if not condition_result:
                    return "ConditionFalse"

        return None

    async def run(self, target: Any, params: Optional[Dict[str, Any]] = None) -> Any:
        run_id = str(uuid4())
~~~~~
~~~~~python
    async def run(self, target: Any, params: Optional[Dict[str, Any]] = None) -> Any:
        run_id = str(uuid4())
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
        # We need to flatten the plan to find params or iterate carefully.
        # Let's just iterate:
        all_nodes = [node for stage in plan for node in stage]
        self._inject_params(all_nodes, params, results)

        for stage in plan:
            # Prepare tasks for this stage
            tasks_to_run = []
            
            for node in stage:
                if node.node_type == "param":
                    continue

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
        
        # Inject params first (usually params are in the first stage or handled implicitly)
        # We need to flatten the plan to find params or iterate carefully.
        # Let's just iterate:
        all_nodes = [node for stage in plan for node in stage]
        self._inject_params(all_nodes, params, results)

        for stage in plan:
            # Prepare tasks for this stage
            tasks_to_run = []
            
            for node in stage:
                if node.node_type == "param":
                    continue

                skip_reason = self.flow_manager.should_skip(node, results)
                if skip_reason:
                    self.flow_manager.mark_skipped(node.id)
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
            # Let's capture the node IDs corresponding to tasks_to_run.
            
            runnable_nodes = []
            for node in stage:
                if node.node_type != "param" and node.id not in skipped_node_ids:
                    runnable_nodes.append(node)
            
            for node, res in zip(runnable_nodes, stage_results):
~~~~~
~~~~~python
            # Let's capture the node IDs corresponding to tasks_to_run.
            
            runnable_nodes = []
            for node in stage:
                if node.node_type != "param" and not self.flow_manager.is_skipped(node.id):
                    runnable_nodes.append(node)
            
            for node, res in zip(runnable_nodes, stage_results):
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
        # Final check: Was the target task executed?
        if target._uuid not in results:
            # If target was skipped itself, or skipped because of upstream.
            if target._uuid in skipped_node_ids:
                # We need to find the node name for the error message
                # Flatten plan to search for the node
~~~~~
~~~~~python
        # Final check: Was the target task executed?
        if target._uuid not in results:
            # If target was skipped itself, or skipped because of upstream.
            if self.flow_manager.is_skipped(target._uuid):
                # We need to find the node name for the error message
                # Flatten plan to search for the node
~~~~~

#### Acts 5: 更新可视化工具

`cs.visualize` 需要能够识别新的边类型，否则生成的图形可能会丢失这些连接线。

~~~~~act
patch_file
src/cascade/tools/visualize.py
~~~~~
~~~~~python
        elif edge.edge_type == EdgeType.IMPLICIT:
            style = ' [style=dotted, color=lightgray, arrowhead=none, label="implicit"]'
        elif edge.router:
            # Router selector edge (which is EdgeType.DATA)
~~~~~
~~~~~python
        elif edge.edge_type == EdgeType.IMPLICIT:
            style = ' [style=dotted, color=lightgray, arrowhead=none, label="implicit"]'
        elif edge.edge_type == EdgeType.ROUTER_ROUTE:
             # Router route edge
            style = ' [style=dashed, color=orange, arrowhead=open, label="route"]'
        elif edge.router:
            # Router selector edge (which is EdgeType.DATA)
~~~~~

### 下一步建议
我们已经完成了架构的重构，现在 `FlowManager` 掌管了跳过逻辑，并且图模型中有了明确的 `ROUTER_ROUTE`。

接下来的计划将是**实现真正的剪枝逻辑**：
1.  在 `Engine` 中，当任务完成时，通知 `FlowManager`。
2.  在 `FlowManager` 中实现 `on_task_finished`。如果完成的任务是一个 `Router` 的 `selector`，则触发剪枝算法。
3.  剪枝算法将查找所有未被选择的 `ROUTER_ROUTE` 边，并将其源节点（如果它是纯粹的分支节点）标记为 `Skipped`（使用一个新的原因代码，例如 `"Pruned"`）。

这将使我们能够解决 "Router executing all branches" 的技术债务。
