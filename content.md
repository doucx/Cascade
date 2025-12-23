为了实现路线图 2.3 的目标，我们将引入“参数归一化”机制。这将通过在 `Node` 对象中引入一个忽略具体字面量值的 `template_id` 来实现。

 主要变更点

1.  **数据模型升级**: 修改 `Node` 定义，增加 `template_id` 字段。该字段将作为“结构哈希”，用于识别在拓扑上等价但参数不同的计算图。
2.  **构建逻辑增强**: 在 `GraphBuilder` 中实现 `template_id` 的计算逻辑。计算时将把 `LazyResult` 的参数中的字面量替换为占位符（`?`），从而实现归一化。

 预期效果

对于 `simple_countdown(10)` 和 `simple_countdown(9)`：
-   它们将生成不同的 `Node` 对象（`id` 不同，`input_bindings` 不同），保证了执行时的正确性。
-   但它们将拥有相同的 `template_id`。这将为下一步在 `GraphExecutionStrategy` 中实现基于模板索引的 Plan 缓存铺平道路。

## [WIP] feat(core): 引入 `Node.template_id` 实现结构归一化

### 错误分析
不涉及错误修复。

### 用户需求
为了优化 TCO 循环和重复子图的性能，系统需要一种机制来识别“结构相同但数据不同”的任务，从而复用已生成的执行计划（Execution Plan）。

### 评论
这是路线图 v3.2 第二阶段的关键步骤。通过引入 `template_id`，我们将计算图的“骨架”（结构）与“血肉”（数据）在哈希层面进行了分离。这是实现 Hashlife 风格缓存和高性能 JIT 的先决条件。

### 目标
1.  在 `Node` 模型中添加 `template_id` 字段。
2.  在 `GraphBuilder` 中实现忽略字面量值的模板哈希计算逻辑。
3.  确保 `LazyResult`、`MappedLazyResult` 和 `Router` 都能正确生成模板哈希。

### 基本原理
目前的 `Node.id` 包含了所有参数的哈希值，导致 `f(10)` 和 `f(9)` 被视为完全不同的实体。通过增加一个将字面量视为占位符的 `template_id`，我们可以捕捉到这两者在计算结构上的同构性。后续的 `GraphExecutionStrategy` 将利用这个 `template_id` 作为缓存键，来复用拓扑排序的结果。

### 标签
#intent/build #flow/draft #priority/high #comp/engine #concept/history #scope/core #ai/instruct #task/domain/core #task/object/graph-builder #task/action/normalization #task/state/begin

---

### Script

#### Acts 1: 更新 `Node` 模型定义

我们需要同时更新 `cascade-spec` 和 `cascade-graph` 中的 `model.py`，为 `Node` 类添加 `template_id` 字段。为了向后兼容和简化初始化，我们将其设为可选（但在 Builder 中会强制赋值）。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/graph/model.py
~~~~~
~~~~~python
    id: str
    name: str
    is_shadow: bool = False  # True if this node is for static analysis only
    tco_cycle_id: Optional[str] = None  # ID of the TCO cycle this node belongs to
~~~~~
~~~~~python
    id: str
    name: str
    template_id: str = ""  # Structural hash (ignoring literals)
    is_shadow: bool = False  # True if this node is for static analysis only
    tco_cycle_id: Optional[str] = None  # ID of the TCO cycle this node belongs to
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python
    id: str
    name: str
    is_shadow: bool = False  # True if this node is for static analysis only
    tco_cycle_id: Optional[str] = None  # ID of the TCO cycle this node belongs to
~~~~~
~~~~~python
    id: str
    name: str
    template_id: str = ""  # Structural hash (ignoring literals)
    is_shadow: bool = False  # True if this node is for static analysis only
    tco_cycle_id: Optional[str] = None  # ID of the TCO cycle this node belongs to
~~~~~

#### Acts 2: 在 `GraphBuilder` 中实现模板哈希计算

这是核心逻辑变更。我们将添加 `_build_template_hash_components` 方法，并在节点构建过程中调用它。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
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

    def _find_dependencies(self, obj: Any, dep_nodes: Dict[str, Node]):
~~~~~
~~~~~python
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
~~~~~

#### Acts 3: 在 `_visit_lazy_result` 中集成模板哈希

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
        structural_hash = self._get_merkle_hash(hash_components)

        # 3. Hash-consing: intern the Node object
        def node_factory():
            input_bindings = {}

            def process_arg(key: str, val: Any):
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    # Store literal value directly
                    input_bindings[key] = val

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
~~~~~
~~~~~python
        structural_hash = self._get_merkle_hash(hash_components)

        # 2b. Compute TEMPLATE hash (Normalization)
        template_components = [f"Task({getattr(result.task, 'name', 'unknown')})"]
        # Policies and Constraints are considered STRUCTURAL
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
            # We treat constraint keys as structural, values as literals?
            # For safety, let's treat constraints as fully structural for now.
            # If f(mem=4) and f(mem=2), they are different templates.
            vals = [
                f"{k}={result._constraints.requirements[k]}" for k in keys
            ]  # This includes values in hash
            template_components.append(f"Constraints({','.join(vals)})")

        template_hash = self._get_merkle_hash(template_components)

        # 3. Hash-consing: intern the Node object
        def node_factory():
            input_bindings = {}

            def process_arg(key: str, val: Any):
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    # Store literal value directly
                    input_bindings[key] = val

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
            )
~~~~~

#### Acts 4: 在 `_visit_mapped_result` 中集成模板哈希

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
        structural_hash = self._get_merkle_hash(hash_components)

        # 3. Hash-consing
        def node_factory():
            input_bindings = {}
            for k, val in result.mapping_kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val

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
~~~~~
~~~~~python
        structural_hash = self._get_merkle_hash(hash_components)

        # 2b. Compute TEMPLATE hash
        template_components = [
            f"Map({getattr(result.factory, 'name', 'factory')})"
        ]
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
~~~~~

#### Acts 5: 更新序列化逻辑以支持 `template_id`

为了保持数据一致性，序列化工具也需要保存和恢复 `template_id`。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~python
def _node_to_dict(node: Node) -> Dict[str, Any]:
    data = {
        "id": node.id,
        "name": node.name,
        "node_type": node.node_type,
        # input_bindings now contains JSON-serializable literals directly.
        "input_bindings": node.input_bindings,
    }
~~~~~
~~~~~python
def _node_to_dict(node: Node) -> Dict[str, Any]:
    data = {
        "id": node.id,
        "template_id": node.template_id,
        "name": node.name,
        "node_type": node.node_type,
        # input_bindings now contains JSON-serializable literals directly.
        "input_bindings": node.input_bindings,
    }
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~python
    node = Node(
        id=data["id"],
        name=data["name"],
        node_type=data["node_type"],
        callable_obj=_load_func_from_path(data.get("callable")),
~~~~~
~~~~~python
    node = Node(
        id=data["id"],
        template_id=data.get("template_id", ""),
        name=data["name"],
        node_type=data["node_type"],
        callable_obj=_load_func_from_path(data.get("callable")),
~~~~~

### 下一步建议
实现 `GraphExecutionStrategy` 中的缓存逻辑升级，利用 `template_id` 和基于索引的 Plan 缓存来替代目前的基于 ID 的缓存。这将使 `f(10)` 和 `f(9)` 能够共享同一个 Plan 模板。
