简要回答
测试失败的原因是 `cs.run()` 内部使用了 `asyncio.run()`，这在已经由 `pytest-asyncio` 启动的事件循环中调用是非法的（Python 不允许嵌套事件循环）。在异步测试环境中，我们应该直接实例化 `Engine` 并 `await engine.run(...)`，而不是使用同步的 `cs.run()` 封装器。

我将生成一个修复计划来重构测试代码。

## [WIP] test: 修复资源调度测试中的嵌套事件循环错误

### 错误分析
测试框架 `pytest-asyncio` 会为标记为 `async` 的测试函数创建一个正在运行的事件循环。`cs.run()` 是一个为同步脚本设计的入口函数，它不仅实例化 `Engine`，还强制调用 `asyncio.run()`。在 `async` 测试函数中调用 `cs.run()` 会导致 `RuntimeError: asyncio.run() cannot be called from a running event loop`。

### 用户需求
修复 `tests/integration/test_resource_scheduling.py` 中的运行时错误，使其能够正确验证资源调度逻辑。

### 评论
这是一个常见的异步测试陷阱。解决办法是遵循 Cascade 的测试最佳实践：在异步测试中，直接使用底层的异步 API (`Engine.run`)，而不是面向最终用户的同步 API (`cs.run`)。这也更符合单元测试“测试组件而非封装”的原则。

### 目标
重构 `tests/integration/test_resource_scheduling.py`，将所有 `cs.run(...)` 调用替换为显式的 `Engine` 实例化和 `await engine.run(...)` 调用。

### 基本原理
直接使用 `Engine` 类不仅解决了事件循环冲突，还允许我们在测试中更精细地控制 `Engine` 的配置（如 `system_resources`），而无需依赖 `cs.run` 的参数透传。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #task/domain/runtime #task/object/resource-manager #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 重构资源调度测试

修改测试文件，将同步调用替换为异步调用。

~~~~~act
write_file
tests/integration/test_resource_scheduling.py
~~~~~
~~~~~python
import pytest
import asyncio
import time
import cascade as cs
from cascade.runtime.engine import Engine

@pytest.mark.asyncio
async def test_resource_concurrency_limit():
    """
    Test that system capacity limits task concurrency.
    We set up a system with 'slots=1', and try to run 2 tasks in parallel that each require 'slots=1'.
    They should execute sequentially, doubling the total time.
    """
    
    @cs.task
    async def slow_task(name: str):
        # Simulate work
        await asyncio.sleep(0.1)
        return time.time()

    # Define two parallel tasks
    t1 = slow_task("t1").with_constraints(slots=1)
    t2 = slow_task("t2").with_constraints(slots=1)
    
    # Run them (we need a way to run both, creating a list)
    @cs.task
    def gather(a, b):
        return a, b

    workflow = gather(t1, t2)

    start_time = time.time()
    
    # Run with limited capacity: only 1 slot available
    # Because both tasks need 1 slot, they must run one after another.
    # FIX: Use Engine directly to avoid nested event loop error in tests
    engine = Engine(system_resources={"slots": 1})
    result = await engine.run(workflow)
    
    duration = time.time() - start_time
    t1_end, t2_end = result
    
    # In parallel, it would take ~0.1s. In serial, ~0.2s.
    # Allow some buffer for overhead.
    assert duration >= 0.2
    
    # One must finish before the other, roughly.
    assert abs(t1_end - t2_end) >= 0.1

@pytest.mark.asyncio
async def test_dynamic_resource_constraint():
    """
    Test that a task can request resources based on an upstream calculation.
    """
    
    @cs.task
    def calculate_cpu_needs():
        return 2

    @cs.task
    def cpu_heavy_task():
        return "Done"

    # CPU needs are determined dynamically
    needs = calculate_cpu_needs()
    
    # The task requests 'cpu' equal to the result of 'needs' (2)
    job = cpu_heavy_task().with_constraints(cpu=needs)

    # We set system capacity to 4.
    engine = Engine(system_resources={"cpu": 4})
    result = await engine.run(job)
    
    assert result == "Done"

@pytest.mark.asyncio
async def test_insufficient_resources_deadlock():
    """
    Test that requesting more resources than available raises an error immediately
    (feasibility check), rather than hanging indefinitely.
    """
    
    @cs.task
    def massive_job():
        return "Should not run"
        
    job = massive_job().with_constraints(memory_gb=64)
    
    # System only has 16GB
    engine = Engine(system_resources={"memory_gb": 16})
    
    with pytest.raises(ValueError, match="exceeds total system capacity"):
        await engine.run(job)
~~~~~

### 下一步建议
一旦测试通过，我们的资源感知调度 MVP 就完成了。接下来，我们可以考虑实现 `cs.config` Provider，这将与现有的机制结合，实现“资源配置代码化”，即把资源需求定义在配置文件中，并在运行时注入到任务约束里。
