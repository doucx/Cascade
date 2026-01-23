当然，这是一个预料之中的错误。我们在前一个步骤中修改了 `BridgedComputeService` 的构造函数签名，要求传入一个 `context` 对象，但没有更新用于测试的 Fixture。

我将立即修复这些测试，为 `BridgedComputeService` 提供一个模拟的 `ExecutionContext`。

## [WIP] fix: 修复因缺少执行上下文而失败的 VM 测试

### 错误分析
在 `BridgedComputeService.__init__` 中添加了 `context: ExecutionContext` 参数后，`packages/cascade-vm/tests/integration/test_compute_adapters.py` 中用于实例化该服务的 `service` fixture 未能提供此必需参数，导致 `TypeError` 并使整个测试套件失败。

### 用户需求
用户需要修复因 `TypeError: ... missing 1 required positional argument: 'context'` 导致的测试失败。

### 评论
这是一个简单的、由 API 变更引起的测试代码同步问题。修复它很简单，只需创建一个合适的 `ExecutionContext` 模拟实例并将其注入到测试 fixture 中即可。这也验证了我们第一阶段的基础设施变更已在类型系统层面正确生效。

### 目标
1.  在 `test_compute_adapters.py` 中导入 `ExecutionContext` 和其他必要的辅助类。
2.  创建一个新的 `pytest` fixture (`mock_context`)，用于构造一个适用于测试的 `ExecutionContext` 实例。
3.  更新 `service` fixture，使其依赖于 `mock_context` 并将该上下文传递给 `BridgedComputeService` 的构造函数。

### 基本原理
测试应该隔离被测单元。通过创建一个包含模拟依赖项（如 `state_backend` 和 `resource_container`）的 `ExecutionContext`，我们可以测试 `BridgedComputeService` 的核心逻辑，而无需启动完整的运行时环境。

### 标签
#intent/fix #flow/ready #priority/high #comp/vm #comp/tests #scope/dx #task/domain/compute #task/object/adapter-layer #task/action/wiring #task/state/continue

---

### Script

#### Acts 1: 更新测试 Fixture 以注入执行上下文

我们将修改 `test_compute_adapters.py`，添加必要的导入，创建一个 `mock_context` fixture，并更新 `service` fixture 以使用它。这将解决所有 `TypeError` 问题。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_compute_adapters.py
~~~~~
~~~~~python.old
import asyncio
import pytest
from unittest.mock import AsyncMock

from cascade.spec.physical.nodes import Token
from cascade.spec.physical.object import Ref
from cascade.runtime.storage import InMemoryObjectStore
from cascade.vm.registry import CodeRegistry
from cascade.vm.compute import ComputeRequest, BridgedComputeService
from cascade.spec.dsl.task import task


# --- Test Functions ---
def sync_add(a, b):
    return a + b


async def async_add(a, b):
    return a + b


@task(mode="compute")
def sync_compute_task(x):
    return x * x


# --- Fixtures ---


@pytest.fixture
def store():
    return InMemoryObjectStore()


@pytest.fixture
def registry():
    return CodeRegistry()


@pytest.fixture
def mock_executor():
    return AsyncMock()


@pytest.fixture
def inbound_queue():
    return asyncio.Queue()


@pytest.fixture
def outbound_queue():
    return asyncio.Queue()


@pytest.fixture
def wakeup_event():
    return asyncio.Event()


@pytest.fixture
def service(
    mock_executor, store, registry, inbound_queue, outbound_queue, wakeup_event
):
    return BridgedComputeService(
        executor=mock_executor,
        store=store,
        registry=registry,
        inbound_queue=inbound_queue,
        outbound_queue=outbound_queue,
        wakeup_event=wakeup_event,
    )
~~~~~
~~~~~python.new
import asyncio
import pytest
from unittest.mock import AsyncMock, Mock
from contextlib import ExitStack

from cascade.spec.physical.nodes import Token
from cascade.spec.physical.object import Ref
from cascade.spec.runtime import ExecutionContext
from cascade.runtime.storage import InMemoryObjectStore
from cascade.vm.registry import CodeRegistry
from cascade.vm.compute import ComputeRequest, BridgedComputeService
from cascade.spec.dsl.task import task


# --- Test Functions ---
def sync_add(a, b):
    return a + b


async def async_add(a, b):
    return a + b


@task(mode="compute")
def sync_compute_task(x):
    return x * x


# --- Fixtures ---


@pytest.fixture
def store():
    return InMemoryObjectStore()


@pytest.fixture
def registry():
    return CodeRegistry()


@pytest.fixture
def mock_executor():
    return AsyncMock()


@pytest.fixture
def inbound_queue():
    return asyncio.Queue()


@pytest.fixture
def outbound_queue():
    return asyncio.Queue()


@pytest.fixture
def wakeup_event():
    return asyncio.Event()


@pytest.fixture
def mock_context(store):
    return ExecutionContext(
        run_id="test-run",
        state_backend=Mock(),
        object_store=store,
        run_stack=ExitStack(),
        resource_container=Mock(),
    )


@pytest.fixture
def service(
    mock_executor,
    store,
    registry,
    inbound_queue,
    outbound_queue,
    wakeup_event,
    mock_context,
):
    return BridgedComputeService(
        executor=mock_executor,
        store=store,
        registry=registry,
        inbound_queue=inbound_queue,
        outbound_queue=outbound_queue,
        context=mock_context,
        wakeup_event=wakeup_event,
    )
~~~~~

### 下一步建议

测试已修复，基础设施已就绪。现在是时候实施此修复路线图的核心部分了。

我将开始**第二阶段和第三阶段：核心解析逻辑重构**。这包括：
1.  在 `BridgedComputeService` 中实现新的 `_bind_execution_arguments` 方法。
2.  重写 `_process_request` 以使用这个新方法，彻底解决参数绑定、依赖注入和上下文感知的问题。
