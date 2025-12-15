好的，我们来完成阶段二的最后一项任务：实现 `Shell` 预置任务类型。完成此项后，我们将正式结束阶段二。

## [WIP] feat(stdlib): 实现 Shell 预置任务以执行外部命令

### 用户需求
为 Cascade 提供一个开箱即用的、健壮的 `shell` 任务，用于在工作流中执行外部 shell 命令，并将其输出传递给下游任务。

### 评论
这是对开发者体验 (DX) 的一次巨大提升。几乎所有的自动化工作流都需要与 shell 交互。通过提供一个内置的、经过良好测试的 `shell` 任务，我们不仅减少了用户的样板代码，还提供了一套比 `subprocess.run` 更高级、更符合 Cascade 声明式理念的接口。

我们选择的 API 形式是 `cs.shell(...)`，它本身就是一个 `@task` 实例，调用它会直接返回一个 `LazyResult`。这种设计比“在用户任务中 `return Shell(...)`”的模式更简洁，并且完全无需修改现有的、已经稳定的执行引擎。

### 目标
1.  创建一个新的模块 `src/cascade/stdlib.py` 用于存放预置任务。
2.  在该模块中，实现一个基于 `asyncio.create_subprocess_shell` 的异步函数，作为 `shell` 任务的底层逻辑。
3.  使用 `@cs.task` 装饰器将此函数包装成一个可重用的 `shell` 任务。
4.  在顶层 `cascade` 包中导出 `shell`，方便用户以 `cs.shell(...)` 的形式调用。
5.  编写全面的测试，覆盖命令成功、失败 (`check=True`) 以及与下游任务集成等场景。

### 基本原理
我们将 `shell` 命令的执行抽象为一个标准的 Cascade 异步任务。这使得 shell 命令可以无缝地融入计算图，享受与其他任务同等的依赖管理、异步执行和错误处理能力。我们使用 `asyncio` 的子进程工具，以确保命令执行不会阻塞整个 `Engine` 的事件循环。

### 标签
#intent/build #flow/ready #priority/high
#comp/stdlib #scope/api #scope/dx
#task/domain/core #task/object/prebuilt-tasks #task/action/implementation
#task/state/end #task/status/completed

---

### Script

#### Acts 1: Create the Standard Library Module

创建 `src/cascade/stdlib.py` 并实现 `shell` 任务。

~~~~~act
write_file
src/cascade/stdlib.py
~~~~~
~~~~~python
import asyncio
from typing import Optional, Tuple
from .spec.task import task

async def _run_shell_command(
    command: str, check: bool = True
) -> str:
    """
    Asynchronously executes a shell command and returns its stdout.
    """
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()

    if check and proc.returncode != 0:
        raise RuntimeError(
            f"Command '{command}' failed with exit code {proc.returncode}:\n"
            f"STDOUT:\n{stdout.decode().strip()}\n"
            f"STDERR:\n{stderr.decode().strip()}"
        )

    return stdout.decode().strip()

# Create a pre-instantiated task for users to import and use directly.
shell = task(_run_shell_command, name="shell")
~~~~~

#### Acts 2: Expose the `shell` Task

在 `src/cascade/__init__.py` 中导出 `shell` 任务。

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
from .spec.task import task, Param, LazyResult
from .spec.resource import resource, inject
from .runtime.engine import Engine
from .runtime.bus import MessageBus
from .runtime.subscribers import HumanReadableLogSubscriber
from .testing import override_resource
~~~~~
~~~~~python
import asyncio
from typing import Any, Dict, Optional

from .spec.task import task, Param, LazyResult
from .spec.resource import resource, inject
from .runtime.engine import Engine
from .runtime.bus import MessageBus
from .runtime.subscribers import HumanReadableLogSubscriber
from .testing import override_resource
from .stdlib import shell
~~~~~

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
__all__ = [
    "task",
    "Param",
    "run",
    "LazyResult",
    "resource",
    "inject",
    "Engine",
    "override_resource",
]
~~~~~
~~~~~python
__all__ = [
    "task",
    "Param",
    "run",
    "LazyResult",
    "resource",
    "inject",
    "Engine",
    "override_resource",
    "shell",
]
~~~~~

#### Acts 3: Add Tests for the `shell` Task

创建 `tests/test_stdlib.py` 并添加测试用例。

~~~~~act
write_file
tests/test_stdlib.py
~~~~~
~~~~~python
import pytest
import cascade as cs

def test_shell_task_success():
    """Tests that a simple shell command runs and captures stdout."""
    # Using `echo` is a reliable cross-platform command
    result = cs.run(cs.shell("echo 'Hello, Cascade!'"))
    assert result == "Hello, Cascade!"

def test_shell_task_failure_with_check():
    """Tests that a failing command with check=True raises an error."""
    # `exit 1` is a simple way to force failure
    with pytest.raises(RuntimeError) as excinfo:
        cs.run(cs.shell("exit 1"))
    
    assert "failed with exit code 1" in str(excinfo.value)

def test_shell_task_integration():
    """Tests that the output of a shell task can be used by another task."""
    @cs.task
    def process_output(text: str):
        return f"Processed: {text.upper()}"

    command_output = cs.shell("echo 'data'")
    final_result = process_output(command_output)

    result = cs.run(final_result)
    assert result == "Processed: DATA"
~~~~~

### 下一步建议
**Cascade 阶段二已正式完成！**

我们成功地实现了依赖注入、一等公民的异步支持、健壮的重试与缓存机制，并提供了便捷的 `shell` 预置任务。框架的核心功能已经非常完善。

我建议创建一个最终的 `[COMMIT]` 计划，将 `shell` 任务的实现提交，并正式为这个阶段的工作画上句号。之后，我们将可以开始规划阶段三的详细任务，例如 `visualize` 工具或更高级的 `CSPSolver`。
