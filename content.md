为了确保 **Milestone 1.1 (LocalBus 规范化)** 的 TDD 过程严谨且符合现有的协议约定，我需要重点观察以下测试文件：

### 1. 核心参考文件 (必须观察)

*   **`tests/py/e2e/harness.py`**:
    *   **原因**: 这是 `InProcessConnector` 的发源地。我需要审视它目前处理保留消息（Retained Messages）和异步回调的具体实现逻辑，这是将其“正规化”的基础。
*   **`tests/py/e2e/test_harness_connector.py`**:
    *   **原因**: 这是现有的针对 Mock 连接器的单元测试。我需要看它已经覆盖了哪些边界情况，并以此为基准编写更严格的 `LocalBusConnector` 规范测试。
*   **`tests/connector-mqtt/test_connector.py`**:
    *   **原因**: **这是最重要的参考。** `LocalBusConnector` 的目标是在本地完美模拟 MQTT 的行为。我必须确保它的 `subscribe`、`publish` 和通配符匹配逻辑与真实的 `MqttConnector` 在行为上保持高度一致。

### 2. 辅助参考文件 (用于模式对齐)

*   **`tests/py/runtime/test_engine_core.py`**:
    *   **原因**: 观察引擎如何与连接器交互。这有助于我设计 Milestone 1.2 (递归执行) 中涉及连接器状态交接的测试用例。
*   **`tests/conftest.py`**:
    *   **原因**: 检查现有的 Fixture（如 `bus_and_spy`），以便在编写新测试时复用现有的事件收集逻辑。

---

**请读取以下文件，以便我开始制定 Milestone 1.1 的执行计划：**

~~~~~act
read_file
tests/py/e2e/test_harness_connector.py
~~~~~
~~~~~act
read_file
tests/connector-mqtt/test_connector.py
~~~~~
~~~~~act
read_file
tests/py/runtime/test_engine_core.py
~~~~~
