My apologies, that was a clear mistake on my part. My previous patch correctly identified that the engine and controller needed to share one connector, but I failed to update all usages of the old variable name. I removed `controller_connector` but missed the direct `.publish()` call that was still using it.

I will create a plan to fix this simple `NameError`.

## [WIP] fix: Correct variable name after test harness refactor

### 错误分析
在 `test_e2e_robustness.py` 测试中，我之前的修改旨在统一 `Engine` 和 `ControllerTestApp` 使用同一个 `InProcessConnector` 实例。我正确地将 `engine_connector` 传递给了 `ControllerTestApp`，但随后完全删除了 `controller_connector` 变量。

然而，测试的后续部分有一行代码 `await controller_connector.publish(...)`，它绕过了 `ControllerTestApp` 的抽象，直接向连接器发布一个格式错误的消息。由于 `controller_connector` 变量已被删除，这行代码现在引发了 `NameError`。

正确的做法是让这个直接调用也使用共享的 `engine_connector` 实例。

### 用户需求
用户要求修复在 `test_e2e_robustness.py` 中因变量未定义而导致的 `NameError`。

### 评论
这是一个简单的疏忽。在重构中统一变量是正确的，但我没有完成所有引用的更新。这个修复将完成上一个计划的意图，使测试逻辑正确无误。

### 目标
1.  在 `test_e2e_robustness.py` 文件中，将对未定义的 `controller_connector` 的调用替换为对 `engine_connector` 的调用。

### 基本原理
为了让测试正常工作，向消息总线发布消息的操作（无论是通过测试辅助工具还是直接调用）都必须使用引擎正在监听的同一个连接器实例。在当前上下文中，这个实例由 `engine_connector` 变量持有。因此，我们只需将错误的变量名更正为正确的即可。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-harness #task/action/bug-fix #task/state/continue

---
### Script

#### Acts 1: 修正 `test_e2e_robustness.py` 中的变量名

我们将修改该文件，使用正确的连接器变量 `engine_connector` 来发布消息。

~~~~~act
patch_file
packages/cascade-engine/tests/e2e/test_e2e_robustness.py
~~~~~
~~~~~python
    payload = asdict(malformed_constraint)
    await controller_connector.publish("cascade/constraints/global", payload)
~~~~~
~~~~~python
    payload = asdict(malformed_constraint)
    await engine_connector.publish("cascade/constraints/global", payload)
~~~~~

### 下一步建议

这个小修正应该能解决最后的测试失败。请重新运行测试套件以确认所有测试现在都已通过。
