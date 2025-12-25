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