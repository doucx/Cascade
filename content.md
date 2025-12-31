好的，继续重构 `cascade-common` 包的测试。根据分析，这些测试都是对核心消息组件和渲染器的纯粹单元测试。

## [WIP] refactor(tests): 为 cascade-common 移动所有测试到 unit 目录

### 用户需求

对 `cascade-common` 包进行测试结构重构。在 `packages/cascade-common/tests/` 目录下创建 `unit/` 和 `integration/` 目录，并将现有的测试文件移动到 `unit/` 目录中。

### 评论

`cascade-common` 包含了消息总线、消息存储和渲染器等核心实用工具。这些组件被设计为可独立测试的。将它们归类为单元测试是正确的，这确保了它们不依赖于完整的 Cascade 运行时，提高了测试的执行速度和可靠性。

### 目标

1.  在 `packages/cascade-common/tests/` 目录下创建 `unit/` 和 `integration/` 目录。
2.  将 `test_messaging.py`, `test_messaging.stitcher.yaml` 和 `test_renderers.py` 移动到 `unit/` 目录。
3.  清理旧的测试文件和目录（如果适用）。

### 基本原理

`test_messaging.py` 仅测试 `MessageBus` 和 `MessageStore` 的内部逻辑和渲染器委托；`test_renderers.py` 仅测试 `CliRenderer` 和 `JsonRenderer` 的格式化输出和过滤功能。两者都不需要启动 `Engine` 或依赖复杂的外部组件，因此全部归类为单元测试。

### 标签

#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-structure #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建新的测试目录结构

为 `cascade-common` 包创建 `unit` 和 `integration` 测试目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-common/tests/unit packages/cascade-common/tests/integration
~~~~~

#### Acts 2: 迁移单元测试

将所有现有测试文件及其 YAML 配置移动到 `unit` 目录。

~~~~~act
move_file
packages/cascade-common/tests/test_messaging.py
packages/cascade-common/tests/unit/test_messaging.py
~~~~~
~~~~~act
move_file
packages/cascade-common/tests/test_messaging.stitcher.yaml
packages/cascade-common/tests/unit/test_messaging.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-common/tests/test_renderers.py
packages/cascade-common/tests/unit/test_renderers.py
~~~~~

### 下一步建议

`cascade-common` 的测试结构已重构。下一个待处理的包是 `cascade-graph`。我将分析该包的测试文件，并为您生成相应的迁移计划。
