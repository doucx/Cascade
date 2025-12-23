# [WIP] feat(engine): Implement generalized structural caching for TCO

### 用户需求
实现“通用图结构缓存”机制，使 `Cascade` 能够识别并复用任意复杂但结构稳定的子图。具体目标是优化 `heavy_complex_countdown` 这类复杂递归任务的性能，使其执行效率接近简单的 TCO 循环。

### 评论
这是 `Cascade` 性能优化的关键一步。目前 `GraphExecutionStrategy` 仅对极其简单的任务开启了“快速通道”，而稍微复杂的图（即使结构完全静态）也会在每次迭代中触发完整的图构建和求解过程。通过引入基于 `StructuralHasher` 的缓存机制，我们可以将 $O(N)$ 的构建/求解开销降低为 $O(1)$ 的查表/注入开销。

### 目标
1.  **统一确定性**: 修改 `GraphBuilder` 和 `StructuralHasher`，确保它们在遍历 `kwargs` 时都采用排序顺序。这是保证“模板”和“数据”能够正确对齐（Hydration）的前提。
2.  **对齐数据提取**: 修改 `StructuralHasher`，使其产生的 `literals` 为线性列表（List），且顺序与 `GraphBuilder` 生成的 `SlotRef` 索引严格一致。
3.  **集成缓存策略**: 重构 `GraphExecutionStrategy`，移除 `_is_simple_task` 限制，全面启用基于结构哈希的缓存。

### 基本原理
Hashlife 模型的核心是将“计算结构”（Template）与“运行时数据”（Flesh/Data）分离。
-   **Template**: 由 `Graph` 和 `ExecutionPlan` 组成，通过 `StructuralHasher` 计算出的哈希值进行索引。
-   **Data**: 在每次运行时，由 `StructuralHasher` 提取出的线性数据列表。
-   **Hydration**: 运行时，引擎直接复用缓存的 Template，并将本次提取的 Data 注入到执行上下文中，从而跳过昂贵的图构建和拓扑排序步骤。

### 标签
#intent/refine #flow/ready #priority/high
#comp/engine #comp/graph #concept/caching #concept/tco
#ai/instruct
#task/domain/performance #task/object/structural-cache #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 确保 GraphBuilder 遍历顺序的确定性

为了让 `GraphBuilder` 生成的 `SlotRef` 索引与后续 `StructuralHasher` 提取的数据顺序一致，`GraphBuilder` 必须按排序后的键遍历 `kwargs`。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
        for i, val in enumerate(result.args):
            process_arg(str(i), val)
        for k, val in result.kwargs.items():
            process_arg(k, val)

        sig = None
~~~~~
~~~~~python
        for i, val in enumerate(result.args):
            process_arg(str(i), val)
        # Sort kwargs to ensure deterministic SlotRef indexing matches StructuralHasher
        for k in sorted(result.kwargs.keys()):
            process_arg(k, result.kwargs[k])

        sig = None
~~~~~

#### Acts 2: 改造 StructuralHasher 以支持数据提取

修改 `StructuralHasher`，使其不仅计算哈希，还按照与 `GraphBuilder` 相同的顺序提取字面量数据列表。这将替代原本的字典式提取。

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

    def __init__(self):
        # Flattened map of {canonical_node_path: {arg_name: value}}
        # path examples: "root", "root.args.0", "root.kwargs.data.selector"
        self.literals: Dict[str, Any] = {}
        self._hash_components: List[str] = []

    def hash(self, target: Any) -> Tuple[str, Dict[str, Any]]:
        self._visit(target, path="root")

        # Create a deterministic hash string
        fingerprint = "|".join(self._hash_components)
        hash_val = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

        return hash_val, self.literals

    def _visit(self, obj: Any, path: str):
        if isinstance(obj, LazyResult):
            self._visit_lazy(obj, path)
        elif isinstance(obj, MappedLazyResult):
            self._visit_mapped(obj, path)
        elif isinstance(obj, Router):
            self._visit_router(obj, path)
        elif isinstance(obj, (list, tuple)):
            self._hash_components.append("List[")
            for i, item in enumerate(obj):
                self._visit(item, f"{path}[{i}]")
            self._hash_components.append("]")
        elif isinstance(obj, dict):
            self._hash_components.append("Dict{")
            for k in sorted(obj.keys()):
                self._hash_components.append(f"{k}:")
                self._visit(obj[k], f"{path}.{k}")
            self._hash_components.append("}")
        elif isinstance(obj, Inject):
            self._hash_components.append(f"Inject({obj.resource_name})")
        else:
            # It's a literal value.
            # We record a placeholder in the hash, and save the value.
            self._hash_components.append("LIT")
            self.literals[path] = obj

    def _visit_lazy(self, lr: LazyResult, path: str):
        # Identification
        task_name = getattr(lr.task, "name", "unknown")
        self._hash_components.append(f"Task({task_name})")

        # Policies (part of structure)
        if lr._retry_policy:
            rp = lr._retry_policy
            self._hash_components.append(
                f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})"
            )
        if lr._cache_policy:
            self._hash_components.append(f"Cache({type(lr._cache_policy).__name__})")

        # Args
        self._hash_components.append("Args:")
        for i, arg in enumerate(lr.args):
            self._visit(arg, f"{path}.args.{i}")

        # Kwargs
        self._hash_components.append("Kwargs:")
        for k in sorted(lr.kwargs.keys()):
            self._hash_components.append(f"{k}=")
            self._visit(lr.kwargs[k], f"{path}.kwargs.{k}")

        # Condition
        if lr._condition:
            self._hash_components.append("Condition:")
            self._visit(lr._condition, f"{path}.condition")

        if lr._dependencies:
            self._hash_components.append("Deps:")
            for i, dep in enumerate(lr._dependencies):
                self._visit(dep, f"{path}.deps.{i}")

    def _visit_mapped(self, mlr: MappedLazyResult, path: str):
        factory_name = getattr(mlr.factory, "name", "unknown")
        self._hash_components.append(f"Map({factory_name})")

        # Kwargs (Mapped inputs)
        self._hash_components.append("MapKwargs:")
        for k in sorted(mlr.mapping_kwargs.keys()):
            self._hash_components.append(f"{k}=")
            self._visit(mlr.mapping_kwargs[k], f"{path}.kwargs.{k}")

        if mlr._condition:
            self._hash_components.append("Condition:")
            self._visit(mlr._condition, f"{path}.condition")

        if mlr._dependencies:
            self._hash_components.append("Deps:")
            for i, dep in enumerate(mlr._dependencies):
                self._visit(dep, f"{path}.deps.{i}")

    def _visit_router(self, router: Router, path: str):
        self._hash_components.append("Router")
        self._hash_components.append("Selector:")
        self._visit(router.selector, f"{path}.selector")

        self._hash_components.append("Routes:")
        for k in sorted(router.routes.keys()):
            # Note: Route keys (k) are structural! (e.g. "prod", "dev")
            self._hash_components.append(f"Key({k})->")
            self._visit(router.routes[k], f"{path}.routes.{k}")
~~~~~
~~~~~python
class StructuralHasher:
    """
    Generates a stable structural hash for a LazyResult tree and extracts
    literal values that fill the structure into a linear list.
    """

    def __init__(self):
        # Linear list of literals extracted in the exact traversal order as GraphBuilder.
        # This corresponds to the DataTuple used at runtime.
        self.data_list: List[Any] = []
        self._hash_components: List[str] = []

    def hash(self, target: Any) -> Tuple[str, List[Any]]:
        self._visit(target)

        # Create a deterministic hash string
        fingerprint = "|".join(self._hash_components)
        hash_val = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

        return hash_val, self.data_list

    def _visit(self, obj: Any):
        if isinstance(obj, LazyResult):
            self._visit_lazy(obj)
        elif isinstance(obj, MappedLazyResult):
            self._visit_mapped(obj)
        elif isinstance(obj, Router):
            self._visit_router(obj)
        elif isinstance(obj, (list, tuple)):
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
            # We record a placeholder in the hash, and save the value.
            self._hash_components.append("LIT")
            self.data_list.append(obj)

    def _visit_lazy(self, lr: LazyResult):
        # Identification
        task_name = getattr(lr.task, "name", "unknown")
        self._hash_components.append(f"Task({task_name})")

        # Policies (part of structure)
        if lr._retry_policy:
            rp = lr._retry_policy
            self._hash_components.append(
                f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})"
            )
        if lr._cache_policy:
            self._hash_components.append(f"Cache({type(lr._cache_policy).__name__})")

        # Args
        self._hash_components.append("Args:")
        for i, arg in enumerate(lr.args):
            self._visit(arg)

        # Kwargs
        self._hash_components.append("Kwargs:")
        for k in sorted(lr.kwargs.keys()):
            self._hash_components.append(f"{k}=")
            self._visit(lr.kwargs[k])

        # Condition
        if lr._condition:
            self._hash_components.append("Condition:")
            self._visit(lr._condition)

        if lr._dependencies:
            self._hash_components.append("Deps:")
            for i, dep in enumerate(lr._dependencies):
                self._visit(dep)

    def _visit_mapped(self, mlr: MappedLazyResult):
        factory_name = getattr(mlr.factory, "name", "unknown")
        self._hash_components.append(f"Map({factory_name})")

        # Kwargs (Mapped inputs)
        self._hash_components.append("MapKwargs:")
        for k in sorted(mlr.mapping_kwargs.keys()):
            self._hash_components.append(f"{k}=")
            self._visit(mlr.mapping_kwargs[k])

        if mlr._condition:
            self._hash_components.append("Condition:")
            self._visit(mlr._condition)

        if mlr._dependencies:
            self._hash_components.append("Deps:")
            for i, dep in enumerate(mlr._dependencies):
                self._visit(dep)

    def _visit_router(self, router: Router):
        self._hash_components.append("Router")
        self._hash_components.append("Selector:")
        self._visit(router.selector)

        self._hash_components.append("Routes:")
        for k in sorted(router.routes.keys()):
            # Note: Route keys (k) are structural! (e.g. "prod", "dev")
            self._hash_components.append(f"Key({k})->")
            self._visit(router.routes[k])
~~~~~

#### Acts 3: 在 GraphExecutionStrategy 中全面启用通用缓存

重构 `execute` 方法，移除对 `_is_simple_task` 的依赖，改为使用 `StructuralHasher` 进行缓存查找。同时，确保在 Cache Hit 时正确地“水合”图数据。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
    def __init__(
        self,
        solver: Solver,
        node_processor: NodeProcessor,
        resource_container: ResourceContainer,
        constraint_manager: ConstraintManager,
        bus: MessageBus,
        wakeup_event: asyncio.Event,
    ):
        self.solver = solver
        self.node_processor = node_processor
        self.resource_container = resource_container
        self.constraint_manager = constraint_manager
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
    def __init__(
        self,
        solver: Solver,
        node_processor: NodeProcessor,
        resource_container: ResourceContainer,
        constraint_manager: ConstraintManager,
        bus: MessageBus,
        wakeup_event: asyncio.Event,
    ):
        self.solver = solver
        self.node_processor = node_processor
        self.resource_container = resource_container
        self.constraint_manager = constraint_manager
        self.bus = bus
        self.wakeup_event = wakeup_event
        # Generalized Structural Cache
        # Key: structural_hash (str)
        # Value: (Graph, ExecutionPlan, canonical_target_node_id)
        self._graph_cache: Dict[str, Tuple[Graph, Any, str]] = {}
        self._hasher = StructuralHasher()

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
                
                # 1. Structural Hashing & Cache Lookup
                # We always compute the hash first. This is O(N) traversal but avoids O(V+E) Solver.
                # It also extracts the data_list (flesh) in the process.
                struct_hash, data_list = self._hasher.hash(current_target)
                data_tuple = tuple(data_list)

                if struct_hash in self._graph_cache:
                    # HIT: Zero-Overhead Hydration
                    graph, plan, canonical_target_id = self._graph_cache[struct_hash]
                    
                    # We need a minimal instance_map to map the current_target's UUID 
                    # to the canonical node ID in the plan.
                    # Note: We ONLY map the target node because that's what we need to return.
                    # Intermediate nodes in the plan use canonical IDs which match the Graph.
                    instance_map = {
                        current_target._uuid: Node(id=canonical_target_id, name="cached_target") 
                    }
                else:
                    # MISS: Build, Solve, and Cache
                    graph, _, full_instance_map = build_graph(current_target)
                    plan = self.solver.resolve(graph)
                    
                    # Identify the canonical target ID
                    canonical_target_node = full_instance_map[current_target._uuid]
                    
                    # Cache the template
                    self._graph_cache[struct_hash] = (graph, plan, canonical_target_node.id)
                    instance_map = full_instance_map

                # 2. Setup Resources (mixed scope)
                required_resources = self.resource_container.scan(graph, data_tuple)
                self.resource_container.setup(
                    required_resources,
                    active_resources,
                    run_stack,
                    step_stack,
                    run_id,
                )

                # 3. Execute Graph
                result = await self._execute_graph(
                    current_target,
                    params,
                    active_resources,
                    run_id,
                    state_backend,
                    graph,
                    data_tuple,  # Injected Flesh
                    plan,
                    instance_map,
                )

            # 4. Check for Tail Call (LazyResult)
            if isinstance(result, (LazyResult, MappedLazyResult)):
                current_target = result
                # STATE GC
                if hasattr(state_backend, "clear"):
                    state_backend.clear()
                # Yield control
                await asyncio.sleep(0)
            else:
                return result
~~~~~
