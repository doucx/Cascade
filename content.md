好的，我将遵循 TDD 流程，生成创建新测试文件的计划。这个计划将引入使用尚未存在的 `cs.Jump`, `cs.select_jump`, 和 `cs.bind` API 的测试用例，从而将我们的开发环境置于 RED 状态。

## [WIP] test: 为显式控制流原语添加失败的测试

### 用户需求
严格遵循 TDD 流程，为“阶段一：引入显式状态转移原语”创建第一个测试文件。这个文件需要定义一个使用 `cs.Jump`, `cs.select_jump`, 和 `cs.bind` 的测试用例，并且这个测试目前必须是失败的（RED 状态）。

### 评论
这是一个完美的 TDD 开端。通过先编写测试，我们不仅明确了最终要实现的 API 接口和行为，还为后续的开发工作提供了一个清晰、可验证的目标。这个测试将成为我们实现新控制流模型的驱动力。

### 目标
1.  创建一个新的测试文件 `tests/engine/runtime/test_explicit_control_flow.py`。
2.  在该文件中，编写一个名为 `test_explicit_jump_loop` 的异步测试用例。
3.  此测试用例将定义一个简单的计数器循环，该循环从 5 倒数到 0。
4.  测试将使用尚不存在的 `cs.Jump`, `cs.select_jump`, `cs.bind` 来构建循环，并断言最终结果为 0。

### 基本原理
此计划的目的是在不动任何生产代码的情况下，建立一个失败的测试基线。这个“失败”是预期的，它将由 `ImportError`（因为 API 不存在）或 `AttributeError` 引起。一旦这个测试文件被创建，我们的下一个任务就是让这个测试通过（进入 GREEN 状态），从而确保我们的 TDD 流程是完整的。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #comp/engine #concept/state #concept/navigation #scope/dx #ai/instruct #task/domain/engine #task/object/control-flow #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 创建失败的测试文件

我们将创建 `tests/engine/runtime/test_explicit_control_flow.py` 文件。它包含一个完整的测试用例，该用例描述了我们期望的新 API 如何协同工作以创建一个显式的、高性能的循环。

~~~~~act
write_file
tests/engine/runtime/test_explicit_control_flow.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver


@pytest.mark.asyncio
async def test_explicit_jump_loop():
    """
    Tests the core explicit state transition mechanism.
    - A task returns a `cs.Jump` signal.
    - `cs.bind` statically connects the task to a `cs.select_jump` chooser.
    - The engine interprets the jump and reschedules the next task with new data,
      bypassing graph rebuilding.
    """

    @cs.task
    def counter(n: int):
        if n <= 0:
            # On terminal condition, signal to exit the loop
            return cs.Jump(target_key="exit", data=n)
        else:
            # Signal to continue the loop, passing n-1 as the new input
            return cs.Jump(target_key="continue", data=n - 1)

    # Define the starting point of the loop
    loop_node = counter(5)

    # Define the jump selector, which maps keys from Jump signals to tasks
    jump_selector = cs.select_jump(
        {
            "continue": loop_node,  # "continue" jumps back to the start of the loop
            "exit": None,  # "exit" breaks the loop
        }
    )

    # Statically bind the control flow: the result of `loop_node` is routed
    # to the `jump_selector`. This creates a structural `ITERATIVE_JUMP` edge.
    cs.bind(loop_node, jump_selector)

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

    # The target is the loop_node itself. The engine should follow the jump
    # signals until the "exit" key is returned.
    final_result = await engine.run(loop_node)

    # The loop should terminate when n is 0, and the data from the final
    # jump signal (n=0) should be the return value.
    assert final_result == 0
~~~~~

### 下一步建议
我们已经成功创建了失败的测试用例，代码库现在处于 RED 状态。

下一步，我们将进入 GREEN 阶段。我将生成一个新的计划，其目标是：
1.  在 `cascade-spec` 包中创建 `cs.Jump` 数据类。
2.  创建 `cs.select_jump` 和 `cs.bind` 函数的存根（stub）。
3.  修改 `GraphBuilder` 以识别这些新原语并创建 `ITERATIVE_JUMP` 类型的边。
4.  修改 `GraphExecutionStrategy` 以便能够解释 `cs.Jump` 返回值并执行跳转。

这将使我们刚刚创建的测试通过。
