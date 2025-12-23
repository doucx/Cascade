好的，我看到了这个 `AttributeError`。问题很明确：`test_engine_vm_integration.py` 中的 `patch` 路径没有随着我们的文件拆分而更新。

旧路径: `cascade.runtime.strategies.BlueprintBuilder`
新路径: `cascade.runtime.strategies.vm.BlueprintBuilder` (因为 `BlueprintBuilder` 现在被 `vm.py` 导入和使用)

这是一个简单的修复。我将更新测试文件中的 `patch` 路径，使其指向正确的位置。

## [WIP] fix(tests): Update patch path for VM strategy in integration test

### 用户需求
在将 `strategies.py` 拆分为一个模块后，`test_engine_vm_integration.py` 中用于 Mock `BlueprintBuilder` 和 `VirtualMachine` 的 `patch` 路径已失效，导致测试失败。需要更新这些路径。

### 评论
这是一个在重构后常见的清理任务。测试代码与被测代码的结构紧密耦合，当被测代码移动时，测试中的硬编码路径也必须随之更新。

### 目标
1.  修改 `tests/engine/integration/test_engine_vm_integration.py`。
2.  将 `patch("cascade.runtime.strategies.BlueprintBuilder")` 更新为 `patch("cascade.runtime.strategies.vm.BlueprintBuilder")`。
3.  将 `patch("cascade.runtime.strategies.VirtualMachine")` 更新为 `patch("cascade.runtime.strategies.vm.VirtualMachine")`。

### 基本原理
`unittest.mock.patch` 需要一个精确的、可导入的字符串路径来定位要替换的对象。在我们将 `VMExecutionStrategy` 及其依赖项移动到 `strategies/vm.py` 文件后，旧的路径 `cascade.runtime.strategies` 不再包含这些类，必须使用新的、更具体的子模块路径。

### 标签
#intent/fix #flow/ready #priority/high
#comp/tests #comp/engine
#ai/instruct
#task/domain/testing #task/object/test-suite #task/action/fix
#task/state/continue #task/status/active

---

### Script

#### Acts 1: Update Mock Patch Paths

我们将精确地替换测试文件中过时的 `patch` 路径。

~~~~~act
patch_file
tests/engine/integration/test_engine_vm_integration.py
~~~~~
~~~~~python
    # Mock BlueprintBuilder and VirtualMachine to verify interaction
    with patch("cascade.runtime.strategies.BlueprintBuilder") as MockBuilder, patch(
        "cascade.runtime.strategies.VirtualMachine"
    ) as MockVM:
        mock_builder_instance = MockBuilder.return_value
        mock_vm_instance = MockVM.return_value
~~~~~
~~~~~python
    # Mock BlueprintBuilder and VirtualMachine to verify interaction
    with patch("cascade.runtime.strategies.vm.BlueprintBuilder") as MockBuilder, patch(
        "cascade.runtime.strategies.vm.VirtualMachine"
    ) as MockVM:
        mock_builder_instance = MockBuilder.return_value
        mock_vm_instance = MockVM.return_value
~~~~~

### 下一步建议
路径修复已完成。请再次运行完整的 `pytest` 测试套件。我们预期所有测试现在都应该能通过，标志着 1.3 阶段的重构已成功完成。
