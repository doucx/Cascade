你的分析非常准确。

1.  **性能未提升**：是因为在我的上一版 `strategies.py` 修改中，为了追求通用性，我移除了基于 `task_obj` 的简单缓存 (`_task_templates`)，试图引入基于 `structural_hash` 的通用缓存 (`_plan_cache`)。但是，由于 `GraphBuilder` 为了修复“真环”Bug 必须生成唯一的节点 ID (Merkle Hash)，导致每一轮递归产生的图虽然结构相同，但**节点 ID 全变了**。因此，`_plan_cache` 的命中率实际上是 **0%**。结果就是每一轮都在完整地构建图和求解，导致性能回退到纯 JIT 水平。
2.  **测试大面积失败**：是因为我在上一版 `build.py` 中为了追求“结构去重”，在哈希计算中移除了 `_uuid`。这导致了对于 `cs.sequence([task_a(), task_a()])` 这样的场景，两个不同的任务实例被错误地合并成了同一个图节点，破坏了工作流的执行语义。

**结论**：我们要解决的核心冲突是 **“实例唯一性” (为了逻辑正确) vs “结构复用性” (为了性能)**。

在没有实现 **Phase 4 (Data Hydration / 数据注入)** 之前，我们无法直接复用包含旧 Node ID 的 Plan。

为了立即修复错误并恢复基线性能，我将采取以下“实用主义”策略：

1.  **逻辑修复 (Correctness)**: 在 `GraphBuilder` 中恢复把 `UUID` 混入节点哈希的操作。这能立即修复那 18 个测试失败，确保 `sequence` 等原语正常工作。
2.  **性能止损 (Performance)**: 将 `hashlib.sha256` 替换为 Python 内置的 `hash()`。对于 100k+ 次的节点构建操作，这将带来显著的 CPU 节省，应该能让 `heavy` 的耗时从 19s 回落到更合理的水平（虽然达不到 VM 的 0.1s，但应优于当前的 19s）。
3.  **API 修复**: 补回遗漏的 `build_graph` 导出。

这将把我们带回到一个**“逻辑正确、无 Bug、性能尚可”**的基线状态。要实现 100x 的 TCO 性能飞跃，我们必须在下一步专门实现“数据注入”机制。

## [fix] fix(engine): 修复测试回归与性能瓶颈

### 错误分析
1.  **逻辑回归**: 由于去除了 UUID 哈希，不同实例的相同任务被错误合并，导致 `test_sequence` 等依赖实例唯一性的测试失败。
2.  **ImportError**: 遗漏了 `build_graph` 导出。
3.  **性能回退**: `hashlib.sha256` 在密集循环中开销过大，且缓存未命中导致全量构建。

### 用户需求
1.  修复所有 18 个测试失败。
2.  修复 `ImportError`。
3.  优化 `GraphBuilder` 的基础性能。

### 目标
1.  在 `build.py` 中恢复 UUID 混淆，并切换到 `hash()`。
2.  在 `strategies.py` 中暂时移除无效的 `_plan_cache` 逻辑（避免混淆），回退到稳定的构建-求解循环。

### 标签
#intent/fix #flow/ready #priority/critical
#comp/engine #comp/graph
#ai/instruct
#task/domain/core #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 GraphBuilder (UUID & Fast Hash)

我们将重写 `build.py`：
1.  补上 `build_graph`。
2.  使用 `hash()` 替代 `sha256`。
3.  **关键**: 在计算 `node_hash` 时，将 `result._uuid` 包含在内。这保证了 `sequence([a, a])` 会生成两个不同的节点。

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

from .hashing import ShallowHasher
from .registry import NodeRegistry


class GraphBuilder:
    def __init__(self, registry: NodeRegistry | None = None):
        self.graph = Graph()
        # Maps a LazyResult's instance UUID to its canonical Node object
        self._visited_instances: Dict[str, Node] = {}
        # Used to detect cycles during static TCO analysis
        self._shadow_visited: Dict[Task, Node] = {}

        self._data_buffer: List[Any] = []
        self.registry = registry if registry is not None else NodeRegistry()
        self.hasher = ShallowHasher()

    def build(self, target: Any) -> Tuple[Graph, Tuple[Any, ...], Dict[str, Node]]:
        self._visit(target)
        return self.graph, tuple(self._data_buffer), self._visited_instances

    def _register_data(self, value: Any) -> SlotRef:
        index = len(self._data_buffer)
        self._data_buffer.append(value)
        return SlotRef(index)

    def _visit(self, value: Any) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

    def _create_node_from_lazy_result(
        self, result: LazyResult, node_id: str
    ) -> Node:
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
            id=node_id,
            name=result.task.name,
            node_type="task",
            callable_obj=result.task.func,
            signature=sig,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
            input_bindings=input_bindings,
        )

    def _visit_lazy_result(self, result: LazyResult) -> Node:
        if result._uuid in self._visited_instances:
            return self._visited_instances[result._uuid]

        # 1. Post-order traversal: Visit children FIRST
        child_edges: List[Tuple[Node, str, EdgeType, Any]] = []

        def visit_child(obj: Any, path: str, edge_type: EdgeType = EdgeType.DATA, meta: Any = None):
            if isinstance(obj, (LazyResult, MappedLazyResult)):
                node = self._visit(obj)
                child_edges.append((node, path, edge_type, meta))
            elif isinstance(obj, Router):
                sel_node = self._visit(obj.selector)
                child_edges.append((sel_node, path, edge_type, obj))
                for k, route_res in obj.routes.items():
                    r_node = self._visit(route_res)
                    child_edges.append((r_node, f"{path}.route[{k}]", EdgeType.ROUTER_ROUTE, None))
            elif isinstance(obj, (list, tuple)):
                for i, item in enumerate(obj):
                    visit_child(item, f"{path}[{i}]" if path else str(i), edge_type, meta)
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    visit_child(v, f"{path}.{k}" if path else str(k), edge_type, meta)
        
        for i, val in enumerate(result.args):
            visit_child(val, str(i))
        for k, val in result.kwargs.items():
            visit_child(val, k)
        
        if result._condition:
            visit_child(result._condition, "_condition", EdgeType.CONDITION)
        if result._constraints:
             for res, req in result._constraints.requirements.items():
                 if isinstance(req, (LazyResult, MappedLazyResult)):
                     visit_child(req, res, EdgeType.CONSTRAINT)
        for dep in result._dependencies:
             visit_child(dep, "<sequence>", EdgeType.SEQUENCE)

        # 2. Compute Structural ID (Fast Hash)
        # We use Python's built-in hash() which is faster than sha256.
        # CRITICAL: We MUST include result._uuid to distinguish different instances
        # of the same task in a sequence (e.g. [a(), a()]).
        # This sacrifices "Automatic Structural Deduping" for "Instance Correctness".
        shell_hash = self.hasher.hash(result)
        
        # Combine shell, UUID, and children IDs
        # We use a tuple to hash, which is very efficient in Python
        child_hashes = tuple((c.id, path, etype) for c, path, etype, _ in child_edges)
        
        # The node_hash uniquely identifies this specific instance in the graph
        node_hash_int = hash((shell_hash, result._uuid, child_hashes))
        # Convert to string for ID compatibility
        node_hash = f"{node_hash_int:x}"

        # 3. Create or Get Canonical Node
        node_factory = lambda: self._create_node_from_lazy_result(result, node_hash)
        node, created_new = self.registry.get_or_create(node_hash, node_factory)

        self._visited_instances[result._uuid] = node

        if created_new:
            self.graph.add_node(node)
            
            if result.task.func:
                if not getattr(result.task, "_tco_analysis_done", False):
                    assign_tco_cycle_ids(result.task)
                node.tco_cycle_id = getattr(result.task, "_tco_cycle_id", None)

                potential_targets = analyze_task_source(result.task)
                self._shadow_visited[result.task] = node
                for target_task in potential_targets:
                    self._visit_shadow_recursive(node, target_task)
            
            for child, path, etype, meta in child_edges:
                edge = Edge(source=child, target=node, arg_name=path, edge_type=etype)
                if etype == EdgeType.DATA and meta:
                     edge.router = meta
                self.graph.add_edge(edge)

        return node

    def _visit_shadow_recursive(self, parent_node: Node, task: Task):
        if task in self._shadow_visited:
            target_node = self._shadow_visited[task]
            self.graph.add_edge(Edge(source=parent_node, target=target_node, arg_name="<potential>", edge_type=EdgeType.POTENTIAL))
            return

        potential_uuid = f"shadow:{parent_node.id}:{task.name}"
        target_node = Node(id=potential_uuid, name=task.name, node_type="task", is_shadow=True, tco_cycle_id=getattr(task, "_tco_cycle_id", None))
        
        self.graph.add_node(target_node)
        self._shadow_visited[task] = target_node
        self.graph.add_edge(Edge(source=parent_node, target=target_node, arg_name="<potential>", edge_type=EdgeType.POTENTIAL))

        for next_task in analyze_task_source(task):
            self._visit_shadow_recursive(target_node, next_task)

    def _visit_mapped_result(self, result: MappedLazyResult) -> Node:
        if result._uuid in self._visited_instances:
            return self._visited_instances[result._uuid]
            
        shallow_hash = self.hasher.hash(result) 
        # append UUID to prevent collisions
        node_hash_int = hash((shallow_hash, result._uuid))
        unique_hash = f"{node_hash_int:x}"

        def node_factory():
            input_bindings = {}
            for k, val in result.mapping_kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = self._register_data(val)
            
            return Node(
                id=unique_hash,
                name=f"map({getattr(result.factory, 'name', 'factory')})",
                node_type="map",
                mapping_factory=result.factory,
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
            )

        node, created_new = self.registry.get_or_create(unique_hash, node_factory)
        self._visited_instances[result._uuid] = node

        if created_new:
            self.graph.add_node(node)
        
        def scan(obj, path):
             if isinstance(obj, (LazyResult, MappedLazyResult)):
                 src = self._visit(obj)
                 self.graph.add_edge(Edge(source=src, target=node, arg_name=path, edge_type=EdgeType.DATA))
             elif isinstance(obj, list):
                 for i, x in enumerate(obj): scan(x, f"{path}[{i}]")
        
        for k, v in result.mapping_kwargs.items():
            scan(v, k)

        return node


def build_graph(
    target: Any, registry: NodeRegistry | None = None
) -> Tuple[Graph, Tuple[Any, ...], Dict[str, Node]]:
    return GraphBuilder(registry=registry).build(target)
~~~~~

#### Acts 2: 恢复 ShallowHasher (包含 UUID)

我们也将 UUID 放回 `ShallowHasher`，虽然现在 `GraphBuilder` 已经显式处理了 UUID，但保持 Hasher 的逻辑一致性没有坏处，而且能作为双重保险。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~
~~~~~python
    def _visit_arg(self, obj: Any):
        """A special visitor for arguments within a LazyResult."""
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            self._hash_components.append("LAZY")
            return
~~~~~
~~~~~python
    def _visit_arg(self, obj: Any):
        """A special visitor for arguments within a LazyResult."""
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            self._hash_components.append(f"LAZY({obj._uuid})")
            return
~~~~~

#### Acts 3: 恢复 GraphExecutionStrategy (移除无效缓存)

既然目前的缓存方案在 UUID 变化下无效，我们将其移除，恢复到干净的“每次构建-求解”状态。虽然这意味着 TCO 性能回退到 JIT 水平，但这是正确的（Correct），而且因为切换到了 `hash()`，性能会比 19s 好。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
        self.bus = bus
        self.wakeup_event = wakeup_event
        # Universal Execution Plan Cache
        # Key: Canonical Structural Hash (Root Node ID)
        # Value: ExecutionPlan
        self._plan_cache: Dict[str, Any] = {}

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        current_target = target

        while True:
            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                # 1. Build Graph (Lightweight / Canonicalizing)
                # We always run build_graph. Thanks to the new Merkle-hashing GraphBuilder,
                # this is deterministic and produces canonical Node IDs based on structure.
                graph, data_tuple, instance_map = build_graph(current_target)
                
                # 2. Identify Root Node
                if isinstance(current_target, (LazyResult, MappedLazyResult)):
                    root_node = instance_map[current_target._uuid]
                    cache_key = root_node.id
                else:
                    # For raw literals (edge case in top level), no caching
                    cache_key = None

                # 3. Check Cache or Solve
                plan = None
                if cache_key and cache_key in self._plan_cache:
                    # HIT: Reuse existing plan.
                    # Because Node IDs are deterministic (Merkle), the cached plan
                    # (which references Node IDs) is valid for the newly built graph.
                    plan = self._plan_cache[cache_key]
                else:
                    # MISS: Run Solver (Expensive)
                    plan = self.solver.resolve(graph)
                    if cache_key:
                        self._plan_cache[cache_key] = plan

                # 4. Setup Resources (mixed scope)
                required_resources = self.resource_container.scan(graph, data_tuple)
~~~~~
~~~~~python
        self.bus = bus
        self.wakeup_event = wakeup_event

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        current_target = target

        while True:
            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                # 1. Build Graph
                graph, data_tuple, instance_map = build_graph(current_target)
                
                # 2. Run Solver
                # Note: For TCO optimization (Phase 4), we will need to implement
                # a caching mechanism here that supports Data Hydration (reusing
                # plan templates with new data). For now, we rebuild and solve every step.
                plan = self.solver.resolve(graph)

                # 3. Setup Resources (mixed scope)
                required_resources = self.resource_container.scan(graph, data_tuple)
~~~~~

### 下一步建议
1.  运行 `pytest`：此时所有 18 个测试失败应全部消失。
2.  运行 `tco_performance.py`：`heavy` 的性能应该比 19s 好（因为换了 `hash()`），但肯定不如 VM，也不会是 0.1s。这是预期的基线状态。
3.  然后，我们可以安全地开启“通用缓存”的下一阶段工作。
