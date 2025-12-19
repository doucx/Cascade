简要回答
我们遇到了 pytest 的一个错误，这是因为 `local_bus` fixture 被定义为 `async` 但其实并不执行任何异步操作，且没有正确标记为异步 fixture。同时，为了防止不同测试用例间的 Event Loop 隔离导致全局 `asyncio.Lock` 报错，我们需要在重置状态时一并重置锁。

我们将修复这两个问题，以确保测试稳定运行。

## [WIP] fix(tests): 修复 LocalBus 测试的 fixture 定义与状态重置

### 错误分析
1.  **Fixture 定义错误**: `pytest.PytestRemovedIn9Warning` 指出 `local_bus` fixture 是异步的 (`async def`)，但没有被正确处理。由于该 fixture 内部只有同步操作（重置类状态），将其改为同步 (`def`) 是最直接的修复方式。
2.  **潜在的 Event Loop 问题**: `LocalBusConnector` 使用一个类级别的全局 `asyncio.Lock`。在测试环境中，每个测试可能会创建新的 Event Loop。如果全局锁绑定到了旧的 Loop，后续测试会失败。因此，我们需要在 `_reset_broker_state` 中重新创建这个锁。

### 用户需求
确保 `LocalBusConnector` 的测试套件能够绿灯通过，为后续功能开发提供稳定的基础。

### 评论
这是 TDD 流程中的典型“红灯修补”环节。在基础设施代码中处理好全局状态和异步上下文的生命周期至关重要。

### 目标
1.  修改 `tests/py/connectors/test_local_connector.py`，将 `local_bus` fixture 改为同步函数。
2.  修改 `packages/cascade-runtime/src/cascade/connectors/local.py`，在 `_reset_broker_state` 中重置 `_lock`。

### 基本原理
将 fixture 改为同步消除了 pytest 的警告。在每个测试开始前重建 `asyncio.Lock` 确保了锁总是隶属于当前测试的 Event Loop，防止了跨 Loop 调用导致的 `Future attached to a different loop` 错误。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #comp/runtime #scope/core #task/domain/telemetry #task/object/local-bus #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复测试 Fixture

移除 `async` 关键字。

~~~~~act
patch_file
tests/py/connectors/test_local_connector.py
~~~~~
~~~~~old
@pytest.fixture
async def local_bus():
    """Provides a fresh LocalBus environment for each test."""
    # LocalBusConnector uses shared class state, so we must clear it before each test
    LocalBusConnector._reset_broker_state()
    yield
    LocalBusConnector._reset_broker_state()
~~~~~
~~~~~new
@pytest.fixture
def local_bus():
    """Provides a fresh LocalBus environment for each test."""
    # LocalBusConnector uses shared class state, so we must clear it before each test
    LocalBusConnector._reset_broker_state()
    yield
    LocalBusConnector._reset_broker_state()
~~~~~

#### Acts 2: 增强状态重置逻辑

在 `_reset_broker_state` 中加入锁的重置。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/connectors/local.py
~~~~~
~~~~~old
    @classmethod
    def _reset_broker_state(cls):
        """Helper for tests to clear the 'broker'."""
        cls._subscriptions.clear()
        cls._retained_messages.clear()
~~~~~
~~~~~new
    @classmethod
    def _reset_broker_state(cls):
        """Helper for tests to clear the 'broker'."""
        cls._subscriptions.clear()
        cls._retained_messages.clear()
        cls._lock = asyncio.Lock()  # Reset lock for new event loop context
~~~~~

### 下一步建议
运行测试 `pytest tests/py/connectors/test_local_connector.py`。如果通过，我们将按计划进入 **里程碑 1.2**，开始对 `Engine` 进行递归改造。
