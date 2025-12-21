## [WIP] fix: 补全 Engine 优化逻辑的 patch 指令

我正在重新发送针对 `engine.py` 的修改指令，确保包含完整的 `path`、`old_str` 和 `new_str` 三部分内容，以实现 TCO 零开销优化。

### 标签
#intent/perf #flow/ready #priority/high #comp/runtime #scope/core #ai/instruct #task/domain/runtime #task/object/tco-optimization #task/action/patch-fix #task/state/continue

---

### Script

#### Acts 1: 补全 `engine.py` 的优化逻辑

我们将分三步对 `engine.py` 进行精确修改。

**1.1 注入 `_is_simple_task` 判定工具**

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
    def register(self, resource_def: ResourceDefinition):
        # We store the full ResourceDefinition to preserve metadata like scope.
        self._resource_providers[resource_def.name] = resource_def

    def get_resource_provider(self, name: str) -> Callable:
~~~~~
~~~~~python
    def register(self, resource_def: ResourceDefinition):
        # We store the full ResourceDefinition to preserve metadata like scope.
        self._resource_providers[resource_def.name] = resource_def

    def _is_simple_task(self, lr: Any) -> bool:
        """
        Checks if the LazyResult is a simple, flat task (no nested dependencies).
        This allows for the Zero-Overhead TCO fast path.
        """
        if not isinstance(lr, LazyResult):
            return False
        if lr._condition or (lr._constraints and not lr._constraints.is_empty()):
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

    def get_resource_provider(self, name: str) -> Callable:
~~~~~

**1.2 在 `run` 方法中初始化 TCO 缓存变量**

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
            # TCO Loop: We keep executing as long as the result is a LazyResult
            current_target = target

            # The global stack holds "run" scoped resources
            with ExitStack() as run_stack:
~~~~~
~~~~~python
            # TCO Loop: We keep executing as long as the result is a LazyResult
            current_target = target

            # Optimization: Reusable graph container for simple recursion (Zero-Overhead TCO)
            # We keep the last simple graph to avoid rebuilding if the structure matches.
            _tco_cached_graph: Optional[Graph] = None
            _tco_cached_task_name: Optional[str] = None

            # The global stack holds "run" scoped resources
            with ExitStack() as run_stack:
~~~~~

**1.3 实现循环内的快速路径 (Fast Path) 调度**

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
                while True:
                    # The step stack holds "task" (step) scoped resources
                    with ExitStack() as step_stack:
                        # 1. Build graph for current target
                        graph = build_graph(current_target)

                        # 2. Setup Resources (mixed scope)
~~~~~
~~~~~python
                while True:
                    # The step stack holds "task" (step) scoped resources
                    with ExitStack() as step_stack:
                        # 1. Build graph for current target
                        graph = None
                        
                        # TCO Optimization: Fast path for simple recursion
                        if self._is_simple_task(current_target):
                            task_name = current_target.task.name
                            if _tco_cached_graph and _tco_cached_task_name == task_name:
                                # HIT: Reuse the graph, just update inputs
                                node = _tco_cached_graph.nodes[0]
                                # Re-construct literal inputs from current args/kwargs
                                node.literal_inputs = {str(i): v for i, v in enumerate(current_target.args)}
                                node.literal_inputs.update(current_target.kwargs)
                                # Update UUID to match current target (important for state backend)
                                node.id = current_target._uuid
                                graph = _tco_cached_graph
                            else:
                                # MISS: Build and cache
                                graph = build_graph(current_target)
                                if len(graph.nodes) == 1:
                                    _tco_cached_graph = graph
                                    _tco_cached_task_name = task_name
                                else:
                                    _tco_cached_graph = None
                        else:
                            # Complex task, standard build
                            graph = build_graph(current_target)
                            _tco_cached_graph = None

                        # 2. Setup Resources (mixed scope)
~~~~~

### 下一步建议
如果测试通过，我们将进行压力测试。你可以运行 `observatory/protoplasm/physics/recursion_test.py` 来直观感受优化前后的 TPS 差异。
