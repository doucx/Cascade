好的，我们正式进入 RED 阶段。

我将生成一个计划，该计划的唯一目的是向现有的测试文件 `tests/engine/runtime/test_explicit_control_flow.py` 中添加一个新的、注定会失败的测试用例。这个测试用例将精确地模拟我们刚刚讨论的 “下游节点返回 Jump 信号” 的场景，从而暴露当前实现的架构缺陷。

## [WIP] test: 添加下游节点返回 Jump 信号的失败测试

### 用户需求
为了驱动下一轮重构，需要创建一个新的测试用-例，该用例会因为 `GraphExecutionStrategy` 无法处理来自非根节点的 `Jump` 信号而失败，并产生一个可预期的 `RuntimeError`。

### 评论
这是一个完美的“红灯”测试。它精确地靶向了我们识别出的架构弱点——上下文丢失。通过创建一个能够稳定复现这个 `RuntimeError` 的测试，我们为接下来的 GREEN 阶段（即实施 `GraphExecutionResult` 重构）设置了一个清晰、无歧义的成功标准。

### 目标
1.  在 `tests/engine/runtime/test_explicit_control_flow.py` 中添加一个名为 `test_explicit_jump_from_downstream_task` 的新测试。
2.  该测试将构建一个两层的工作流：一个 `main_task` 调用一个 `decider_task`。
3.  `Jump` 信号由下游的 `decider_task` 返回。
4.  `cs.bind` 调用将绑定在 `decider_task` 上。
5.  断言该工作流会因为引擎无法在 `decider_task` 节点上找到跳转边而失败。

### 基本原理
当前的 `GraphExecutionStrategy` 在收到 `Jump` 信号时，错误地假设信号来源于当前执行步骤的根节点 (`current_target`)。本测试通过构建一个 `main_task -> decider_task` 的图，并让 `decider_task` 返回 `Jump`，来打破这一假设。

由于 `bind` 是正确地绑定在 `decider_task` 上的，图本身是正确的。但引擎的运行时逻辑会错误地在 `main_task` 上寻找跳转边，导致查找失败，从而触发我们预期的 `RuntimeError`。这个失败将驱动我们重构 `_execute_graph` 的返回契约。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #comp/engine #concept/state #concept/navigation #scope/core #ai/instruct #task/domain/engine #task/object/control-flow #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 添加暴露架构缺陷的测试用例

我们将通过 `patch_file` 在 `test_explicit_control_flow.py` 的末尾追加一个新的测试函数。

~~~~~act
patch_file
tests/engine/runtime/test_explicit_control_flow.py
~~~~~
~~~~~python
    # The loop should terminate when n is 0, and the data from the final
    # jump signal (n=0) should be the return value.
    assert final_result == 0
~~~~~
~~~~~python
    # The loop should terminate when n is 0, and the data from the final
    # jump signal (n=0) should be the return value.
    assert final_result == 0


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

### 下一步建议
我们已经成功地创建了一个测试用例来复现架构缺陷，代码库现在处于明确的 RED 状态。

下一步，我们将进入 GREEN 阶段。我将生成一个新计划，通过实施 `GraphExecutionResult` 重构方案来修复这个问题，其核心是修改 `_execute_graph` 的返回契约，使其能够将 `source_node_id` 传递回主执行循环。这将使新旧两个测试都通过。
