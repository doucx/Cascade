简要回答
通过分析 `heavy` 路径的 Profile 数据，我发现了两个关键的性能“出血点”：
1.  **闭包创建开销 (Closure Overhead)**: 在 `build_graph` 内部，我们每访问一个节点都会创建一个复杂的 `node_factory` 闭包。在 `heavy` 路径的 10 节点长链中，这意味着每秒创建数万个闭包，即使节点最终是从 Registry 中复用的。
2.  **参数解析仪式 (Argument Resolution Ceremony)**: `ArgumentResolver.resolve` 占据了总耗时的很大比例（`simple` 路径中约 25%）。它在每轮循环中都重复进行 `_resolve_structure`（递归检查）、`inspect.bind_partial` 和 `Inject` 检查，即使该节点没有任何资源注入。

我将生成一个优化计划，通过“惰性闭包”和“解析路径预判”来解决这些问题。

## [WIP] perf: 实施“惰性构建”与“解析旁路”以消除 TCO 性能回归

### 评论
Profile 数据揭示了 Python 动态特性的成本。
在 `heavy` 路径中，`_visit_lazy_result` 的累积耗时高达 1.6s，其中大部分是在做 Registry 命中前的准备工作。通过将这些工作移入 Registry 缺失的分支，我们可以大幅提升慢速路径的效率。
在 `simple` 路径中，我们将为 `Node` 引入一个 `has_complex_inputs` 标志。如果节点只包含字面量且没有 `Inject` 需求，我们将直接进行字典合并，绕过复杂的解析器逻辑。

### 目标
1.  **优化 `GraphBuilder`**: 仅在 Registry 未命中时才计算 `input_bindings` 和创建 `Node` 对象。
2.  **优化 `ArgumentResolver`**: 为简单节点提供快速解析路径。
3.  **优化 `Node` 模型**: 在构建时预判其解析复杂性。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #comp/graph #scope/core #ai/instruct #task/domain/core #task/object/tco-fast-path #task/action/overhead-reduction #task/state/continue

---

### Script

#### Acts 1: 优化 `GraphBuilder` 以减少冗余计算
我们将修改 `_visit_lazy_result`，使其先查询 Registry。只有在需要创建新节点时，才执行耗时的属性提取。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
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

        node, created_new = self.registry.get_or_create(structural_hash, node_factory)
~~~~~
~~~~~python
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
                template_components.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
            if result._cache_policy:
                template_components.append(f"Cache({type(result._cache_policy).__name__})")

            template_components.append("Args:")
            template_components.extend(self._build_template_hash_components_from_arg(result.args, dep_nodes))
            template_components.append("Kwargs:")
            template_components.extend(self._build_template_hash_components_from_arg(result.kwargs, dep_nodes))

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
            )
            self.registry._registry[structural_hash] = node

        self._visited_instances[result._uuid] = node
~~~~~

#### Acts 2: 增强 `Node` 模型以支持快速解析路径

~~~~~act
patch_file
packages/cascade-spec/src/cascade/graph/model.py
~~~~~
~~~~~python
    # Pre-resolved literal inputs for the task
    literal_inputs: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
~~~~~
~~~~~python
    # Pre-resolved literal inputs for the task
    literal_inputs: Dict[str, Any] = field(default_factory=dict)

    # Optimization: Flag indicating if the node requires complex resolution 
    # (e.g., has Inject markers or complex nested structures in bindings)
    has_complex_inputs: bool = False

    def __hash__(self):
~~~~~

#### Acts 3: 在 `GraphBuilder` 中预计算 `has_complex_inputs`

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
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
            )
~~~~~
~~~~~python
            # Check for complex resolution needs
            has_complex = False
            if sig:
                has_complex = any(isinstance(p.default, Inject) for p in sig.parameters.values())
            
            if not has_complex:
                # Check for complex structures in literals
                from cascade.spec.resource import Inject as InjectMarker
                def is_complex(v):
                    if isinstance(v, InjectMarker): return True
                    if isinstance(v, list): return any(is_complex(x) for x in v)
                    if isinstance(v, dict): return any(is_complex(x) for x in v.values())
                    return False
                has_complex = any(is_complex(v) for v in input_bindings.values())

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
~~~~~

#### Acts 4: 优化 `ArgumentResolver.resolve`

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
    def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        instance_map: Dict[str, Node],
        user_params: Dict[str, Any] = None,
        input_overrides: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        args = []
        kwargs = {}

        # 1. Reconstruct initial args/kwargs from Bindings (Literals)
        # Apply overrides if provided (for TCO fast path)
        bindings = node.input_bindings
        if input_overrides:
            bindings = bindings.copy()
            bindings.update(input_overrides)

        positional_args_dict = {}
        for name, value_raw in bindings.items():
            # Recursively resolve structures (e.g., lists containing Inject)
            value = self._resolve_structure(
                value_raw, node.id, state_backend, resource_context, graph
            )

            if name.isdigit():
                positional_args_dict[int(name)] = value
            else:
                kwargs[name] = value

        sorted_indices = sorted(positional_args_dict.keys())
        args = [positional_args_dict[i] for i in sorted_indices]

        # 2. Overlay Dependencies from Edges
        incoming_edges = [e for e in graph.edges if e.target.id == node.id]

        for edge in incoming_edges:
~~~~~
~~~~~python
    def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        instance_map: Dict[str, Node],
        user_params: Dict[str, Any] = None,
        input_overrides: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        # FAST PATH: If node is simple and we have no overrides or complex bindings
        if not node.has_complex_inputs and not input_overrides:
            incoming_edges = [e for e in graph.edges if e.target.id == node.id]
            if not incoming_edges:
                # No dependencies and no overrides: return bindings as is
                args = []
                kwargs = {}
                for name, value in node.input_bindings.items():
                    if name.isdigit():
                        idx = int(name)
                        while len(args) <= idx: args.append(None)
                        args[idx] = value
                    else:
                        kwargs[name] = value
                return args, kwargs

        # SLOW PATH: Existing logic
        args = []
        kwargs = {}

        # 1. Reconstruct initial args/kwargs from Bindings (Literals)
        bindings = node.input_bindings
        if input_overrides:
            bindings = bindings.copy()
            bindings.update(input_overrides)

        positional_args_dict = {}
        for name, value_raw in bindings.items():
            if node.has_complex_inputs:
                value = self._resolve_structure(
                    value_raw, node.id, state_backend, resource_context, graph
                )
            else:
                value = value_raw

            if name.isdigit():
                positional_args_dict[int(name)] = value
            else:
                kwargs[name] = value

        sorted_indices = sorted(positional_args_dict.keys())
        args = [positional_args_dict[i] for i in sorted_indices]

        # 2. Overlay Dependencies from Edges
        incoming_edges = [e for e in graph.edges if e.target.id == node.id]
        if not incoming_edges:
            return args, kwargs
            
        for edge in incoming_edges:
~~~~~

### 下一步建议
我们已经显著精简了慢速路径中的图构建逻辑（Acts 1）和快速路径中的参数解析逻辑（Acts 4）。

请再次运行：
1. `python scripts/profile_entry.py heavy 1000`：观察 `build_graph` 的耗时是否下降。
2. `python scripts/profile_entry.py simple 1000`：观察 `resolve` 的耗时是否下降。

如果 `heavy` 的性能没有恢复到 1k+ TPS，我们将考虑进一步优化 `_get_merkle_hash`，例如在循环中避免频繁的字符串拼接和字节编码转换。
