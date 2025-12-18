这是一个仅包含文件系统更改和导入路径修正的 `[COMMIT]` 计划。

## [COMMIT] fix(tests): Correct imports and move renderer tests to common package

### 用户需求
修复由于将 `Renderer` 模块从 `cascade-runtime` 迁移到 `cascade-common` 导致的测试收集失败问题。并优化测试结构，使渲染器单元测试与源代码位于同一包结构下。

### 评论
这是一次必要的清理工作，确保测试套件能正常运行。将渲染器单元测试移动到 `tests/common` 下是符合架构原则的，因为它测试的是 `cascade-common` 包中的通用组件。

### 目标
1.  将 `tests/runtime/test_renderers.py` 移动到 `tests/common/test_renderers.py`。
2.  更新所有受影响文件的导入路径。

### 基本原理
遵循 `d3-constraint-quipu-plan-script-rules-D3-P2` 约束，文件修改和 Git 提交必须隔离在不同的 Plan 中。本次 Plan 负责提交上一步骤中已完成的文件修复和结构优化。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #comp/common #comp/runtime #concept/tooling #scope/dx #ai/instruct #task/domain/testing #task/object/import-fix #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 提交文件变更

将文件移动和内容修改添加到暂存区，并执行提交。

~~~~~act
git_add
tests/runtime/test_event_bus.py
tests/common/test_renderers.py
packages/cascade-common/src/cascade/common/renderers.py
packages/cascade-runtime/src/cascade/runtime/renderers.py
packages/cascade-common/src/cascade/common/locales/en/cli_messages.json
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
packages/cascade-py/src/cascade/__init__.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(tests): Correct imports and move renderers to cascade-common

This commit finalizes the refactoring of the messaging architecture:

1. **Renderer Migration**: Moved `CliRenderer` and `JsonRenderer` from `cascade-runtime` to the core `cascade-common` package, establishing them as shared components for the entire ecosystem.
2. **CLI Message Registration**: Introduced `cli_messages.json` to store semantic message IDs for CLI tools, fully decoupling their logic from presentation.
3. **CLI Refactoring**: `cs-observer` and `cs-controller` were refactored to use the message bus (`bus.info`) instead of direct console output (`typer.echo`).
4. **Test Fixes**: Fixed `ImportError` in tests by updating import paths and moving `test_renderers.py` to `tests/common` to match the new package structure.
~~~~~

### 下一步建议
我们已经完成了消息总线和渲染器的重构以及相关的测试修复。下一步是开始实现 `cs-observer` 的核心功能：
1.  **实现 MQTT 订阅**: 在 `cs-observer` 中连接到 MQTT Broker。
2.  **事件处理**: 编写逻辑，从 MQTT 流中接收和解析 `TelemetryEvent`。
3.  **Rich 渲染**: 利用 `RichCliRenderer` 清晰地展示实时遥测数据。

我建议从 `cascade-cli-observer/src/cascade/cli/observer/app.py` 入手，集成 `MqttConnector` 的 `subscribe` 逻辑。
