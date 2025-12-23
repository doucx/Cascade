好的，我将执行修复计划。

我需要在更新 `current_target` 之前，正确地将**当前正在执行的任务**保存为 `last_executed_task`，而不是像之前那样错误地保存了**下一个要执行的任务**。这消除了 `step_one` 错误地复用图结构去执行 `step_two` 导致的死循环。

### 简要回答
我将修复 `GraphExecutionStrategy` 中的 Fast Path 逻辑错误。之前错误地将 `result.task`（下一跳任务）记录为 `last_task`，导致非自递归的 TCO（如 A->B）在执行 B 时错误地与 B 自己比较并命中 Fast Path，从而复用 A 的图无限执行 A。修正后，将正确记录当前执行完毕的任务 A 为 `last_executed_task`，确保只有真正的自递归（A->A）才能触发优化。

## [WIP] fix: 修正 TCO Fast Path 中 last_task 更新时机导致的无限递归

### 用户需求
修复 `tests/engine/runtime/test_engine_recursion.py` 中的挂起/死循环问题。该问题由 TCO Fast Path 逻辑错误导致：在处理非自递归任务转换（如 `step_one` -> `step_two`）时，错误地复用了上一个任务的图结构。

### 评论
这是一个典型的“差一错误 (Off-by-one error)”变种。在状态机循环中，状态更新的时机至关重要。我错误地在迭代结束时，用“下一个状态”覆盖了“当前状态”的记录变量，导致下一次迭代开始时的“状态变更检测”失效（变成了“自己等于自己”）。

### 目标
在 `GraphExecutionStrategy.execute` 循环中，将 `last_task` 变量重命名为 `last_executed_task` 以明确语义，并确保它在 `current_target` 更新为 `result` **之前**被赋值。

### 基本原理
只有当 `current_target.task`（即将执行的任务）与 `last_executed_task`（刚刚执行完的任务）是同一个对象时，我们才能安全地复用图结构。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #task/domain/performance #task/object/tco-fast-path #task/action/bugfix #task/state/end

---

### Script

#### Acts 1: 修复 strategies.py 中的 last_task 更新逻辑

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
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
                    last_executed_task is not None
                    and last_graph is not None
                    and isinstance(current_target, LazyResult)
                    and current_target.task == last_executed_task
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

            # Capture the task we just executed BEFORE updating current_target
            if isinstance(current_target, LazyResult):
                last_executed_task = current_target.task
            else:
                last_executed_task = None

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

### 下一步建议
现在可以再次运行测试了。这个修复应该能够解决无限递归问题，并且不影响 TCO 的性能优化。
