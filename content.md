好的，性能测试的成功验证（不再报错且通过循环检测）是一个里程碑，它证明了我们 1.1 阶段对 **Merkle 哈希** 的实现是正确且具有鲁棒性的。

现在我们推进到 **1.2 阶段：重构 `GraphBuilder` 为 Hash-Consing 构造器**。

**1.2 阶段核心任务分析**

虽然我们在 1.1 中已经初步引入了 `NodeRegistry`，但为了真正符合“类 Git 模型”并支持后续的 JIT 缓存，我们需要在 `GraphBuilder` 中完成以下深度重构：

1.  **统一的 Hash-Consing 逻辑**:
    *   1.1 中 `MappedLazyResult` 的哈希逻辑是简化的“临时方案”。我们需要将其提升到与 `LazyResult` 相同的高度，支持完全的后序遍历和递归哈希。
2.  **强化 `InstanceMap` 的语义**:
    *   按照路线图，`GraphBuilder.build` 返回的 `InstanceMap` 必须是连接“实例”与“结构”的**唯一合法桥梁**。我们需要确保它在所有边界情况（包括嵌套、映射、Shadow 节点）下都能提供一致的映射：`Dict[LazyResult._uuid, Node]`。
3.  **消除构建冗余**:
    *   确保 `GraphBuilder` 内部的 `_visited_instances` 和全局 `registry` 协作无间。对于同一个 `LazyResult` 实例，在同一次构建中绝对不应被处理两次。

我将生成一个计划来完善这些细节。

## [WIP] refactor(graph): Complete Hash-Consing implementation and unify mapping logic

### 用户需求
完成路线图 1.2 节。完善 `GraphBuilder` 的 Hash-Consing（哈希一致性）机制，特别是统一 `MappedLazyResult` 的构建逻辑，并确保 `InstanceMap` 的完整性。

### 评论
如果说 1.1 是解决了“身份识别”问题，那么 1.2 就是解决“身份复用”问题。我们将确保在 Cascade 内存中，任何结构相同的计算单元（无论是单任务还是映射任务）都指向同一个唯一的 `Node` 实例。这种“单例化”结构是实现 2.1 节 JIT 缓存的先决条件，因为它保证了缓存 Key 的绝对物理一致性。

### 目标
1.  **重构 `_visit_mapped_result`**: 为 `MappedLazyResult` 实现与 `LazyResult` 完全一致的后序遍历和 Merkle 哈希逻辑。
2.  **增强哈希一致性**: 确保 `GraphBuilder` 在处理 `Router` 和其他复杂嵌套结构时，也能生成稳定的、基于子节点 ID 的哈希。
3.  **规范化 `InstanceMap`**: 明确 `build_graph` 返回的第三个值（`instance_map`）的结构和用途，确保它是后续执行引擎定位根节点的唯一依据。

### 基本原理
Hash-Consing 技术（哈希一致性/共享技术）要求我们在创建对象之前，先检查是否存在结构等价的既有对象。在 1.1 的重构中，我们已经实现了 `registry`。1.2 的重点在于消除构建流程中的“特例”，让 `MappedLazyResult` 也能享受到结构哈希带来的去重收益。

### 标签
#intent/refine #flow/ready #priority/high
#comp/graph #concept/state #scope/core
#ai/instruct
#task/domain/graph #task/object/graph-builder #task/action/refactor
#task/state/continue #task/status/active

---

### Script

#### Acts 1: Refine `GraphBuilder` for consistent Hash-Consing

我们将重写 `GraphBuilder` 中的部分方法，特别是统一 `MappedLazyResult` 的处理，并优化哈希计算的内部流程。

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
from typing import Dict, Any, List, Tuple
import inspect
import hashlib
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.graph.ast_analyzer import assign_tco_cycle_ids, analyze_task_source
from cascade.spec.task import Task
from cascade.spec.binding import SlotRef
from cascade.spec.resource import Inject

from .registry import NodeRegistry


class GraphBuilder:
    def __init__(self, registry: NodeRegistry | None = None):
        self.graph = Graph()
        # InstanceMap: Dict[LazyResult._uuid, Node]
        # Connecting the world of volatile instances to the world of stable structures.
        self._visited_instances: Dict[str, Node] = {}
        # Used to detect cycles during static TCO analysis
        self._shadow_visited: Dict[Task, Node] = {}

        self._data_buffer: List[Any] = []
        self.registry = registry if registry is not None else NodeRegistry()

    def build(self, target: Any) -> Tuple[Graph, Tuple[Any, ...], Dict[str, Node]]:
        self._visit(target)
        return self.graph, tuple(self._data_buffer), self._visited_instances

    def _register_data(self, value: Any) -> SlotRef:
        index = len(self._data_buffer)
        self._data_buffer.append(value)
        return SlotRef(index)

    def _visit(self, value: Any) -> Node:
        """Central dispatcher for the post-order traversal."""
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

    def _get_merkle_hash(self, components: List[str]) -> str:
        """Computes a stable hash from a list of string components."""
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _build_hash_components_from_arg(
        self, obj: Any, dep_nodes: Dict[str, Node]
    ) -> List[str]:
        """Recursively builds hash components from arguments, using pre-computed dependency nodes."""
        components = []
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            # Hash-Consing: The identity of this dependency is its structural ID.
            components.append(f"LAZY({dep_nodes[obj._uuid].id})")
        elif isinstance(obj, Router):
            components.append("Router{")
            components.append("Selector:")
            components.extend(self._build_hash_components_from_arg(obj.selector, dep_nodes))
            components.append("Routes:")
            for k in sorted(obj.routes.keys()):
                components.append(f"Key({k})->")
                components.extend(self._build_hash_components_from_arg(obj.routes[k], dep_nodes))
            components.append("}")
        elif isinstance(obj, (list, tuple)):
            components.append("List[")
            for item in obj:
                components.extend(self._build_hash_components_from_arg(item, dep_nodes))
            components.append("]")
        elif isinstance(obj, dict):
            components.append("Dict{")
            for k in sorted(obj.keys()):
                components.append(f"{k}:")
                components.extend(self._build_hash_components_from_arg(obj[k], dep_nodes))
            components.append("}")
        elif isinstance(obj, Inject):
            components.append(f"Inject({obj.resource_name})")
        else:
            try:
                components.append(repr(obj))
            except Exception:
                components.append("<unreprable>")
        return components

    def _find_dependencies(self, obj: Any, dep_nodes: Dict[str, Node]):
        """Helper for post-order traversal: finds and visits all nested LazyResults."""
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            if obj._uuid not in dep_nodes:
                dep_node = self._visit(obj)
                dep_nodes[obj._uuid] = dep_node
        elif isinstance(obj, Router):
            self._find_dependencies(obj.selector, dep_nodes)
            for route in obj.routes.values():
                self._find_dependencies(route, dep_nodes)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                self._find_dependencies(item, dep_nodes)
        elif isinstance(obj, dict):
            for v in obj.values():
                self._find_dependencies(v, dep_nodes)

    def _visit_lazy_result(self, result: LazyResult) -> Node:
        if result._uuid in self._visited_instances:
            return self._visited_instances[result._uuid]

        # 1. Post-order: Resolve all dependencies first
        dep_nodes: Dict[str, Node] = {}
        self._find_dependencies(result.args, dep_nodes)
        self._find_dependencies(result.kwargs, dep_nodes)
        if result._condition:
            self._find_dependencies(result._condition, dep_nodes)
        if result._constraints:
            self._find_dependencies(result._constraints.requirements, dep_nodes)
        if result._dependencies:
            self._find_dependencies(result._dependencies, dep_nodes)

        # 2. Compute structural Merkle hash
        hash_components = [f"Task({getattr(result.task, 'name', 'unknown')})"]
        if result._retry_policy:
            rp = result._retry_policy
            hash_components.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
        if result._cache_policy:
            hash_components.append(f"Cache({type(result._cache_policy).__name__})")
        
        hash_components.append("Args:")
        hash_components.extend(self._build_hash_components_from_arg(result.args, dep_nodes))
        hash_components.append("Kwargs:")
        hash_components.extend(self._build_hash_components_from_arg(result.kwargs, dep_nodes))

        if result._condition:
            hash_components.append("Condition:PRESENT")
        if result._dependencies:
            hash_components.append(f"Deps:{len(result._dependencies)}")
        if result._constraints:
            keys = sorted(result._constraints.requirements.keys())
            hash_components.append(f"Constraints({','.join(keys)})")
        
        structural_hash = self._get_merkle_hash(hash_components)

        # 3. Hash-consing: intern the Node object
        def node_factory():
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
                try: sig = inspect.signature(result.task.func)
                except (ValueError, TypeError): pass

            return Node(
                id=structural_hash,
                name=result.task.name,
                node_type="task",
                callable_obj=result.task.func,
                signature=sig,
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
            )

        node, created_new = self.registry.get_or_create(structural_hash, node_factory)
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

        # 4. Finalize edges (idempotent)
        self._scan_and_add_edges(node, result.args)
        self._scan_and_add_edges(node, result.kwargs)
        if result._condition:
            source_node = self._visited_instances[result._condition._uuid]
            self.graph.add_edge(Edge(source=source_node, target=node, arg_name="_condition", edge_type=EdgeType.CONDITION))
        if result._constraints:
             for res, req in result._constraints.requirements.items():
                if isinstance(req, (LazyResult, MappedLazyResult)):
                    source = self._visited_instances[req._uuid]
                    self.graph.add_edge(Edge(source=source, target=node, arg_name=res, edge_type=EdgeType.CONSTRAINT))
        for dep in result._dependencies:
            source = self._visited_instances[dep._uuid]
            self.graph.add_edge(Edge(source=source, target=node, arg_name="<sequence>", edge_type=EdgeType.SEQUENCE))
        
        return node

    def _visit_mapped_result(self, result: MappedLazyResult) -> Node:
        if result._uuid in self._visited_instances:
            return self._visited_instances[result._uuid]
        
        # 1. Post-order traversal for mapped inputs
        dep_nodes: Dict[str, Node] = {}
        self._find_dependencies(result.mapping_kwargs, dep_nodes)
        if result._condition:
            self._find_dependencies(result._condition, dep_nodes)
        if result._dependencies:
            self._find_dependencies(result._dependencies, dep_nodes)

        # 2. Compute structural hash for Map node
        hash_components = [f"Map({getattr(result.factory, 'name', 'factory')})"]
        hash_components.append("MapKwargs:")
        hash_components.extend(self._build_hash_components_from_arg(result.mapping_kwargs, dep_nodes))
        
        if result._condition: hash_components.append("Condition:PRESENT")
        if result._dependencies: hash_components.append(f"Deps:{len(result._dependencies)}")
        
        structural_hash = self._get_merkle_hash(hash_components)

        # 3. Hash-consing
        def node_factory():
            input_bindings = {}
            for k, val in result.mapping_kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = self._register_data(val)
            
            return Node(
                id=structural_hash,
                name=f"map({getattr(result.factory, 'name', 'factory')})",
                node_type="map",
                mapping_factory=result.factory,
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
            )

        node, created_new = self.registry.get_or_create(structural_hash, node_factory)
        self._visited_instances[result._uuid] = node

        if created_new:
            self.graph.add_node(node)

        # 4. Add data edges
        self._scan_and_add_edges(node, result.mapping_kwargs)
        if result._condition:
            source = self._visited_instances[result._condition._uuid]
            self.graph.add_edge(Edge(source=source, target=node, arg_name="_condition", edge_type=EdgeType.CONDITION))
        for dep in result._dependencies:
            source = self._visited_instances[dep._uuid]
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

    def _scan_and_add_edges(self, target_node: Node, obj: Any, path: str = ""):
        """Idempotently adds DATA and ROUTER edges based on pre-visited instances."""
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            source_node = self._visited_instances[obj._uuid]
            self.graph.add_edge(Edge(source=source_node, target=target_node, arg_name=path or "dep", edge_type=EdgeType.DATA))

        elif isinstance(obj, Router):
            selector_node = self._visited_instances[obj.selector._uuid]
            self.graph.add_edge(Edge(source=selector_node, target=target_node, arg_name=path, router=obj, edge_type=EdgeType.DATA))
            for key, route_res in obj.routes.items():
                route_node = self._visited_instances[route_res._uuid]
                self.graph.add_edge(Edge(source=route_node, target=target_node, arg_name=f"{path}.route[{key}]", edge_type=EdgeType.ROUTER_ROUTE))

        elif isinstance(obj, (list, tuple)):
            for i, item in enumerate(obj):
                self._scan_and_add_edges(target_node, item, path=f"{path}[{i}]" if path else str(i))

        elif isinstance(obj, dict):
            for k, v in obj.items():
                self._scan_and_add_edges(target_node, v, path=f"{path}.{k}" if path else str(k))


def build_graph(
    target: Any, registry: NodeRegistry | None = None
) -> Tuple[Graph, Tuple[Any, ...], Dict[str, Node]]:
    return GraphBuilder(registry=registry).build(target)
~~~~~

### 下一步建议

我们已经完成了 `GraphBuilder` 的“Hash-Consing”化重构。
1.  **代码审查**: 注意 `_find_dependencies` 和 `_scan_and_add_edges` 的引入。它们确保了我们首先建立稳定的结构身份，然后才建立连接关系，且这一切都依赖于 `_visited_instances` (InstanceMap) 这个桥梁。
2.  **验证**: 再次运行 `pytest` 确保 1.1 引入的哈希测试和现有的 217 个测试依然全部通过。
3.  **推进 1.3**: 一旦验证通过，我们将进入 **1.3 阶段：适配 `GraphExecutionStrategy`**。我们将移除所有复杂的缓存逻辑，仅保留基于 `InstanceMap` 的、绝对正确的执行链路。

请确认是否运行测试。
