你的观察非常敏锐，两个测试都通过了。

**这不完全符合预期，但揭示了我们当前实现的一个重要特征：**

1.  `test_reactor_respects_resource_concurrency_limit` (Phase 4.1) 的通过是**符合预期的**。我们已经成功地在 `step()` 中加入了资源检查，阻止了任务的过载提交。
2.  `test_reactor_waits_for_resources_and_wakes_up` (Phase 4.2) 的通过是**偶然的，因为它依赖于测试本身的结构**。测试用例通过手动调用第二次 `reactor.step()` 来“轮询”`Reactor` 的状态，从而触发了对等待中任务的重新评估和调度。这在功能上是正确的，但效率低下，不符合我们对一个**主动的、事件驱动的物理引擎**的设想。

一个真正的 `Reactor` 不应该依赖外部调用 `step()` 来唤醒。当一个任务完成并释放资源时，`Reactor` 应该**内部地、主动地**意识到这一点，并立即重新评估等待队列，而不是进入休眠等待下一次外部“心跳”。

为了驱动这个更高级的实现，我们将创建一个新的、更严格的测试，它将不再手动调用第二次 `step()`。这个测试在当前实现下将会**失败 (RED)**，从而将我们带回 TDD 的正确轨道。

## [WIP] test(vm): add proactive reactor wakeup test

### 用户需求
当前 Phase 4.2 的测试由于测试用例的结构而通过，未能暴露 `Reactor` 缺乏主动唤醒机制的缺陷。需要创建一个新的、更严格的测试，使我们重新进入 RED 状态，以驱动一个真正的事件驱动唤醒逻辑的实现。

### 评论
这是一个关键的架构精炼步骤。当前的实现是“被动”的，它依赖外部循环来重新评估待定任务。新的测试将强制 `Reactor` 变得“主动”：当资源被释放时，它必须有能力自我唤醒并立即调度下一个合适的任务，而不是等待外部的下一个 `step()` 调用。这将使 `Reactor` 成为一个真正独立的、高效的物理引擎。

### 目标
1.  创建一个新的测试文件 `packages/cascade-vm/tests/reactor/test_reactor_wakeup_mechanism.py`。
2.  在其中编写一个测试用例，该用例只调用一次 `reactor.step()`，并依赖 `Reactor` 的内部逻辑来完成对第二个任务的调度。
3.  该测试将通过 `asyncio.Event` 等待第二个任务被提交，如果 `Reactor` 没有主动唤醒逻辑，测试将超时失败。

### 基本原理
我们通过模拟一个极快的任务来创造一个竞争条件：第一个任务在 `step()` 循环内部完成并释放资源。一个高效的 `Reactor` 应该能在同一个 `step()` 周期内捕获这个变化并调度下一个任务。新的测试通过移除外部的轮询调用 (`step()`)，精确地暴露了当前实现中缺失的内部循环/触发机制。

### 标签
#intent/tooling #intent/architect #flow/draft #priority/high #comp/tests #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/runtime #task/object/reactor #task/action/refine #task/state/continue

---

### Script

#### Acts 1: 创建主动唤醒机制的测试文件

这个新的测试将取代 `test_reactor_waits_for_resources_and_wakes_up` 作为 Phase 4.2 的主要驱动力。它更严格地定义了“唤醒”的行为。

~~~~~act
write_file
packages/cascade-vm/tests/reactor/test_reactor_wakeup_mechanism.py
~~~~~
~~~~~python
import pytest
import asyncio
from unittest.mock import AsyncMock

from cascade.spec.physics import DataNode, FuncNode, Token, Port
from cascade.vm.reactor import Reactor, TokenGenerated, ExecutionFinished
from cascade.runtime.resource_manager import ResourceManager


def create_topology(n_nodes: int):
    """Creates a simple fan-out topology."""
    nodes, inputs = [], []
    for i in range(n_nodes):
        f_node = FuncNode(name=f"task_{i}", resource_requirements={"slots": 1})
        d_in = DataNode(name=f"in_{i}")
        f_node.add_input(Port(name="arg", source=d_in))
        nodes.append(f_node)
        inputs.append(d_in)
    return nodes, inputs


@pytest.mark.asyncio
async def test_reactor_proactively_wakes_up_on_resource_release():
    """
    Phase 4.2 TDD (Strict): Reactor must wake up internally, not via polling.

    This test calls `step()` only ONCE. It simulates a fast task that
    finishes and emits an ExecutionFinished event *during* the initial step.
    A truly event-driven reactor should process this new event and schedule
    the next pending task without needing another external `step()` call.
    """
    rm = ResourceManager(capacity={"slots": 1})
    mock_executor = AsyncMock()

    # Synchronization primitive: this event is set when the SECOND task is submitted
    second_task_submitted = asyncio.Event()

    # --- Mock Executor Side Effect ---
    # This is the core of the test's strictness.
    # When the first task is submitted, it immediately pushes its own "Finished" event back.
    # When the second task is submitted, it signals the test to finish.
    async def executor_side_effect(node, inputs):
        if mock_executor.submit.call_count == 1:
            # First task: immediately signal completion
            # This pushes an event into the queue WHILE a step() is active.
            reactor.push_event(ExecutionFinished(node=node, outputs={}))
        elif mock_executor.submit.call_count == 2:
            # Second task: signal success to the test harness
            second_task_submitted.set()

    mock_executor.submit.side_effect = executor_side_effect
    # ---

    reactor = Reactor(executor=mock_executor, resource_manager=rm)

    # 1. Setup A and B
    func_nodes, data_nodes = create_topology(2)
    for n in func_nodes + data_nodes:
        reactor.register_node(n)

    # 2. Trigger both tasks to be ready
    for d in data_nodes:
        reactor.push_event(TokenGenerated(node=d, token=Token(1)))

    # 3. Action: Call step() only ONCE.
    # Expected internal flow:
    # - step() starts.
    # - Processes TokenGenerated events. Both A and B are now data-ready.
    # - Fires task A. B becomes pending.
    # - `executor.submit(A)` is called.
    # - Side effect triggers, pushing `ExecutionFinished(A)` into the event queue.
    # - A truly event-driven reactor would re-loop, process this event, release
    #   resources, and re-evaluate pending tasks, thus firing B.
    # - `executor.submit(B)` is called.
    # - Side effect triggers, setting `second_task_submitted`.
    await reactor.step()

    # 4. Assertion: Wait for the event signaling the second task was submitted.
    # The current implementation will fail here (timeout) because it finishes the
    # `step()` after submitting task A and does not re-process the new event.
    try:
        await asyncio.wait_for(second_task_submitted.wait(), timeout=0.5)
    except asyncio.TimeoutError:
        pytest.fail(
            "Reactor did not proactively wake up and schedule the second task. "
            f"Only {mock_executor.submit.call_count} task(s) were submitted."
        )

    assert mock_executor.submit.call_count == 2
~~~~~

### 下一步建议
我们现在有了一个会失败的、定义了更高级行为的测试。`test_reactor_proactively_wakes_up_on_resource_release` 将会因为 `asyncio.TimeoutError` 而失败，标志着我们进入了 Phase 4.2 的 **RED** 状态。

下一步是修改 `Reactor` 的 `step()` 方法，使其包含一个内部循环，只要事件队列非空或有状态变更，就持续处理，直到达到一个稳定的不动点。这将使其从一个单次心跳的执行器演变为一个自我维持的反应循环。
