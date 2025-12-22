You are absolutely right to be suspicious. This is a classic sign of a subtle but fundamental issue in the test harness itself. The repeated failure, even after logical fixes, means we've been treating symptoms, not the disease.

The logs gave us the final, crucial clue. The fact that *no* logs from the connector appeared when we expected them means the `publish` call is happening in a completely different, isolated context from the `subscribe` call.

**The root cause is test state pollution.**

The `LocalBusConnector` uses **class-level variables** (`_wildcard_subscriptions`, `_retained_messages`, etc.) to simulate a shared broker. However, `pytest` runs tests in isolation, but it doesn't automatically reset class-level state between test functions in different files. A previous test that used `LocalBusConnector` (like `test_e2e_control_plane.py`) likely left the shared state in an unexpected condition, or its background tasks were not properly cleaned up, causing our test to fail.

The solution is to explicitly and aggressively reset the connector's "broker state" before every test that uses it.

## [WIP] fix(tests): Isolate connector state to prevent test pollution

### 错误分析
测试 `test_engine_recovers_from_malformed_rate_limit` 的持续失败，根源在于 `LocalBusConnector` 的类级别状态在不同的 `pytest` 测试会话之间发生了泄漏。由于 `_wildcard_subscriptions` 等核心状态字典是类变量，一个测试的残留状态会污染下一个测试，导致 `Engine` 的 `subscribe` 和 `Controller` 的 `publish` 运行在不一致的、被破坏的 broker 状态之上，消息因此丢失。

### 用户需求
通过在测试开始前强制重置 `LocalBusConnector` 的共享状态，来修复测试的稳定性和可靠性。

### 评论
这是一个至关重要的修复，它加固了我们整个端到端测试体系的基石。一个可靠的测试套件必须保证每个测试都在一个干净、可预测的环境中运行。通过引入一个专门的 fixture 来管理共享状态的生命周期，我们根除了这种跨测试污染的风险。

### 目标
1.  在 `test_e2e_robustness.py` 中创建一个新的 `pytest` fixture，该 fixture 在每次测试前调用 `InProcessConnector._reset_broker_state()`。
2.  将此 fixture 应用于失败的测试函数。
3.  为了最终验证，暂时在 `publish` 方法中重新加入一个调试日志，以确认 `Engine` 的订阅在 `publish` 时是可见的。

### 基本原理
通过在测试的 `setup` 阶段调用 `_reset_broker_state()`，我们确保了 `_wildcard_subscriptions` 字典和 `_lock` 都是为当前测试的事件循环全新创建的，从而保证了测试的完全隔离和确定性。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/test-harness #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建并应用状态重置 Fixture

我们将创建 `clean_connector_state` fixture 并将其应用到测试中。

~~~~~act
patch_file
tests/engine/e2e/test_e2e_robustness.py
~~~~~
~~~~~python
from .harness import InProcessConnector, MockWorkExecutor, ControllerTestApp


@pytest.fixture
def mock_ui_bus(monkeypatch):
~~~~~
~~~~~python
from .harness import InProcessConnector, MockWorkExecutor, ControllerTestApp


@pytest.fixture(autouse=True)
def clean_connector_state():
    """Ensures the LocalBusConnector's class-level state is reset for each test."""
    InProcessConnector._reset_broker_state()
    yield
    InProcessConnector._reset_broker_state()


@pytest.fixture
def mock_ui_bus(monkeypatch):
~~~~~

#### Acts 2: 重新引入关键调试日志以进行最终验证

我们只在 `publish` 方法中添加一个日志，打印出订阅列表的状态。这将是最终的证据。

~~~~~act
patch_file
packages/cascade-connector-local/src/cascade/connectors/local/bus.py
~~~~~
~~~~~python
    async def publish(
        self, topic: str, payload: Any, qos: int = 0, retain: bool = False
    ) -> None:
        if not self._is_connected:
            return

        async with self._get_lock():
            # Handle Retention
            if retain:
~~~~~
~~~~~python
    async def publish(
        self, topic: str, payload: Any, qos: int = 0, retain: bool = False
    ) -> None:
        if not self._is_connected:
            return

        async with self._get_lock():
            # --- DEBUG ---
            print(f"DEBUG PUBLISH '{topic}': WILDCARD SUBS: {list(self._wildcard_subscriptions.keys())}")
            # --- END DEBUG ---

            # Handle Retention
            if retain:
~~~~~

### 下一步建议

请运行测试。

这次，你应该会在日志中看到：
`DEBUG PUBLISH 'cascade/constraints/global': WILDCARD SUBS: ['cascade/constraints/#']`

紧接着，测试应该会通过。如果成功，我们就可以移除最后的调试日志，并生成最终的 `[COMMIT]` 计划了。
