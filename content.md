好的，收到了新的测试失败报告。这次有两个独立的问题，我来逐一分析和修复。

 错误分析

1.  **`AssertionError: Expected 'warning' to be called once. Called 2 times.`**
    *   **问题**: 在我们新写的测试 `test_dynamic_recursion_emits_warning` 中，警告被发出了两次，而测试断言只应发出一次。
    *   **原因**: 我们的工作流是 `dynamic_recursive_task(1)`。引擎在 TCO 循环中运行它。
        1.  **第一次迭代**: 引擎遇到 `dynamic_recursive_task(1)`，进入慢速路径并构建图。它遍历图中的节点，发现 `dynamic_recursive_task` 节点有 `warns_dynamic_recursion=True` 标志，于是**发出第一次警告**。任务执行后返回 `dynamic_recursive_task(some_other_task(0))`。
        2.  **第二次迭代**: 引擎现在处理 `dynamic_recursive_task(some_other_task(0))`。由于参数中仍包含 `LazyResult`，它**再次进入慢速路径并重新构建图**。它再次遍历新图中的节点，再次发现 `dynamic_recursive_task` 节点的警告标志，于是**发出第二次警告**。
    *   **结论**: 警告逻辑在每次图重建时都会触发。这是不正确的行为，因为静态分析警告是针对函数代码的，应该在每次运行中只报告一次。

2.  **`TypeError: 'AnalysisResult' object is not iterable`**
    *   **问题**: `tests/engine/graph/test_ast_analyzer.py` 中的单元测试全部失败。
    *   **原因**: 这正是我在上一个计划中试图修复的问题。看起来我修复 `ImportError` 的计划被优先采纳，而修复这些单元测试的计划没有被应用。这些测试仍然直接迭代 `analyze_task_source` 的 `AnalysisResult` 返回值，而不是访问其 `.targets` 属性。

 解决方案

1.  **防止重复警告**: 我将在 `GraphExecutionStrategy` 中引入一个 `set` 来跟踪在当前运行中已经发出过警告的任务名称。在发布新警告之前，会先检查该任务是否已经报告过，从而确保每个警告只发出一次。
2.  **修复单元测试**: 我将重新应用对 `test_ast_analyzer.py` 的修复，确保所有测试用例都正确地访问 `analysis_result.targets`。

我将生成一个计划来同时解决这两个问题。

## [WIP] fix: 修正静态分析警告逻辑并修复单元测试

### 错误分析
当前实现存在两个缺陷：
1.  **重复警告**: `GraphExecutionStrategy` 在 TCO 循环的每次图重建中都会重复发出相同的静态分析警告，导致 `AssertionError`。
2.  **单元测试过时**: `test_ast_analyzer.py` 中的单元测试没有适配 `analyze_task_source` 函数的新 `AnalysisResult` 返回类型，导致 `TypeError`。

### 用户需求
修复上述两个问题，使静态分析警告只在每次运行时对每个违规任务触发一次，并让所有相关单元测试通过。

### 评论
这是一个重要的健壮性修复。确保警告的唯一性可以提供更清晰、无干扰的用户反馈。同时，修复单元测试是保证我们静态分析器本身逻辑正确性的基础。

### 目标
1.  在 `GraphExecutionStrategy` 中添加一个状态变量（`_issued_warnings`），用于跟踪已发出的警告，防止重复。
2.  修改 `tests/engine/graph/test_ast_analyzer.py`，使其所有测试用例都正确地从 `AnalysisResult` 对象中获取 `.targets` 列表进行断言。

### 基本原理
通过在 `GraphExecutionStrategy` 实例的生命周期内维护一个已报告警告的集合，我们可以轻松地在发布事件前进行检查，实现警告的幂等性。对于单元测试，这是一个简单的适配，只需将对返回值的直接使用改为访问其 `.targets` 属性即可。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #comp/tests #scope/core #scope/dx #ai/instruct #task/domain/runtime #task/object/static-analysis #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: `cascade-engine` - 防止重复警告

我们首先修改 `GraphExecutionStrategy` 来跟踪已发出的警告。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
        self.bus = bus
        self.wakeup_event = wakeup_event

        # JIT Compilation Cache
        # Maps template_id to an IndexedExecutionPlan (List[List[int]])
~~~~~
~~~~~python
        self.bus = bus
        self.wakeup_event = wakeup_event

        # Tracks warnings issued in this run to avoid duplicates
        self._issued_warnings: Set[str] = set()

        # JIT Compilation Cache
        # Maps template_id to an IndexedExecutionPlan (List[List[int]])
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
                    # Post-build analysis checks
                    for node in graph.nodes:
                        if node.warns_dynamic_recursion:
                            self.bus.publish(
                                StaticAnalysisWarning(
                                    run_id=run_id,
                                    task_id=node.structural_id,
                                    task_name=node.name,
                                    warning_code="CS-W001",
                                    message=(
                                        f"Task '{node.name}' uses a dynamic recursion pattern (calling other "
                                        "tasks in its arguments) which disables TCO optimizations, "
                                        "leading to significant performance degradation."
                                    ),
                                )
                            )

                    target_node = instance_map[current_target._uuid]
~~~~~
~~~~~python
                    # Post-build analysis checks
                    for node in graph.nodes:
                        if node.warns_dynamic_recursion and node.name not in self._issued_warnings:
                            self.bus.publish(
                                StaticAnalysisWarning(
                                    run_id=run_id,
                                    task_id=node.structural_id,
                                    task_name=node.name,
                                    warning_code="CS-W001",
                                    message=(
                                        f"Task '{node.name}' uses a dynamic recursion pattern (calling other "
                                        "tasks in its arguments) which disables TCO optimizations, "
                                        "leading to significant performance degradation."
                                    ),
                                )
                            )
                            self._issued_warnings.add(node.name)

                    target_node = instance_map[current_target._uuid]
~~~~~

#### Acts 2: `tests` - 修复单元测试

现在，我们应用之前被遗漏的修复，更新 `test_ast_analyzer.py` 文件。

~~~~~act
write_file
tests/engine/graph/test_ast_analyzer.py
~~~~~
~~~~~python
from cascade.spec.task import task
from cascade.graph.ast_analyzer import analyze_task_source

# --- Setup Dummy Tasks ---


@task
def downstream_a(x):
    return x


@task
def downstream_b(x):
    return x * 2


# --- Scenarios ---


def test_analyze_direct_return():
    """Test standard 'return task(...)' pattern with branching."""

    @task
    def orchestrator(x):
        if x > 5:
            return downstream_a(x)
        else:
            return downstream_b(x)

    analysis_result = analyze_task_source(orchestrator)
    targets = analysis_result.targets

    target_names = {t.name for t in targets}
    assert "downstream_a" in target_names
    assert "downstream_b" in target_names
    assert len(targets) == 2


def test_analyze_map_return():
    """Test 'return task.map(...)' pattern."""

    @task
    def mapper_orchestrator(items):
        return downstream_a.map(x=items)

    analysis_result = analyze_task_source(mapper_orchestrator)
    targets = analysis_result.targets
    target_names = {t.name for t in targets}
    assert "downstream_a" in target_names


def test_analyze_with_alias_in_globals():
    """Test when tasks are aliased in global scope."""
    alias_task = downstream_a

    @task
    def alias_user():
        return alias_task(1)

    analysis_result = analyze_task_source(alias_user)
    targets = analysis_result.targets
    target_names = {t.name for t in targets}
    assert "downstream_a" in target_names


def test_analyze_no_tco():
    """Test that regular returns are ignored."""

    @task
    def simple_calc():
        return 42

    analysis_result = analyze_task_source(simple_calc)
    targets = analysis_result.targets
    assert len(targets) == 0


def test_analyze_complex_attribute_access():
    """Test resolving tasks within namespaces."""

    class Actions:
        op = downstream_b

    actions = Actions()

    @task
    def namespace_user():
        return actions.op(10)

    analysis_result = analyze_task_source(namespace_user)
    targets = analysis_result.targets
    target_names = {t.name for t in targets}
    assert "downstream_b" in target_names
~~~~~

### 下一步建议
我们已经同时修复了逻辑错误和单元测试。现在，整个测试套件应该能够完全通过了。

请重新运行测试以确认。如果一切顺利，我们将正式完成“阶段二”，并可以安全地进入“阶段三”的核心性能优化工作。
