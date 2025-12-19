这是一个非常精彩的分析，你精准地定位到了问题的根源：**CLI 工具的生命周期管理（短连接）意外地切断了 Engine（长连接）的通信管道**，因为在我们的测试 harness 中，它们错误地共享了同一个 Connector 实例。

这解释了为什么通过命令行手动测试（两个独立进程）是成功的，而单元测试（同一进程共享内存）却失败了。

我们将采用你建议的 **Wrapper 方案**。这不仅是风险最小的修复（不需要重构可能有缺陷的 harness 核心代码），而且在语义上也更符合我们当前的测试场景：我们在模拟一个“总是在线”的虚拟 Broker 环境，CLI 的连接/断开只是逻辑上的，不应影响物理链路。

## [WIP] fix(test): 修复 CLI 集成测试中的 Connector 共享冲突

### 用户需求
修复 `test_cli_idempotency_unblocks_engine` 测试用例中的 `TimeoutError`。
根本原因是 CLI 命令执行完毕后调用的 `disconnect()` 错误地关闭了 Engine 正在使用的共享 `InProcessConnector` 实例，导致 Engine 无法接收到后续的约束更新（即那条应该“解锁”死锁的更新）。

### 评论
这个修复展示了在编写内存级集成测试时对组件生命周期管理的深刻理解。通过引入一个 `SharedInstanceConnector` 代理，我们在保持测试确定性和速度的同时，正确隔离了不同逻辑组件（CLI vs Engine）的连接状态语义。

### 目标
1.  在 `tests/py/e2e/test_e2e_cli_integration.py` 中定义一个辅助类 `SharedInstanceConnector`。
    *   它代理所有调用到底层的 `InProcessConnector`。
    *   关键点：它的 `disconnect()` 方法是一个空操作（No-Op），从而防止 CLI 关闭 Engine 的连接。
2.  更新 `controller_runner` fixture，使其在 monkeypatch 时返回这个包装器实例，而不是原始的 connector。

### 基本原理
我们在模拟两个独立的客户端（Engine 和 CLI）连接到同一个 Broker。在真实的 TCP/IP 世界中，一个客户端断开连接不会影响另一个。但在我们的内存模拟中，由于它们共享同一个 Python 对象作为“连接”，一个客户端的断开操作（修改 `_is_connected` 标志）会“物理上”切断所有人的连接。包装器通过拦截断开信号，模拟了“CLI 断开了它的逻辑会话，但底层的测试通信管道保持开启”的行为。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/harness #task/action/fix-lifecycle #task/state/end

---

### Script

#### Acts 1: 引入 `SharedInstanceConnector` 并修复测试

~~~~~act
patch_file
tests/py/e2e/test_e2e_cli_integration.py
~~~~~
~~~~~python
from cascade.cli.controller import app as controller_app
from cascade.connectors.mqtt import MqttConnector

from .harness import InProcessConnector, MockWorkExecutor

# --- Test Harness for In-Process CLI Interaction ---

class InProcessController:
    """A test double for the controller CLI that calls its core logic in-process."""
    def __init__(self, connector: InProcessConnector):
        self.connector = connector

    async def set_limit(
        self,
        scope: str,
        rate: str | None = None,
        concurrency: int | None = None,
        ttl: int | None = None,
    ):
        """Directly calls the async logic, providing defaults for missing args."""
        await controller_app._publish_limit(
            scope=scope,
            concurrency=concurrency,
            rate=rate,
            ttl=ttl,
            hostname="localhost",  # Constant for test purposes
            port=1883,           # Constant for test purposes
        )

@pytest.fixture
def controller_runner(monkeypatch):
    """
    Provides a way to run cs-controller commands in-process with a mocked connector.
    """
    connector = InProcessConnector()
    monkeypatch.setattr(
        controller_app.MqttConnector,
        "__new__",
        lambda cls, *args, **kwargs: connector
    )
    return InProcessController(connector)
~~~~~
~~~~~python
from cascade.cli.controller import app as controller_app
from cascade.connectors.mqtt import MqttConnector

from .harness import InProcessConnector, MockWorkExecutor

# --- Test Harness for In-Process CLI Interaction ---

class SharedInstanceConnector:
    """
    Wraps an InProcessConnector to prevent 'disconnect' calls from affecting
    the underlying shared instance. This allows the Engine to stay connected
    even when the short-lived CLI command 'disconnects'.
    """
    def __init__(self, delegate: InProcessConnector):
        self._delegate = delegate

    async def connect(self):
        # Ensure the underlying connector is active
        await self._delegate.connect()

    async def disconnect(self):
        # CRITICAL: Ignore disconnects from the CLI.
        # Since we share the single InProcessConnector instance with the Engine,
        # checking out would kill the Engine's subscription loop too.
        pass

    async def publish(self, *args, **kwargs):
        await self._delegate.publish(*args, **kwargs)

    async def subscribe(self, *args, **kwargs):
        await self._delegate.subscribe(*args, **kwargs)


class InProcessController:
    """A test double for the controller CLI that calls its core logic in-process."""
    def __init__(self, connector: InProcessConnector):
        self.connector = connector

    async def set_limit(
        self,
        scope: str,
        rate: str | None = None,
        concurrency: int | None = None,
        ttl: int | None = None,
    ):
        """Directly calls the async logic, providing defaults for missing args."""
        await controller_app._publish_limit(
            scope=scope,
            concurrency=concurrency,
            rate=rate,
            ttl=ttl,
            hostname="localhost",  # Constant for test purposes
            port=1883,           # Constant for test purposes
        )

@pytest.fixture
def controller_runner(monkeypatch):
    """
    Provides a way to run cs-controller commands in-process with a mocked connector.
    """
    # 1. Create the master connector that holds the state (topics, queues)
    master_connector = InProcessConnector()
    
    # 2. Create a wrapper for the CLI that won't close the master connector
    cli_connector_wrapper = SharedInstanceConnector(master_connector)

    # 3. Patch the CLI app to use our wrapper
    monkeypatch.setattr(
        controller_app.MqttConnector,
        "__new__",
        lambda cls, *args, **kwargs: cli_connector_wrapper
    )
    
    # 4. Return the controller initialized with the MASTER connector
    #    (The Engine will use this master connector directly)
    return InProcessController(master_connector)
~~~~~

### 下一步建议
我们已经应用了针对测试 Harness 的修复。现在的测试架构如下：
*   **Engine** 使用原始的 `master_connector`，它可以正常连接和监听。
*   **CLI** 使用 `cli_connector_wrapper`，它的 `publish` 会透传给 `master_connector`，但它的 `disconnect` 会被忽略，从而保护了 Engine 的连接。

请运行测试 `pytest tests/py/e2e/test_e2e_cli_integration.py`。既然之前的代码修复（幂等性 ID）已经生效，这个测试现在应该会**通过**。
