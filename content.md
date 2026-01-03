好的，我分析了错误日志和 `rg` 的输出。

## [WIP] refactor: Centralize TimedMockExecutor and fix test failures

### 错误分析
1.  **TypeError (根本原因)**: 多个测试文件（`test_e2e_local_connector.py`）中的 `TimedMockExecutor` 的 `execute` 方法签名是 `(self, node, args, kwargs)`，这与 `LocalExecutor` 的基类接口 `(self, node, callable_obj, args, kwargs)` 不匹配。`NodeProcessor` 在调用时传递了5个参数，导致 `TypeError`。
2.  **TimeoutError (副作用)**: 在 `test_pause_and_resume_e2e` 中，由于 `TypeError` 导致后台的 `engine.run` 任务崩溃，测试的主协程一直在等待一个永远不会完成的任务，最终超时。
3.  **DRY 违规 (问题的根源)**: `rg` 的输出明确显示，`TimedMockExecutor` 这个测试辅助类在三个不同的文件中被重复定义。这种代码重复导致了当核心接口变更时，只有一个定义被正确更新，而其他的定义被遗漏，从而引发了上述错误。

### 用户需求
修复 E2E 测试中的 `TypeError` 和 `TimeoutError`，并解决 `TimedMockExecutor` 的代码重复问题。

### 评论
这是一个典型的因违反 DRY（Don't Repeat Yourself）原则而导致维护困难和引入错误的案例。通过将 `TimedMockExecutor` 提取到一个共享的测试工具模块（`cascade.testing`），我们可以一劳永逸地解决这个问题，确保所有测试都使用统一且正确的实现，并简化未来的维护工作。

### 目标
1.  在 `cascade.testing` 模块中创建一个统一的、签名正确的 `TimedMockExecutor` 类。
2.  将这个新的 `TimedMockExecutor` 导出到 `cascade.testing` 的 `__all__` 中。
3.  重构所有使用本地 `TimedMockExecutor` 定义的测试文件，让它们改为从 `cascade.testing` 导入并使用这个共享的类。

### 基本原理
我们将遵循软件工程的最佳实践，将重复的测试辅助代码抽象到一个公共位置。`packages/cascade-sdk/src/cascade/testing.py` 是存放这类工具的理想场所。通过此重构，我们将修复所有因签名不匹配引起的 `TypeError`，进而解决连锁导致的 `TimeoutError`。

### 标签
#intent/refine #intent/fix #flow/ready #priority/high #comp/tests #comp/engine #scope/dx #task/domain/testing #task/object/test-helpers #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建共享的 TimedMockExecutor

我们将在 `cascade.testing` 模块中定义一个标准的 `TimedMockExecutor`，并将其导出。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/testing.py
~~~~~
~~~~~python.old
class MockConnector(Connector):
    def __init__(self):
        self.subscriptions: Dict[str, Callable[[str, Dict], Awaitable[None]]] = {}
~~~~~
~~~~~python.new
from cascade.adapters.executors.local import LocalExecutor


class TimedMockExecutor(LocalExecutor):
    def __init__(self, delay: float = 0.0):
        super().__init__()
        self.delay = delay

    async def execute(self, node, callable_obj, args, kwargs):
        await asyncio.sleep(self.delay)
        return await super().execute(node, callable_obj, args, kwargs)


class MockConnector(Connector):
    def __init__(self):
        self.subscriptions: Dict[str, Callable[[str, Dict], Awaitable[None]]] = {}
~~~~~
~~~~~act
patch_file
packages/cascade-sdk/src/cascade/testing.py
~~~~~
~~~~~python.old
    async def _publish(self, scope: str, constraint: GlobalConstraint):
        payload = asdict(constraint)
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        await self.connector.publish(topic, payload, retain=True)
~~~~~
~~~~~python.new
    async def _publish(self, scope: str, constraint: GlobalConstraint):
        payload = asdict(constraint)
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        await self.connector.publish(topic, payload, retain=True)


__all__ = [
    "override_resource",
    "SpySubscriber",
    "SpySolver",
    "MockSolver",
    "SpyExecutor",
    "MockExecutor",
    "MockSubscriptionHandle",
    "MockConnector",
    "ControllerTestApp",
    "TimedMockExecutor",
]
~~~~~

#### Acts 2: 更新 E2E 测试以使用共享 Executor

移除 `test_e2e_local_connector.py` 中的本地定义，并修正 `execute` 方法的签名。

~~~~~act
patch_file
tests/e2e/runtime/test_e2e_local_connector.py
~~~~~
~~~~~python.old
@pytest.fixture
def engine(unique_paths, bus_and_spy):
    """Provides a fully configured Engine using the LocalConnector."""
    db_path, uds_path = unique_paths
    bus, _ = bus_and_spy
    connector = LocalConnector(db_path=db_path, uds_path=uds_path)

    class TimedMockExecutor(LocalExecutor):
        async def execute(self, node, args, kwargs):
            await asyncio.sleep(0.05)
            return await super().execute(node, args, kwargs)

    return Engine(
        solver=NativeSolver(),
        executor=TimedMockExecutor(),
        bus=bus,
        connector=connector,
    )
~~~~~
~~~~~python.new
@pytest.fixture
def engine(unique_paths, bus_and_spy):
    """Provides a fully configured Engine using the LocalConnector."""
    from cascade.testing import TimedMockExecutor

    db_path, uds_path = unique_paths
    bus, _ = bus_and_spy
    connector = LocalConnector(db_path=db_path, uds_path=uds_path)

    return Engine(
        solver=NativeSolver(),
        executor=TimedMockExecutor(delay=0.05),
        bus=bus,
        connector=connector,
    )
~~~~~

#### Acts 3: 更新集成测试以使用共享 Executor

现在修复 `test_engine_constraints.py`，它之前使用了基于 `SpyExecutor` 的错误版本。

~~~~~act
patch_file
packages/cascade-engine/tests/integration/test_engine_constraints.py
~~~~~
~~~~~python.old
import asyncio

import pytest

from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.spec.constraint import GlobalConstraint
from cascade.testing import MockConnector, SpyExecutor, MockExecutor


class TimedMockExecutor(SpyExecutor):
    def __init__(self, delay: float = 0.0):
        super().__init__()
        self.delay = delay

    async def execute(self, node, callable_obj, args, kwargs):
        await asyncio.sleep(self.delay)
        return await super().execute(node, callable_obj, args, kwargs)


# --- Test Fixtures and Mocks ---
~~~~~
~~~~~python.new
import asyncio

import pytest

from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.spec.constraint import GlobalConstraint
from cascade.testing import MockConnector, MockExecutor, TimedMockExecutor


# --- Test Fixtures and Mocks ---
~~~~~

#### Acts 4: 统一并发测试中的 Executor 定义

最后，我们也更新 `test_engine_concurrency.py` 以使用共享的辅助类。

~~~~~act
patch_file
packages/cascade-engine/tests/integration/test_engine_concurrency.py
~~~~~
~~~~~python.old
import time
import asyncio
import pytest
import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.testing import MockConnector


class TimedMockExecutor(LocalExecutor):
    def __init__(self, delay: float = 0.0):
        super().__init__()
        self.delay = delay

    async def execute(self, node, callable_obj, args, kwargs):
        await asyncio.sleep(self.delay)
        return await super().execute(node, callable_obj, args, kwargs)
~~~~~
~~~~~python.new
import time
import asyncio
import pytest
import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.testing import MockConnector, TimedMockExecutor
~~~~~

### 下一步建议
所有已知的 `TimedMockExecutor` 定义都已被重构。现在可以重新运行完整的测试套件，以确认所有相关错误都已解决。
