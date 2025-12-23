简要回答
我将修改 `cascade.runtime.strategies.GraphExecutionStrategy`，在 TCO 循环中增加一个“快速通道 (Fast Path)”。当检测到简单的自递归任务时，直接复用上一次的图结构，从而绕过昂贵的哈希计算和图构建过程。

## [WIP] refactor: 为 GraphExecutionStrategy 实现 TCO 快速通道

### 用户需求
在 TCO 循环中，针对结构稳定的自递归调用（如计数器、轮询循环），消除每次迭代都进行全量对象树哈希 (`StructuralHasher`) 和缓存查找的开销，以恢复性能。

### 评论
这是一个关键的性能优化。通过引入 Fast Path，我们将 O(N) 的图结构检查降低为 O(1) 的引用相等性检查。

### 目标
修改 `execute` 方法：
1.  引入 `last_task`, `last_graph`, `last_plan` 状态变量。
2.  添加 `_is_simple_task` 辅助方法。
3.  在循环开始处添加检测逻辑：如果 `current_target` 是同一个任务且为简单任务，直接复用 `last_graph`。

### 基本原理
对于自递归的 TCO，除了参数值变化外，任务本身和图的拓扑结构是完全不变的。通过识别这种模式，我们可以安全地跳过所有结构分析步骤，仅更新图节点的字面量输入。

### 标签
#intent/refine #flow/ready #priority/critical #comp/engine #concept/state #task/domain/performance #task/object/tco-loop #task/action/optimization #task/state/continue

---

### Script

#### Acts 1: 修改 strategies.py 实现 Fast Path

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
        self._graph_cache: Dict[str, Tuple[Graph, Any]] = {}

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
                # 1. Get Graph and Plan, using Structural Hash Cache
                hasher = StructuralHasher()
                struct_hash, literals = hasher.hash(current_target)

                graph = None
                plan = None

                if struct_hash in self._graph_cache:
                    # CACHE HIT: Reuse graph and plan
                    cached_graph, cached_plan = self._graph_cache[struct_hash]
                    if len(cached_graph.nodes) > 1:
                        graph = build_graph(current_target)
                        plan = self.solver.resolve(graph)
                    else:
                        graph = cached_graph
                        plan = cached_plan
                        self._update_graph_literals(graph, current_target, literals)
                else:
                    # CACHE MISS: Build, solve, and cache
                    graph = build_graph(current_target)
                    plan = self.solver.resolve(graph)
                    self._graph_cache[struct_hash] = (graph, plan)

                # 2. Setup Resources (mixed scope)
                required_resources = self.resource_container.scan(graph)
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
                    plan,
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

    def _update_graph_literals(
        self, graph: Graph, target: Any, literals: Dict[str, Any]
    ):
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
        self._graph_cache: Dict[str, Tuple[Graph, Any]] = {}

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
        last_task = None
        last_graph = None
        last_plan = None

        while True:
            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                graph = None
                plan = None
                literals = None

                # --- FAST PATH CHECK ---
                is_fast_path = False
                if (
                    last_task is not None
                    and last_graph is not None
                    and isinstance(current_target, LazyResult)
                    and current_target.task == last_task
                ):
                    if self._is_simple_task(current_target):
                        is_fast_path = True
                        graph = last_graph
                        plan = last_plan
                        # Update literals in O(1) without hashing
                        self._update_graph_literals(graph, current_target, {})

                if not is_fast_path:
                    # --- SLOW PATH (Hashing & Cache) ---
                    # 1. Get Graph and Plan, using Structural Hash Cache
                    hasher = StructuralHasher()
                    struct_hash, literals = hasher.hash(current_target)

                    if struct_hash in self._graph_cache:
                        # CACHE HIT: Reuse graph and plan
                        cached_graph, cached_plan = self._graph_cache[struct_hash]
                        if len(cached_graph.nodes) > 1:
                            graph = build_graph(current_target)
                            plan = self.solver.resolve(graph)
                        else:
                            graph = cached_graph
                            plan = cached_plan
                            self._update_graph_literals(graph, current_target, literals)
                    else:
                        # CACHE MISS: Build, solve, and cache
                        graph = build_graph(current_target)
                        plan = self.solver.resolve(graph)
                        self._graph_cache[struct_hash] = (graph, plan)
                    
                    # Update cache for next iteration possibility
                    last_graph = graph
                    last_plan = plan

                # 2. Setup Resources (mixed scope)
                required_resources = self.resource_container.scan(graph)
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
                    plan,
                )

            # 4. Check for Tail Call (LazyResult)
            if isinstance(result, (LazyResult, MappedLazyResult)):
                if isinstance(result, LazyResult):
                    last_task = result.task
                else:
                    # Mapped results are complex, disable fast path for next step
                    last_task = None

                current_target = result
                # STATE GC
                if hasattr(state_backend, "clear"):
                    state_backend.clear()
                # Yield control
                await asyncio.sleep(0)
            else:
                return result

    def _update_graph_literals(
        self, graph: Graph, target: Any, literals: Dict[str, Any]
    ):
~~~~~

### 下一步建议
我们已经实现了 TCO 快速通道。现在请再次运行基准测试。如果一切顺利，我们应该能看到 `simple_countdown` 的性能有显著提升。
