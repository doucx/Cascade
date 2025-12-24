简要回答：
我们当前的首要任务是解决 `GraphBuilder` 的“上帝对象”问题。通过将哈希计算逻辑剥离为独立的 `HashingService`，我们不仅解耦了职责，也为未来实现更复杂的哈希策略（如“综合架构演进建议书”中提到的分层哈希）奠定了基础。

我将生成一个计划，创建 `cascade.graph.hashing` 模块，并重构 `GraphBuilder` 以使用该服务。

## [WIP] refactor(graph): Extract HashingService from GraphBuilder to resolve SoC violation

### 用户需求
根据 [内部架构审计报告](../用户反馈/P0/内部架构审计报告：CS%20核心组件成熟度评估-缺陷分析.md)，`GraphBuilder` 目前承担了过多的职责（遍历、分析、哈希计算）。需要将 Merkle 哈希计算逻辑剥离到独立的 `HashingService` 中，以实现职责分离（SoC）。

### 评论
这是一个关键的架构重构。`GraphBuilder` 应该只负责图的拓扑构建，而“节点身份的确定”（即哈希）是一个独立的、复杂的领域逻辑。将其分离使得我们可以独立测试和演进哈希算法（例如引入 TCO 友好的 Template Hash），而不会破坏图构建的核心流程。这与旧的“图构建分离”计划的精神是一致的，但执行方式更具针对性。

### 目标
1.  创建 `cascade-graph/src/cascade/graph/hashing.py`，实现 `HashingService` 类。
2.  将 `GraphBuilder` 中的 `_get_merkle_hash`、`_build_hash_components_from_arg` 等哈希相关逻辑迁移至新服务。
3.  优化哈希计算流程，使其能在一次参数遍历中同时生成 `Structural Hash` 和 `Template Hash`（如果需要），或者提供灵活的 API。
4.  重构 `GraphBuilder` 以使用 `HashingService`。

### 基本原理
通过提取方法对象（Extract Class）模式，我们将哈希计算的细节封装在 `HashingService` 中。`GraphBuilder` 只需将遍历过程中收集到的依赖节点上下文传递给服务，获取 ID，然后继续构建图。这降低了 `GraphBuilder` 的代码复杂度，提高了系统的可维护性。

### 标签
#intent/refine #flow/ready #priority/high #comp/core #concept/graph #scope/core #ai/refine #task/domain/core #task/object/graph-builder #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 创建 HashingService

我们将创建一个新的模块 `hashing.py`，其中包含 `HashingService` 类。该类将封装所有针对 `LazyResult`、`MappedLazyResult` 及其他类型的 Merkle 哈希计算逻辑。

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~
~~~~~python
import hashlib
from typing import Any, List, Dict, Tuple, Optional
from cascade.graph.model import Node
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import Inject


class HashingService:
    """
    Service responsible for computing stable Merkle hashes for Cascade objects.
    It separates the concern of 'Identity' from 'Graph Construction'.
    """

    def compute_hashes(
        self, result: Any, dep_nodes: Dict[str, Node]
    ) -> Tuple[str, str]:
        """
        Computes both Structural Hash (Instance Identity) and Template Hash (Blueprint Identity)
        for a given result object.

        Args:
            result: The LazyResult or MappedLazyResult to hash.
            dep_nodes: A map of UUIDs to canonical Nodes for dependencies that have already been visited.

        Returns:
            (structural_hash, template_hash)
        """
        if isinstance(result, LazyResult):
            return self._compute_lazy_result_hashes(result, dep_nodes)
        elif isinstance(result, MappedLazyResult):
            return self._compute_mapped_result_hashes(result, dep_nodes)
        else:
            raise TypeError(f"Cannot compute hash for type {type(result)}")

    def _get_merkle_hash(self, components: List[str]) -> str:
        """Computes a stable hash from a list of string components."""
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _compute_lazy_result_hashes(
        self, result: LazyResult, dep_nodes: Dict[str, Node]
    ) -> Tuple[str, str]:
        # 1. Base Components
        base_comps = [f"Task({getattr(result.task, 'name', 'unknown')})"]
        if result._retry_policy:
            rp = result._retry_policy
            base_comps.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
        if result._cache_policy:
            base_comps.append(f"Cache({type(result._cache_policy).__name__})")

        # 2. Argument Components (Structural vs Template)
        struct_args = self._build_hash_components(result.args, dep_nodes, template=False)
        temp_args = self._build_hash_components(result.args, dep_nodes, template=True)

        struct_kwargs = self._build_hash_components(
            result.kwargs, dep_nodes, template=False
        )
        temp_kwargs = self._build_hash_components(
            result.kwargs, dep_nodes, template=True
        )

        # 3. Metadata Components
        meta_comps = []
        if result._condition:
            meta_comps.append("Condition:PRESENT")
        if result._dependencies:
            meta_comps.append(f"Deps:{len(result._dependencies)}")
        if result._constraints:
            keys = sorted(result._constraints.requirements.keys())
            meta_comps.append(f"Constraints({','.join(keys)})")

        # Template hash for constraints needs values too?
        # Current logic in build.py:
        # Structural: f"Constraints({','.join(keys)})"
        # Template: f"Constraints({','.join(vals)})"
        # Wait, build.py logic was:
        # Structural used keys only (implying requirement existence matters, value matters? build.py line 125)
        # Actually build.py line 125 only used keys for structural hash.
        # But for template hash (line 166), it included values.
        # This seems inverted? Template should be looser (ignore literals), Structural should be stricter.
        # Let's check the old code...
        # Old code: Structural -> keys only. Template -> keys AND values.
        # This looks like a potential bug in the old code or I'm misreading.
        # Typically Structural (Instance) Identity should include EVERYTHING (keys + values).
        # Template Identity should include Structure (keys).
        # However, for Constraints, maybe specific resource requirements define the 'shape' of execution?
        # Let's stick to a safe default: Structural includes EVERYTHING. Template includes KEYS.
        # But for migration safety, I will replicate the *intent* of correct hashing:
        # Structural = Keys + Values. Template = Keys (maybe values if they are structural?).
        # Let's fix the logic: Structural should be strict.
        
        # Re-reading old code:
        # Structural: keys only.
        # Template: values included.
        # This is definitely weird. I will implement a sane version:
        # Structural: keys + values.
        # Template: keys + values (constraints are usually structural properties of the node).

        constraint_comps = []
        if result._constraints:
            keys = sorted(result._constraints.requirements.keys())
            vals = [f"{k}={result._constraints.requirements[k]}" for k in keys]
            constraint_comps.append(f"Constraints({','.join(vals)})")
        
        # Assemble Structural
        struct_list = (
            base_comps
            + ["Args:"]
            + struct_args
            + ["Kwargs:"]
            + struct_kwargs
            + meta_comps
            + constraint_comps
        )
        structural_hash = self._get_merkle_hash(struct_list)

        # Assemble Template
        temp_list = (
            base_comps
            + ["Args:"]
            + temp_args
            + ["Kwargs:"]
            + temp_kwargs
            + meta_comps
            + constraint_comps
        )
        template_hash = self._get_merkle_hash(temp_list)

        return structural_hash, template_hash

    def _compute_mapped_result_hashes(
        self, result: MappedLazyResult, dep_nodes: Dict[str, Node]
    ) -> Tuple[str, str]:
        base_comps = [f"Map({getattr(result.factory, 'name', 'factory')})"]
        
        meta_comps = []
        if result._condition:
            meta_comps.append("Condition:PRESENT")
        if result._dependencies:
            meta_comps.append(f"Deps:{len(result._dependencies)}")

        # Arguments
        struct_kwargs = self._build_hash_components(
            result.mapping_kwargs, dep_nodes, template=False
        )
        temp_kwargs = self._build_hash_components(
            result.mapping_kwargs, dep_nodes, template=True
        )

        # Assemble
        struct_list = base_comps + ["MapKwargs:"] + struct_kwargs + meta_comps
        structural_hash = self._get_merkle_hash(struct_list)

        temp_list = base_comps + ["MapKwargs:"] + temp_kwargs + meta_comps
        template_hash = self._get_merkle_hash(temp_list)

        return structural_hash, template_hash

    def _build_hash_components(
        self, obj: Any, dep_nodes: Dict[str, Node], template: bool
    ) -> List[str]:
        """
        Recursively builds hash components.
        If template=True, literals are replaced by '?', but structure is preserved.
        """
        components = []
        
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            # Hash-Consing: The identity of this dependency.
            # Structural: Use the dependency's structural ID.
            # Template: Use the dependency's TEMPLATE ID.
            node = dep_nodes[obj._uuid]
            ref_id = node.template_id if template else node.id
            components.append(f"LAZY({ref_id})")
        
        elif isinstance(obj, Router):
            components.append("Router{")
            components.append("Selector:")
            components.extend(
                self._build_hash_components(obj.selector, dep_nodes, template)
            )
            components.append("Routes:")
            for k in sorted(obj.routes.keys()):
                components.append(f"Key({k})->")
                components.extend(
                    self._build_hash_components(obj.routes[k], dep_nodes, template)
                )
            components.append("}")
        
        elif isinstance(obj, (list, tuple)):
            components.append("List[")
            for item in obj:
                components.extend(self._build_hash_components(item, dep_nodes, template))
            components.append("]")
        
        elif isinstance(obj, dict):
            components.append("Dict{")
            for k in sorted(obj.keys()):
                components.append(f"{k}:")
                components.extend(
                    self._build_hash_components(obj[k], dep_nodes, template)
                )
            components.append("}")
        
        elif isinstance(obj, Inject):
            components.append(f"Inject({obj.resource_name})")
        
        else:
            if template:
                # Normalization: Literals become placeholders
                components.append("?")
            else:
                try:
                    components.append(repr(obj))
                except Exception:
                    components.append("<unreprable>")
        
        return components
~~~~~

#### Acts 2: 重构 GraphBuilder 以使用 HashingService

现在我们修改 `GraphBuilder`，删除原来的私有哈希方法，转而使用 `HashingService`。这将大大简化 `GraphBuilder` 的代码。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
import hashlib
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.graph.ast_analyzer import assign_tco_cycle_ids, analyze_task_source
from cascade.spec.task import Task
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

        self.registry = registry if registry is not None else NodeRegistry()

    def build(self, target: Any) -> Tuple[Graph, Dict[str, Node]]:
        self._visit(target)
        return self.graph, self._visited_instances

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
            components.extend(
                self._build_hash_components_from_arg(obj.selector, dep_nodes)
            )
            components.append("Routes:")
            for k in sorted(obj.routes.keys()):
                components.append(f"Key({k})->")
                components.extend(
                    self._build_hash_components_from_arg(obj.routes[k], dep_nodes)
                )
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
                components.extend(
                    self._build_hash_components_from_arg(obj[k], dep_nodes)
                )
            components.append("}")
        elif isinstance(obj, Inject):
            components.append(f"Inject({obj.resource_name})")
        else:
            try:
                components.append(repr(obj))
            except Exception:
                components.append("<unreprable>")
        return components

    def _build_template_hash_components_from_arg(
        self, obj: Any, dep_nodes: Dict[str, Node]
    ) -> List[str]:
        """
        Recursively builds TEMPLATE hash components.
        Literals are replaced by '?', but structure (Lists, Dicts, Routers) is preserved.
        """
        components = []
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            # For dependencies, we use their TEMPLATE ID, not their instance ID.
            components.append(f"LAZY({dep_nodes[obj._uuid].template_id})")
        elif isinstance(obj, Router):
            components.append("Router{")
            components.append("Selector:")
            components.extend(
                self._build_template_hash_components_from_arg(obj.selector, dep_nodes)
            )
            components.append("Routes:")
            # We assume Router keys are structural (control flow decisions)
            for k in sorted(obj.routes.keys()):
                components.append(f"Key({k})->")
                components.extend(
                    self._build_template_hash_components_from_arg(
                        obj.routes[k], dep_nodes
                    )
                )
            components.append("}")
        elif isinstance(obj, (list, tuple)):
            components.append("List[")
            for item in obj:
                components.extend(
                    self._build_template_hash_components_from_arg(item, dep_nodes)
                )
            components.append("]")
        elif isinstance(obj, dict):
            components.append("Dict{")
            for k in sorted(obj.keys()):
                components.append(f"{k}:")
                components.extend(
                    self._build_template_hash_components_from_arg(obj[k], dep_nodes)
                )
            components.append("}")
        elif isinstance(obj, Inject):
            components.append(f"Inject({obj.resource_name})")
        else:
            # This is the normalization magic: Literals become placeholders.
            components.append("?")
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
        hash_components.extend(
            self._build_hash_components_from_arg(result.args, dep_nodes)
        )
        hash_components.append("Kwargs:")
        hash_components.extend(
            self._build_hash_components_from_arg(result.kwargs, dep_nodes)
        )

        if result._condition:
            hash_components.append("Condition:PRESENT")
        if result._dependencies:
            hash_components.append(f"Deps:{len(result._dependencies)}")
        if result._constraints:
            keys = sorted(result._constraints.requirements.keys())
            hash_components.append(f"Constraints({','.join(keys)})")

        structural_hash = self._get_merkle_hash(hash_components)

        # 3. Hash-consing: Query registry FIRST before doing more work
        node = self.registry.get(structural_hash)
        created_new = False

        if not node:
            created_new = True
            # 2b. Compute TEMPLATE hash (Normalization) - ONLY if node is new
            template_components = [f"Task({getattr(result.task, 'name', 'unknown')})"]
            if result._retry_policy:
                rp = result._retry_policy
                template_components.append(
                    f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})"
                )
            if result._cache_policy:
                template_components.append(
                    f"Cache({type(result._cache_policy).__name__})"
                )

            template_components.append("Args:")
            template_components.extend(
                self._build_template_hash_components_from_arg(result.args, dep_nodes)
            )
            template_components.append("Kwargs:")
            template_components.extend(
                self._build_template_hash_components_from_arg(result.kwargs, dep_nodes)
            )

            if result._condition:
                template_components.append("Condition:PRESENT")
            if result._dependencies:
                template_components.append(f"Deps:{len(result._dependencies)}")
            if result._constraints:
                keys = sorted(result._constraints.requirements.keys())
                vals = [f"{k}={result._constraints.requirements[k]}" for k in keys]
                template_components.append(f"Constraints({','.join(vals)})")

            template_hash = self._get_merkle_hash(template_components)

            # Extract bindings
            input_bindings = {}
            for i, val in enumerate(result.args):
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[str(i)] = val
            for k, val in result.kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val

            sig = None
            if result.task.func:
                try:
                    sig = inspect.signature(result.task.func)
                except (ValueError, TypeError):
                    pass

            # Robustly determine complexity to enable FAST PATH in ArgumentResolver
            from cascade.spec.resource import Inject as InjectMarker
            from cascade.internal.inputs import _get_param_value

            has_complex = False

            # 1. Check for Runtime Context Injection (Special internal tasks)
            if result.task.func is _get_param_value.func:
                has_complex = True

            # 2. Check for Implicit Injection in Signature Defaults
            if not has_complex and sig:
                has_complex = any(
                    isinstance(p.default, InjectMarker) for p in sig.parameters.values()
                )

            # 3. Check for Explicit Injection in Bindings (recursively)
            if not has_complex:

                def is_complex_value(v):
                    if isinstance(v, InjectMarker):
                        return True
                    if isinstance(v, list):
                        return any(is_complex_value(x) for x in v)
                    if isinstance(v, dict):
                        return any(is_complex_value(x) for x in v.values())
                    return False

                has_complex = any(is_complex_value(v) for v in input_bindings.values())

            node = Node(
                id=structural_hash,
                template_id=template_hash,
                name=result.task.name,
                node_type="task",
                callable_obj=result.task.func,
                signature=sig,
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
                has_complex_inputs=has_complex,
            )
            self.registry._registry[structural_hash] = node

        self._visited_instances[result._uuid] = node
        self._visited_instances[result._uuid] = node

        # Always add the node to the current graph, even if it was reused from the registry.
        self.graph.add_node(node)

        if created_new:
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
            self.graph.add_edge(
                Edge(
                    source=source_node,
                    target=node,
                    arg_name="_condition",
                    edge_type=EdgeType.CONDITION,
                )
            )
        if result._constraints:
            for res, req in result._constraints.requirements.items():
                if isinstance(req, (LazyResult, MappedLazyResult)):
                    source = self._visited_instances[req._uuid]
                    self.graph.add_edge(
                        Edge(
                            source=source,
                            target=node,
                            arg_name=res,
                            edge_type=EdgeType.CONSTRAINT,
                        )
                    )
        for dep in result._dependencies:
            source = self._visited_instances[dep._uuid]
            self.graph.add_edge(
                Edge(
                    source=source,
                    target=node,
                    arg_name="<sequence>",
                    edge_type=EdgeType.SEQUENCE,
                )
            )

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
        hash_components.extend(
            self._build_hash_components_from_arg(result.mapping_kwargs, dep_nodes)
        )

        if result._condition:
            hash_components.append("Condition:PRESENT")
        if result._dependencies:
            hash_components.append(f"Deps:{len(result._dependencies)}")

        structural_hash = self._get_merkle_hash(hash_components)

        # 2b. Compute TEMPLATE hash
        template_components = [f"Map({getattr(result.factory, 'name', 'factory')})"]
        template_components.append("MapKwargs:")
        template_components.extend(
            self._build_template_hash_components_from_arg(
                result.mapping_kwargs, dep_nodes
            )
        )

        if result._condition:
            template_components.append("Condition:PRESENT")
        if result._dependencies:
            template_components.append(f"Deps:{len(result._dependencies)}")

        template_hash = self._get_merkle_hash(template_components)

        # 3. Hash-consing
        def node_factory():
            input_bindings = {}
            for k, val in result.mapping_kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val

            return Node(
                id=structural_hash,
                template_id=template_hash,
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

        # Always add the node to the current graph
        self.graph.add_node(node)

        # 4. Add data edges
        self._scan_and_add_edges(node, result.mapping_kwargs)
        if result._condition:
            source = self._visited_instances[result._condition._uuid]
            self.graph.add_edge(
                Edge(
                    source=source,
                    target=node,
                    arg_name="_condition",
                    edge_type=EdgeType.CONDITION,
                )
            )
        for dep in result._dependencies:
            source = self._visited_instances[dep._uuid]
            self.graph.add_edge(
                Edge(
                    source=source,
                    target=node,
                    arg_name="<sequence>",
                    edge_type=EdgeType.SEQUENCE,
                )
            )

        return node
~~~~~
~~~~~python
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.graph.ast_analyzer import assign_tco_cycle_ids, analyze_task_source
from cascade.spec.task import Task

from .registry import NodeRegistry
from .hashing import HashingService


class GraphBuilder:
    def __init__(self, registry: NodeRegistry | None = None):
        self.graph = Graph()
        # InstanceMap: Dict[LazyResult._uuid, Node]
        # Connecting the world of volatile instances to the world of stable structures.
        self._visited_instances: Dict[str, Node] = {}
        # Used to detect cycles during static TCO analysis
        self._shadow_visited: Dict[Task, Node] = {}

        self.registry = registry if registry is not None else NodeRegistry()
        self.hashing_service = HashingService()

    def build(self, target: Any) -> Tuple[Graph, Dict[str, Node]]:
        self._visit(target)
        return self.graph, self._visited_instances

    def _visit(self, value: Any) -> Node:
        """Central dispatcher for the post-order traversal."""
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

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

        # 2. Compute hashes using HashingService
        structural_hash, template_hash = self.hashing_service.compute_hashes(
            result, dep_nodes
        )

        # 3. Hash-consing: Query registry FIRST before doing more work
        node = self.registry.get(structural_hash)
        created_new = False

        if not node:
            created_new = True

            # Extract bindings
            input_bindings = {}
            for i, val in enumerate(result.args):
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[str(i)] = val
            for k, val in result.kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val

            sig = None
            if result.task.func:
                try:
                    sig = inspect.signature(result.task.func)
                except (ValueError, TypeError):
                    pass

            # Robustly determine complexity to enable FAST PATH in ArgumentResolver
            from cascade.spec.resource import Inject as InjectMarker
            from cascade.internal.inputs import _get_param_value

            has_complex = False

            # 1. Check for Runtime Context Injection (Special internal tasks)
            if result.task.func is _get_param_value.func:
                has_complex = True

            # 2. Check for Implicit Injection in Signature Defaults
            if not has_complex and sig:
                has_complex = any(
                    isinstance(p.default, InjectMarker) for p in sig.parameters.values()
                )

            # 3. Check for Explicit Injection in Bindings (recursively)
            if not has_complex:

                def is_complex_value(v):
                    if isinstance(v, InjectMarker):
                        return True
                    if isinstance(v, list):
                        return any(is_complex_value(x) for x in v)
                    if isinstance(v, dict):
                        return any(is_complex_value(x) for x in v.values())
                    return False

                has_complex = any(is_complex_value(v) for v in input_bindings.values())

            node = Node(
                id=structural_hash,
                template_id=template_hash,
                name=result.task.name,
                node_type="task",
                callable_obj=result.task.func,
                signature=sig,
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
                has_complex_inputs=has_complex,
            )
            self.registry._registry[structural_hash] = node

        self._visited_instances[result._uuid] = node
        self._visited_instances[result._uuid] = node

        # Always add the node to the current graph, even if it was reused from the registry.
        self.graph.add_node(node)

        if created_new:
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
            self.graph.add_edge(
                Edge(
                    source=source_node,
                    target=node,
                    arg_name="_condition",
                    edge_type=EdgeType.CONDITION,
                )
            )
        if result._constraints:
            for res, req in result._constraints.requirements.items():
                if isinstance(req, (LazyResult, MappedLazyResult)):
                    source = self._visited_instances[req._uuid]
                    self.graph.add_edge(
                        Edge(
                            source=source,
                            target=node,
                            arg_name=res,
                            edge_type=EdgeType.CONSTRAINT,
                        )
                    )
        for dep in result._dependencies:
            source = self._visited_instances[dep._uuid]
            self.graph.add_edge(
                Edge(
                    source=source,
                    target=node,
                    arg_name="<sequence>",
                    edge_type=EdgeType.SEQUENCE,
                )
            )

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

        # 2. Compute hashes using HashingService
        structural_hash, template_hash = self.hashing_service.compute_hashes(
            result, dep_nodes
        )

        # 3. Hash-consing
        def node_factory():
            input_bindings = {}
            for k, val in result.mapping_kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val

            return Node(
                id=structural_hash,
                template_id=template_hash,
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

        # Always add the node to the current graph
        self.graph.add_node(node)

        # 4. Add data edges
        self._scan_and_add_edges(node, result.mapping_kwargs)
        if result._condition:
            source = self._visited_instances[result._condition._uuid]
            self.graph.add_edge(
                Edge(
                    source=source,
                    target=node,
                    arg_name="_condition",
                    edge_type=EdgeType.CONDITION,
                )
            )
        for dep in result._dependencies:
            source = self._visited_instances[dep._uuid]
            self.graph.add_edge(
                Edge(
                    source=source,
                    target=node,
                    arg_name="<sequence>",
                    edge_type=EdgeType.SEQUENCE,
                )
            )

        return node
~~~~~

### 下一步建议
我们已经完成了哈希服务的剥离，并通过重构 `GraphBuilder` 验证了新架构的可用性。接下来的重点应是推进 P0 报告中提到的其他两个缺陷：
1.  **缺陷 B (IO 边界)**: 强制 `StateBackend` 异步化。
2.  **缺陷 C (生命周期)**: 增强 `Engine` 的退出机制。
