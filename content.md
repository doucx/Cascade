这是一个包含两个子任务的重构计划：分离 `cascade-cli-controller` 和 `cascade-cli-observer` 两个包的测试。

## [WIP] refactor(tests): 分离 cascade-cli-controller 和 observer 的测试

### 用户需求

继续测试分离任务。将 `cascade-cli-controller` 和 `cascade-cli-observer` 包中的现有测试文件迁移到新创建的 `unit/` 或 `integration/` 目录中。

### 评论

这两个包是 CLI 工具，其测试主要围绕 `Typer` CLI 运行器和 `MqttConnector` 的交互展开。
*   `controller` 的两个测试都涉及 CLI 调用或网络发布逻辑，被归类为集成测试。
*   `observer` 的测试中，事件处理逻辑可以被视为单元测试，而验证整个发布-订阅契约的测试则被视为集成测试。

### 目标

1.  重构 `packages/cascade-cli-controller/tests`：创建 `integration/` 目录，并将所有现有测试文件移动到其中。
2.  重构 `packages/cascade-cli-observer/tests`：创建 `unit/` 和 `integration/` 目录，并按以下分类移动文件：
    *   `test_observer_app.py` -> `unit/` (验证独立的事件回调逻辑)。
    *   `test_telemetry_contract.py` -> `integration/` (验证跨模块的数据流契约)。

### 基本原理

对于 CLI 相关的测试，我们遵循以下原则：
1.  **Controller Tests**: 它们测试的是“通过 CLI 触发 MQTT 发布”的流程，这涉及到 CLI/HTTP/MQTT 三个组件的集成，因此是集成测试。
2.  **Observer Tests**:
    *   `test_observer_app.py` 仅测试 `on_message` 这个核心回调函数，隔离了网络连接，是验证业务逻辑的单元测试。
    *   `test_telemetry_contract.py` 模拟了整个发布-订阅生命周期，是标准的集成测试。

### 标签

#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-structure #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 packages/cascade-cli-controller/tests

创建 `integration` 目录并迁移所有测试文件。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-cli-controller/tests/integration
~~~~~

~~~~~act
move_file
packages/cascade-cli-controller/tests/test_controller_app.py
packages/cascade-cli-controller/tests/integration/test_controller_app.py
~~~~~
~~~~~act
move_file
packages/cascade-cli-controller/tests/test_controller_app.stitcher.yaml
packages/cascade-cli-controller/tests/integration/test_controller_app.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-cli-controller/tests/test_controller_cli.py
packages/cascade-cli-controller/tests/integration/test_controller_cli.py
~~~~~
~~~~~act
move_file
packages/cascade-cli-controller/tests/test_controller_cli.stitcher.yaml
packages/cascade-cli-controller/tests/integration/test_controller_cli.stitcher.yaml
~~~~~

#### Acts 2: 重构 packages/cascade-cli-observer/tests

创建 `unit` 和 `integration` 目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-cli-observer/tests/unit packages/cascade-cli-observer/tests/integration
~~~~~

#### Acts 3: 迁移 Observer 单元测试

将验证 `on_message` 事件处理逻辑的文件移动到 `unit`。

~~~~~act
move_file
packages/cascade-cli-observer/tests/test_observer_app.py
packages/cascade-cli-observer/tests/unit/test_observer_app.py
~~~~~
~~~~~act
move_file
packages/cascade-cli-observer/tests/test_observer_app.stitcher.yaml
packages/cascade-cli-observer/tests/unit/test_observer_app.stitcher.yaml
~~~~~

#### Acts 4: 迁移 Observer 集成测试

将验证生产者-消费者契约的文件移动到 `integration`。

~~~~~act
move_file
packages/cascade-cli-observer/tests/test_telemetry_contract.py
packages/cascade-cli-observer/tests/integration/test_telemetry_contract.py
~~~~~
~~~~~act
move_file
packages/cascade-cli-observer/tests/test_telemetry_contract.stitcher.yaml
packages/cascade-cli-observer/tests/integration/test_telemetry_contract.stitcher.yaml
~~~~~

### 下一步建议

我们已经完成了对 CLI 工具测试的重构。接下来可以继续处理其余的包，如 `pyneedle-pointer` 和 `pyneedle-runtime`，以实现整个代码库的测试结构统一。
