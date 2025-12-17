Your analysis is spot on. The test failures are a classic case of trying to start a new asyncio event loop from within an already running one.

Here is my analysis of the error and the plan to fix it.

### 错误分析

**根本原因**: `pytest-asyncio` 与 `cs.run` 的冲突。

1.  **`pytest-asyncio` 的工作方式**: 当你使用 `@pytest.mark.asyncio` 装饰一个测试函数时，`pytest-asyncio` 插件会负责创建一个 asyncio 事件循环，并在这个循环中运行你的 `async def` 测试函数。
2.  **`cs.run` 的工作方式**: `cs.run` 是一个为最终用户设计的高级便捷函数。它的核心职责是**创建并管理一个全新的事件循环**来运行 Cascade 工作流，这通过调用 `asyncio.run()` 实现。
3.  **冲突点**: 在测试函数执行时，我们已经处于一个由 `pytest-asyncio` 管理的事件循环中。此时调用 `cs.run()`，它又试图调用 `asyncio.run()` 来创建一个新的事件循环。Asyncio 规范明确禁止在同一个线程中从一个正在运行的循环内部启动另一个循环，因此抛出了 `RuntimeError: asyncio.run() cannot be called from a running event loop`。

**解决方案**:

在异步测试环境中，我们不应该使用 `cs.run()` 这个高级封装。我们应该直接与 `cascade.Engine` 交互，并使用 `await` 在 `pytest-asyncio` 提供的现有事件循环中执行工作流。

此外，在 `test_prompt_composition` 测试中，为了确保 `read` 操作在 `write` 操作之后执行，原测试试图创建一个 `read_after_write` 任务。这种方式是正确的，但其实现返回了一个 `LazyResult`，这是不合法的。一个标准的 `@cs.task` 必须返回一个具体的、可序列化的值，而不是另一个 `LazyResult`。

我们将通过一个小幅改进 `_stdin_read_line_task` 来解决这个问题，使其能够接受一个哑元（dummy）参数，从而允许我们以一种更清晰、更直接的方式建立数据依赖，以确保执行顺序。

### 目标
1.  修改 `_stdin_read_line_task` 任务，使其可以接受一个位置参数，从而能够通过数据依赖来强制执行顺序。
2.  重写 `tests/providers/test_stdio.py` 中的所有测试用例，使用 `await engine.run()` 代替 `cs.run()`，并在 `test_prompt_composition` 中使用新的依赖模式。

### 基本原理
我们将直接实例化 `cascade.Engine` 并 `await` 其 `.run()` 方法，使其在 `pytest-asyncio` 管理的事件循环中正确执行。对于 `test_prompt_composition`，我们将利用数据依赖这一 Cascade 核心机制来确保 `write` 操作先于 `read` 操作，通过将 `write` 任务的结果传递给 `read` 任务。

### 标签
#intent/fix #flow/ready #priority/high #comp/core #comp/tests #concept/io #scope/dx #ai/instruct #task/domain/core #task/object/stdio-providers #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 改进标准输入 Provider 以支持依赖

我们将修改 `src/cascade/providers/stdio.py` 中的 `_stdin_read_line_task`，为其添加一个哑元位置参数。这个改动是向后兼容的，但极大地增强了它的可组合性。

~~~~~act
patch_file
src/cascade/providers/stdio.py
~~~~~
~~~~~python
@task(name="stdin_read_line")
async def _stdin_read_line_task() -> str:
    """Reads a single line from standard input."""
    def blocking_read():
        return sys.stdin.readline().strip()
    return await asyncio.to_thread(blocking_read)
~~~~~
~~~~~python
@task(name="stdin_read_line")
async def _stdin_read_line_task(*_args) -> str:
    """
    Reads a single line from standard input.
    Accepts positional arguments to allow data dependencies for ordering.
    """
    def blocking_read():
        return sys.stdin.readline().strip()
    return await asyncio.to_thread(blocking_read)
~~~~~

#### Acts 2: 修正测试文件

现在，我们将重写 `tests/providers/test_stdio.py`，采用正确的异步测试模式，并利用我们刚刚进行的改进来简化 `test_prompt_composition`。

~~~~~act
write_file
tests/providers/test_stdio.py
~~~~~
~~~~~python
import pytest
import cascade as cs
import io
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver

@pytest.fixture
def engine():
    """Provides a default Cascade Engine for tests."""
    return cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )

@pytest.mark.asyncio
async def test_stdout_write(engine, capsys):
    """
    Tests that cs.io.stdout.write correctly prints to standard output.
    """
    workflow = cs.io.stdout.write("Hello, Interactive World!")
    
    await engine.run(workflow)
    
    captured = capsys.readouterr()
    assert captured.out == "Hello, Interactive World!\n"

@pytest.mark.asyncio
async def test_stdin_read_line(engine, monkeypatch):
    """
    Tests that cs.io.stdin.read_line correctly reads from standard input.
    """
    # Simulate user typing 'test input' and pressing Enter
    mock_stdin = io.StringIO("test input\n")
    monkeypatch.setattr('sys.stdin', mock_stdin)
    
    @cs.task
    def process_input(user_text: str):
        return f"Received: {user_text.upper()}"

    # Define the workflow
    user_line = cs.io.stdin.read_line()
    workflow = process_input(user_line)
    
    result = await engine.run(workflow)
    
    assert result == "Received: TEST INPUT"

@pytest.mark.asyncio
async def test_prompt_composition(engine, capsys, monkeypatch):
    """
    Tests the composition of write and read to simulate a user prompt.
    """
    mock_stdin = io.StringIO("Cascade User\n")
    monkeypatch.setattr('sys.stdin', mock_stdin)
    
    @cs.task
    def create_greeting(name: str):
        return f"Hello, {name}!"

    # The "prompt" pattern
    prompt_message = "Please enter your name: "
    write_prompt = cs.io.stdout.write(prompt_message)
    
    # Create a data dependency to ensure write_prompt runs before read_line.
    # The result of write_prompt (None) is passed to read_line,
    # which now accepts it as a positional argument.
    user_name = cs.io.stdin.read_line(write_prompt)
    workflow = create_greeting(user_name)

    result = await engine.run(workflow)

    # Verify the output and the final result
    captured = capsys.readouterr()
    assert captured.out == prompt_message + "\n"
    assert result == "Hello, Cascade User!"
~~~~~

### 下一步建议
我们已经修复了测试并改进了 Provider 的设计。现在所有测试应该都能通过。

在确认测试通过后，我将为您生成一个 `[COMMIT]` 计划，将这些修复和改进作为一个完整的逻辑单元提交到版本控制中。请指示我继续。
