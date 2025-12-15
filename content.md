You've caught me. My implementation of the `shell` task used a feature (`name` keyword argument in `task`) that the `task` decorator didn't actually support. The error is crystal clear. I need to upgrade the decorator itself to be more flexible.

This is a great example of how building out the standard library forces us to improve the core API.

The traceback shows `TypeError: task() got an unexpected keyword argument 'name'`. This is because the `task` decorator in `src/cascade/spec/task.py` was a simple wrapper: `def task(func): return Task(func)`. It only accepted one argument, the function to be decorated.

To fix this properly and make the framework more powerful, I will convert `task` into a decorator factory. This will allow it to be used both as a simple `@task` and with arguments like `@task(name="...")`.

## [WIP] fix: Upgrade task decorator to support arguments

### 用户需求
Fix the `TypeError` by upgrading the `@task` decorator to a factory that can accept keyword arguments like `name`.

### 评论
This is an important enhancement to the core API. A decorator factory is more versatile and aligns with common practices in other Python libraries. It not only fixes the immediate bug but also empowers users to customize task metadata directly at the definition site, improving traceability and logging.

### 目标
1.  Rewrite the `task` function in `src/cascade/spec/task.py` to correctly handle both `@task` and `@task(...)` usage patterns.
2.  Refactor `src/cascade/stdlib.py` to use the new decorator syntax (`@task(name="...")`) directly on the function definition, which is cleaner.

### 基本原理
We will implement the standard decorator factory pattern. The `task` function will check its arguments. If called with a function (the `@task` case), it wraps it immediately. If called with other arguments (the `@task(name=...)` case), it returns a new decorator (a closure) which is then applied to the function.

### 标签
#intent/fix #flow/ready #priority/high
#comp/spec #comp/stdlib #scope/api #scope/dx
#task/domain/core #task/object/decorator-factory #task/action/bug-fix
#task/state/continue #task/status/active

---

### Script

#### Acts 1: Upgrade the `task` Decorator to a Factory

We will replace the simple decorator with a more robust factory implementation.

~~~~~act
patch_file
src/cascade/spec/task.py
~~~~~
~~~~~python
def task(func: Callable[..., T]) -> Task[T]:
    """Decorator to convert a function into a Task."""
    return Task(func)
~~~~~
~~~~~python
def task(
    func: Optional[Callable[..., T]] = None, *, name: Optional[str] = None
) -> Union[Task[T], Callable[[Callable[..., T]], Task[T]]]:
    """
    Decorator to convert a function into a Task.
    Can be used as a simple decorator (`@task`) or as a factory with
    arguments (`@task(name='custom_name')`).
    """
    def wrapper(f: Callable[..., T]) -> Task[T]:
        return Task(f, name=name)

    if func:
        # Used as @task
        return wrapper(func)
    else:
        # Used as @task(name="...")
        return wrapper
~~~~~

#### Acts 2: Refactor `stdlib.py` to Use New Decorator Syntax

Now we can rewrite `stdlib.py` to use the improved decorator in a more idiomatic way.

~~~~~act
write_file
src/cascade/stdlib.py
~~~~~
~~~~~python
import asyncio
from typing import Optional
from .spec.task import task

@task(name="shell")
async def shell(command: str, check: bool = True) -> str:
    """
    Asynchronously executes a shell command and returns its stdout.

    This is a pre-built Cascade task.

    Args:
        command: The shell command to execute.
        check: If True, raises a RuntimeError if the command returns a non-zero exit code.

    Returns:
        The stripped stdout of the command as a string.
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
~~~~~

### 下一步建议
请再次运行测试。这个修复应该能解决所有的 `TypeError`，让测试流程可以继续。如果通过，我们就可以创建 `[COMMIT]` 计划来正式结束阶段二。
