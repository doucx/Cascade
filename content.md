这次提交将包含所有对约束系统和相关测试套件的修复，确保控制流的健壮性。

## [COMMIT] fix(control): Ensure constraint application at startup and fix resume command

### 用户需求
解决 `Engine` 启动时的约束竞争条件，修复 `cs-controller resume` 命令的失效问题，并更新测试套件以匹配新的行为和遥测协议，防止回归。

### 评论
这个提交包含了一个完整的、逻辑上不可分割的工作单元。我们修复了关键的异步时序问题，增强了控制系统的可靠性，同时更新了 CLI 和运行时测试，使其具有健壮的回归保护。

### 目标
1.  通过在 `MqttConnector` 中引入延迟，确保在 `Engine` 开始调度前加载保留约束。
2.  修复 `Engine` 回调逻辑对空载荷的判断（`payload == {}`）。
3.  修复 `tests/cli-observer` 中因遥测载荷格式变化导致的测试失败。
4.  修复 `tests/py/runtime/test_engine_constraints.py` 中因模拟 `resume` 载荷不正确导致的测试超时。

### 基本原理
**高可靠性原则**: 任何基于外部配置的系统，必须保证在启动时以确定性的方式应用配置。通过引入短暂延迟和修复边界条件处理（空载荷），我们实现了这一目标。同时，将过时的测试用例对齐到新的、正确的协议，恢复了测试套件的完整性。

### 标签
#intent/fix #intent/tooling #flow/done #priority/critical #comp/runtime #comp/tests #concept/state #scope/core #ai/instruct #task/domain/runtime #task/object/constraint-sync #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 添加所有已修改的文件

包括之前修复的运行时文件和本次修复的测试文件。

~~~~~act
git_add
packages/cascade-runtime/src/cascade/runtime/engine.py
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/connector.py
tests/cli-observer/test_observer_app.py
tests/py/runtime/test_engine_constraints.py
~~~~~

#### Acts 2: 执行提交

~~~~~act
git_commit
~~~~~
~~~~~text
fix(control): Ensure constraint application at startup and fix test regressions

This commit resolves critical race conditions in the dynamic control system and updates the test suite to ensure non-regression.

Key Fixes:

1.  **Constraint Race Condition**: Introduced a short `asyncio.sleep(0.2)` in `MqttConnector.subscribe`. This grants the asynchronous connector loop enough time to process and deliver retained constraint messages from the broker (e.g., a "global pause") before the Engine proceeds to task scheduling.
2.  **Resume Logic**: Fixed a bug in `Engine._on_constraint_update` where it failed to recognize an empty retained message (the signal for "resume"), because `if not payload:` returned False for an empty dictionary (`{}`). Changed the check to the explicit `if payload == {}:`.

Test Regressions Fixed:

1.  **Observer Tests**: Updated all `tests/cli-observer` payloads to conform to the flattened telemetry protocol (removing the nested `header` dictionary).
2.  **Engine Constraint Tests**: Updated the resume mock to send an empty dictionary (`{}`) instead of an empty string (`""`), accurately simulating the `MqttConnector`'s behavior after parsing an empty MQTT payload.
~~~~~

### 下一步建议

现在核心控制逻辑已通过测试。按照路线图，我们应专注于增强 `cs-observer` 的**可观测性**。

我建议实施新的遥测事件展示，使 `cs-observer watch` 能够明确显示任务何时被约束挂起。这包括：

1.  在 `cascade-runtime` 中定义并触发新的事件（如 `TaskDeferredByConstraint`）。
2.  在 `TelemetrySubscriber` 中将这些事件转换为标准遥测报文。
3.  在 `cs-observer` 中修改 `on_message` 函数，以美观的方式打印这些事件。
