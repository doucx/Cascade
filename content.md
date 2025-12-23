好的，我将执行“第一阶段：紧急修复”。

正如分析所示，虽然路线图建议在 `Task` 类内部实现缓存逻辑，但由于 `cascade-spec`（底层）无法反向依赖 `cascade-graph`（上层，包含 AST 分析器），这将导致循环依赖。因此，我将采用**架构兼容**的变通方案：在 `Task` 类中仅添加用于存储缓存的字段，而将“检查缓存-执行分析-写入缓存”的控制逻辑放在 `GraphBuilder` 中。这既实现了性能目标，又维护了正确的依赖层级。

以下是执行计划。

## 标签
#intent/perf #flow/ready #priority/critical #comp/core #comp/graph #task/domain/performance #task/object/ast-analysis #task/action/caching #task/state/begin

---

### 简要回答
我将执行第一阶段的性能修复。为了避免底层 `spec` 包反向依赖上层 `graph` 包，我将在 `Task` 对象上增加缓存字段，但在 `GraphBuilder` 中实现缓存的填充逻辑，从而在 O(1) 时间内获取 TCO 目标。

## [WIP] perf: 在 Task 对象上缓存 AST 分析结果以优化 TCO 性能

### 用户需求
解决由 `GraphBuilder` 在 TCO 循环的热路径中频繁调用 `analyze_task_source`（涉及昂贵的 AST 解析和 I/O）导致的严重性能回归问题。

### 评论
这是一个关键的性能修复。当前的实现在每次构建图节点时都重新解析源码，导致 TCO 性能下降了 2.5x 到 3.6x。通过在长生命周期的 `Task` 对象上缓存分析结果，我们可以消除这些重复开销。

### 目标
1.  修改 `cascade.spec.task.Task`，添加 `_potential_tco_targets` 字段用于存储分析结果。
2.  修改 `cascade.graph.build.GraphBuilder`，在访问任务时优先读取缓存，仅在缓存为空时调用 `analyze_task_source` 并回填缓存。

### 基本原理
`Task` 对象通常在模块加载时创建且生命周期贯穿整个应用运行过程，是存储静态分析结果的理想位置。将计算逻辑移至 `GraphBuilder` 避免了 `cascade-spec` 对 `cascade-graph` 的不当依赖，保持了架构的整洁。

### 标签
#intent/perf #flow/ready #priority/critical #comp/core #comp/graph #task/domain/performance #task/object/ast-analysis #task/action/caching #task/state/begin

---

### Script

#### Acts 1: 在 Task 类中添加缓存字段

我们在 `Task` 类的 `__init__` 方法中初始化 `_potential_tco_targets` 为 `None`。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/task.py
~~~~~
~~~~~python
    def __init__(self, func: Callable[..., T], name: Optional[str] = None):
        self.func = func
        self.name = name or func.__name__
        self._signature = inspect.signature(func)
        self.is_async = inspect.iscoroutinefunction(func)

    def __call__(self, *args, **kwargs) -> LazyResult[T]:
~~~~~
~~~~~python
    def __init__(self, func: Callable[..., T], name: Optional[str] = None):
        self.func = func
        self.name = name or func.__name__
        self._signature = inspect.signature(func)
        self.is_async = inspect.iscoroutinefunction(func)
        # Cache for AST analysis results to verify TCO paths
        self._potential_tco_targets: Optional[List["Task"]] = None

    def __call__(self, *args, **kwargs) -> LazyResult[T]:
~~~~~

#### Acts 2: 在 GraphBuilder 中实现缓存逻辑

我们修改 `_visit_lazy_result` 方法，使其在执行 AST 分析前先检查 `Task` 对象上的缓存。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
        # 6. Static TCO Analysis
        if scan_for_tco and result.task.func:
            potential_targets = analyze_task_source(result.task.func)
            for target_task in potential_targets:
                potential_uuid = f"potential:{result._uuid}:{target_task.name}"
                
                shadow_lr = LazyResult(
~~~~~
~~~~~python
        # 6. Static TCO Analysis
        if scan_for_tco and result.task.func:
            # Check cache on Task object to avoid re-parsing AST
            if getattr(result.task, "_potential_tco_targets", None) is None:
                result.task._potential_tco_targets = analyze_task_source(result.task.func)

            potential_targets = result.task._potential_tco_targets
            for target_task in potential_targets:
                potential_uuid = f"potential:{result._uuid}:{target_task.name}"
                
                shadow_lr = LazyResult(
~~~~~

### 下一步建议
虽然我无法直接运行基准测试脚本，但此更改在逻辑上直接消除了热路径上的重复 I/O 和解析操作。建议在本地环境中运行 `simple_countdown` 基准测试以验证性能提升是否符合预期（目标 TPS > 4500）。接下来可以考虑将此更改提交。
