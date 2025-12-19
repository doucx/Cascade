好的，我们正处于 TDD 流程的 **Green** 阶段。测试已经明确了我们的目标，现在我将编写最少的代码来使这些测试通过。

这包括创建新的 `time.py` 提供者模块，实现 `cs.wait` 任务，并通过 `pyproject.toml` 中的入口点将其注册到 Cascade 生态系统中。

## [WIP] feat(providers): 实现时间原语 cs.wait

### 错误分析
无（这是 TDD 的实现阶段）。

### 用户需求
实现 `cs.wait` 原子任务，使其满足 TDD 测试用例中定义的契约：
1.  它必须是一个基于 `asyncio.sleep` 的非阻塞任务。
2.  它必须能接受动态 `LazyResult` 作为延迟参数。

### 评论
`cs.wait` 的实现非常直接，它是一个典型的原子提供者：职责单一、逻辑简单、可组合。通过将其注册为插件，我们遵循了 Cascade 的可扩展设计原则，将核心引擎与具体功能解耦。

### 目标
1.  创建 `packages/cascade-py/src/cascade/providers/time.py` 文件。
2.  在该文件中定义一个名为 `_wait_task` 的 `@cs.task`，其核心逻辑是 `await asyncio.sleep(delay)`。
3.  创建 `TimeWaitProvider` 类，并将其注册到 `cascade-py` 的 `pyproject.toml` 中。

### 基本原理
通过在 `pyproject.toml` 的 `cascade.providers` 入口点组中注册 `TimeWaitProvider`，Cascade 的 `ProviderRegistry` 将在启动时自动发现并加载它。当用户调用 `cs.wait(...)` 时，`__getattr__` 魔法方法会从注册表中查找名为 `wait` 的提供者，并返回其工厂函数（即 `_wait_task`），从而创建一个 `LazyResult` 并将其集成到计算图中。

### 标签
#intent/build #flow/ready #priority/high #comp/core #concept/time #scope/api #ai/instruct #task/domain/providers #task/object/wait-primitive #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建 `time.py` 提供者模块

我们将创建新的文件 `packages/cascade-py/src/cascade/providers/time.py`，其中包含 `cs.wait` 的核心实现。

~~~~~act
write_file
packages/cascade-py/src/cascade/providers/time.py
~~~~~
~~~~~python
import asyncio
from typing import Union

from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider


@task(name="wait")
async def _wait_task(delay: Union[float, int]) -> None:
    """
    Asynchronously waits for a specified duration.
    This is a non-blocking operation.

    Args:
        delay: The duration to wait in seconds.
    """
    await asyncio.sleep(float(delay))


class TimeWaitProvider(Provider):
    name = "wait"

    def create_factory(self) -> LazyFactory:
        return _wait_task

~~~~~

#### Acts 2: 注册 `cs.wait` 提供者

现在，我们将新的提供者注册到 `cascade-py` 的入口点，使其能够被动态加载。

~~~~~act
patch_file
packages/cascade-py/pyproject.toml
~~~~~
~~~~~python
[project.entry-points."cascade.providers"]
shell = "cascade.providers.shell:ShellProvider"
template = "cascade.providers.template:TemplateProvider"
"http.get" = "cascade.providers.http:HttpGetProvider"
~~~~~
~~~~~python
[project.entry-points."cascade.providers"]
shell = "cascade.providers.shell:ShellProvider"
wait = "cascade.providers.time:TimeWaitProvider"
template = "cascade.providers.template:TemplateProvider"
"http.get" = "cascade.providers.http:HttpGetProvider"
~~~~~

### 下一步建议
运行测试。现在 `cs.wait` 已经实现并注册，之前失败的测试应该会全部通过。确认通过后，我将为这个功能创建一个 `[COMMIT]` 计划。
