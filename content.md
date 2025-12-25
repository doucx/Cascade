好的，我们开始实施“关于引入‘计算与 IO 隔离’调度语法糖的建议书”中提出的改进。

这是一个重要的架构升级，旨在通过自动将同步阻塞任务卸载到线程池，来防止它们阻塞核心事件循环，从而显著提升开发者体验 (DX) 和运行时性能。

我将严格遵循 TDD (测试驱动开发) 流程。第一步是创建一个新的测试文件，并编写一个明确的、当前会失败的测试用例。这个测试用例将精确地描述我们期望实现的行为：一个同步阻塞任务不应阻塞并发的异步任务。

## [WIP] feat: 为同步任务实现隐式线程卸载

### 用户需求
根据建议书的第一点，实现对同步 (`def`) 任务的“隐式卸载”。框架应能自动识别同步任务，并将其执行过程移至独立的线程中，以避免阻塞 `asyncio` 事件循环。

### 评论
这是对 Cascade 核心调度逻辑的一次关键增强。它解决了 Python 异步编程中的一个普遍痛点，使得开发者可以自然地混合使用同步和异步代码，而无需手动管理线程池。这使得框架更加智能、健壮，也更符合直觉。

### 目标
1.  创建一个新的测试文件 `tests/engine/e2e/test_offloading.py`。
2.  在该文件中，编写一个名为 `test_sync_task_offloading_prevents_blocking` 的测试用例。
3.  此测试用例将定义一个同步的、使用 `time.sleep` 的阻塞任务和一个普通的异步任务。
4.  它将断言异步任务的完成时间早于同步任务，并且总执行时间证明了它们是并行运行的。
5.  在当前的代码实现下，此测试**必须失败**，从而为我们的 TDD 流程建立一个清晰的“RED”状态。

### 基本原理
我们遵循 TDD 的“红-绿-重构”循环。第一步（RED）至关重要，它要求我们首先定义“完成”的标准。通过编写一个失败的测试，我们精确地捕获了当前系统不符合预期的行为（即事件循环被阻塞）。这个测试将成为后续代码修改的最终验证标准。只有当这个测试通过时，我们才能确定新功能已正确实现。

### 标签
#intent/build #intent/tooling #flow/ready #priority/high #comp/engine #comp/spec #comp/tests #concept/executor #scope/dx #ai/instruct #task/domain/testing #task/object/offloading-feature #task/action/tdd-setup #task/state/begin

---

### Script

#### Acts 1: 创建 TDD 测试文件

我将创建新的测试文件 `tests/engine/e2e/test_offloading.py`，其中包含一个用于验证同步任务卸载功能的、当前注定会失败的测试。

~~~~~act
write_file
tests/engine/e2e/test_offloading.py
~~~~~
~~~~~python
import asyncio
import time
import pytest
from cascade import task


@task(pure=True)
def blocking_sync_task(duration: float) -> float:
    """一个同步任务，通过 time.sleep 模拟一个阻塞的 CPU 密集型或 IO 操作。"""
    time.sleep(duration)
    return time.time()


@task(pure=True)
async def non_blocking_async_task() -> float:
    """一个异步任务，它应该能够并发执行。"""
    # 睡眠0秒以确保它能将控制权交还给事件循环
    await asyncio.sleep(0)
    return time.time()


@pytest.mark.asyncio
async def test_sync_task_offloading_prevents_blocking():
    """
    测试一个同步的阻塞任务是否被卸载到线程中，
    从而允许其他异步任务并发执行而不会被阻塞。

    此测试在功能实现前会失败，因为同步任务会阻塞整个事件循环，
    导致异步任务在其完成后才能执行。
    """
    from cascade.runtime.engine import Engine
    from cascade.runtime.bus import MessageBus
    from cascade.adapters.solvers.native import NativeSolver
    from cascade.adapters.executors.local import LocalExecutor

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),  # 使用一个静默的总线以保持测试输出干净
    )

    # 这两个任务彼此独立，应该并行运行。
    # 理想情况下，异步任务会立即执行，而同步任务会在一个独立的线程中阻塞。
    sync_result_lr = blocking_sync_task(0.2)
    async_result_lr = non_blocking_async_task()

    # 工作流的目标是这两个任务的结果列表。
    workflow = [sync_result_lr, async_result_lr]

    start_time = time.time()
    results = await engine.run(workflow)
    end_time = time.time()

    # 从结果中解包完成时间
    sync_finish_time, async_finish_time = results
    total_duration = end_time - start_time

    # 核心断言：
    # 1. 异步任务的完成时间戳应该小于同步任务的完成时间戳。
    #    (当前会失败，因为同步任务阻塞了事件循环)
    assert async_finish_time < sync_finish_time

    # 2. 总运行时间应该略大于阻塞任务的持续时间，证明它们是并行运行的。
    #    (当前会失败，因为总时间约等于两者之和)
    assert 0.2 < total_duration < 0.25
~~~~~

### 下一步建议
我们已经成功创建了失败的测试用例 (RED 状态)。下一步是修改 `cascade-spec` 和 `cascade-engine` 的代码，以实现隐式卸载逻辑，最终使这个测试通过 (GREEN 状态)。

具体的修改将涉及：
1.  在 `cascade.spec.task.Task` 类中，增加一个标志来识别函数是同步还是异步。
2.  修改 `cascade.adapters.executors.local.LocalExecutor`，使其在执行同步任务时，使用 `asyncio.to_thread` 将其调用包装起来。

如果你同意，我将生成下一个计划来执行这些代码修改。
