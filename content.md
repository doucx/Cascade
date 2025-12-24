My apologies. The test failure indicates a deeper issue that I overlooked. The failure is not in the `visualize.py` change I proposed, but in the TDD test case I created. The traceback is extremely clear.

Thank you for providing the error log and the performance benchmark files. They were crucial in diagnosing the problem.

I will now generate a new plan to fix this issue.

## [WIP] fix: 修正 visualize 测试用例中错误的跳转目标类型

### 错误分析
测试失败的根本原因在于我创建的 TDD 测试用例中，向 `cs.select_jump` 传递了一个错误的类型。

1.  **错误根源**: 在 `test_visualize_iterative_jump_edge` 中，`cs.select_jump` 的 `routes` 字典被定义为 `{"next": state_machine}`。这里的 `state_machine` 是 `@cs.task` 装饰器返回的 `Task` 对象本身，而不是一个 `LazyResult` 实例（即对 `state_machine()` 的一次调用）。
2.  **`GraphBuilder` 的行为**: 当 `GraphBuilder` 遍历图的依赖关系时，它会检查 `JumpSelector` 内部的 `routes`。它期望找到 `LazyResult` 实例（代表图中的节点）作为跳转目标。
3.  **冲突点**: 当 `GraphBuilder` 遇到裸露的 `Task` 对象时，它不知道如何处理，因为它不是图的一个有效组成部分（它是一个节点的“模板”，而不是节点本身），因此正确地抛出了 `TypeError: Cannot build graph from type <class 'cascade.spec.task.Task'>`。
4.  **正确用法佐证**: 您提供的性能测试文件 `tco_performance.py` 中的 `create_explicit_loop` 函数清晰地展示了正确模式：`step` 是一个 `LazyResult`，然后这个 `step` 被传递给 `cs.select_jump`，从而构成一个自引用的循环。我的测试代码没有遵循这个模式。

### 用户需求
修正 `tests/sdk/tools/test_visualize.py` 中的 `test_visualize_iterative_jump_edge` 测试用例，确保传递给 `cs.select_jump` 的跳转目标是 `LazyResult` 实例，而不是 `Task` 对象。

### 评论
这是一个典型的 TDD 成功案例。测试在暴露我们预期的渲染问题**之前**，先暴露了一个更深层次的、关于如何正确构建循环图的 API 使用错误。这证明了编写高保真度测试的重要性。通过修正这个测试，我们不仅能继续验证可视化功能，还能确保我们的测试套件本身就是新 API 的正确使用范例。

### 目标
1.  修改 `test_visualize_iterative_jump_edge` 函数。
2.  将 `cs.select_jump` 的定义从 `{"next": state_machine}` 更改为 `{"next": start_node}`，其中 `start_node` 是我们希望循环跳转到的 `LazyResult` 实例。

### 基本原理
为了在图中创建一个自引用的循环，`select_jump` 的目标必须是图中已经存在的节点。在我们的测试场景中，`start_node` (即 `state_machine(0)`) 就是这个节点。通过将 `start_node` 自身作为 `next` 键的目标，我们正确地声明了一个状态机，其中 "next" 状态就是重新执行状态机本身（但带有新数据）。此修正将使图构建成功，从而允许我们真正地测试 `visualize.py` 的渲染逻辑。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/visualization #task/object/explicit-jumps #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 `test_visualize.py` 中错误的跳转目标

我们将 `patch` 测试文件，将传递给 `select_jump` 的 `Task` 对象替换为正确的 `LazyResult` 实例。

~~~~~act
patch_file
tests/sdk/tools/test_visualize.py
~~~~~
~~~~~python
    # The selector maps jump keys to their target LazyResults
    selector = cs.select_jump(
        {
            "next": state_machine,  # A jump to "next" re-invokes the same task
            None: None,  # A normal return value exits the loop
        }
    )
~~~~~
~~~~~python
    # The selector maps jump keys to their target LazyResults
    # The target MUST be a LazyResult instance, not a raw Task.
    # To create a loop, we point it back to the start_node itself.
    start_node = state_machine(0)

    selector = cs.select_jump(
        {
            "next": start_node,  # A jump to "next" re-invokes the same task
            None: None,  # A normal return value exits the loop
        }
    )

    # Initial call to the task, starting the state machine
    # start_node = state_machine(0) <-- This is now defined before selector

    # Statically bind the task's jump signals to the selector
    cs.bind(start_node, selector)
~~~~~
~~~~~act
patch_file
tests/sdk/tools/test_visualize.py
~~~~~
~~~~~python
    # Initial call to the task, starting the state machine
    start_node = state_machine(0)

    # Statically bind the task's jump signals to the selector
    cs.bind(start_node, selector)
~~~~~
~~~~~python
    # Statically bind the task's jump signals to the selector
    cs.bind(start_node, selector)
~~~~~

### 下一步建议
我们已经修复了测试用例本身的问题。现在，请重新运行测试。如果测试通过，说明我们之前对 `visualize.py` 的修改是正确的，我们可以继续进行 `[COMMIT]` 计划。如果测试仍然失败，但出现了新的、与渲染相关的断言错误，那也意味着我们已经进入了 TDD 的正确轨道。
