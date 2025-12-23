## [WIP] 升级 `GraphExecutionStrategy`

### Script

#### Acts 1: 重构 GraphBuilder 以实现 Merkle 哈希 (规范化构建)

我们将重写 `packages/cascade-graph/src/cascade/graph/build.py` 中的 `GraphBuilder` 类。核心改变是将遍历顺序从“先序 (Pre-order)”改为“后序 (Post-order)”。

这意味着我们先递归构建所有子节点的 `Node` 对象，然后利用子节点的 ID（也就是它们的结构哈希）来计算当前节点的哈希。这种“自底向上”的构建方式（类似 Merkle Tree）确保了：
1.  **确定性**: 节点的 ID 仅取决于其结构和依赖，与 `LazyResult` 的瞬时 UUID 无关。
2.  **唯一性**: 结构不同的节点（如 `noop(d1)` 和 `noop(d2)`，其中 d1!=d2）会拥有不同的 ID，从而避免了之前的“真环”Bug。
3.  **缓存友好**: 结构相同的子图会自动拥有相同的 ID，天然支持去重和缓存。

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
import hashlib

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

        # 1. Post-order traversal: Visit children FIRST to get their canonical IDs
        child_edges: List[Tuple[Node, str, EdgeType, Any]] = []

        def visit_child(obj: Any, path: str, edge_type: EdgeType = EdgeType.DATA, meta: Any = None):
            if isinstance(obj, (LazyResult, MappedLazyResult)):
                node = self._visit(obj)
                child_edges.append((node, path, edge_type, meta))
            elif isinstance(obj, Router):
                # For routers, we visit the selector and routes
                sel_node = self._visit(obj.selector)
                child_edges.append((sel_node, path, edge_type, obj)) # Router object as meta
                for k, route_res in obj.routes.items():
                    r_node = self._visit(route_res)
                    child_edges.append((r_node, f"{path}.route[{k}]", EdgeType.ROUTER_ROUTE, None))
            elif isinstance(obj, (list, tuple)):
                for i, item in enumerate(obj):
                    visit_child(item, f"{path}[{i}]" if path else str(i), edge_type, meta)
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    visit_child(v, f"{path}.{k}" if path else str(k), edge_type, meta)
        
        # Scan args and kwargs
        for i, val in enumerate(result.args):
            visit_child(val, str(i))
        for k, val in result.kwargs.items():
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

        # 2. Compute Merkle Hash
        # The hash depends on the "Local Shell" (task name, literals) AND the IDs of children.
        # ShallowHasher gives us the shell hash.
        shell_hash = self.hasher.hash(result)
        
        # Combine with child IDs to form a Deep Structural Hash
        hasher = hashlib.sha256(shell_hash.encode())
        for child, path, etype, _ in child_edges:
            # We mix in the Child ID, the Arg Path, and Edge Type.
            # This ensures structural uniqueness.
            combo = f"{child.id}|{path}|{etype.name}"
            hasher.update(combo.encode())
        
        node_hash = hasher.hexdigest()

        # 3. Create or Get Canonical Node
        node_factory = lambda: self._create_node_from_lazy_result(result, node_hash)
        node, created_new = self.registry.get_or_create(node_hash, node_factory)

        self._visited_instances[result._uuid] = node

        if created_new:
            self.graph.add_node(node)
            
            # Static Analysis for TCO (Shadow Nodes)
            if result.task.func:
                if not getattr(result.task, "_tco_analysis_done", False):
                    assign_tco_cycle_ids(result.task)
                node.tco_cycle_id = getattr(result.task, "_tco_cycle_id", None)

                potential_targets = analyze_task_source(result.task)
                self._shadow_visited[result.task] = node
                for target_task in potential_targets:
                    self._visit_shadow_recursive(node, target_task)
            
            # Add edges (now that we have the parent node)
            for child, path, etype, meta in child_edges:
                edge = Edge(source=child, target=node, arg_name=path, edge_type=etype)
                if etype == EdgeType.DATA and meta: # It's a router selector
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
        # TODO: Implement Merkle hashing for MappedLazyResult too.
        # For now, keeping legacy behavior but ensuring UUID reuse works locally.
        if result._uuid in self._visited_instances:
            return self._visited_instances[result._uuid]
            
        # Fallback to shallow hash for now (less critical for recursion benchmarks)
        # In a full implementation, this should mirror _visit_lazy_result
        shallow_hash = self.hasher.hash(result) 
        # append UUID to prevent collisions in fallback mode
        unique_hash = f"{shallow_hash}:{result._uuid}"

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
        
        # Scan children (simplified for mapped)
        def scan(obj, path):
             if isinstance(obj, (LazyResult, MappedLazyResult)):
                 src = self._visit(obj)
                 self.graph.add_edge(Edge(source=src, target=node, arg_name=path, edge_type=EdgeType.DATA))
             elif isinstance(obj, list):
                 for i, x in enumerate(obj): scan(x, f"{path}[{i}]")
        
        for k, v in result.mapping_kwargs.items():
            scan(v, k)

        return node
~~~~~

#### Acts 2: 恢复 ShallowHasher (移除 UUID)

既然 `GraphBuilder` 已经通过 Merkle 方式实现了结构化哈希和节点去重，`ShallowHasher` 就不再需要包含 UUID 了。它应该回归其本职工作：仅计算当前节点的“浅层”特征（Task 名、参数字面量结构）。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~
~~~~~python
    def _visit_arg(self, obj: Any):
        """A special visitor for arguments within a LazyResult."""
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            # Must include UUID to distinguish different instances with similar structure
            # to prevent incorrect node merging (which causes cycles).
            self._hash_components.append(f"LAZY({obj._uuid})")
            return
~~~~~
~~~~~python
    def _visit_arg(self, obj: Any):
        """A special visitor for arguments within a LazyResult."""
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            self._hash_components.append("LAZY")
            return
~~~~~

#### Acts 3: 升级 GraphExecutionStrategy (启用结构化缓存)

最后，我们修改 `GraphExecutionStrategy`。
1.  删除 `_is_simple_task` 及其相关逻辑。
2.  在 `execute` 循环中，始终调用 `build_graph`。
3.  利用 `build_graph` 返回的规范化 `Root Node ID` 作为缓存键。
4.  如果命中缓存，直接复用 Plan，跳过 Solver。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
        self.bus = bus
        self.wakeup_event = wakeup_event
        # Cache for structural hashing (slow path)
        self._graph_cache: Dict[str, Tuple[Graph, Any]] = {}
        # Cache for Zero-Overhead TCO (fast path), keyed by Task object
        self._task_templates: Dict[Any, Tuple[Graph, Any]] = {}

    def _is_simple_task(self, lr: Any) -> bool:
        """
        Checks if the LazyResult is a simple, flat task (no nested dependencies).
        This allows for the Zero-Overhead TCO fast path.
        """
        if not isinstance(lr, LazyResult):
            return False
        if lr._condition or (lr._constraints and not lr._constraints.is_empty()):
            return False

        # Explicit dependencies
        if lr._dependencies:
            return False

        def _has_lazy(obj):
            if isinstance(obj, (LazyResult, MappedLazyResult)):
                return True
            if isinstance(obj, (list, tuple)):
                return any(_has_lazy(x) for x in obj)
            if isinstance(obj, dict):
                return any(_has_lazy(v) for v in obj.values())
            return False

        # Check args and kwargs recursively
        for arg in lr.args:
            if _has_lazy(arg):
                return False

        for v in lr.kwargs.values():
            if _has_lazy(v):
                return False

        return True

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

        # Optimization state for TCO Fast Path
        last_executed_task = None
        last_tco_cycle_id = None

        while True:
            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                graph, plan, data_tuple, instance_map = None, None, (), None

                is_fast_path = False
                if isinstance(current_target, LazyResult) and self._is_simple_task(
                    current_target
                ):
                    task_obj = current_target.task
                    cycle_id = getattr(task_obj, "_tco_cycle_id", None)

                    is_tco_candidate = (
                        cycle_id and cycle_id == last_tco_cycle_id
                    ) or (task_obj == last_executed_task)

                    if is_tco_candidate and task_obj in self._task_templates:
                        is_fast_path = True

                if is_fast_path:
                    # FAST PATH: Reuse plan, rebuild graph quickly to get data
                    graph, plan = self._task_templates[current_target.task]
                    _, data_tuple, instance_map = build_graph(current_target)

                    # BUGFIX: The instance_map from the new build_graph will contain a new,
                    # ephemeral node ID for the current_target. However, the execution plan
                    # uses the canonical node ID from the cached graph. We must align them.
                    # For a simple TCO task, the canonical target is the first (and only)
                    # node in the first stage of the plan.
                    if plan and plan[0]:
                        canonical_target_node = plan[0][0]
                        instance_map[current_target._uuid] = canonical_target_node
                else:
                    # STANDARD PATH: Build graph and resolve plan for the first time
                    graph, data_tuple, instance_map = build_graph(current_target)
                    plan = self.solver.resolve(graph)

                    # Cache the template for future TCO loops
                    if isinstance(current_target, LazyResult) and self._is_simple_task(
                        current_target
                    ):
                        self._task_templates[current_target.task] = (graph, plan)

                # Update state for next iteration
                if isinstance(current_target, LazyResult):
                    last_executed_task = current_target.task
                    last_tco_cycle_id = getattr(current_target.task, "_tco_cycle_id", None)
                else:
                    last_executed_task = None
                    last_tco_cycle_id = None
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
                self.resource_container.setup(
                    required_resources,
                    active_resources,
                    run_stack,
                    step_stack,
                    run_id,
                )

                # 5. Execute Graph
                result = await self._execute_graph(
                    current_target,
                    params,
                    active_resources,
                    run_id,
                    state_backend,
                    graph,
                    data_tuple,
                    plan,
                    instance_map,
                )
~~~~~

### 下一步建议
1.  **运行基准测试**: 再次运行 `tco_performance.py`。我们预期 `heavy_complex_countdown` 的性能将大幅提升，从 ~1000 TPS 跃升至与 `simple_countdown` 相近的水平 (~8000 TPS)。
2.  **验证回归**: 运行 `pytest` 确保没有引入新的回归。
3.  **庆祝**: 如果成功，这将标志着 Cascade 正式完成了向高性能通用结构缓存架构的转型。
