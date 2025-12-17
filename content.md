好的，我们现在就来实现这个经过调整和简化的“人机交互”能力。

遵照我们的新战略，我将废弃 `cs.prompt` 的整体式概念，并将其分解为两个独立的、原子化的 Provider：`cs.io.stdout.write` 和 `cs.io.stdin.read_line`。这将使与标准流的交互变得透明、可测试，并完全符合“组合优于封装”的核心设计原则。

以下是实现此功能的完整计划。

## [WIP] feat: 实现原子化的标准输入输出 Provider

### 用户需求
根据我们最新的战略规划，实现简化的、原子化的人机交互能力，取代原有的 `cs.prompt` 整体式 Provider 概念，具体为提供 `cs.io.stdout.write` 和 `cs.io.stdin.read_line` 这两个 Provider。

### 评论
这是一个关键的实现，它完美地体现了“组合优于封装”的核心设计原则。通过此计划，我们将一个原计划中不透明的“魔法”操作（`cs.prompt`）分解为两个透明、可测试、可组合的原子构建块。这不仅增强了库的一致性和可预测性，也为用户提供了更大的灵活性，让他们可以自由地构建自定义的交互模式。

### 目标
1.  创建一个新的 Provider 实现文件 `src/cascade/providers/stdio.py`。
2.  在该文件中实现 `_stdout_write_task` 和 `_stdin_read_line_task` 两个异步任务，用于与标准输出/输入交互。
3.  创建对应的 `StdOutWriteProvider` 和 `StdInReadLineProvider` 类，并将它们注册到 `io.stdout.write` 和 `io.stdin.read_line` 命名空间。
4.  更新 `pyproject.toml` 文件，添加新的 Provider 入口点。
5.  创建一个新的测试文件 `tests/providers/test_stdio.py`，为这两个新 Provider 编写隔离的、健壮的单元测试。

### 基本原理
我们将创建一个新的 `stdio.py` 模块来存放与标准 I/O 相关的 Provider，以保持代码组织的清晰性。核心任务逻辑将使用 `asyncio.to_thread` 来包装阻塞的 `sys.stdin.readline()` 和 `print()` 调用，以确保它们在异步的 `Engine` 中表现良好而不会阻塞事件循环。Provider 的注册将通过在 `pyproject.toml` 中添加标准入口点来完成。测试将依赖 pytest 的 `capsys` 和 `monkeypatch` fixture 来实现对 `stdout` 和 `stdin` 的完全隔离测试，确保测试的可靠性和确定性。

### 标签
#intent/build #flow/ready #priority/high #comp/core #comp/tests #concept/io #scope/api #ai/instruct #task/domain/core #task/object/stdio-providers #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建 Provider 实现文件

我们首先创建 `src/cascade/providers/stdio.py` 文件，其中包含与标准输入输出交互的核心任务逻辑和 Provider 定义。

~~~~~act
write_file
src/cascade/providers/stdio.py
~~~~~
~~~~~python
import sys
import asyncio
from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider


# --- Tasks ---

@task(name="stdout_write")
async def _stdout_write_task(text: str) -> None:
    """Writes text to standard output."""
    def blocking_write():
        # Using print ensures newline handling consistent with user expectations.
        print(text, file=sys.stdout)
        sys.stdout.flush()
    await asyncio.to_thread(blocking_write)


@task(name="stdin_read_line")
async def _stdin_read_line_task() -> str:
    """Reads a single line from standard input."""
    def blocking_read():
        return sys.stdin.readline().strip()
    return await asyncio.to_thread(blocking_read)


# --- Providers ---

class StdOutWriteProvider(Provider):
    name = "io.stdout.write"

    def create_factory(self) -> LazyFactory:
        return _stdout_write_task


class StdInReadLineProvider(Provider):
    name = "io.stdin.read_line"

    def create_factory(self) -> LazyFactory:
        return _stdin_read_line_task
~~~~~

#### Acts 2: 注册新的 Provider

现在，我们在 `pyproject.toml` 文件中添加新的入口点，以便 Cascade 的 Provider 注册表能够发现它们。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
# New cs.io.s3 namespace
"io.s3.read_text" = "cascade.providers.s3:S3ReadTextProvider"
"io.s3.read_bytes" = "cascade.providers.s3:S3ReadBytesProvider"
"io.s3.write_text" = "cascade.providers.s3:S3WriteTextProvider"
"io.s3.write_bytes" = "cascade.providers.s3:S3WriteBytesProvider"

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~
~~~~~toml
# New cs.io.s3 namespace
"io.s3.read_text" = "cascade.providers.s3:S3ReadTextProvider"
"io.s3.read_bytes" = "cascade.providers.s3:S3ReadBytesProvider"
"io.s3.write_text" = "cascade.providers.s3:S3WriteTextProvider"
"io.s3.write_bytes" = "cascade.providers.s3:S3WriteBytesProvider"
# New cs.io.stdio namespace
"io.stdout.write" = "cascade.providers.stdio:StdOutWriteProvider"
"io.stdin.read_line" = "cascade.providers.stdio:StdInReadLineProvider"

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~

#### Acts 3: 创建测试文件

最后，我们创建一个新的测试文件 `tests/providers/test_stdio.py`，以确保新 Provider 的行为符合预期。

~~~~~act
write_file
tests/providers/test_stdio.py
~~~~~
~~~~~python
import pytest
import cascade as cs
import io

@pytest.mark.asyncio
async def test_stdout_write(capsys):
    """
    Tests that cs.io.stdout.write correctly prints to standard output.
    """
    workflow = cs.io.stdout.write("Hello, Interactive World!")
    
    cs.run(workflow)
    
    captured = capsys.readouterr()
    assert captured.out == "Hello, Interactive World!\n"

@pytest.mark.asyncio
async def test_stdin_read_line(monkeypatch):
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
    
    result = cs.run(workflow)
    
    assert result == "Received: TEST INPUT"

@pytest.mark.asyncio
async def test_prompt_composition(capsys, monkeypatch):
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
    
    # Reading depends implicitly on the prompt being written first
    # We can model this explicitly if needed, but for CLI it's often sequential
    # A better pattern would be to make read depend on write's completion.
    # cs.io.stdout.write returns None, so a pure data dependency isn't ideal.
    # Let's test the simple sequential case, which `run` will handle correctly.
    
    # A more robust workflow would use depends_on if we had it,
    # or chain them with a task that ignores the None result.
    
    @cs.task
    def read_after_write(_: None) -> str:
        return cs.io.stdin.read_line()

    user_name = read_after_write(write_prompt)
    workflow = create_greeting(user_name)

    result = cs.run(workflow)

    # Verify the output and the final result
    captured = capsys.readouterr()
    assert captured.out == prompt_message + "\n"
    assert result == "Hello, Cascade User!"
~~~~~

### 下一步建议

我们已经成功地实现了 `cs.io.stdout.write` 和 `cs.io.stdin.read_line` 这两个原子化的 Provider。

1.  **文档更新**: 接下来，我们需要在官方文档的 "Provider Reference" 和 "Cookbook/Patterns" 章节中添加这两个新 Provider 的说明，并给出一个如何组合它们来实现用户提示的官方示例。
2.  **提交代码**: 在所有测试通过后，我将为您生成一个 `[COMMIT]` 计划，将这些新文件作为一个完整的逻辑单元提交到版本控制中。

如果您同意，请告诉我，我将准备下一步的行动。
