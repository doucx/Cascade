你的观察非常敏锐。

之前的测试失败原因分析有误。在阻塞模式下，`async` 任务确实是在 `sync` 任务完成后才执行的，但由于 `async` 任务使用了 `sleep(0)`，它几乎在 `sync` 任务返回后的瞬间就完成了。这导致两个时间戳极其接近，甚至可能因为系统调度的微小抖动导致顺序颠倒，从而使测试变得不可靠（Flaky）。

为了构建一个**确定性**的测试，我们需要引入显著的时间差，使得“串行执行”和“并行执行”在时间轴上呈现出截然不同的特征。

新的测试逻辑
1.  **Sync Task (Blocking)**: `time.sleep(0.2s)`.
2.  **Async Task (Non-blocking)**: `await asyncio.sleep(0.1s)`.

**预期行为分析**:
*   **当前 (Blocking)**:
    1.  Sync task 运行并阻塞 0.2s。
    2.  Sync task 完成。
    3.  Async task 开始，并等待 0.1s。
    4.  Async task 完成。
    *   **结果**: Async 结束时间 **晚于** Sync 结束时间。
*   **未来 (Offloaded)**:
    1.  Sync task (在线程中) 和 Async task (在循环中) 几乎同时开始。
    2.  Async task 在 0.1s 后完成。
    3.  Sync task 在 0.2s 后完成。
    *   **结果**: Async 结束时间 **早于** Sync 结束时间。

这将产生一个明确的、基于逻辑而非巧合的失败（RED）。

## [WIP] fix(test): Refactor offloading test for deterministic failure

### 用户需求
重新编写测试用例 `tests/engine/e2e/test_offloading.py`。
1.  使用显著的时间间隔（0.2s vs 0.1s）来区分串行和并行执行。
2.  将所有注释和文档字符串转换为英文。
3.  确保测试在当前（阻塞）架构下必然失败，且失败原因明确指向“异步任务完成得太晚”。

### 评论
这个修正案消除了测试中的不确定性。通过强制异步任务拥有一个比同步任务短、但非零的持续时间，我们建立了一个可靠的时序基准：只有当两者真正并行运行时，短任务才能先完成。

### 目标
1.  重写 `tests/engine/e2e/test_offloading.py`。
2.  验证测试失败，并确认失败原因是 `async_timestamp > sync_timestamp`（即串行执行）。

### 基本原理
TDD 的核心在于测试的**保真度**。一个依赖于微秒级差异的测试是不可信的。通过引入宏观的时间窗口（0.1s），我们将测试的信噪比提高到了可接受的范围，确保通过（GREEN）状态不仅仅是运气。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/offloading-feature #task/action/test-correction #task/state/continue

---

### Script

#### Acts 1: Overwrite the test file with robust logic and English comments

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
    """
    A synchronous task that blocks the thread using time.sleep.
    Represents a CPU-bound or blocking I/O operation.
    """
    time.sleep(duration)
    return time.time()


@task(pure=True)
async def non_blocking_async_task(duration: float) -> float:
    """
    An asynchronous task that yields control using asyncio.sleep.
    """
    await asyncio.sleep(duration)
    return time.time()


@task(pure=True)
def collect_results(sync_res, async_res):
    """
    Aggregates results to form a single target for the workflow.
    """
    return [sync_res, async_res]


@pytest.mark.asyncio
async def test_sync_task_offloading_prevents_blocking():
    """
    Verifies that synchronous blocking tasks are offloaded to a separate thread,
    allowing other async tasks to execute concurrently.

    FAILURE CONDITION (Current):
        Since offloading is not implemented, 'blocking_sync_task' will block the
        main event loop for 0.2s. 'non_blocking_async_task' will only start
        AFTER the sync task finishes.
        Result: async_task finishes AFTER sync_task.

    SUCCESS CONDITION (Expected):
        'blocking_sync_task' is offloaded. Both tasks start roughly at the same time.
        Since async task (0.1s) is shorter than sync task (0.2s), it should
        finish first.
        Result: async_task finishes BEFORE sync_task.
    """
    from cascade.runtime.engine import Engine
    from cascade.runtime.bus import MessageBus
    from cascade.adapters.solvers.native import NativeSolver
    from cascade.adapters.executors.local import LocalExecutor

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),  # Silent bus
    )

    # 1. Sync task takes 0.2s
    sync_result_lr = blocking_sync_task(0.2)
    # 2. Async task takes 0.1s
    async_result_lr = non_blocking_async_task(0.1)

    # If parallel: Async finishes at T+0.1, Sync at T+0.2
    # If serial: Sync finishes at T+0.2, Async starts then finishes at T+0.3

    workflow_target = collect_results(sync_result_lr, async_result_lr)

    start_time = time.time()
    results = await engine.run(workflow_target)
    end_time = time.time()

    sync_finish_time, async_finish_time = results
    total_duration = end_time - start_time

    # Assertion 1: The async task should finish BEFORE the sync task.
    # This proves they were running in parallel.
    assert async_finish_time < sync_finish_time, (
        f"Async task finished at {async_finish_time}, which is after Sync task {sync_finish_time}. "
        "This indicates sequential execution (loop blocked)."
    )

    # Assertion 2: Total duration should be close to the longest task (0.2s),
    # not the sum of both (0.3s).
    # We allow a small buffer for overhead (0.25s).
    assert total_duration < 0.25, (
        f"Total duration {total_duration}s exceeds expected parallel time. "
        "This indicates sequential execution."
    )
~~~~~

### 下一步建议
等待此测试运行。它应该会以一种非常明确的方式失败：`Async task finished at ..., which is after Sync task ...`。这将确认我们不仅修复了测试结构，而且准确地捕获了我们要解决的性能问题。

一旦确认失败，我将着手修改 `Task` 定义和 `LocalExecutor` 来使测试变绿。
