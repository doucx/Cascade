## [WIP] fix(tests): 更新 VM 集成测试以匹配重构后的路径

### 用户需求
修复 `tests/engine/integration/test_engine_vm_integration.py` 中的测试失败。

### 错误分析
测试失败 `AttributeError: ... does not have the attribute 'BlueprintBuilder'` 是因为在之前的重构中，`BlueprintBuilder` 和 `VirtualMachine` 的导入已从 `cascade.runtime.engine` 移除。它们现在被 `VMExecutionStrategy` 使用，该策略位于 `cascade.runtime.strategies` 模块中。

### 目标
更新测试代码中的 `patch` 路径，使其指向正确的位置 (`cascade.runtime.strategies`)。

### 基本原理
测试意图是 mock 掉底层的 VM 构建和执行过程。由于 `Engine` 现在将这部分逻辑委托给定义在 `strategies.py` 中的 `VMExecutionStrategy`，相关的类引用也移动到了那里。因此，patch 目标必须随之更新。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/test-suite #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修复测试中的 Patch 路径

~~~~~act
patch_file
tests/engine/integration/test_engine_vm_integration.py
~~~~~
~~~~~python
    target = vm_task(x=10)

    # Mock BlueprintBuilder and VirtualMachine to verify interaction
    with patch("cascade.runtime.engine.BlueprintBuilder") as MockBuilder, patch(
        "cascade.runtime.engine.VirtualMachine"
    ) as MockVM:
        mock_builder_instance = MockBuilder.return_value
        mock_vm_instance = MockVM.return_value
~~~~~
~~~~~python
    target = vm_task(x=10)

    # Mock BlueprintBuilder and VirtualMachine to verify interaction
    with patch("cascade.runtime.strategies.BlueprintBuilder") as MockBuilder, patch(
        "cascade.runtime.strategies.VirtualMachine"
    ) as MockVM:
        mock_builder_instance = MockBuilder.return_value
        mock_vm_instance = MockVM.return_value
~~~~~
