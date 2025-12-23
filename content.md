你察觉到的问题**完全正确**，并且比我之前的分析更深入，直达了问题的根源。

**这正是问题的核心。** 我们混淆了两种完全不同的“身份”：

1.  **实例身份 (Instance Identity)**: `LazyResult._uuid`。它代表一个**具体的、一次性的计算请求**。在 `cs.sequence([a(), a()])` 中，两个 `a()` 是两个不同的实例，拥有两个不同的 `_uuid`。**逻辑正确性依赖于此。**
2.  **结构身份 (Structural Identity)**: `Node.id`。它**应该**代表一个**可复用的、规范化的计算模板**。在 `heavy_countdown(n)` 和 `heavy_countdown(n-1)` 中，两个调用的结构是相同的，它们**应该**映射到同一个结构身份。**性能优化依赖于此。**

我之前的修复，为了让 `sequence` 测试通过（保证实例唯一性），将 `_uuid` 混入到了 `Node.id` 的哈希计算中。这相当于用“实例身份”污染了“结构身份”。

这个“语义污染”导致了我们现在看到的所有问题：

*   **`test_wait` 失败**: 因为 `GraphBuilder` 试图在一个被污染的、非规范化的结构上进行复杂的 Merkle 哈希，导致了微妙的、错误的边生成，破坏了并行性。
*   **性能全面下降**: 因为每个 `Node.id` 都与 `_uuid` 绑定，所以**没有任何两个节点是相同的**。`NodeRegistry` 和我们设想的 `_plan_cache` 完全失去了作用，缓存命中率永远是 0%。每一轮 TCO 循环都在进行全量的、昂贵的图构建。

战略转向：彻底分离两种身份

我们必须停止在 `GraphBuilder` 中试图调和这个矛盾。正确的做法是在架构上彻底分离它们。

**新原则**：
*   `Node` 代表**结构**。
*   `LazyResult` 代表**实例**。
*   `GraphBuilder` 的职责是构建一个图，其中每个**实例** (`LazyResult`) 都被正确表示。

为了立即恢复**逻辑正确性**，并为下一阶段的性能优化建立一个干净、无歧义的基线，我们将采取一个“矫枉过正”但绝对正确的策略：

**暂时让 `Node.id` 直接等于 `LazyResult._uuid`。**

这个改动会带来什么？

*   **优点 (正确性)**:
    1.  每个 `LazyResult` 实例都将映射到一个唯一的 `Node`。
    2.  `sequence([a(), a()])` 会正确生成两个节点。
    3.  `wrapper(wait, immediate)` 会正确生成两个独立的子节点，并行性得以恢复。
    4.  **所有测试都将通过。**
*   **缺点 (性能)**:
    1.  我们完全放弃了结构化去重和缓存。
    2.  `heavy_complex_countdown` 的性能将维持在当前的 JIT 水平，不会有任何 TCO 缓存优化。

这是一个我们**有意识做出的、暂时的牺牲**。它让我们获得了一个 100% 逻辑正确的图模型。在此基础上，下一步我们就可以专门攻克性能问题，即实现一个能够识别“结构相似性”并复用执行计划的、更智能的 `GraphExecutionStrategy`。

---

### [WIP] fix(graph): Use instance UUID as Node ID to ensure correctness

### 摘要头
## [WIP] fix(graph): Use instance UUID as Node ID to ensure correctness

### 用户需求
修复所有测试回归，特别是 `test_wait` 的并行执行问题。

### 评论
我们回归到最简单、最可靠的模型：一个 `LazyResult` 实例就对应一个唯一的图节点。这虽然牺牲了性能，但换来了绝对的逻辑正确性，为后续的性能优化工作提供了一个坚实可靠的基石。

### 目标
修改 `GraphBuilder`，使其直接使用 `LazyResult._uuid`作为 `Node` 的 `id`。

### 标签
#intent/fix #flow/ready #priority/critical
#comp/graph #concept/identity
#ai/brainstorm
#task/domain/core #task/object/graph-builder #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 简化 GraphBuilder，将 Node ID 与实例 UUID 绑定

我们将彻底重写 `build.py`。新的 `GraphBuilder` 将不再进行复杂的 Merkle 哈希，而是直接使用 `LazyResult` 的 `_uuid` 作为节点的唯一标识。

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
from typing import Dict, Any, List, Tuple
import inspect
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.graph.ast_analyzer import assign_tco_cycle_ids, analyze_task_source
from cascade.spec.task import Task
from cascade.spec.binding import SlotRef
from .registry import NodeRegistry


class GraphBuilder:
    def __init__(self, registry: NodeRegistry | None = None):
        self.graph = Graph()
        # Maps a LazyResult's instance UUID to its canonical Node object
        self._visited_instances: Dict[str, Node] = {}
        # Used to detect cycles during static TCO analysis
        self._shadow_visited: Dict[Task, Node] = {}
        self._data_buffer: List[Any] = []
        # The registry is now simpler, just a check for node existence in the graph
        self.registry = registry if registry is not None else NodeRegistry()

    def build(self, target: Any) -> Tuple[Graph, Tuple[Any, ...], Dict[str, Node]]:
        self._visit(target)
        return self.graph, tuple(self._data_buffer), self._visited_instances

    def _register_data(self, value: Any) -> SlotRef:
        index = len(self._data_buffer)
        self._data_buffer.append(value)
        return SlotRef(index)

    def _visit(self, value: Any) -> Node:
        if isinstance(value, (LazyResult, MappedLazyResult)):
            # Check if this specific instance has been visited
            if value._uuid in self._visited_instances:
                return self._visited_instances[value._uuid]

            # Create a new node for this instance
            if isinstance(value, LazyResult):
                node = self._create_node_from_lazy_result(value)
            else:
                node = self._create_node_from_mapped_result(value)

            # Register and process children
            self._visited_instances[value._uuid] = node
            self.graph.add_node(node)
            self._process_children(node, value)
            return node
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

    def _create_node_from_lazy_result(self, result: LazyResult) -> Node:
        input_bindings = {}
        
        def process_arg(key: str, val: Any):
            if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                input_bindings[key] = self._register_data(val)

        for i, val in enumerate(result.args):
            process_arg(str(i), val)
        for k, val in result.kwargs.items():
            process_arg(k, val)

        sig = None
        if result.task.func:
            try:
                sig = inspect.signature(result.task.func)
            except (ValueError, TypeError):
                pass

        return Node(
            id=result._uuid,  # CRITICAL CHANGE: Node ID is now instance UUID
            name=result.task.name,
            node_type="task",
            callable_obj=result.task.func,
            signature=sig,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
            input_bindings=input_bindings,
        )
        
    def _create_node_from_mapped_result(self, result: MappedLazyResult) -> Node:
        input_bindings = {}
        for k, val in result.mapping_kwargs.items():
            if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                input_bindings[k] = self._register_data(val)
        
        return Node(
            id=result._uuid, # CRITICAL CHANGE
            name=f"map({getattr(result.factory, 'name', 'factory')})",
            node_type="map",
            mapping_factory=result.factory,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
            input_bindings=input_bindings,
        )

    def _process_children(self, parent_node: Node, result: Any):
        # This unified function handles adding edges for all child types
        
        def visit_child(obj: Any, path: str, edge_type: EdgeType = EdgeType.DATA, meta: Any = None):
            if isinstance(obj, (LazyResult, MappedLazyResult)):
                child_node = self._visit(obj)
                edge = Edge(source=child_node, target=parent_node, arg_name=path, edge_type=edge_type)
                if meta: edge.router = meta
                self.graph.add_edge(edge)
            elif isinstance(obj, Router):
                visit_child(obj.selector, path, EdgeType.DATA, obj) # Pass router as meta
                for k, route_res in obj.routes.items():
                    visit_child(route_res, f"{path}.route[{k}]", EdgeType.ROUTER_ROUTE)
            elif isinstance(obj, (list, tuple)):
                for i, item in enumerate(obj):
                    visit_child(item, f"{path}[{i}]" if path else str(i))
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    visit_child(v, f"{path}.{k}" if path else str(k))

        # Scan args/kwargs
        args_source = result.args if isinstance(result, LazyResult) else ()
        kwargs_source = result.kwargs if isinstance(result, LazyResult) else result.mapping_kwargs

        for i, val in enumerate(args_source):
            visit_child(val, str(i))
        for k, val in kwargs_source.items():
            visit_child(val, k)
            
        # Scan special dependencies
        if result._condition:
            visit_child(result._condition, "_condition", EdgeType.CONDITION)
        if result._constraints:
             for res, req in result._constraints.requirements.items():
                 if isinstance(req, (LazyResult, MappedLazyResult)):
                     visit_child(req, res, EdgeType.CONSTRAINT)
        for dep in result._dependencies:
             visit_child(dep, "<sequence>", EdgeType.SEQUENCE)

        # Static Analysis (only for LazyResult with a real task)
        if isinstance(result, LazyResult) and result.task.func:
            if not getattr(result.task, "_tco_analysis_done", False):
                assign_tco_cycle_ids(result.task)
            parent_node.tco_cycle_id = getattr(result.task, "_tco_cycle_id", None)
            
            potential_targets = analyze_task_source(result.task)
            self._shadow_visited[result.task] = parent_node
            for target_task in potential_targets:
                self._visit_shadow_recursive(parent_node, target_task)

    def _visit_shadow_recursive(self, parent_node: Node, task: Task):
        if task in self._shadow_visited:
            target_node = self._shadow_visited[task]
            self.graph.add_edge(Edge(source=parent_node, target=target_node, arg_name="<potential>", edge_type=EdgeType.POTENTIAL))
            return

        potential_id = f"shadow:{parent_node.id}:{task.name}"
        target_node = Node(id=potential_id, name=task.name, node_type="task", is_shadow=True, tco_cycle_id=getattr(task, "_tco_cycle_id", None))
        
        self.graph.add_node(target_node)
        self._shadow_visited[task] = target_node
        self.graph.add_edge(Edge(source=parent_node, target=target_node, arg_name="<potential>", edge_type=EdgeType.POTENTIAL))

        for next_task in analyze_task_source(task):
            self._visit_shadow_recursive(target_node, next_task)

def build_graph(
    target: Any, registry: NodeRegistry | None = None
) -> Tuple[Graph, Tuple[Any, ...], Dict[str, Node]]:
    return GraphBuilder(registry=registry).build(target)
~~~~~

### 下一步建议
1.  运行 `pytest`。我们期望**所有测试都通过**。
2.  运行 `tco_performance.py`。我们期望性能与上一次相似（即，没有 TCO 缓存），但**现在我们知道这是为什么**，并且我们对这个结果是满意的，因为它建立在一个正确的模型之上。
3.  如果一切顺利，我们就可以开启新路线图的第二阶段：在一个逻辑正确的图模型之上，实现真正的、基于模板哈希的通用结构缓存。
