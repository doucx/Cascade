简要回答：
`test_full_ref_based_e2e_flow` 失败的原因是 `func_map` 中缺少了对 `probe.const` 节点的映射。在 `add_one(10)` 的编译过程中，编译器为常量 `10` 生成了一个 `F_probe` 节点，但测试 harness 未加载对应的 `const_probe` 标准库函数，导致 Reactor 在尝试执行该节点时抛出 `ValueError: No function mapped`，进而导致测试超时。

我们将修复此测试配置错误。

## [WIP] fix(tests): 修复集成测试中缺失 const_probe 映射的问题

### 错误分析
测试日志显示 `ERROR cascade.vm.reactor:reactor.py:188 Error executing task probe.const...: No function mapped for node probe.const...`。这是因为集成测试手动构建 `func_map` 时，只包含了 Triad 和 Dispatcher，遗漏了用于处理常量输入的 `const_probe`。

### 用户需求
修复 `packages/cascade-vm/tests/integration/test_ref_architecture.py`，使其能够正确运行包含常量参数的工作流。

### 目标
1.  在测试文件中导入 `cascade.std.probe.const.const_probe`。
2.  在构建 `func_map` 的循环中添加对 `probe.const.*` ID 模式的匹配，并将其映射到 `const_probe`。

### 基本原理
集成测试手动组装运行时环境时，必须显式包含所有生成的物理图节点所需的内核函数。编译器会将常量参数转换为 `F_probe` 节点，因此运行时必须提供对应的实现。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #ai/instruct #task/domain/testing #task/object/integration-test #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 添加 const_probe 到集成测试

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ref_architecture.py
~~~~~
~~~~~python.old
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.triad.dispatcher import standard_dispatcher


# --- User-defined tasks for the test ---
~~~~~
~~~~~python.new
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.triad.dispatcher import standard_dispatcher
from cascade.std.probe.const import const_probe


# --- User-defined tasks for the test ---
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ref_architecture.py
~~~~~
~~~~~python.old
        elif "observer" in node_id:
            func_map[node_id] = standard_observer
        # All user workers are now implemented by the dispatcher
        elif node_id in assembly.symbol_table:
            func_map[node_id] = standard_dispatcher

    # 5. Setup and prime the VM Harness
~~~~~
~~~~~python.new
        elif "observer" in node_id:
            func_map[node_id] = standard_observer
        elif node_id.startswith("probe.const."):
            func_map[node_id] = const_probe
        # All user workers are now implemented by the dispatcher
        elif node_id in assembly.symbol_table:
            func_map[node_id] = standard_dispatcher

    # 5. Setup and prime the VM Harness
~~~~~

### 下一步建议
再次运行测试。如果通过，我们将完成所有验证工作，并可以提交代码。
