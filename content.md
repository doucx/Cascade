你的分析非常准确。

根据路线图 `Cascade 架构演进技术路线图 (v2.0).md` 和当前的代码库状态，我们可以确认：

1.  **阶段 2.4 (引擎集成) 确实已完成**：`cascade-runtime` 中的 `Engine` 和 `TelemetrySubscriber` 已经具备了与 `Connector` 协议交互的所有必要钩子。引擎已经准备好使用一个连接器，但目前还没有具体的实现。
2.  **阶段 2.3 (实现 MQTT 连接器) 尚未开始**：代码库中不存在 `cascade-connector-mqtt` 这个独立的包，也没有任何 `aiomqtt` 的依赖或实现代码。

因此，你的判断是正确的，当前最合适的任务就是开始实现 **阶段 2.3**，创建 `cascade-connector-mqtt` 包。这将使我们能够真正利用已经构建好的遥测基础设施，让 Cascade 工作流的状态变得可观测。

我将生成一个计划来创建这个新包的基本结构和骨架代码。

## [WIP] feat: 创建 MQTT 连接器包 (`cascade-connector-mqtt`)

### 用户需求
根据项目路线图，需要开始实现阶段 2.3，即创建一个新的、独立的 `cascade-connector-mqtt` 包。这个包将提供 `Connector` 协议的具体 MQTT 实现，从而启用 Cascade 的遥测功能。

### 评论
这是解锁 Cascade 可观测性能力的关键一步。通过创建一个独立的包，我们遵循了“零强制依赖”的设计原则，确保只有需要遥测功能的用户才需要安装 `aiomqtt` 等重量级依赖。此计划将为该连接器奠定基础，创建必要的项目文件和代码骨架。

### 目标
1.  在 `packages` 目录下创建 `cascade-connector-mqtt` 的完整目录结构。
2.  创建 `pyproject.toml` 文件，定义项目元数据和其对 `cascade-interfaces` 及 `aiomqtt` 的依赖。
3.  创建 `MqttConnector` 类的骨架，使其符合 `cascade.interfaces.protocols.Connector` 协议。
4.  创建一个初步的测试文件，为后续的 TDD 开发做准备。

### 基本原理
我们将遵循现有的 monorepo 结构，在 `packages/` 目录下添加一个新的子包。这个包将是自包含的，只依赖于 `cascade-interfaces` 来获取协议定义。初始实现将是一个带有 `TODO` 注释的骨架，明确后续开发需要完成的具体逻辑，如 `connect`, `publish`, `subscribe` 和 `disconnect` 方法的实现。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/sync #scope/api #ai/instruct #task/domain/runtime #task/object/mqtt-connector #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建新包的目录结构

首先，我们在 `packages` 目录下创建 `cascade-connector-mqtt` 的标准 Python 包结构。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-connector-mqtt/src/cascade/connectors/mqtt
mkdir -p packages/cascade-connector-mqtt/tests
~~~~~

#### Acts 2: 定义项目配置文件

创建 `pyproject.toml` 文件，声明项目名称、版本、依赖项和构建配置。

~~~~~act
write_file
packages/cascade-connector-mqtt/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-connector-mqtt"
version = "0.1.0"
description = "An MQTT connector for the Cascade workflow engine."
requires-python = ">=3.8"
dependencies = [
  "cascade-interfaces",
  "aiomqtt"
]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true
~~~~~

#### Acts 3: 创建包的初始化文件和连接器骨架

现在，我们创建 `__init__.py` 文件来暴露 `MqttConnector`，并创建 `connector.py` 文件，其中包含符合 `Connector` 协议的类骨架。

~~~~~act
write_file
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-interfaces) in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .connector import MqttConnector

__all__ = ["MqttConnector"]
~~~~~

~~~~~act
write_file
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/connector.py
~~~~~
~~~~~python
from typing import Callable, Awaitable, Dict, Any

try:
    import aiomqtt
except ImportError:
    aiomqtt = None


class MqttConnector:
    """
    Implements the Connector protocol for MQTT.

    This connector enables Cascade to publish telemetry data to an MQTT broker
    and subscribe to control commands.
    """
    def __init__(self, hostname: str, port: int = 1883, **kwargs):
        if aiomqtt is None:
            raise ImportError(
                "The 'aiomqtt' library is required to use the MqttConnector. "
                "Please install it: pip install cascade-connector-mqtt"
            )
        self.hostname = hostname
        self.port = port
        self.client_kwargs = kwargs
        self._client: "aiomqtt.Client" | None = None

    async def connect(self) -> None:
        """Establishes a connection to the MQTT Broker."""
        # TODO: Implement connection logic, including LWT message.
        # Use self.hostname, self.port, and self.client_kwargs.
        pass

    async def disconnect(self) -> None:
        """Disconnects from the MQTT Broker and cleans up resources."""
        # TODO: Implement disconnection logic.
        pass

    async def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0) -> None:
        """Publishes a message to a specific topic."""
        # TODO: Implement publishing logic.
        # - Ensure payload is JSON serialized.
        # - Make it fire-and-forget (e.g., using asyncio.create_task).
        # - Handle potential connection errors gracefully.
        pass

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        """Subscribes to a topic to receive messages."""
        # TODO: Implement subscription logic.
        # - The client needs a message handling loop.
        # - This method should register the topic and callback.
        # - The loop will decode JSON and invoke the callback.
        pass
~~~~~

#### Acts 4: 创建初始测试文件

最后，我们创建一个空的测试文件，为接下来的 TDD 开发周期做好准备。

~~~~~act
write_file
packages/cascade-connector-mqtt/tests/test_connector.py
~~~~~
~~~~~python
import pytest
from cascade.connectors.mqtt import MqttConnector

def test_mqtt_connector_instantiation():
    """
    Tests that the MqttConnector can be instantiated.
    """
    try:
        connector = MqttConnector(hostname="localhost")
        assert connector.hostname == "localhost"
    except ImportError:
        pytest.skip("aiomqtt not installed, skipping MQTT connector tests.")

# TODO: Add more tests for connect, disconnect, publish, and subscribe methods using a mock broker.
~~~~~

### 下一步建议
我们已经成功创建了 `cascade-connector-mqtt` 包的骨架。

下一步是采用 TDD 的方式，逐一实现 `MqttConnector` 类中的 `TODO` 功能点：
1.  **`connect` / `disconnect`**: 编写测试，使用 mock 的 `aiomqtt.Client` 来验证连接和断开连接方法是否被正确调用。
2.  **`publish`**: 编写测试，验证 `publish` 方法是否将 Python 字典正确序列化为 JSON 字符串，并调用了 mock client 的 `publish` 方法。
3.  **`subscribe`**: 这是最复杂的部分，需要模拟消息的接收，并验证注册的回调函数是否被正确调用。

如果你同意，我们可以从实现 `connect` 和 `disconnect` 方法及其测试开始。
