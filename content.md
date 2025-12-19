简要回答
分析报告：
1.  **状态泄漏 (State Leakage)**：`LocalBusConnector` 的核心状态（订阅和保留消息）存储在类属性中。由于现有的 E2E 测试没有调用清理逻辑，测试用例之间的状态发生了严重的互相干扰。例如，上一个测试留下的“全局暂停”保留消息导致下一个测试的任务无法启动，从而引发 `TimeoutError`。
2.  **死任务干扰**：类属性中的 `_subscriptions` 积累了大量已经销毁的旧 Engine 的消息队列。当新测试发布消息时，总线会尝试向这些“僵尸队列”推送消息，虽然不会报错，但会造成资源浪费和逻辑混乱。
3.  **锁的生命周期**：类级别的 `_lock` 必须在每个测试开始前重置，以确保它总是绑定到当前测试的 `asyncio` 事件循环。

我将通过在全局 `conftest.py` 中注入自动清理逻辑来彻底解决这些稳定性问题。

## [COMMIT] fix(tests): 强制 LocalBusConnector 在测试间进行状态清理

### 错误分析
- **根本原因**：`LocalBusConnector` 作为一个内存中的单例 Broker，在测试环境下的生命周期管理缺失。
- **故障现象**：
    - `test_runtime_pause_interrupts_stage` 失败是因为它接收到了上一个测试残留的 `pause` 保留消息。
    - `test_e2e_rate_limit_control` 卡死通常是因为总线状态混乱或锁竞争。
    - `test_e2e_ttl_expiration` 失败是因为它跳过了预期的阻塞阶段，直接执行了任务。

### 用户需求
确保 Cascade 的测试套件在并发或顺序执行时具有完全的隔离性，消除由于内存总线状态残留导致的随机失败。

### 评论
在 E2E 测试中，基础设施的“洁净度”是确定性的前提。通过 `pytest` 钩子进行全局清理是处理此类类级别共享状态的最稳健方案。

### 目标
1.  修改 `tests/conftest.py`，增加一个 `autouse` 级别的异步 fixture。
2.  该 fixture 在每个测试开始前和结束后都调用 `LocalBusConnector._reset_broker_state()`。
3.  确保 `LocalBusConnector` 的锁和字典在重置时被彻底清空。

### 基本原理
利用 `pytest` 的生命周期管理，我们强制在每个测试用例执行前后将内存总线恢复到初始状态。这确保了每个测试都运行在一个“干净的宇宙”中，不再受其他测试留下的保留消息或订阅的影响。

### 标签
#intent/fix #flow/ready #priority/high 
#comp/tests #comp/runtime #concept/telemetry #scope/dx
#task/domain/testing #task/object/local-bus #task/action/cleanup
#task/state/end

---

### Script

#### Acts 1: 全局注入清理逻辑

我们修改 `tests/conftest.py`。如果系统中安装了 `cascade-runtime`，我们就自动执行清理。

~~~~~act
patch_file
tests/conftest.py
~~~~~
~~~~~python
import pytest
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event


class SpySubscriber:
~~~~~
~~~~~python
import pytest
import asyncio
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


class SpySubscriber:
~~~~~

#### Acts 2: 移除 `harness.py` 中残留的冗余逻辑

确保 `harness.py` 干净，不包含任何可能干扰 `LocalBusConnector` 状态的初始化代码。

~~~~~act
patch_file
tests/py/e2e/harness.py
~~~~~
~~~~~python
# Alias for backward compatibility with existing e2e tests
InProcessConnector = LocalBusConnector


class ControllerTestApp:
~~~~~
~~~~~python
# Alias for backward compatibility with existing e2e tests
# LocalBusConnector handles its own global state internally.
InProcessConnector = LocalBusConnector


class ControllerTestApp:
~~~~~

### 下一步建议

现在隔离机制已经建立，请重新运行全量测试：
`pytest tests/py/e2e/`

如果通过，说明 **里程碑 1.1** 已经完全达成。我们已经拥有了一个隔离、确定且健壮的内存实验环境。

接下来，我们将进入 **里程碑 1.2**：**实现尾递归优化 (TCO)**。这一步至关重要，它将允许工作流通过末尾返回自身来实现 Agent 的“永生”循环。我们需要修改 `Engine` 的核心运行循环。准备好了吗？
