好的，我来分析这些测试失败的原因。

 错误分析

上次的修复解决了 Fixture 的发现问题，但暴露出了更深层次的、与测试隔离性相关的故障。失败的测试都是端到端（E2E）测试，它们对时序和组件间的通信非常敏感。

经过分析，我发现了两个独立但相关的问题：

1.  **关键的 `autouse` Fixture 位置错误**：在之前的重构中，一个名为 `cleanup_local_bus` 的、带有 `@pytest.fixture(autouse=True)` 标记的 Fixture 被留在了根目录的 `tests/conftest.py` 中。这个 Fixture 的作用是在每次测试前后重置 `InProcessConnector`（一个内存消息代理）的状态。由于它现在的位置，`cascade-engine` 包内的 E2E 测试**无法发现并执行它**。这导致了**测试间的状态泄漏**：一个测试留下的消息（例如 "pause" 或 "resume"）会干扰下一个测试的执行，从而引发各种不可预测的行为，包括 `TimeoutError` 和死锁。

2.  **测试桩（Test Double）配置错误**：在 `test_e2e_robustness.py` 文件中，测试代码创建了两个**完全独立**的 `InProcessConnector` 实例：一个给 `Engine` (`engine_connector`)，另一个给 `ControllerTestApp` (`controller_connector`)。这意味着控制器发布命令的总线与引擎监听的总线根本不是同一个，它们之间无法通信。因此，测试中断言引擎会进入等待状态的逻辑永远不会成功，因为它从未收到任何指令。

这两个问题共同导致了 E2E 测试的失败。根本解决方案是：**将特定于 `cascade-engine` E2E 测试的 Fixture 移动到正确的位置，并修复错误的测试桩配置。**

## [WIP] fix: Isolate engine E2E tests and repair harness

### 错误分析
在解决了 Fixture 的发现问题后，E2E 测试仍然失败，表现为超时和断言失败。根本原因有两个：

1.  **测试状态泄漏**：一个用于清理 `InProcessConnector` 状态的全局 `autouse` Fixture (`cleanup_local_bus`) 在上次重构后被留在了顶层 `tests/conftest.py` 中。由于 `pytest` 的发现规则，`cascade-engine` 包内的测试无法再找到并执行这个 Fixture。这导致了测试间的状态污染，一个测试留下的消息会影响后续测试的正确性，从而引发了看似随机的超时和死锁。
2.  **测试桩配置错误**：在 `test_e2e_robustness.py` 中，测试控制器和被测引擎被错误地配置了两个独立的 `InProcessConnector` 实例，导致它们之间无法通信，测试逻辑因此失败。

### 用户需求
用户要求修复 `cascade-engine` 包中失败的 E2E 测试，这些测试表现为超时和逻辑断言失败。

### 评论
这些失败是典型的在大型重构后出现的“第二波”问题。修复这些问题对于确保测试套件的可靠性和稳定性至关重要。将特定于领域的测试基础设施（如此处的 `conftest.py`）与其测试代码放在一起，是实现真正模块化和可维护性的最后一步。

### 目标
1.  在 `packages/cascade-engine/tests/e2e/` 目录下创建一个新的 `conftest.py` 文件。
2.  将 `cleanup_local_bus` Fixture 从根 `tests/conftest.py` 移动到这个新文件中，以确保它能被所有 `cascade-engine` E2E 测试自动应用。
3.  修改 `test_e2e_robustness.py`，确保控制器和引擎共享同一个 `InProcessConnector` 实例。

### 基本原理
通过在 `e2e` 测试目录下创建 `conftest.py` 并移入 `cleanup_local_bus` Fixture，我们利用 `pytest` 的 Fixture 发现机制，确保了每个 E2E 测试在运行时都能享有一个干净、隔离的消息总线环境，从而消除了状态泄漏。同时，通过修正 `test_e2e_robustness.py` 中的测试桩，我们恢复了被测系统与测试控制器之间的通信链路，使其能够按预期工作。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/brainstorm #task/domain/testing #task/object/test-isolation #task/action/refactor #task/state/continue

---
### Script

#### Acts 1: 为 Engine E2E 测试创建专属的 conftest

我们将为 `cascade-engine` 的 E2E 测试创建一个 `conftest.py` 文件，并将用于状态清理的 `autouse` Fixture 移入其中。

~~~~~act
write_file
packages/cascade-engine/tests/e2e/conftest.py
~~~~~
~~~~~python
import pytest

# Attempt to import LocalBusConnector for global cleanup
try:
    from cascade.connectors.local.bus import LocalBusConnector
except ImportError:
    LocalBusConnector = None


@pytest.fixture(autouse=True)
def cleanup_local_bus():
    """
    Ensures that the memory broker state is completely cleared between tests.
    This prevents state leakage (retained messages/subscriptions) which
    causes unpredictable failures in E2E tests.
    """
    if LocalBusConnector:
        LocalBusConnector._reset_broker_state()
    yield
    if LocalBusConnector:
        LocalBusConnector._reset_broker_state()
~~~~~

#### Acts 2: 清理根目录的 conftest.py

现在，从根 `tests/conftest.py` 文件中移除已经迁移的 Fixture。由于这是其中唯一的 Fixture，该文件将变为空。

~~~~~act
patch_file
tests/conftest.py
~~~~~
~~~~~python
import pytest
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event

# Attempt to import LocalBusConnector for global cleanup
try:
    from cascade.connectors.local import LocalBusConnector
except ImportError:
    LocalBusConnector = None


@pytest.fixture(autouse=True)
def cleanup_local_bus():
    """
    Ensures that the memory broker state is completely cleared between tests.
    This prevents state leakage (retained messages/subscriptions) which
    causes unpredictable failures in E2E tests.
    """
    if LocalBusConnector:
        LocalBusConnector._reset_broker_state()
    yield
    if LocalBusConnector:
        LocalBusConnector._reset_broker_state()
~~~~~
~~~~~python
# This file is intentionally left empty. It serves as a pytest discovery root
# for integration tests that span multiple packages.
# Fixtures specific to a single package should be placed in that package's
# own tests/conftest.py file.
~~~~~

#### Acts 3: 修复 `test_e2e_robustness.py` 中的连接器配置

我们将修改此测试，确保引擎和控制器共享同一个 `InProcessConnector` 实例。

~~~~~act
patch_file
packages/cascade-engine/tests/e2e/test_e2e_robustness.py
~~~~~
~~~~~python
    engine_bus, spy = bus_and_spy
    engine_connector = InProcessConnector()
    controller_connector = InProcessConnector()
    controller = ControllerTestApp(controller_connector)
~~~~~
~~~~~python
    engine_bus, spy = bus_and_spy
    engine_connector = InProcessConnector()
    controller = ControllerTestApp(engine_connector)
~~~~~

### 下一步建议

我们已经解决了测试隔离性和测试桩配置这两个核心问题。现在，测试套件应该能够稳定地通过了。我强烈建议您立即重新运行整个测试套件，以确认所有问题都已解决。

`pytest`
