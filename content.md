好的，我们正式开始 **任务 1.3：实现物理执行接口**。

按照 TDD 流程，我们首先进入 **RED** 状态，通过编写测试来精确定义 `PhysicsExecutor` 的 API 和核心行为契约。

## [WIP] test(vm): 为 PhysicsExecutor 创建 TDD 单元测试

### 用户需求
为 `cascade-vm` 中的 `PhysicsExecutor` 创建单元测试，定义其 API 并验证其核心能力：异步地、非阻塞地将函数提交到线程池执行。

### 评论
`PhysicsExecutor` 是 `Reactor` 的“肌肉”。它的职责是将 `Reactor` 决定的计算任务（纯 Python 函数）安全地在后台线程中执行，并将结果或异常返回给 `Reactor`。本测试的核心是验证其 **非阻塞** 的契约：`submit` 调用必须立即返回，允许 `Reactor` 的主事件循环继续处理其他任务，这对于构建一个高并发的物理引擎至关重要。

### 目标
1.  创建 `test_executor.py` 文件。
2.  定义 `PhysicsExecutor` 的核心 API `submit(func, args)`。
3.  编写测试用例，验证：
    *   基本函数可以被正确执行并返回结果。
    *   耗时的阻塞函数 (`time.sleep`) 在后台执行，`submit` 调用本身不会阻塞事件循环。
    *   在工作线程中抛出的异常能被正确地传播回主调用方。
4.  创建一个空的 `PhysicsExecutor` 类，使测试失败 (RED)。

### 基本原理
我们将使用 `pytest.mark.asyncio` 来测试异步代码。对于非阻塞行为的验证，我们将提交一个带有 `time.sleep` 的函数，并测量 `submit` 调用本身消耗的时间（应接近于零）和任务完成的总时间（应接近于 `sleep` 的时长），以此来证明其异步性。

### 标签
#intent/tooling #flow/ready #priority/high #comp/vm #concept/executor #scope/core #ai/instruct #task/domain/vm #task/object/physics-executor #task/action/tdd #task/state/continue

---

### Script

#### Acts 1: 编写 PhysicsExecutor 单元测试

我们创建测试文件，定义 `PhysicsExecutor` 的行为契约。

~~~~~act
write_file
packages/cascade-vm/tests/unit/test_executor.py
~~~~~
~~~~~python
import pytest
import asyncio
import time
from typing import Callable, Any

from cascade.vm.executor import PhysicsExecutor

# --- Helper functions for testing ---

def add(x: int, y: int) -> int:
    """A simple, pure computation function."""
    return x + y

def blocking_io_simulation(duration: float) -> float:
    """Simulates a blocking I/O call like a network request or disk read."""
    time.sleep(duration)
    return duration

def raises_error():
    """A function that always fails."""
    raise ValueError("Task failed successfully")

# --- Tests ---

@pytest.mark.asyncio
async def test_executor_submit_simple_computation():
    """Verify that a simple function can be executed and its result returned."""
    executor = PhysicsExecutor()
    result = await executor.submit(add, (2, 3))
    assert result == 5

@pytest.mark.asyncio
async def test_executor_is_non_blocking():
    """
    Verify that submitting a blocking task does not block the main asyncio event loop.
    The `submit` call should return immediately.
    """
    executor = PhysicsExecutor()
    sleep_duration = 0.1

    start_time = time.monotonic()
    
    # Create a task for the long-running job
    exec_task = asyncio.create_task(
        executor.submit(blocking_io_simulation, (sleep_duration,))
    )
    
    # This point should be reached almost instantly
    time_after_submit = time.monotonic()
    
    # Yield control to allow the task to start
    await asyncio.sleep(0) 
    
    # Assert that the submit call itself was non-blocking
    assert (time_after_submit - start_time) < (sleep_duration / 2)
    
    # Now, await the actual result
    result = await exec_task
    end_time = time.monotonic()
    
    # Assert the task ran for the expected duration
    assert result == sleep_duration
    assert (end_time - start_time) >= sleep_duration

@pytest.mark.asyncio
async def test_executor_propagates_exceptions():
    """Verify that exceptions raised in the worker thread are re-raised in the caller."""
    executor = PhysicsExecutor()
    
    with pytest.raises(ValueError, match="Task failed successfully"):
        await executor.submit(raises_error, ())
~~~~~

#### Acts 2: 创建 API 桩文件 (Entering RED)

创建 `executor.py` 并定义 `PhysicsExecutor` 的空实现，以使测试失败。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/executor.py
~~~~~
~~~~~python
from typing import Callable, Any, Tuple
from concurrent.futures import ThreadPoolExecutor


class PhysicsExecutor:
    """
    Manages a thread pool to execute blocking or CPU-bound functions
    off the main asyncio event loop.
    """

    def __init__(self):
        # The executor will be created here, but the submit logic is missing.
        pass

    async def submit(self, func: Callable, args: Tuple) -> Any:
        """
        Submits a function to be run in a background thread.

        Args:
            func: The function to execute.
            args: A tuple of positional arguments for the function.

        Returns:
            The result of the function call.
        
        Raises:
            Exception: Any exception raised by the target function.
        """
        raise NotImplementedError
~~~~~

### 下一步建议

现在，运行 `pytest packages/cascade-vm/tests/unit/test_executor.py` 将会因为 `NotImplementedError` 而失败。

接下来的 **GREEN** 阶段任务是：
1.  在 `PhysicsExecutor.__init__` 中初始化一个 `concurrent.futures.ThreadPoolExecutor`。
2.  实现 `submit` 方法，使用 `asyncio.get_running_loop().run_in_executor()` 将函数和参数委托给线程池。
3.  确保测试通过。
