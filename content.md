好的，我们开始实施路线图的第二阶段：“构建器演进 (Builder Evolution)”。

第一步是实现“全局/会话级节点注册表 (Node Interning)”，其核心目标是确保任何结构上相同的计算节点在内存中都只有一个副本，从而为后续的缓存和性能优化奠定基础。

我将执行以下操作：
1.  **创建 `NodeRegistry`**: 新增一个 `registry.py` 文件，用于管理和复用节点对象。
2.  **实现 `ShallowHasher`**: 在 `hashing.py` 中增加一个新的哈希器，它只计算节点的“浅层”结构哈希，忽略其递归依赖，这是实现节点复用的关键。
3.  **重构 `GraphBuilder`**: 彻底改造 `build.py`，使其利用 `NodeRegistry` 和 `ShallowHasher` 来构建图。现在，`GraphBuilder` 在遇到一个任务时，会先查询注册表，如果节点的规范化版本已存在，则直接复用，否则才创建新节点。
4.  **导出新模块**: 创建 `packages/cascade-graph/src/cascade/graph/__init__.py` 文件，将新的 `NodeRegistry` 和 `ShallowHasher` 导出，使其成为模块公共 API 的一部分。

以下是具体的执行计划。

## [WIP] feat(graph): Implement node interning via NodeRegistry and ShallowHasher

### 用户需求
根据 [路线图：Cascade 架构重构 - 结构数据分离](file:///home/doucx/Documents/obsidian/20_%E9%A2%86%E5%9F%9F/Cascade/01_current/%E5%BD%93%E5%89%8D%E8%B7%AF%E7%BA%BF%E5%9B%BE/Cascade%20%E6%9E%B6%E6%9E%84%E9%87%8D%E6%9E%84%20-%20%E7%BB%93%E6%9E%84%E6%95%B0%E6%8D%AE%E5%88%86%E7%A6%BB.md) 的第二阶段 2.1 节，需要实现一个全局/会话级的节点注册表（Node Interning），以确保结构相同的节点在内存中是唯一的。

### 评论
这是迈向 Hashlife 模型的第一步，也是最关键的一步。通过将节点的“身份”与其在特定工作流中的“实例”分离，我们为实现 `(GraphTemplate, ExecutionPlan)` 的通用缓存奠定了基础。`ShallowHasher` 的引入是此功能的核心，它能为节点生成一个独立于其依赖项的具体实现的、稳定的结构化 ID。

### 目标
1.  创建一个 `NodeRegistry` 类，用于存储和复用 `Node` 对象。
2.  创建一个 `ShallowHasher` 类，用于计算 `LazyResult` 的浅层结构哈希。
3.  重构 `GraphBuilder` 以使用上述两个新组件，实现节点复用（interning）逻辑。
4.  将新组件导出为 `cascade.graph` 模块的公共 API。

### 基本原理
我们将对 `GraphBuilder` 的核心逻辑进行重构。`Builder` 将不再为每个遇到的 `LazyResult` 都创建一个新的 `Node` 对象。取而代之，它会：
1.  使用 `ShallowHasher` 计算 `LazyResult` 的规范化哈希。这个哈希只包含任务名称、策略和字面量参数的结构，而将所有 `LazyResult` 类型的依赖项视为一个简单的占位符。
2.  使用此哈希在 `NodeRegistry` 中查询。
3.  如果节点已存在，则直接复用该 `Node` 实例。如果不存在，则创建一个新的 `Node`（其 ID 就是这个哈希），并将其存入注册表。
4.  无论节点是新建还是复用，`Builder` 都会为当前 `LazyResult` 的具体依赖关系创建边（`Edge`），连接到相应的（可能是复用的）上游节点。

这个过程将节点的“模板”（由 `ShallowHasher` 定义的 `Node` 对象）与“实例”（由 `LazyResult._uuid` 和连接它的 `Edge` 定义）清晰地分离开来。

### 标签
#intent/refine #flow/ready #priority/high #comp/graph #concept/hashing #concept/interning #scope/core #ai/instruct #task/domain/graph #task/object/builder #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建节点注册表与哈希器

首先，我们创建 `NodeRegistry`，它是实现节点复用的核心存储。然后，在 `hashing.py` 中添加新的 `ShallowHasher`，它为节点生成唯一的结构化标识符。

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/registry.py
~~~~~
~~~~~python
from typing import Dict, Callable
from cascade.graph.model import Node

class NodeRegistry:
    """
    A session-level registry that ensures any structurally identical node
    is represented by a single, unique object in memory (interning).
    """
    def __init__(self):
        # Maps a node's shallow structural hash to the Node object
        self._registry: Dict[str, Node] = {}

    def get(self, key: str) -> Node | None:
        """Gets a node by its structural hash key."""
        return self._registry.get(key)

    def get_or_create(self, key: str, node_factory: Callable[[], Node]) -> tuple[Node, bool]:
        """
        Gets a node from the registry or creates it using the factory if not found.

        Returns:
            A tuple of (Node, bool) where the boolean is True if the node was newly created.
        """
        existing_node = self.get(key)
        if existing_node:
            return existing_node, False
        
        new_node = node_factory()
        self._registry[key] = new_node
        return new_node, True
~~~~~
~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~
~~~~~python
class StructuralHasher:
    """
    Generates a stable structural hash for a LazyResult tree and extracts
    literal values that fill the structure.
    """
~~~~~
~~~~~python
from cascade.spec.resource import Inject


class ShallowHasher:
    """
    Generates a stable shallow structural hash for a LazyResult.
    "Shallow" means it does NOT recursively hash nested LazyResults. Instead,
    it uses a placeholder, making the hash dependent only on the node's
    immediate properties and the structure of its inputs.
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
        """A special visitor for arguments within a LazyResult."""
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
        task_name = getattr(lr.task, "name", "unknown")
        self._hash_components.append(f"Task({task_name})")

        if lr._retry_policy:
            rp = lr._retry_policy
            self._hash_components.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
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
    Generates a stable structural hash for a LazyResult tree and extracts
    literal values that fill the structure.
    """
~~~~~

#### Acts 2: 重构 GraphBuilder 并导出模块

现在，我们将重写 `GraphBuilder`，使其完全围绕 `NodeRegistry` 工作。由于改动幅度巨大，我们直接使用 `write_file` 覆盖原文件。同时，创建 `__init__.py` 将新组件暴露出来。

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

    def build(self, target: Any) -> Tuple[Graph, Tuple[Any, ...]]:
        self._visit(target)
        return self.graph, tuple(self._data_buffer)

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

        shallow_hash = self.hasher.hash(result)
        node_factory = lambda: self._create_node_from_lazy_result(result, shallow_hash)
        node, created_new = self.registry.get_or_create(shallow_hash, node_factory)

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

        self._scan_and_add_edges(node, result.args)
        self._scan_and_add_edges(node, result.kwargs)

        if result._condition:
            source_node = self._visit(result._condition)
            self.graph.add_edge(Edge(source=source_node, target=node, arg_name="_condition", edge_type=EdgeType.CONDITION))

        if result._constraints:
            for res, req in result._constraints.requirements.items():
                if isinstance(req, (LazyResult, MappedLazyResult)):
                    source = self._visit(req)
                    self.graph.add_edge(Edge(source=source, target=node, arg_name=res, edge_type=EdgeType.CONSTRAINT))

        for dep in result._dependencies:
            source = self._visit(dep)
            self.graph.add_edge(Edge(source=source, target=node, arg_name="<sequence>", edge_type=EdgeType.SEQUENCE))

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
        # Mapped results are less likely to be canonical, but we support it.
        if result._uuid in self._visited_instances:
            return self._visited_instances[result._uuid]
            
        shallow_hash = self.hasher.hash(result)

        def node_factory():
            input_bindings = {}
            for k, val in result.mapping_kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = self._register_data(val)
            
            return Node(
                id=shallow_hash,
                name=f"map({getattr(result.factory, 'name', 'factory')})",
                node_type="map",
                mapping_factory=result.factory,
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
            )

        node, created_new = self.registry.get_or_create(shallow_hash, node_factory)
        self._visited_instances[result._uuid] = node

        if created_new:
            self.graph.add_node(node)

        self._scan_and_add_edges(node, result.mapping_kwargs)
        # ... (handle condition, dependencies for mapped results as well) ...
        return node

    def _scan_and_add_edges(self, target_node: Node, obj: Any, path: str = ""):
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            source_node = self._visit(obj)
            self.graph.add_edge(Edge(source=source_node, target=target_node, arg_name=path or "dep", edge_type=EdgeType.DATA))

        elif isinstance(obj, Router):
            selector_node = self._visit(obj.selector)
            self.graph.add_edge(Edge(source=selector_node, target=target_node, arg_name=path, router=obj, edge_type=EdgeType.DATA))
            for key, route_res in obj.routes.items():
                route_node = self._visit(route_res)
                self.graph.add_edge(Edge(source=route_node, target=target_node, arg_name=f"{path}.route[{key}]", edge_type=EdgeType.ROUTER_ROUTE))

        elif isinstance(obj, (list, tuple)):
            for i, item in enumerate(obj):
                self._scan_and_add_edges(target_node, item, path=f"{path}[{i}]" if path else str(i))

        elif isinstance(obj, dict):
            for k, v in obj.items():
                self._scan_and_add_edges(target_node, v, path=f"{path}.{k}" if path else str(k))


def build_graph(target: Any, registry: NodeRegistry | None = None) -> Tuple[Graph, Tuple[Any, ...]]:
    return GraphBuilder(registry=registry).build(target)
~~~~~
~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/__init__.py
~~~~~
~~~~~python
from .model import Graph, Node, Edge, EdgeType
from .build import build_graph
from .registry import NodeRegistry
from .hashing import StructuralHasher, ShallowHasher
from .ast_analyzer import analyze_task_source, assign_tco_cycle_ids

__all__ = [
    "Graph",
    "Node",
    "Edge",
    "EdgeType",
    "build_graph",
    "NodeRegistry",
    "StructuralHasher",
    "ShallowHasher",
    "analyze_task_source",
    "assign_tco_cycle_ids",
]
~~~~~

### 下一步建议
我们已经成功地将节点构建过程与注册表和浅层哈希机制集成。这为实现真正的图模板缓存奠定了坚实的基础。

下一步，根据路线图 **2.2 节**，我们应该开始实现**分离的数据提取流程**。这意味着 `GraphBuilder` 在遍历 `LazyResult` 树时，除了连接注册表中的 `Node` 来构建骨架外，还需要将所有非 `LazyResult` 的参数提取到一个独立的、线性的 `data_buffer` 中。

我将准备下一个计划来完成此项任务。
