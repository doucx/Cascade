基准测试结果非常清晰地揭示了本次优化的副作用：**“静态分析税” (Static Analysis Tax)**。

结果分析

1.  **[1] Optimized Path (simple_countdown)**:
    *   性能保持稳定 (0.76s -> 0.74s)。
    *   这证明了对于符合 `_is_simple_task` 的任务，O(1) 快速通道成功绕过了所有开销，达到了预期效果。

2.  **[2] Heavy Un-optimized Path (heavy_complex_countdown)**:
    *   **性能大幅下降** (8.68s -> 18.71s)，TPS 降低了约 **53%**。
    *   **原因分析**: 
        *   `heavy_complex_countdown` 包含 10 个 `noop` 任务依赖，因此它不满足 `_is_simple_task` 条件，被迫走“慢速通道”。
        *   在慢速通道中，由于 `len(nodes) > 1`，引擎在每轮迭代都会调用 `build_graph`。
        *   在新的 `GraphBuilder` 中，每次调用 `build_graph` 都会触发 `assign_tco_cycle_ids` 及其内部的递归 DFS。
        *   **致命伤**: 在 `ast_analyzer.py` 的 DFS 过程中，我直接调用了 `analyze_task_source(current_task.func)`。这个函数内部包含 `inspect.getsource` 和 `ast.parse`，它们是极其昂贵的。
        *   在 `heavy_complex_countdown` 的例子中，每轮迭代都会对 11 个任务进行 11 次完整的 AST 解析。10,000 次迭代意味着 110,000 次 AST 解析，这正是性能腰斩的原因。

3.  **[3] VM Path & [4] Imperative**:
    *   保持稳定，符合预期。

解决方案

我们需要消除“慢速通道”中的重复分析开销。核心思路是：**AST 分析结果必须在 Task 级别进行永久缓存**，确保每个 Task 在其生命周期内只被解析一次。

---

## [WIP] fix(engine): 消除静态分析重复开销，优化热路径性能

### 错误分析
在 `assign_tco_cycle_ids` 的递归过程中，每次都重新解析源码，导致在无法进入快速通道的复杂循环中，每一轮迭代都承受了巨大的 AST 解析开销。

### 解决方案
1.  **缓存 `analyze_task_source`**: 在 `Task` 对象上缓存静态分析发现的潜在目标。
2.  **优化 DFS 逻辑**: 让 `assign_tco_cycle_ids` 优先读取缓存，避免重复的 I/O 和解析操作。
3.  **全局分析标记**: 为 `Task` 增加一个 `_static_analysis_done` 标记，确保 `assign_tco_cycle_ids` 对同一个起始任务只运行一次 DFS。

### 标签
#intent/perf #flow/ready #priority/critical #comp/graph #concept/tco #scope/core #task/domain/engine #task/object/ast-cache #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 为 analyze_task_source 增加 Task 级缓存

我们修改 `analyze_task_source`，使其接收 `Task` 对象而不是裸函数，从而能够利用缓存。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/ast_analyzer.py
~~~~~
~~~~~python
def analyze_task_source(task_func: Callable) -> List[Task]:
    """
    Analyzes a task function's source code to find potential TCO targets.
    """
    try:
        source = inspect.getsource(task_func)
        source = textwrap.dedent(source)
        tree = ast.parse(source)
    except (OSError, SyntaxError) as e:
        logger.warning(f"Could not parse source for {task_func.__name__}: {e}")
        return []

    resolver = ReferenceResolver(task_func)
    visitor = TcoVisitor(resolver)
    visitor.visit(tree)

    return list(visitor.potential_targets)


def assign_tco_cycle_ids(root_task: Task) -> None:
~~~~~
~~~~~python
def analyze_task_source(task: Task) -> List[Task]:
    """
    Analyzes a task function's source code to find potential TCO targets.
    Results are cached on the Task object to avoid redundant AST parsing.
    """
    # 1. Return cached results if available
    if hasattr(task, "_potential_tco_targets") and task._potential_tco_targets is not None:
        return task._potential_tco_targets

    task_func = task.func
    if not task_func:
        return []

    try:
        source = inspect.getsource(task_func)
        source = textwrap.dedent(source)
        tree = ast.parse(source)
    except (OSError, SyntaxError, TypeError) as e:
        # Some callables (like built-ins) might not have source code
        logger.debug(f"Could not parse source for {task.name}: {e}")
        task._potential_tco_targets = []
        return []

    resolver = ReferenceResolver(task_func)
    visitor = TcoVisitor(resolver)
    visitor.visit(tree)

    # 2. Cache the result
    task._potential_tco_targets = list(visitor.potential_targets)
    return task._potential_tco_targets


def assign_tco_cycle_ids(root_task: Task) -> None:
~~~~~

#### Acts 2: 优化 assign_tco_cycle_ids 避免重复 DFS

我们确保对每个任务只进行一次完整的 TCO 循环分析，并使用缓存的调用图。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/ast_analyzer.py
~~~~~
~~~~~python
def assign_tco_cycle_ids(root_task: Task) -> None:
    """
    Performs a recursive static analysis starting from root_task to identify
    Strongly Connected Components (cycles) in the task call graph.

    If a cycle is detected (e.g., A -> B -> A), a unique 'tco_cycle_id' is
    generated and assigned to the '_tco_cycle_id' attribute of all Tasks
    involved in that cycle.

    This enables the Engine to recognize multi-task TCO loops at runtime.
    """
    # Use a simple DFS to detect cycles
    visited = set()
    recursion_stack = set()
    path: List[Task] = []

    def _dfs(current_task: Task):
        visited.add(current_task)
        recursion_stack.add(current_task)
        path.append(current_task)

        # Get static targets (memoize if needed, but analyze_task_source is fast enough)
        targets = analyze_task_source(current_task.func)

        for target in targets:
            if target not in visited:
                _dfs(target)
            elif target in recursion_stack:
~~~~~
~~~~~python
def assign_tco_cycle_ids(root_task: Task) -> None:
    """
    Performs a recursive static analysis starting from root_task to identify
    Strongly Connected Components (cycles) in the task call graph.
    """
    # 1. Skip if this branch has already been fully analyzed
    if getattr(root_task, "_tco_analysis_done", False):
        return

    # Use a simple DFS to detect cycles
    visited = set()
    recursion_stack = set()
    path: List[Task] = []

    def _dfs(current_task: Task):
        visited.add(current_task)
        recursion_stack.add(current_task)
        path.append(current_task)

        # Get static targets using the cached analyzer
        targets = analyze_task_source(current_task)

        for target in targets:
            if target not in visited:
                _dfs(target)
            elif target in recursion_stack:
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/ast_analyzer.py
~~~~~
~~~~~python
        recursion_stack.remove(current_task)
        path.pop()

    _dfs(root_task)
~~~~~
~~~~~python
        recursion_stack.remove(current_task)
        path.pop()
        # Mark individual task as processed to avoid re-entering its branch in future DFS runs
        current_task._tco_analysis_done = True

    _dfs(root_task)
~~~~~

#### Acts 3: 适配 GraphBuilder 调整后的接口

由于 `analyze_task_source` 现在的签名已变更，我们需要同步更新 `GraphBuilder`。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
        # 6. Static TCO Analysis
        if scan_for_tco and result.task.func:
            # 6.1 Analyze and tag cycles if not already done
            if getattr(result.task, "_tco_cycle_id", None) is None:
                assign_tco_cycle_ids(result.task)
            
            # Propagate cycle ID to the Node
            node.tco_cycle_id = getattr(result.task, "_tco_cycle_id", None)

            # 6.2 Check cache on Task object to avoid re-parsing AST
            if getattr(result.task, "_potential_tco_targets", None) is None:
                result.task._potential_tco_targets = analyze_task_source(
                    result.task.func
                )

            potential_targets = result.task._potential_tco_targets
~~~~~
~~~~~python
        # 6. Static TCO Analysis
        if scan_for_tco and result.task.func:
            # 6.1 Analyze and tag cycles if not already done
            if not getattr(result.task, "_tco_analysis_done", False):
                assign_tco_cycle_ids(result.task)
            
            # Propagate cycle ID to the Node
            node.tco_cycle_id = getattr(result.task, "_tco_cycle_id", None)

            # 6.2 Retrieve potential targets (using cache)
            potential_targets = analyze_task_source(result.task)
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
        # Recursively expand its potential targets
        if getattr(task, "_potential_tco_targets", None) is None:
            task._potential_tco_targets = analyze_task_source(task.func)
        
        for next_task in task._potential_tco_targets:
            self._visit_shadow_recursive(target_node, next_task)
~~~~~
~~~~~python
        # Recursively expand its potential targets (using cache)
        potential_targets = analyze_task_source(task)
        
        for next_task in potential_targets:
            self._visit_shadow_recursive(target_node, next_task)
~~~~~

### 下一步建议

修复缓存问题后，`heavy_complex_countdown` 的性能应该会恢复到接近 8s 的水平（甚至更好，因为虽然它没进快速通道，但其内部的 AST 解析也被缓存了）。

接下来：
1.  **重跑基准测试**: 验证分析开销是否已被成功摊平。
2.  **Generalizing Structural Caching**: 按照路线图，下一步应该是让 `heavy_complex_countdown` 这种结构稳定但复杂的任务也能进入快速通道。目前它被 `_is_simple_task` 挡住了，因为 `_is_simple_task` 暂时禁止了带依赖的任务。
3.  **[COMMIT]**: 将这些核心优化提交。
