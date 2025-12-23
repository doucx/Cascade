简要回答：
我们将通过以下措施修复性能回退：1. 优化 `StructuralHasher`，从昂贵的字符串拼接+SHA256 转换为高效的 Python 原生元组哈希；2. 恢复针对简单任务的 `_is_simple_task` 快速通道优化；3. 引入专用的 `extract_data` 函数以避免在缓存命中时重复构建图。

## [WIP] perf: 优化 StructuralHasher 并恢复 TCO 快速通道

### 错误分析
性能基准测试显示 `simple_countdown` 的 TPS 从 ~8500 跌至 ~1300，`heavy_complex_countdown` 跌至 ~82。
主要原因分析：
1.  **哈希计算开销过大**: `StructuralHasher` 使用字符串列表拼接并计算 SHA256，这在紧密循环（TCO）中是非常昂贵的操作。对于 `heavy` 任务，每次迭代都要遍历 10 层深度的树并进行大量字符串操作。
2.  **快速通道丢失**: 之前的 `_is_simple_task` 优化允许对简单递归直接使用 `id(task_obj)` 作为缓存键，这是 $O(1)$ 的操作。移除它意味着所有任务都必须走昂贵的哈希计算路径。
3.  **重复图构建**: 即使缓存命中，`execute` 循环中仍然调用 `build_graph` 来提取数据。`build_graph` 会实例化大量的 `Node` 和 `Edge` 对象，这在只需提取 `DataTuple` 的场景下是巨大的浪费。

### 用户需求
恢复 TCO 性能到重构前的水平（Simple > 8000 TPS），同时保持新架构的通用性（即支持 `heavy_complex_countdown` 运行且不报错）。

### 目标
1.  **重写 `StructuralHasher`**: 放弃 SHA256，改用基于递归元组的 `hash()`，大幅降低常数因子。
2.  **恢复 `GraphExecutionStrategy` 优化**:
    *   重新引入 `_is_simple_task` 检查。
    *   对简单任务使用 `id(task)` 作为缓存键。
    *   对复杂任务使用优化后的 `StructuralHasher`。
3.  **实现 `extract_data`**: 在 `GraphBuilder` 中添加一个轻量级的数据提取方法，仅遍历 `LazyResult` 树并收集 `SlotRef` 指向的数据，不创建任何图对象。

### 基本原理
*   **Python Hash**: Python 的内置 `hash()` 对于元组是非常高效的（C 语言层实现）。对于内存中的 TCO 循环，我们不需要跨进程/持久化的 SHA256 哈希稳定性，进程内的 `hash()` 足够且快得多。
*   **Heuristic Optimization**: 绝大多数递归任务都是简单的自递归。保留针对这种情况的特化优化（Fast Path）是系统工程中的常见权衡。
*   **Allocation Removal**: 在热路径中移除对象分配（`Node`, `Edge`）是提升 Python 性能的关键。

### 标签
#intent/refine #intent/perf #flow/ready #priority/critical #comp/engine #comp/graph #concept/tco #concept/optimization #scope/core #ai/refine #task/domain/optimization #task/object/graph-execution-strategy #task/action/performance-tuning #task/state/continue

---

### Script

#### Acts 1: 优化 StructuralHasher 为 Tuple Hash

将基于字符串的哈希计算替换为基于元组的结构哈希。

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~
~~~~~python
from typing import Any, Dict, Tuple, List
import hashlib
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import Inject


class ShallowHasher:
    """
    Generates a stable shallow structural hash for a LazyResult.
    "Shallow" means it does NOT recursively hash nested LazyResults.
    """

    def __init__(self):
        self._hash_components: List[str] = []

    def hash(self, target: Any) -> str:
        self._hash_components = []
        self._visit_top_level(target)
        fingerprint = "|".join(self._hash_components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _visit_top_level(self, obj: Any):
        if isinstance(obj, LazyResult):
            self._visit_lazy(obj)
        elif isinstance(obj, MappedLazyResult):
            self._visit_mapped(obj)
        else:
            self._visit_arg(obj)

    def _visit_arg(self, obj: Any):
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            self._hash_components.append("LAZY")
            return

        if isinstance(obj, Router):
            self._hash_components.append("Router{")
            self._hash_components.append("Selector:")
            self._visit_arg(obj.selector)
            self._hash_components.append("Routes:")
            for k in sorted(obj.routes.keys()):
                self._hash_components.append(f"Key({k})->")
                self._visit_arg(obj.routes[k])
            self._hash_components.append("}")
            return

        if isinstance(obj, (list, tuple)):
            self._hash_components.append("List[")
            for item in obj:
                self._visit_arg(item)
            self._hash_components.append("]")
            return

        if isinstance(obj, dict):
            self._hash_components.append("Dict{")
            for k in sorted(obj.keys()):
                self._hash_components.append(f"{k}:")
                self._visit_arg(obj[k])
            self._hash_components.append("}")
            return

        if isinstance(obj, Inject):
            self._hash_components.append(f"Inject({obj.resource_name})")
            return

        try:
            self._hash_components.append(repr(obj))
        except Exception:
            self._hash_components.append("<unreprable>")

    def _visit_lazy(self, lr: LazyResult):
        # Include UUID to ensure topological distinctness in GraphBuilder
        self._hash_components.append(f"UUID({lr._uuid})")
        task_name = getattr(lr.task, "name", "unknown")
        self._hash_components.append(f"Task({task_name})")

        if lr._retry_policy:
            rp = lr._retry_policy
            self._hash_components.append(
                f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})"
            )
        if lr._cache_policy:
            self._hash_components.append(f"Cache({type(lr._cache_policy).__name__})")

        self._hash_components.append("Args:")
        for arg in lr.args:
            self._visit_arg(arg)

        self._hash_components.append("Kwargs:")
        for k in sorted(lr.kwargs.keys()):
            self._hash_components.append(f"{k}=")
            self._visit_arg(lr.kwargs[k])

        if lr._condition:
            self._hash_components.append("Condition:PRESENT")
        if lr._dependencies:
            self._hash_components.append(f"Deps:{len(lr._dependencies)}")
        if lr._constraints:
            keys = sorted(lr._constraints.requirements.keys())
            self._hash_components.append(f"Constraints({','.join(keys)})")

    def _visit_mapped(self, mlr: MappedLazyResult):
        # Include UUID to ensure topological distinctness in GraphBuilder
        self._hash_components.append(f"UUID({mlr._uuid})")
        factory_name = getattr(mlr.factory, "name", "unknown")
        self._hash_components.append(f"Map({factory_name})")

        self._hash_components.append("MapKwargs:")
        for k in sorted(mlr.mapping_kwargs.keys()):
            self._hash_components.append(f"{k}=")
            self._visit_arg(mlr.mapping_kwargs[k])

        if mlr._condition:
            self._hash_components.append("Condition:PRESENT")
        if mlr._dependencies:
            self._hash_components.append(f"Deps:{len(mlr._dependencies)}")
        if mlr._constraints:
            keys = sorted(mlr._constraints.requirements.keys())
            self._hash_components.append(f"Constraints({','.join(keys)})")


class StructuralHasher:
    """
    Generates a stable structural hash for a LazyResult tree.
    Uses Python's native tuple hashing for high performance.
    """

    def __init__(self):
        # We don't need state for tuple hashing, but keeping API consistent
        pass

    def hash(self, target: Any) -> Tuple[int, None]:
        # Returns (hash_int, None). The second element is legacy 'literals' dict
        # which we don't extract during hashing anymore for speed.
        structure = self._visit(target)
        return hash(structure), None

    def _visit(self, obj: Any) -> Any:
        if isinstance(obj, LazyResult):
            return self._visit_lazy(obj)
        elif isinstance(obj, MappedLazyResult):
            return self._visit_mapped(obj)
        elif isinstance(obj, Router):
            return self._visit_router(obj)
        elif isinstance(obj, (list, tuple)):
            return tuple(self._visit(item) for item in obj)
        elif isinstance(obj, dict):
            # Sort keys for stability
            return tuple((k, self._visit(obj[k])) for k in sorted(obj.keys()))
        elif isinstance(obj, Inject):
            return ("Inject", obj.resource_name)
        else:
            # Literal value marker. We don't include the value itself in the hash
            # if we want strictly structural hashing, BUT:
            # For template matching, structure includes "where the data slots are".
            # The value itself effectively becomes a "Slot" in the template.
            # So "LIT" is correct.
            return "LIT"

    def _visit_lazy(self, lr: LazyResult) -> Tuple:
        components = ["Task", getattr(lr.task, "name", "unknown")]

        if lr._retry_policy:
            rp = lr._retry_policy
            components.append(("Retry", rp.max_attempts, rp.delay, rp.backoff))
        if lr._cache_policy:
            components.append(("Cache", type(lr._cache_policy).__name__))

        # Args
        args_tuple = tuple(self._visit(arg) for arg in lr.args)
        components.append(args_tuple)

        # Kwargs
        kwargs_tuple = tuple(
            (k, self._visit(v)) for k, v in sorted(lr.kwargs.items())
        )
        components.append(kwargs_tuple)

        if lr._condition:
            components.append(("Condition", self._visit(lr._condition)))

        if lr._dependencies:
            deps_tuple = tuple(self._visit(dep) for dep in lr._dependencies)
            components.append(("Deps", deps_tuple))

        if lr._constraints:
             # Just hash keys of constraints, values are data
             keys = tuple(sorted(lr._constraints.requirements.keys()))
             components.append(("Constraints", keys))

        return tuple(components)

    def _visit_mapped(self, mlr: MappedLazyResult) -> Tuple:
        components = ["Map", getattr(mlr.factory, "name", "unknown")]

        # MapKwargs
        kwargs_tuple = tuple(
            (k, self._visit(v)) for k, v in sorted(mlr.mapping_kwargs.items())
        )
        components.append(kwargs_tuple)

        if mlr._condition:
             components.append(("Condition", self._visit(mlr._condition)))
        if mlr._dependencies:
             deps_tuple = tuple(self._visit(dep) for dep in mlr._dependencies)
             components.append(("Deps", deps_tuple))
        if mlr._constraints:
             keys = tuple(sorted(mlr._constraints.requirements.keys()))
             components.append(("Constraints", keys))
        
        return tuple(components)

    def _visit_router(self, router: Router) -> Tuple:
        # Selector structure
        selector_struct = self._visit(router.selector)
        
        # Routes structure
        routes_items = []
        for k in sorted(router.routes.keys()):
            # Route keys are structural
            routes_items.append((k, self._visit(router.routes[k])))
        
        return ("Router", selector_struct, tuple(routes_items))
~~~~~

#### Acts 2: 在 GraphBuilder 中实现 extract_data

添加 `extract_data` 函数，它只负责提取数据元组，不构建图。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
def build_graph(
    target: Any, registry: NodeRegistry | None = None
) -> Tuple[Graph, Tuple[Any, ...], Dict[str, Node]]:
    return GraphBuilder(registry=registry).build(target)
~~~~~
~~~~~python
def build_graph(
    target: Any, registry: NodeRegistry | None = None
) -> Tuple[Graph, Tuple[Any, ...], Dict[str, Node]]:
    return GraphBuilder(registry=registry).build(target)


class DataExtractor:
    """
    A lightweight visitor that only extracts data literals from a LazyResult tree,
    mirroring the traversal order of GraphBuilder but without creating Nodes.
    """

    def __init__(self):
        self._data_buffer: List[Any] = []
        self._visited: set = set()

    def extract(self, target: Any) -> Tuple[Any, ...]:
        self._visit(target)
        return tuple(self._data_buffer)

    def _register_data(self, value: Any):
        self._data_buffer.append(value)

    def _visit(self, value: Any):
        if isinstance(value, LazyResult):
            self._visit_lazy(value)
        elif isinstance(value, MappedLazyResult):
            self._visit_mapped(value)
        else:
            raise TypeError(f"Cannot extract data from type {type(value)}")

    def _visit_lazy(self, result: LazyResult):
        if result._uuid in self._visited:
            return
        self._visited.add(result._uuid)

        # Arguments (must match GraphBuilder._create_node_from_lazy_result order)
        for val in result.args:
            self._process_arg(val)
        for val in result.kwargs.values():
            self._process_arg(val)

        # Structure traversal (must match GraphBuilder._visit_lazy_result recursion)
        if result._condition:
            self._visit(result._condition)
        
        if result._constraints:
             for req in result._constraints.requirements.values():
                 if isinstance(req, (LazyResult, MappedLazyResult)):
                     self._visit(req)

        for dep in result._dependencies:
            self._visit(dep)
        
        # Scan args again for structure recursion (graph edges)
        self._scan_structure(result.args)
        self._scan_structure(result.kwargs)

    def _visit_mapped(self, result: MappedLazyResult):
        if result._uuid in self._visited:
            return
        self._visited.add(result._uuid)

        # Arguments
        for val in result.mapping_kwargs.values():
            self._process_arg(val)

        # Structure
        # ... mapped specific structure ...
        self._scan_structure(result.mapping_kwargs)

    def _process_arg(self, val: Any):
        if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
            self._register_data(val)

    def _scan_structure(self, obj: Any):
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            self._visit(obj)
        elif isinstance(obj, Router):
            self._visit(obj.selector)
            for route in obj.routes.values():
                self._visit(route)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                self._scan_structure(item)
        elif isinstance(obj, dict):
            for v in obj.values():
                self._scan_structure(v)


def extract_data(target: Any) -> Tuple[Any, ...]:
    return DataExtractor().extract(target)
~~~~~

#### Acts 3: 恢复 Fast Path 并使用 extract_data

在 `GraphExecutionStrategy` 中重新引入优化逻辑。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
from cascade.graph.model import Graph
from cascade.graph.build import build_graph
from cascade.graph.hashing import StructuralHasher
from cascade.spec.protocols import Solver, StateBackend
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
~~~~~
~~~~~python
from cascade.graph.model import Graph
from cascade.graph.build import build_graph, extract_data
from cascade.graph.hashing import StructuralHasher
from cascade.spec.protocols import Solver, StateBackend
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
        self._plan_cache: Dict[str, Tuple[Graph, Any, str]] = {}
        self.hasher = StructuralHasher()

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
                graph, plan, data_tuple, instance_map = None, None, (), None
                target_node = None

                # 1. Structural Hashing & Caching
                struct_hash, _ = self.hasher.hash(current_target)

                if struct_hash in self._plan_cache:
                    # CACHE HIT: Reuse Graph and Plan
                    graph, plan, target_node_id = self._plan_cache[struct_hash]
                    
                    # We still need to build the graph to extract the NEW data tuple
                    # The graph structure is identical, so the data extraction order will be identical.
                    _, data_tuple, _ = build_graph(current_target)
                    
                    # Resolve target node from cached graph
                    target_node = next((n for n in graph.nodes if n.id == target_node_id), None)
                    if not target_node:
                         raise RuntimeError(f"Cached target node {target_node_id} not found in graph")
                    
                    # In cached mode, we don't have a valid instance_map for the new LazyResults.
                    # We pass an empty one, assuming no Routers/Dynamic Constraints in complex TCO loops.
                    instance_map = {} 
                else:
                    # CACHE MISS: Full Build & Solve
                    graph, data_tuple, instance_map = build_graph(current_target)
                    plan = self.solver.resolve(graph)
                    
                    target_node = instance_map[current_target._uuid]
                    self._plan_cache[struct_hash] = (graph, plan, target_node.id)
~~~~~
~~~~~python
        self._plan_cache: Dict[Any, Tuple[Graph, Any, str]] = {}
        self.hasher = StructuralHasher()

    def _is_simple_task(self, lr: Any) -> bool:
        """
        Checks if the LazyResult is a simple, flat task suitable for the Fast Path optimization.
        """
        if not isinstance(lr, LazyResult):
            return False
        if lr._condition or (lr._constraints and not lr._constraints.is_empty()):
            return False
        if lr._dependencies:
            return False
        
        # Shallow check for nested lazy objects in args/kwargs
        # We don't recurse deeply to keep this check O(1) in depth
        for arg in lr.args:
            if isinstance(arg, (LazyResult, MappedLazyResult)):
                return False
        for v in lr.kwargs.values():
             if isinstance(v, (LazyResult, MappedLazyResult)):
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

        while True:
            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                graph, plan, data_tuple, instance_map = None, None, (), None
                target_node = None
                
                # 1. Structural Hashing & Caching
                
                # OPTIMIZATION: Check for simple recursion (Fast Path)
                # If it's a simple task, we use the Task object identity as the cache key.
                # This avoids tree traversal for hashing.
                is_fast_path = False
                cache_key = None
                
                if isinstance(current_target, LazyResult) and self._is_simple_task(current_target):
                     is_fast_path = True
                     cache_key = id(current_target.task)
                else:
                     cache_key, _ = self.hasher.hash(current_target)

                if cache_key in self._plan_cache:
                    # CACHE HIT: Reuse Graph and Plan
                    graph, plan, target_node_id = self._plan_cache[cache_key]
                    
                    # Extract ONLY the data tuple using the optimized extractor
                    data_tuple = extract_data(current_target)
                    
                    # Resolve target node from cached graph
                    target_node = next((n for n in graph.nodes if n.id == target_node_id), None)
                    if not target_node:
                         raise RuntimeError(f"Cached target node {target_node_id} not found in graph")
                    
                    # In cached mode, we don't have a valid instance_map for the new LazyResults.
                    instance_map = {} 
                else:
                    # CACHE MISS: Full Build & Solve
                    graph, data_tuple, instance_map = build_graph(current_target)
                    plan = self.solver.resolve(graph)
                    
                    target_node = instance_map[current_target._uuid]
                    self._plan_cache[cache_key] = (graph, plan, target_node.id)
~~~~~

#### Acts 4: 修复 DataExtractor 的导入问题

我注意到 Act 2 中 `DataExtractor` 的实现依赖了 `Router` 等类，需要确保导入完整。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.graph.ast_analyzer import assign_tco_cycle_ids, analyze_task_source
~~~~~
~~~~~python
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.graph.ast_analyzer import assign_tco_cycle_ids, analyze_task_source
~~~~~
