你说得完全正确。

我为之前的错误操作道歉。我错误地编写了一个“断言失败”的测试，它在代码有缺陷时通过了，这违背了 TDD 的核心原则。一个真正的 RED 测试应该是在代码有缺陷时**失败**，而不是在有缺陷时**通过**。我制造了一个“假阴性”的绿色状态，这掩盖了问题，而不是暴露它。

感谢你的纠正。我现在将修正这个错误。我将重写这个测试，使其断言**正确的最终行为**。这样，在当前有缺陷的代码下，它会因为未捕获的 `RuntimeError` 而失败，从而将我们的测试套件置于一个真正的、字面意义上的 **RED** 状态。

## [WIP] fix(test): 修正下游跳转测试以断言成功，进入 RED 状态

### 错误分析
上一个计划中创建的测试 `test_explicit_jump_from_downstream_task_fails_as_expected` 是一个 TDD 反模式。它通过 `pytest.raises` 来断言一个已知的 `RuntimeError`，导致测试在代码存在缺陷的情况下反而显示为 `PASSED`。一个正确的 TDD 测试应该断言期望的**成功**结果，并在代码有缺陷时因为异常或断言失败而明确地 `FAILED`。

### 用户需求
修改 `test_explicit_jump_from_downstream_task_fails_as_expected` 测试，移除 `pytest.raises`，并改为断言工作流的最终正确输出结果。这将使测试套件进入一个真正的 RED 状态，为后续的修复工作提供一个明确的目标。

### 评论
这是一个关键的流程修正。通过将测试的目的从“证明存在一个 bug”转变为“定义正确的行为”，我们回到了 TDD 的正轨。现在，这个测试的失败将直接、无歧义地告诉我们 `GraphExecutionStrategy` 的上下文丢失问题尚未解决。

### 目标
1.  重命名测试函数为 `test_explicit_jump_from_downstream_task`。
2.  移除 `with pytest.raises(...)` 上下文管理器。
3.  捕获 `engine.run` 的返回值。
4.  在测试末尾添加 `assert final_result == 0`，断言循环的正确最终结果。

### 基本原理
通过断言最终状态（`final_result == 0`），我们为引擎的行为定义了一个清晰的契约：无论 `Jump` 信号来自何处，引擎都必须正确地路由控制流并完成循环。在当前的代码实现下，这个测试会因为未处理的 `RuntimeError` 而中断并失败，这正是 TDD 流程中一个有效的 RED 信号。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/tdd-process #task/action/correction #task-state/continue

---

### Script

#### Acts 1: 将测试修正为断言成功

我们将使用 `patch_file` 替换整个函数，将其从一个“期望失败”的测试改为一个“期望成功”的测试。

~~~~~act
patch_file
tests/engine/runtime/test_explicit_control_flow.py
~~~~~
~~~~~python
@pytest.mark.asyncio
async def test_explicit_jump_from_downstream_task_fails_as_expected():
    """
    This test is designed to FAIL with the current architecture to prove a flaw.
    The Jump signal is returned by a downstream task (`decider`), not the
    graph root (`main_task`). The engine is expected to lose context and fail
    to find the ITERATIVE_JUMP edge, which is correctly bound to `decider`.
    """

    @cs.task
    def decider(n: int):
        if n <= 0:
            return cs.Jump(target_key="exit", data=n)
        else:
            return cs.Jump(target_key="continue", data=n - 1)

    @cs.task
    def main_task(n: int):
        # This task delegates the jump decision to a downstream task
        return decider(n)

    # The jump selector's target must be the task that receives the new data
    loop_node = decider(cs.Param("next_n"))

    jump_selector = cs.select_jump(
        {
            "continue": loop_node,
            "exit": None,
        }
    )

    # CRITICAL: The binding is correctly placed on the task that returns the Jump signal.
    cs.bind(loop_node, jump_selector)

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

    # We run the main_task, which is the root of the graph for this step.
    # The engine is expected to fail because it will look for a jump edge on
    # `main_task`'s node, not on `decider`'s node.
    with pytest.raises(
        RuntimeError,
        match="Task returned a Jump signal but has no bound 'select_jump'",
    ):
        await engine.run(main_task(3))
~~~~~
~~~~~python
@pytest.mark.asyncio
async def test_explicit_jump_from_downstream_task():
    """
    Tests that the engine can correctly handle a Jump signal that originates
    from a downstream task, not the root of the execution graph for that step.
    """

    @cs.task
    def decider(n: int):
        if n <= 0:
            return cs.Jump(target_key="exit", data=n)
        else:
            return cs.Jump(target_key="continue", data=n - 1)

    @cs.task
    def main_task(n: int):
        # This task delegates the jump decision to a downstream task
        return decider(n)

    # The jump selector's target must be the task that receives the new data.
    # Here, 'decider' is the task that gets re-invoked with new data.
    loop_node = decider(cs.Param("next_n"))

    jump_selector = cs.select_jump(
        {
            "continue": loop_node,
            "exit": None,
        }
    )

    # CRITICAL: The binding is correctly placed on the task that returns the
    # Jump signal (`decider`), which is instantiated here as `loop_node`.
    cs.bind(loop_node, jump_selector)

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

    # We run the main_task. The engine must be smart enough to identify that
    # the Jump signal came from `decider` and find the binding there.
    final_result = await engine.run(main_task(3))

    assert final_result == 0
~~~~~

### 下一步建议
我们已经将测试修正为正确的 TDD 形式。现在，当您运行测试时，它应该会因为未捕获的 `RuntimeError` 而失败，从而使测试套件进入一个真正的 RED 状态。

下一步，我们将进入 GREEN 阶段。我将生成一个新计划，通过实施 `GraphExecutionResult` 重构方案来修复这个问题，让两个测试都通过。
