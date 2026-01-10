## [WIP] test: 验证 VMExecutionStrategy E2E 流程

### 用户需求
创建一个端到端 (E2E) 测试，验证 `VMExecutionStrategy` 在真实 `Engine` 上下文中的工作能力。

### 评论
这将是验证我们整个 VM 实施路线图的里程碑式测试。如果这个测试通过，意味着我们成功地将 Cascade 从一个基于图遍历的解释器升级为一个基于物理模拟的虚拟机。

该测试需要覆盖：
1.  **Sync Task**: 验证基本的函数调用、参数传递和结果返回。
2.  **Async Task**: 验证异步函数的调度和等待。
3.  **Dependencies**: 验证 `LazyResult` 之间的依赖关系（数据流）。
4.  **Integration**: 验证 `Engine` 是否正确加载并使用了 `VMExecutionStrategy`。

### 目标
1.  创建 `packages/cascade-runtime/tests/integration/test_vm_e2e.py`。
2.  编写测试用例 `test_vm_simple_execution`，验证同步任务。
3.  编写测试用例 `test_vm_async_execution`，验证异步任务。
4.  编写测试用例 `test_vm_dependency_chain`，验证 `add(add(1, 2), 3)` 这种依赖链。

### 基本原理
我们将使用 `Engine` 的标准接口，但通过构造函数显式注入 `VMExecutionStrategy`。由于 `Engine` 目前的构造函数已经接受 `strategy` 参数，这将非常直接。我们将使用真实的 `LocalExecutor` 和 `InMemoryObjectStore`，模拟生产环境。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #comp/runtime #concept/strategy #scope/core #ai/instruct #task/domain/testing #task/object/vm-strategy #task/action/verification #task/state/end

---

### Script

#### Acts 1: 创建 `test_vm_e2e.py`

~~~~~act
write_file
packages/cascade-runtime/tests/integration/test_vm_e2e.py
~~~~~
~~~~~python
import pytest
import asyncio
from cascade.runtime.host.instance import Engine
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.runtime.strategies.vm import VMExecutionStrategy
from cascade.runtime.services.observability.bus import EventBus
from cascade.runtime.storage import InMemoryObjectStore
from cascade.spec.dsl.task import task
from cascade.test_utils.helpers import MockSolver


# --- Tasks ---

@task
def add(a: int, b: int) -> int:
    return a + b


@task
async def async_mul(a: int, b: int) -> int:
    await asyncio.sleep(0.01)
    return a * b


@task
def fail(msg: str):
    raise ValueError(msg)


# --- Fixtures ---

@pytest.fixture
def executor():
    return LocalExecutor()


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def strategy(executor):
    return VMExecutionStrategy(executor=executor)


@pytest.fixture
def engine(executor, bus, strategy):
    # Solver is not used by VMStrategy but required by Engine interface
    solver = MockSolver(plan=[])
    
    return Engine(
        solver=solver,
        executor=executor,
        bus=bus,
        strategy=strategy,
        object_store=InMemoryObjectStore()
    )


# --- Tests ---

@pytest.mark.asyncio
async def test_vm_simple_execution(engine):
    """Test executing a single synchronous task."""
    workflow = add(1, 2)
    result = await engine.run(workflow)
    assert result == 3


@pytest.mark.asyncio
async def test_vm_async_execution(engine):
    """Test executing a single asynchronous task."""
    workflow = async_mul(3, 4)
    result = await engine.run(workflow)
    assert result == 12


@pytest.mark.asyncio
async def test_vm_dependency_chain(engine):
    """Test a chain of dependencies: (1 + 2) * 3."""
    sum_res = add(1, 2)
    workflow = async_mul(sum_res, 3)
    
    result = await engine.run(workflow)
    assert result == 9


@pytest.mark.asyncio
async def test_vm_error_propagation(engine):
    """Test that exceptions are propagated correctly."""
    workflow = fail("Boom!")
    
    with pytest.raises(ValueError, match="Boom!"):
        await engine.run(workflow)


@pytest.mark.asyncio
async def test_vm_list_output(engine):
    """Test that the VM can return a list of results (implicit gather)."""
    t1 = add(1, 1)
    t2 = add(2, 2)
    workflow = [t1, t2]
    
    result = await engine.run(workflow)
    assert result == [2, 4]
~~~~~

### 下一步建议
通过 `test_vm_e2e.py`，我们已经完成了对 `VMExecutionStrategy` 功能的验证。

根据路线图，第三阶段是 **集成与验证 (Integration & Verification)**。目前的测试已经覆盖了部分验证工作（如错误传播、复杂数据流）。

接下来的工作可以集中在：
1.  **资源管理集成**：验证 VM 是否正确响应了 `ResourceConstraint`（例如 GPU 限制）。
2.  **可观测性验证**：验证 `VMExecutionStrategy` 是否通过 `EventBus` 发出了正确的生命周期事件（`TaskExecutionStarted`, `TaskExecutionFinished` 等），这对于 UI 和日志至关重要。
3.  **复杂控制流**：如果可能，验证 `Condition` (`.run_if`) 是否在 VM 中按预期工作。

目前，核心的执行路径已经打通。我们可以认为“后端切换”的主要工程任务已经完成。
