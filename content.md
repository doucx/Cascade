好的，我将同时处理 `cascade-connector-local` 和 `cascade-connector-mqtt` 两个连接器包的测试结构，根据它们的测试性质进行分类。

## [WIP] refactor(tests): 分离连接器包的测试 (MQTT: Unit, Local: Integration)

### 用户需求

继续对 `cascade-connector-local` 和 `cascade-connector-mqtt` 包进行测试结构重构，将测试文件分离到 `unit/` 和 `integration/` 目录中。

### 评论

这次重构的分类结果很好地体现了测试原则：
*   **`cascade-connector-local`**: 测试的是它内部的、自洽的消息传递机制，这是该组件的完整功能合约，因此属于**集成测试**（Component-Internal Integration）。
*   **`cascade-connector-mqtt`**: 通过对外部网络库 `aiomqtt` 的全面 Mock，它的测试专注于验证 `MqttConnector` 自身的逻辑、参数传递和生命周期管理，使其成为纯粹的**单元测试**。

这种明确的分离将极大地增强测试套件的清晰度和维护性。

### 目标

1.  在 `packages/cascade-connector-local/tests/` 下创建 `integration/` 目录，并将所有文件移入。
2.  在 `packages/cascade-connector-mqtt/tests/` 下创建 `unit/` 目录，并将所有文件移入。
3.  清理旧的、不再需要的顶级测试文件。

### 基本原理

如评论所述，我们严格遵循测试边界原则：
*   **Local Connector**: 专注于测试组件的完整行为，即使没有外部依赖，也属于集成测试。
*   **MQTT Connector**: 彻底 Mock 外部依赖，专注于测试 `MqttConnector` 类的实例化、方法调用顺序和参数转换（例如，将 Python Dict 转换为 JSON 字符串），是典型的单元测试。

### 标签

#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-structure #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 处理 `cascade-connector-local` (Integration)

创建 `integration` 目录并迁移文件。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-connector-local/tests/integration
~~~~~

~~~~~act
move_file
packages/cascade-connector-local/tests/test_local_connector.py
packages/cascade-connector-local/tests/integration/test_local_connector.py
~~~~~
~~~~~act
move_file
packages/cascade-connector-local/tests/test_local_connector.stitcher.yaml
packages/cascade-connector-local/tests/integration/test_local_connector.stitcher.yaml
~~~~~

#### Acts 2: 处理 `cascade-connector-mqtt` (Unit)

创建 `unit` 目录并迁移文件。由于 MQTT Connector 测试使用了 Mock，它们属于单元测试。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-connector-mqtt/tests/unit
~~~~~

~~~~~act
move_file
packages/cascade-connector-mqtt/tests/conftest.py
packages/cascade-connector-mqtt/tests/unit/conftest.py
~~~~~
~~~~~act
move_file
packages/cascade-connector-mqtt/tests/conftest.stitcher.yaml
packages/cascade-connector-mqtt/tests/unit/conftest.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-connector-mqtt/tests/test_connector.py
packages/cascade-connector-mqtt/tests/unit/test_connector.py
~~~~~
~~~~~act
move_file
packages/cascade-connector-mqtt/tests/test_connector.stitcher.yaml
packages/cascade-connector-mqtt/tests/unit/test_connector.stitcher.yaml
~~~~~

### 下一步建议

接下来，我们将继续处理 `cascade-graph` 包。我将分析该包的测试文件，并生成相应的迁移计划。
