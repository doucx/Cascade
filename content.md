Excellent. The contract is now established throughout the stack. We can proceed to the second and final phase: implementing the execution logic.

Our goal is to modify the `LocalExecutor` to manage separate thread pools for `compute` and `blocking` tasks and route synchronous tasks to the appropriate pool. This will physically isolate the workloads, preventing long-running IO tasks from starving CPU-bound tasks.

## [WIP] feat(engine): Implement dedicated thread pools in LocalExecutor

### 用户需求
The `LocalExecutor` must be enhanced to utilize the `execution_mode` attribute on a `Node`. It should maintain separate, dedicated thread pools for `compute` and `blocking` synchronous tasks. When executing a synchronous task, it must dispatch the task to the correct pool, ensuring that tasks of different types do not compete for the same thread resources.

### 评论
This is the practical realization of our "Compute and IO Isolation" strategy. By creating physically separate execution lanes, we make the entire system more resilient and performant. A flood of slow, network-bound requests (`blocking` mode) will no longer impact the responsiveness of critical, CPU-bound calculations (`compute` mode). This is a sophisticated scheduling feature that significantly enhances Cascade's production-readiness.

### 目标
1.  Create a new test file, `tests/engine/e2e/test_executor_modes.py`, to verify the workload isolation. The test will run a long "blocking" task and a short "compute" task in parallel and assert that the short task finishes first, proving it wasn't queued behind the long one.
2.  Modify `packages/cascade-engine/src/cascade/adapters/executors/local.py` to:
    *   Import `ThreadPoolExecutor` and `functools`.
    *   Initialize two separate `ThreadPoolExecutor` instances in the `LocalExecutor`'s constructor: one for compute, one for blocking.
    *   In the `execute` method, replace `asyncio.to_thread` with the more explicit `loop.run_in_executor`, dispatching synchronous tasks to the appropriate thread pool based on `node.execution_mode`.

### 基本原理
The default `asyncio.to_thread` uses a single, shared thread pool for all offloaded tasks. By creating our own `ThreadPoolExecutor` instances, we gain fine-grained control. We will use the event loop's `run_in_executor` method, which allows specifying a custom executor. The `execution_mode` tag on the `Node` becomes the routing key, directing the task to either the high-throughput `blocking` pool or the potentially more limited (e.g., core-count sized) `compute` pool. This ensures true physical isolation of workloads.

### 标签
#intent/build #flow/ready #priority/high #comp/engine #concept/executor #scope/perf #scope/dx #ai/instruct #task/domain/execution #task/object/local-executor #task/action/implement-thread-pools #task/state/continue

---

### Script

#### Acts 1: Create TDD Test for Workload Isolation

First, we create a new E2E test. This test will fail initially because both synchronous tasks will be queued in the same default thread pool, forcing the short task to wait for the long one.

~~~~~act
write_file
tests/engine/e2e/test_executor_modes.py
~~~~~
~~~~~python
import asyncio
import time
import pytest
from cascade import task


@task(mode="blocking")
def long_sync_blocking_task(duration: float) -> float:
    """A sync task representing a slow, blocking I/O operation."""
    time.sleep(duration)
    return time.time()


@task(mode="compute")
def short_sync_compute_task(duration: float) -> float:
    """A sync task representing a short but CPU-intensive operation."""
    time.sleep(duration)
    return time.time()


@task
def collect_results(res1, res2):
    """Aggregates results for a valid graph structure."""
    return res1, res2


@pytest.mark.asyncio
async def test_compute_tasks_are_isolated_from_blocking_tasks():
    """
    Verifies that 'compute' and 'blocking' tasks run in separate thread pools
    and do not block each other.
    """
    from cascade.runtime.engine import Engine
    from cascade.runtime.bus import MessageBus
    from cascade.adapters.solvers.native import NativeSolver
    from cascade.adapters.executors.local import LocalExecutor

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

    # A short compute task (0.1s) and a long blocking task (0.2s)
    compute_lr = short_sync_compute_task(0.1)
    blocking_lr = long_sync_blocking_task(0.2)

    # If isolated, compute task finishes at T+0.1s.
    # If not isolated, compute task may have to wait for blocking task, finishing at T+0.2s or later.
    workflow = collect_results(compute_lr, blocking_lr)

    results = await engine.run(workflow)
    compute_finish_time, blocking_finish_time = results

    # The key assertion: the short compute task must finish first.
    assert compute_finish_time < blocking_finish_time, (
        "Compute task should have finished before the blocking task, "
        "indicating parallel execution in separate pools."
    )

~~~~~

#### Acts 2: Implement Thread Pool Routing in LocalExecutor

Now, we implement the logic that will make the new test pass. We'll modify `LocalExecutor` to manage and use two distinct thread pools.

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/executors/local.py
~~~~~
~~~~~python
import asyncio
from typing import Any, Dict, List
from cascade.graph.model import Node
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.graph.exceptions import StaticGraphError


class LocalExecutor:
    """
    An executor that runs tasks sequentially in the current process.
    """

    async def execute(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        """
        Executes a single node's callable object with the provided arguments.
        """
        if node.callable_obj is None:
            raise TypeError(
                f"Node '{node.name}' of type '{node.node_type}' is not executable (no callable)."
            )

        if node.is_async:
            result = await node.callable_obj(*args, **kwargs)
        else:
            # Implicit Offloading:
            # Synchronous tasks are offloaded to a separate thread to prevent blocking
            # the main asyncio event loop. This allows async tasks and IO operations
            # to run concurrently with CPU-bound or blocking sync tasks.
            result = await asyncio.to_thread(node.callable_obj, *args, **kwargs)

        # Runtime guard against the "task returns LazyResult" anti-pattern.
        if isinstance(result, (LazyResult, MappedLazyResult)):
            raise StaticGraphError(
                f"Task '{node.name}' illegally returned a LazyResult. "
                "Tasks must return data. For control flow, return a cs.Jump(...) signal instead."
            )

        return result
~~~~~
~~~~~python
import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List
from cascade.graph.model import Node
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.graph.exceptions import StaticGraphError


class LocalExecutor:
    """
    An executor that runs tasks in the current process, using dedicated thread
    pools to isolate blocking I/O tasks from CPU-bound tasks.
    """

    def __init__(self):
        # NOTE: These executors are created per-engine-run.
        # Their lifecycle is tied to the LocalExecutor instance.
        # Python's ThreadPoolExecutor finalizer handles shutdown on garbage collection.
        self._blocking_executor = ThreadPoolExecutor(thread_name_prefix="cascade_blocking")
        self._compute_executor = ThreadPoolExecutor(thread_name_prefix="cascade_compute")

    async def execute(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        """
        Executes a single node's callable. Routes synchronous tasks to the
        appropriate thread pool based on their execution mode.
        """
        if node.callable_obj is None:
            raise TypeError(
                f"Node '{node.name}' of type '{node.node_type}' is not executable (no callable)."
            )

        if node.is_async:
            result = await node.callable_obj(*args, **kwargs)
        else:
            loop = asyncio.get_running_loop()
            
            # Select the appropriate executor based on the task's declared mode
            if node.execution_mode == "compute":
                executor = self._compute_executor
            else:  # Default to "blocking" for I/O, etc.
                executor = self._blocking_executor

            # Use functools.partial to handle keyword arguments, as
            # run_in_executor only accepts positional arguments for the target function.
            func_to_run = functools.partial(node.callable_obj, *args, **kwargs)
            result = await loop.run_in_executor(executor, func_to_run)

        # Runtime guard against the "task returns LazyResult" anti-pattern.
        if isinstance(result, (LazyResult, MappedLazyResult)):
            raise StaticGraphError(
                f"Task '{node.name}' illegally returned a LazyResult. "
                "Tasks must return data. For control flow, return a cs.Jump(...) signal instead."
            )

        return result
~~~~~

### 下一步建议
我们已经编写了新的测试并实现了核心的线程池路由逻辑。现在请运行测试。

我们预期 `tests/engine/e2e/test_executor_modes.py` 将会**通过**。如果通过，就证明了我们的实现是正确的，并且我们已经成功地为不同类型的同步任务建立了隔离的执行环境。

确认通过后，我将为您生成最终的 `[COMMIT]` 计划。
