简要回答：
好的，我们将开始“通用图结构缓存”的第一阶段。本阶段的核心任务是引入“基于遍历顺序的结构化 ID (Traversal-based Structural ID)”，以实现 Graph 模板与动态数据的解耦。我们将重构 `StructuralHasher` 和 `GraphBuilder`，使它们采用严格一致的 DFS 遍历顺序，并利用该顺序生成的 ID 来精确映射“骨架（Node）”与“血肉（Literals）”。

## [WIP] feat: 实现基于结构化 ID 的图模板水合机制

### 用户需求
为了实现任意复杂度的图结构缓存，系统需要能够将一个 `LazyResult` 树拆解为“静态结构模板”和“动态数据字典”。具体需求包括：
1.  在 `Node` 模型中增加 `structural_id` 字段。
2.  重构 `StructuralHasher`，使其支持 DAG 遍历，并生成 `{structural_id: literal_inputs}` 形式的数据映射。
3.  同步更新 `GraphBuilder`，确保其遍历顺序与 Hasher 一致，并为生成的 Node 分配相同的 `structural_id`。
4.  在 `GraphExecutionStrategy` 中实现基于 `structural_id` 的 O(1) 数据注入（水合）逻辑。

### 评论
这是一个具有深远影响的架构变更。通过引入确定性的 `structural_id`，我们实际上为 Cascade 引入了一套内部的“内存寻址”机制，这不仅解决了缓存问题，也为未来的分布式图传输和状态同步奠定了基础。选择“基于遍历顺序”的生成策略是明智的，它避免了复杂的路径计算，且天然适应 DAG 结构。

### 目标
1.  修改 `cascade-spec`，为 `Node` 添加 `structural_id`。
2.  重写 `StructuralHasher`，实现 DAG 感知的遍历和 ID 生成。
3.  更新 `GraphBuilder` 以匹配新的 ID 生成逻辑。
4.  在 `GraphExecutionStrategy` 中实现 `_hydrate_graph` 方法。

### 基本原理
目前的 `StructuralHasher` 和 `GraphBuilder` 虽然都执行遍历，但缺乏统一的坐标系。通过强制两者遵循相同的 DFS 顺序（Pre-order），我们可以隐式地建立起 `LazyResult` 实例与 `Graph Node` 之间的一一对应关系。这个顺序索引（0, 1, 2...）即为 `structural_id`，它是连接模板与数据的唯一桥梁。

### 标签
#intent/architect #flow/draft #priority/high #comp/engine #comp/graph #concept/state #scope/core #ai/instruct #task/domain/core #task/object/graph-cache #task/action/template-hydration #task/state/begin

---

### Script

#### Acts 1: 更新 Node 模型定义

我们在 `Node` 类中添加 `structural_id` 字段。这将用于存储该节点在图遍历中的规范化索引。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/graph/model.py
~~~~~
~~~~~python
    id: str
    name: str
    is_shadow: bool = False  # True if this node is for static analysis only
    tco_cycle_id: Optional[str] = None  # ID of the TCO cycle this node belongs to

    # Core spec
    node_type: str = "task"  # "task", "param", or "map"
~~~~~
~~~~~python
    id: str
    name: str
    is_shadow: bool = False  # True if this node is for static analysis only
    tco_cycle_id: Optional[str] = None  # ID of the TCO cycle this node belongs to
    structural_id: Optional[int] = None  # Canonical ID based on traversal order

    # Core spec
    node_type: str = "task"  # "task", "param", or "map"
~~~~~

#### Acts 2: 重构 StructuralHasher

我们将 `StructuralHasher` 重写为支持 DAG 遍历。它将维护一个 `visited` 字典来处理共享引用，并使用计数器生成 `structural_id`。返回的 literals 将不再使用冗长的路径字符串，而是使用紧凑的 `{structural_id: inputs}` 映射。

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~
~~~~~python
from typing import Any, Dict, Tuple, List, Set
import hashlib
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import Inject


class StructuralHasher:
    """
    Generates a stable structural hash for a LazyResult tree and extracts
    literal values that fill the structure.
    
    It uses a deterministic DFS traversal to assign a 'structural_id' to each
    unique LazyResult node. The returned literals are keyed by this ID.
    """

    def __init__(self):
        # Map of {structural_id: {arg_name: value}}
        self.literals: Dict[int, Dict[str, Any]] = {}
        self._hash_components: List[str] = []
        
        # DAG support: track visited objects by their id()
        # Maps id(obj) -> structural_id
        self._visited: Dict[int, int] = {}
        self._counter = 0

    def hash(self, target: Any) -> Tuple[str, Dict[int, Dict[str, Any]]]:
        self._visit(target)

        # Create a deterministic hash string
        fingerprint = "|".join(self._hash_components)
        hash_val = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

        return hash_val, self.literals

    def _get_next_id(self) -> int:
        sid = self._counter
        self._counter += 1
        return sid

    def _visit(self, obj: Any, role: str = ""):
        # If this is a complex node (LazyResult/Router), check DAG cache
        if isinstance(obj, (LazyResult, MappedLazyResult, Router)):
            if id(obj) in self._visited:
                # Already visited, record reference to its ID to capture topology
                sid = self._visited[id(obj)]
                self._hash_components.append(f"Ref({sid})")
                return
            
            # New node: assign ID
            sid = self._get_next_id()
            self._visited[id(obj)] = sid
            self._hash_components.append(f"Node({sid}):{role}")
            
            # Initialize literal storage for this node
            self.literals[sid] = {}
            
            # Dispatch based on type
            if isinstance(obj, LazyResult):
                self._visit_lazy(obj, sid)
            elif isinstance(obj, MappedLazyResult):
                self._visit_mapped(obj, sid)
            elif isinstance(obj, Router):
                self._visit_router(obj, sid)
            return

        # Container types pass-through (recursion)
        if isinstance(obj, (list, tuple)):
            self._hash_components.append("List[")
            for i, item in enumerate(obj):
                self._visit(item)
            self._hash_components.append("]")
        elif isinstance(obj, dict):
            self._hash_components.append("Dict{")
            for k in sorted(obj.keys()):
                self._hash_components.append(f"{k}:")
                self._visit(obj[k])
            self._hash_components.append("}")
        elif isinstance(obj, Inject):
            self._hash_components.append(f"Inject({obj.resource_name})")
        else:
            # It's a literal value.
            # We assume it belongs to the *current* context.
            # However, _visit is recursive. To map literals to the correct Node,
            # we need context. But wait, `literals` dict is populated inside 
            # _visit_lazy/_visit_mapped which know their `sid`.
            # If we encounter a literal here, it means it's nested in a list/dict 
            # structure *outside* of a Node context? 
            # Actually, _visit_lazy calls _scan_args which handles literals.
            # This generic _visit is mostly for structural containers.
            
            # If we reach here with a primitive, it's structure-level data (like list content)
            # but usually args are handled specifically.
            self._hash_components.append("LIT")
            # We don't save it to self.literals here because we don't know the 'key'.
            # The caller (_scan_args) handles the saving.
            pass

    def _visit_lazy(self, lr: LazyResult, sid: int):
        # Identification
        task_name = getattr(lr.task, "name", "unknown")
        self._hash_components.append(f"Task({task_name})")

        # Policies
        if lr._retry_policy:
            rp = lr._retry_policy
            self._hash_components.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
        if lr._cache_policy:
            self._hash_components.append(f"Cache({type(lr._cache_policy).__name__})")

        # Args
        for i, arg in enumerate(lr.args):
            self._scan_arg(sid, str(i), arg)

        # Kwargs
        for k in sorted(lr.kwargs.keys()):
            self._scan_arg(sid, k, lr.kwargs[k])

        # Condition
        if lr._condition:
            self._hash_components.append("Condition:")
            self._visit(lr._condition)

        if lr._dependencies:
            self._hash_components.append("Deps:")
            for dep in lr._dependencies:
                self._visit(dep)

    def _visit_mapped(self, mlr: MappedLazyResult, sid: int):
        factory_name = getattr(mlr.factory, "name", "unknown")
        self._hash_components.append(f"Map({factory_name})")

        # Mapping Kwargs
        for k in sorted(mlr.mapping_kwargs.keys()):
            self._scan_arg(sid, k, mlr.mapping_kwargs[k])

        if mlr._condition:
            self._hash_components.append("Condition:")
            self._visit(mlr._condition)

        if mlr._dependencies:
            self._hash_components.append("Deps:")
            for dep in mlr._dependencies:
                self._visit(dep)

    def _visit_router(self, router: Router, sid: int):
        self._hash_components.append("Router")
        self._hash_components.append("Selector:")
        self._visit(router.selector)

        self._hash_components.append("Routes:")
        for k in sorted(router.routes.keys()):
            self._hash_components.append(f"Key({k})->")
            self._visit(router.routes[k])

    def _scan_arg(self, sid: int, key: str, value: Any):
        """Helper to process an argument: either record it as literal or visit it as structure."""
        if isinstance(value, (LazyResult, MappedLazyResult, Router)):
            self._visit(value)
        elif isinstance(value, (list, tuple, dict)):
            # For containers, we must recurse to check for nested LazyResults.
            # But the container itself is also "literal structure". 
            # This is tricky. Simplified approach:
            # We only treat TOP-LEVEL primitives as literals for now in this version?
            # Or we recurse? 
            # Existing Hash logic mixed structure and data. 
            # Here we assume: if it contains LazyResult, it's structure. If not, it's literal.
            # For this phase, let's keep it simple: We treat containers as structure in Hash,
            # but we also need to extract the values if they are literals.
            
            # Let's delegate to _visit which handles recursion.
            # But how to capture the value if it's purely literal?
            # We record it in literals[sid][key] = value, BUT use a placeholder in hash?
            
            # Optimization: If the value is "simple" (JSON serializable + no LazyResult),
            # we treat it as a Literal.
            if self._is_pure_literal(value):
                self._hash_components.append("LIT")
                self.literals[sid][key] = value
            else:
                # It's mixed. We recurse.
                # This means the list/dict structure becomes part of the hash graph.
                self._visit(value)
        else:
            # Primitive Literal
            self._hash_components.append("LIT")
            self.literals[sid][key] = value

    def _is_pure_literal(self, obj: Any) -> bool:
        """Deep check if obj contains any Lazy types."""
        if isinstance(obj, (LazyResult, MappedLazyResult, Router)):
            return False
        if isinstance(obj, (list, tuple)):
            return all(self._is_pure_literal(x) for x in obj)
        if isinstance(obj, dict):
            return all(self._is_pure_literal(v) for v in obj.values())
        return True
~~~~~

#### Acts 3: 更新 GraphBuilder

我们更新 `GraphBuilder`，使其使用与 `StructuralHasher` 相同的 ID 分配逻辑（基于 `id()` 的去重和自增计数器）。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
class GraphBuilder:
    def __init__(self):
        self.graph = Graph()
        self._visited: Dict[str, Node] = {}
        # Used to detect cycles during shadow node expansion
        self._shadow_visited: Dict[Task, Node] = {}

    def build(self, target: LazyResult) -> Graph:
        self._visit(target)
        return self.graph

    def _visit(self, value: Any, scan_for_tco: bool = True) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value, scan_for_tco)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

    def _visit_lazy_result(self, result: LazyResult, scan_for_tco: bool = True) -> Node:
        if result._uuid in self._visited:
            return self._visited[result._uuid]
~~~~~
~~~~~python
class GraphBuilder:
    def __init__(self):
        self.graph = Graph()
        self._visited: Dict[str, Node] = {}
        # Used to detect cycles during shadow node expansion
        self._shadow_visited: Dict[Task, Node] = {}
        
        # Structural ID tracking (must match StructuralHasher logic)
        self._structural_counter = 0
        # Map LazyResult UUID -> structural_id to handle DAG shared references
        self._structural_map: Dict[str, int] = {}

    def build(self, target: LazyResult) -> Graph:
        self._visit(target)
        return self.graph
    
    def _get_structural_id(self, uuid: str) -> int:
        if uuid not in self._structural_map:
            self._structural_map[uuid] = self._structural_counter
            self._structural_counter += 1
        return self._structural_map[uuid]

    def _visit(self, value: Any, scan_for_tco: bool = True) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value, scan_for_tco)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

    def _visit_lazy_result(self, result: LazyResult, scan_for_tco: bool = True) -> Node:
        # Assign structural ID *before* checking visited to ensure counter increments correctly
        # for new nodes, or retrieves existing ID for visited ones.
        # Note: Hasher increments only on first visit. We do same here via _get_structural_id.
        sid = self._get_structural_id(result._uuid)

        if result._uuid in self._visited:
            return self._visited[result._uuid]
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
        node = Node(
            id=result._uuid,
            name=result.task.name,
            node_type="task",
            callable_obj=result.task.func,
            signature=sig,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
            literal_inputs=literal_inputs,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node
~~~~~
~~~~~python
        node = Node(
            id=result._uuid,
            name=result.task.name,
            node_type="task",
            callable_obj=result.task.func,
            signature=sig,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
            literal_inputs=literal_inputs,
            structural_id=sid,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
    def _visit_mapped_result(self, result: MappedLazyResult) -> Node:
        if result._uuid in self._visited:
            return self._visited[result._uuid]

        node = Node(
            id=result._uuid,
            name=f"map({getattr(result.factory, 'name', 'factory')})",
            node_type="map",
            mapping_factory=result.factory,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
            literal_inputs=result.mapping_kwargs,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node
~~~~~
~~~~~python
    def _visit_mapped_result(self, result: MappedLazyResult) -> Node:
        sid = self._get_structural_id(result._uuid)

        if result._uuid in self._visited:
            return self._visited[result._uuid]

        node = Node(
            id=result._uuid,
            name=f"map({getattr(result.factory, 'name', 'factory')})",
            node_type="map",
            mapping_factory=result.factory,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
            literal_inputs=result.mapping_kwargs,
            structural_id=sid,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node
~~~~~

#### Acts 4: 实现数据注入 (Hydration)

最后，我们在 `GraphExecutionStrategy` 中实现 `_update_graph_literals` 方法，使其利用 `structural_id` 将 Hasher 提取的 literals 注入回 Graph。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
    def _update_graph_literals(
        self, graph: Graph, target: Any, literals: Dict[str, Any]
    ):
        # ... logic moved from Engine ...
        if graph.nodes:
            # FIX: Previously used nodes[-1], which became incorrect when shadow nodes
            # were appended to the end of the list by static analysis.
            # GraphBuilder uses a top-down approach (pre-order traversal), so the
            # root target node is always the FIRST node added to the graph.
            target_node = graph.nodes[0]
            target_node.id = target._uuid
            if hasattr(target, "args") and hasattr(target, "kwargs"):
                target_node.literal_inputs = {
                    str(i): v for i, v in enumerate(target.args)
                }
                target_node.literal_inputs.update(target.kwargs)
~~~~~
~~~~~python
    def _update_graph_literals(
        self, graph: Graph, target: Any, literals: Dict[int, Dict[str, Any]]
    ):
        """
        Hydrates a template graph with new literal values.
        Matches nodes by their 'structural_id'.
        """
        # Create a fast lookup for graph nodes by structural_id
        # We assume the graph structure is static, so we could cache this map on the graph object
        # but for now we build it on the fly (O(N)).
        nodes_by_sid = {n.structural_id: n for n in graph.nodes if n.structural_id is not None}

        # The 'target' passed here is the root of the NEW LazyResult tree.
        # We need to assign its UUID to the root node of the graph (which has structural_id 0).
        # This ensures that subsequent lookups for the target result succeed.
        if 0 in nodes_by_sid:
            root_node = nodes_by_sid[0]
            root_node.id = target._uuid
        
        # Inject literals
        for sid, inputs in literals.items():
            if sid in nodes_by_sid:
                node = nodes_by_sid[sid]
                # Update in-place. Note: this modifies the graph object!
                # Since we are reusing the graph instance from cache, this assumes
                # single-threaded execution or that we copy the graph before hydration.
                # Given Python's GIL and current architecture, modifying the cached graph
                # effectively resets it for the current run. 
                # TODO: If we move to concurrent graph usage, we must deepcopy the graph first.
                node.literal_inputs = inputs.copy()
~~~~~

### 下一步建议
我们已经完成了核心机制的改造。接下来的工作应集中在：
1.  **测试验证**: 编写单元测试验证 `StructuralHasher` 和 `GraphBuilder` 对于相同的 `LazyResult` 结构是否生成完全一致的 ID 序列。
2.  **集成测试**: 验证 `hydrate_graph` 是否能正确地将参数注入到复用的图模板中，并成功执行。
3.  **并发安全性**: 当前的实现直接修改了缓存中的 `Graph` 对象。如果未来支持多线程/异步并发使用同一个模板，需要在 `hydrate` 前执行 `graph.copy()`。这是下一个优化点。
