简要回答
非常抱歉，我在上一个计划中引入了两个严重的回归错误：一是在快速路径中解包缓存数据时少算了一个字段，二是在 `execute` 循环中错误地假设 `current_target` 总是具有 `.task` 属性（忽略了 `MappedLazyResult`）。我将立即生成修复计划。

## [WIP] fix: 修复 TCO 快速路径中的解包错误与类型兼容性问题

### 错误分析
1.  **解包错误 (`ValueError`)**: 我将 `_cycle_cache` 修改为存储 4 个值（增加资源缓存），但在 `execute` 函数的快速路径解包逻辑中仍然只写了 3 个变量名。
2.  **类型兼容性错误 (`AttributeError`)**: 在 `strategies/graph.py` 中，我使用了 `current_target.task` 来获取 `_tco_cycle_id`。然而，当用户使用 `.map()` 时，`current_target` 是 `MappedLazyResult` 类型，它没有 `task` 属性（应为 `factory`）。

### 用户需求
修复 `tco_performance.py` 运行时的崩溃，并确保所有现有的 E2E 测试和 Map 测试能够通过。

### 目标
1.  修正 `graph.py` 中的快速路径解包逻辑。
2.  使用 `getattr` 安全地从 `current_target` 获取 `task` 和 `_tco_cycle_id`。
3.  确保 `MappedLazyResult` 也能兼容 `execute` 循环的初始化检查。

### 基本原理
在动态类型的异步循环中，必须始终通过 `getattr` 或显式的类型检查来访问可能不存在的属性。同时，缓存元组的结构必须在生产者和消费者之间保持严格同步。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #concept/executor #scope/core #ai/instruct #task/domain/core #task/object/tco-fast-path #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `GraphExecutionStrategy` 中的解包与属性访问

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
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

        while True:
            # Check for Zero-Overhead TCO Fast Path
            cycle_id = getattr(current_target.task, "_tco_cycle_id", None)
            fast_path_data = None

            if cycle_id and cycle_id in self._cycle_cache:
                if self._are_args_simple(current_target):
                    fast_path_data = self._cycle_cache[cycle_id]

            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                input_overrides = None

                if fast_path_data:
                    # FAST PATH: Reuse Graph & Plan
                    graph, indexed_plan, root_node_id = fast_path_data
                    # Reconstruct virtual instance map for current iteration
                    target_node = next(n for n in graph.nodes if n.id == root_node_id)
                    instance_map = {current_target._uuid: target_node}
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

        while True:
            # Check for Zero-Overhead TCO Fast Path
            # Use getattr safely as MappedLazyResult uses .factory instead of .task
            target_task = getattr(current_target, "task", None)
            cycle_id = getattr(target_task, "_tco_cycle_id", None) if target_task else None
            fast_path_data = None

            if cycle_id and cycle_id in self._cycle_cache:
                if self._are_args_simple(current_target):
                    fast_path_data = self._cycle_cache[cycle_id]

            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                input_overrides = None

                if fast_path_data:
                    # FAST PATH: Reuse Graph & Plan
                    # Unpack all 4 cached values: graph, indexed_plan, root_node_id, req_res
                    graph, indexed_plan, root_node_id, _ = fast_path_data
                    # Reconstruct virtual instance map for current iteration
                    target_node = next(n for n in graph.nodes if n.id == root_node_id)
                    instance_map = {current_target._uuid: target_node}
~~~~~

#### Acts 2: 进一步增强 `_are_args_simple` 的兼容性

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
    def _are_args_simple(self, lazy_result: LazyResult) -> bool:
        """
        Checks if the LazyResult arguments contain any nested LazyResults.
        """
        for arg in lazy_result.args:
            if isinstance(arg, (LazyResult, MappedLazyResult)):
                return False
        for val in lazy_result.kwargs.values():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                return False
        return True
~~~~~
~~~~~python
    def _are_args_simple(self, lazy_result: Any) -> bool:
        """
        Checks if the LazyResult arguments contain any nested LazyResults.
        """
        # Handle both LazyResult (args/kwargs) and MappedLazyResult (mapping_kwargs)
        args = getattr(lazy_result, "args", [])
        kwargs = getattr(lazy_result, "kwargs", {})
        if hasattr(lazy_result, "mapping_kwargs"):
            kwargs = lazy_result.mapping_kwargs

        for arg in args:
            if isinstance(arg, (LazyResult, MappedLazyResult)):
                return False
        for val in kwargs.values():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                return False
        return True
~~~~~

### 下一步建议
修复已经应用。现在请先运行 `pytest tests/engine/runtime/test_engine_recursion.py` 验证 TCO 基础功能，然后再次运行 `observatory/benchmarks/tco_performance.py` 查看优化后的性能数据。

我们目前实现了编译旁路（Acts 1）和一部分执行旁路（`_execute_hot_node`），如果性能仍有提升空间，我们可以考虑在 `_execute_hot_node` 内部实现针对热节点的参数预解析（Pre-binding）。
