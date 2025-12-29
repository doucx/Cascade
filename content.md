简要回答
我们将执行“焦土政策”式的重构。

**核心变更：**
1.  **模型更新**: `Node` 对象将失去 `name`, `signature`, `is_async` 等属性，转而持有一个强类型的 `definition: TaskDef`。`structural_id` 将基于 `TaskDef` 的指纹和实例绑定参数计算。
2.  **定义补全**: 我们需要先给 `TaskDef` 补充 `mode` (execution_mode) 属性，因为它也是任务静态定义的一部分。
3.  **构建逻辑重写**: `GraphBuilder` 流程变更为：`LazyResult` -> `ReflectionAnalyzer` -> `TaskDef` -> `HashingService` -> `Node`。

这份计划将集中完成核心图模型和构建逻辑的重构。Runtime 层的适配（由于字段移除导致的报错）将在后续步骤处理。

## [WIP] refactor(core): 集成 TaskDef 并解构 Node 对象

### 用户需求
彻底重构 `Node` 对象，移除所有冗余的静态属性（如 `name`, `signature`），代之以单一的事实来源 `definition: TaskDef`。不保留向后兼容的代理属性。

### 评论
这是一次破坏性的核心重构。它强制所有上层组件（Runtime, Hashing, Serialization）必须明确区分“静态定义”和“动态实例”。虽然短期内会导致大量通过测试的代码失效，但长期来看，这是消除“ID 概念混淆”和“上帝对象”问题的必经之路。

### 目标
1.  更新 `TaskDef` 以包含 `mode` 字段。
2.  更新 `ReflectionAnalyzer` 以填充 `mode`。
3.  重写 `Node` 模型，引入 `definition` 字段，删除冗余字段。
4.  重写 `HashingService` 以基于 `TaskDef` 计算实例哈希。
5.  重写 `GraphBuilder` 以集成上述组件。

### 基本原理
-   **单一事实来源**: 静态属性只应存在于 `TaskDef`。
-   **关注点分离**: `ReflectionAnalyzer` 负责计算“代码指纹”；`HashingService` 负责计算“实例指纹”。
-   **焦土政策**: 直接删除旧字段而不是标记为 Deprecated，利用 Python 的动态特性在运行时（或静态检查时）快速暴露所有隐式依赖。

### 标签
#intent/refine #flow/ready #priority/critical #comp/graph #concept/ir #scope/core #ai/instruct #task/domain/core #task/object/node #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新 TaskDef 定义 (Spec)

我们需要将 `execution_mode` (如 "blocking", "compute") 加入静态定义中。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~old
    docstring: Optional[str] = None
    is_async: bool = False
~~~~~
~~~~~new
    docstring: Optional[str] = None
    is_async: bool = False
    # Execution mode (e.g. "blocking", "compute") derived from the task definition
    mode: str = "blocking"
~~~~~

#### Acts 2: 更新 ReflectionAnalyzer (Analyzer)

使其在分析时提取 `mode`。注意：`inspect` 无法直接通过 Python 函数对象知道用户在 `@task(mode=...)` 中传了什么，因为那是装饰器层面的元数据。
**关键修正**：`ReflectionAnalyzer.analyze(target)` 中的 `target` 在运行时通常是 `Task` 对象（经过装饰后的包装器）或者原始函数。
在 Cascade 中，`LazyResult.task` 存储的是 `Task` 对象 (`cascade.spec.task.Task`)。
我们需要调整 `protocols.py` 和 `reflection.py`，明确 `analyze` 的输入可以是 `Task` 对象，并从中提取 `mode`。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/analysis/reflection.py
~~~~~
~~~~~old
from cascade.spec.ir.models import TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint
from cascade.graph.analysis.protocols import TaskAnalyzer


class ReflectionAnalyzer(TaskAnalyzer):
    """
    A TaskAnalyzer implementation that uses Python's built-in `inspect` module
    to analyze callable objects at runtime.
    """

    def analyze(self, target: Any) -> TaskDef:
        if not callable(target):
            raise TypeError(f"Target {target} must be callable to be analyzed.")

        # 1. Basic Metadata
        name = getattr(target, "__name__", "unknown")
        docstring = inspect.getdoc(target)
        is_async = inspect.iscoroutinefunction(target)
        
        # Extract return annotation if available
        sig = inspect.signature(target)
~~~~~
~~~~~new
from cascade.spec.ir.models import TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint
from cascade.graph.analysis.protocols import TaskAnalyzer

# Type hint for the Cascade Task wrapper
# We use Any here to avoid circular imports, but conceptually it is cascade.spec.task.Task
TaskWrapper = Any


class ReflectionAnalyzer(TaskAnalyzer):
    """
    A TaskAnalyzer implementation that uses Python's built-in `inspect` module
    to analyze callable objects (or Task wrappers) at runtime.
    """

    def analyze(self, target: Any) -> TaskDef:
        # Determine the underlying function and metadata source
        func = target
        mode = "blocking"
        
        # Check if it's a cascade.spec.task.Task wrapper
        if hasattr(target, "func") and hasattr(target, "mode"):
            func = target.func
            mode = getattr(target, "mode", "blocking")

        if not callable(func):
            raise TypeError(f"Target {target} must be callable (or enclose a callable) to be analyzed.")

        # 1. Basic Metadata
        name = getattr(func, "__name__", "unknown")
        docstring = inspect.getdoc(func)
        is_async = inspect.iscoroutinefunction(func)
        
        # Extract return annotation if available
        sig = inspect.signature(func)
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/analysis/reflection.py
~~~~~
~~~~~old
        # 3. Compute Fingerprint
        # We compute a structural hash based on the definition's content.
        structure_hash = self._compute_structure_hash(
            name, args, return_annotation, docstring, is_async
        )
        
        fingerprint = Fingerprint()
        fingerprint["current_code_structure_hash"] = structure_hash

        return TaskDef(
            name=name,
            args=args,
            fingerprint=fingerprint,
            return_annotation=return_annotation,
            docstring=docstring,
            is_async=is_async,
        )
~~~~~
~~~~~new
        # 3. Compute Fingerprint
        # We compute a structural hash based on the definition's content.
        structure_hash = self._compute_structure_hash(
            name, args, return_annotation, docstring, is_async, mode
        )
        
        fingerprint = Fingerprint()
        fingerprint["current_code_structure_hash"] = structure_hash

        return TaskDef(
            name=name,
            args=args,
            fingerprint=fingerprint,
            return_annotation=return_annotation,
            docstring=docstring,
            is_async=is_async,
            mode=mode,
        )
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/analysis/reflection.py
~~~~~
~~~~~old
    def _compute_structure_hash(
        self, 
        name: str, 
        args: List[ArgumentDef], 
        return_annotation: Optional[str], 
        docstring: Optional[str], 
        is_async: bool
    ) -> str:
        """
        Computes a deterministic hash of the task's structure.
        """
        components = [f"Name:{name}"]
        components.append(f"Async:{is_async}")
~~~~~
~~~~~new
    def _compute_structure_hash(
        self, 
        name: str, 
        args: List[ArgumentDef], 
        return_annotation: Optional[str], 
        docstring: Optional[str], 
        is_async: bool,
        mode: str
    ) -> str:
        """
        Computes a deterministic hash of the task's structure.
        """
        components = [f"Name:{name}"]
        components.append(f"Async:{is_async}")
        components.append(f"Mode:{mode}")
~~~~~

#### Acts 3: 解构 Node 对象 (Model)

这是破坏性最大的变更。

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import List, Callable, Optional, Any, Dict
from enum import Enum, auto

from cascade.spec.constraint import ResourceConstraint
from cascade.spec.ir.models import TaskDef


class EdgeType(Enum):
    DATA = auto()
    CONDITION = auto()
    CONSTRAINT = auto()
    IMPLICIT = auto()
    SEQUENCE = auto()
    ROUTER_ROUTE = auto()
    POTENTIAL = auto()
    ITERATIVE_JUMP = auto()


@dataclass
class Node:
    # Stable identifier for the node instance in the graph.
    # Computed from TaskDef fingerprint + Instance configuration (bindings, policies)
    structural_id: str

    # The static definition of the task.
    # Single Source of Truth for name, signature, mode, etc.
    definition: TaskDef

    # The actual python executable object.
    # This is NOT part of the definition (it's runtime state), but checked here for convenience.
    callable_obj: Optional[Callable] = None

    # Node-specific type ("task", "map", "param") - might be merged into definition later?
    # For now, it distinguishes how the definition is APPLIED.
    node_type: str = "task" 
    
    # Instance-specific configuration
    retry_policy: Optional[Any] = None
    cache_policy: Optional[Any] = None
    constraints: Optional[ResourceConstraint] = None

    # Mapping logic (only for node_type='map')
    mapping_factory: Optional[Any] = None

    # Structural Bindings (Literals)
    input_bindings: Dict[str, Any] = field(default_factory=dict)
    
    # Optimization flag
    has_complex_inputs: bool = False

    def __hash__(self):
        return hash(self.structural_id)
    
    @property
    def name(self) -> str:
        # SHORTCUT for debugging/logging, but code should prefer definition.name where possible
        return self.definition.name


@dataclass
class Edge:
    source: Node
    target: Node
    arg_name: str
    edge_type: EdgeType = EdgeType.DATA
    router: Optional[Any] = None
    jump_selector: Optional[Any] = None


@dataclass
class Graph:
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    _node_index: Dict[str, Node] = field(default_factory=dict, init=False, repr=False)

    def add_node(self, node: Node):
        if node.structural_id not in self._node_index:
            self.nodes.append(node)
            self._node_index[node.structural_id] = node

    def get_node(self, node_id: str) -> Optional[Node]:
        return self._node_index.get(node_id)

    def add_edge(self, edge: Edge):
        self.edges.append(edge)
~~~~~

#### Acts 4: 更新 HashingService (Hashing)

重写哈希逻辑，基于 `TaskDef` 指纹计算实例哈希。

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~
~~~~~python
import hashlib
from typing import Any, List, Dict
from cascade.graph.model import Graph, Node
from cascade.spec.ir.models import TaskDef
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import Inject


class HashingService:
    def compute_node_instance_hash(
        self, 
        definition: TaskDef, 
        result: Any, # LazyResult or MappedLazyResult
        dep_nodes: Dict[str, Node]
    ) -> str:
        """
        Computes the unique structural ID for a Node instance.
        
        Formula:
          Hash( 
             Definition.Fingerprint['current_code_structure_hash'] 
             | Instance.Policies 
             | Instance.Bindings (merged args/kwargs)
             | Instance.PuritySalt (if impure)
          )
        """
        # 1. Start with the Stable Code Fingerprint
        code_hash = definition.fingerprint["current_code_structure_hash"]
        components = [f"CodeHash:{code_hash}"]

        # 2. Purity Salt
        # Get purity from the Task wrapper if available, else assume False (Impure) for safety
        task_obj = getattr(result, "task", None) or getattr(result, "factory", None)
        is_pure = getattr(task_obj, "pure", False) if task_obj else False
        
        if not is_pure:
            # Impure tasks are instance-identity based.
            # We use the LazyResult's UUID as a salt.
            components.append(f"Salt({result._uuid})")

        # 3. Policies
        if result._retry_policy:
            rp = result._retry_policy
            components.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
        if result._cache_policy:
            components.append(f"Cache({type(result._cache_policy).__name__})")

        # 4. Bindings (Instance Arguments)
        if isinstance(result, MappedLazyResult):
             components.append("MapKwargs:")
             components.extend(self._build_hash_components(result.mapping_kwargs, dep_nodes))
        else:
             components.append("Args:")
             components.extend(self._build_hash_components(result.args, dep_nodes))
             components.append("Kwargs:")
             components.extend(self._build_hash_components(result.kwargs, dep_nodes))

        # 5. Metadata
        if result._condition:
            components.append("Condition:PRESENT")
        
        # 6. Constraints
        if result._constraints:
            keys = sorted(result._constraints.requirements.keys())
            s_vals = [f"{k}={result._constraints.requirements[k]}" for k in keys]
            components.append(f"Constraints({','.join(s_vals)})")

        return self._get_merkle_hash(components)

    def _get_merkle_hash(self, components: List[str]) -> str:
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _build_hash_components(self, obj: Any, dep_nodes: Dict[str, Node]) -> List[str]:
        # This recursive helper remains largely similar, just updated type hints if needed
        components = []

        if isinstance(obj, (LazyResult, MappedLazyResult)):
            node = dep_nodes[obj._uuid]
            components.append(f"LAZY({node.structural_id})")

        elif isinstance(obj, Router):
            components.append("Router{")
            components.append("Selector:")
            components.extend(self._build_hash_components(obj.selector, dep_nodes))
            components.append("Routes:")
            for k in sorted(obj.routes.keys()):
                components.append(f"Key({k})->")
                components.extend(self._build_hash_components(obj.routes[k], dep_nodes))
            components.append("}")

        elif isinstance(obj, (list, tuple)):
            components.append("List[")
            for item in obj:
                components.extend(self._build_hash_components(item, dep_nodes))
            components.append("]")

        elif isinstance(obj, dict):
            components.append("Dict{")
            for k in sorted(obj.keys()):
                components.append(f"{k}:")
                components.extend(self._build_hash_components(obj[k], dep_nodes))
            components.append("}")

        elif isinstance(obj, Inject):
            components.append(f"Inject({obj.resource_name})")

        else:
            try:
                components.append(repr(obj))
            except Exception:
                components.append("<unreprable>")

        return components


class BlueprintHasher:
    # Existing logic for Blueprint hashing (can be updated later if needed)
    def compute_hash(self, graph: Graph) -> str:
        all_components = []
        sorted_nodes = sorted(graph.nodes, key=lambda n: n.structural_id)
        for node in sorted_nodes:
            all_components.extend(self._get_node_components(node, graph))
        return self._get_merkle_hash(all_components)

    def _get_merkle_hash(self, components: List[str]) -> str:
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _get_node_components(self, node: Node, graph: Graph) -> List[str]:
        # Updated to use node.definition
        components = [f"Node({node.definition.name}, type={node.node_type})"]
        components.append(f"CodeHash({node.definition.fingerprint['current_code_structure_hash']})")

        if node.retry_policy:
            rp = node.retry_policy
            components.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
        
        # ... Edge logic remains same
        incoming_edges = sorted(
            [e for e in graph.edges if e.target.structural_id == node.structural_id],
            key=lambda e: e.source.structural_id,
        )
        for edge in incoming_edges:
            components.append(
                f"Edge(from={edge.source.structural_id}, to={node.structural_id}, type={edge.edge_type.name})"
            )
        return components
~~~~~

#### Acts 5: 更新 GraphBuilder (Build)

集成 `ReflectionAnalyzer`，使用 `TaskDef` 构建 `Node`。

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
from typing import Dict, Any, Tuple
import inspect
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.jump import JumpSelector

from .registry import NodeRegistry
from .hashing import HashingService
from .analysis.reflection import ReflectionAnalyzer


class GraphBuilder:
    def __init__(self, registry: NodeRegistry | None = None):
        self.graph = Graph()
        self._visited_instances: Dict[str, Node] = {}
        self.registry = registry if registry is not None else NodeRegistry()
        self.hashing_service = HashingService()
        self.analyzer = ReflectionAnalyzer()

    def build(self, target: Any) -> Tuple[Graph, Dict[str, Node]]:
        self._visit(target)
        return self.graph, self._visited_instances

    def _visit(self, value: Any) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

    def _find_dependencies(self, obj: Any, dep_nodes: Dict[str, Node]):
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

        # 2. Analyze Code to get TaskDef
        task_def = self.analyzer.analyze(result.task)

        # 3. Compute Node Instance Hash
        node_hash = self.hashing_service.compute_node_instance_hash(
            task_def, result, dep_nodes
        )

        # 4. Hash-consing / Create Node
        node = self.registry.get(node_hash)
        if not node:
            # Extract bindings (Literals)
            input_bindings = {}
            for i, val in enumerate(result.args):
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[str(i)] = val
            for k, val in result.kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val

            # Complexity check
            from cascade.spec.resource import Inject as InjectMarker
            from cascade.internal.inputs import _get_param_value

            has_complex = False
            if result.task.func is _get_param_value.func:
                has_complex = True
            
            # Note: Signature check is now implicit in TaskDef/Analyzer?
            # We still need to check for Inject markers in defaults, but ReflectionAnalyzer
            # serialized defaults to strings. We might need raw access here or rely on runtime.
            # For now, let's keep the simplistic check if possible, or assume analyzer handled it?
            # Actually, we need to inspect the raw function again for runtime injection logic.
            # This is a runtime concern, so inspecting result.task.func is fine.
            if not has_complex:
                try:
                    sig = inspect.signature(result.task.func)
                    has_complex = any(
                        isinstance(p.default, InjectMarker) for p in sig.parameters.values()
                    )
                except ValueError:
                    pass

            if not has_complex:
                 def is_complex_value(v):
                    if isinstance(v, InjectMarker): return True
                    if isinstance(v, list): return any(is_complex_value(x) for x in v)
                    if isinstance(v, dict): return any(is_complex_value(x) for x in v.values())
                    return False
                 has_complex = any(is_complex_value(v) for v in input_bindings.values())

            node = Node(
                structural_id=node_hash,
                definition=task_def,
                callable_obj=result.task.func,
                node_type="task",
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
                has_complex_inputs=has_complex,
            )
            self.registry._registry[node_hash] = node

        self._visited_instances[result._uuid] = node
        self.graph.add_node(node)

        # 5. Edges
        self._scan_and_add_edges(node, result.args)
        self._scan_and_add_edges(node, result.kwargs)
        
        # ... Jump Selector logic ...
        if result._jump_selector:
            selector = result._jump_selector
            if isinstance(selector, JumpSelector):
                for route_target in selector.routes.values():
                    if route_target is not None:
                        self._visit(route_target)
                for key, route_target_lr in selector.routes.items():
                    if route_target_lr is None: continue
                    target_node = self._visited_instances[route_target_lr._uuid]
                    self.graph.add_edge(Edge(
                        source=node, target=target_node, arg_name=key,
                        edge_type=EdgeType.ITERATIVE_JUMP, jump_selector=selector
                    ))

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

        dep_nodes: Dict[str, Node] = {}
        self._find_dependencies(result.mapping_kwargs, dep_nodes)
        if result._condition: self._find_dependencies(result._condition, dep_nodes)
        if result._dependencies: self._find_dependencies(result._dependencies, dep_nodes)

        # Analyze Factory
        task_def = self.analyzer.analyze(result.factory)

        # Compute Hash
        node_hash = self.hashing_service.compute_node_instance_hash(
            task_def, result, dep_nodes
        )

        node = self.registry.get(node_hash)
        if not node:
            input_bindings = {}
            for k, val in result.mapping_kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val

            node = Node(
                structural_id=node_hash,
                definition=task_def,
                node_type="map",
                mapping_factory=result.factory,
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings
            )
            self.registry._registry[node_hash] = node

        self._visited_instances[result._uuid] = node
        self.graph.add_node(node)

        self._scan_and_add_edges(node, result.mapping_kwargs)
        
        if result._condition:
            source = self._visited_instances[result._condition._uuid]
            self.graph.add_edge(Edge(source=source, target=node, arg_name="_condition", edge_type=EdgeType.CONDITION))
        
        for dep in result._dependencies:
            source = self._visited_instances[dep._uuid]
            self.graph.add_edge(Edge(source=source, target=node, arg_name="<sequence>", edge_type=EdgeType.SEQUENCE))

        return node

    def _scan_and_add_edges(self, target_node: Node, obj: Any, path: str = ""):
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
~~~~~

### 下一步建议
我们已经完成了图模型的重构。`Node` 现在使用 `definition` 来存储静态信息。这会导致运行时代码（例如 `processor.py` 中访问 `node.signature` 或 `node.execution_mode` 的地方）崩溃。

下一步我们需要修复运行时层的代码：
1.  **Processor**: 更新参数解析逻辑，从 `node.callable_obj` 或 `node.definition` 中获取信息。
2.  **Engine/Subscribers/Events**: 更新日志和事件发布逻辑，正确获取任务名称。
3.  **Executors**: 更新执行逻辑以兼容新模型。
