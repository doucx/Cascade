好的，我来修复 `test_resource_contention.py` 中因 `EventDrivenRunner` 签名变更导致的 `TypeError`。

## [WIP] fix(compiler): 修复资源竞争测试中的 Runner 初始化错误

### 错误分析

`EventDrivenRunner` 的构造函数 `__init__` 在之前的重构中被更新，增加了 `code_registry` 作为必需的参数。然而，位于 `cascade-compiler` 包内的集成测试 `test_resource_contention.py` 在初始化 `EventDrivenRunner` 时没有提供这个参数，导致了 `TypeError`。

### 用户需求

修复 `packages/cascade-compiler/tests/integration/test_resource_contention.py` 中的测试失败。

### 评论

这是一个常见的、因 API 变更而产生的连锁反应。修复它能确保我们的测试套件与最新的组件接口保持同步，维持测试的有效性。由于此测试使用一个 `mock_worker` 而不是通过 `standard_dispatcher` 调用真实代码，我们只需传入一个空的 `CodeRegistry` 实例即可满足签名要求。

### 目标

1.  在 `test_resource_contention.py` 中导入 `CodeRegistry`。
2.  在实例化 `EventDrivenRunner` 时，传入一个 `CodeRegistry` 对象。

### 基本原理

保持测试代码与被测代码的接口同步是测试驱动开发的基本要求。通过修复这个简单的初始化错误，我们恢复了该集成测试的健康状态，确保资源管理相关的物理拓扑和执行逻辑能够被持续验证。

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-runner #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `test_resource_contention.py`

我们将导入 `CodeRegistry` 并更新 `EventDrivenRunner` 的调用。

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
from cascade.vm.harness import EventDrivenRunner
from cascade.runtime.services.observability.events import (
    Event,
    TaskExecutionStarted,
    TaskExecutionFinished,
)
from cascade.compiler.utils.inspector import GraphInspector
from cascade.reflection import PhysicalIdGenerator
~~~~~
~~~~~python.new
from cascade.vm.harness import EventDrivenRunner
from cascade.runtime.services.observability.events import (
    Event,
    TaskExecutionStarted,
    TaskExecutionFinished,
)
from cascade.compiler.utils.inspector import GraphInspector
from cascade.reflection import PhysicalIdGenerator
from cascade.vm.registry import CodeRegistry
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
        elif "observability" in node_id:
            func_map[node_id] = standard_observer

    runner = EventDrivenRunner(physical_graph, func_map)
    runner.prime()

    await runner.start_loop()
~~~~~
~~~~~python.new
        elif "observability" in node_id:
            func_map[node_id] = standard_observer

    code_registry = CodeRegistry()
    runner = EventDrivenRunner(physical_graph, func_map, code_registry)
    runner.prime()

    await runner.start_loop()
~~~~~

### 下一步建议

现在所有的测试应该都已修复并能通过。我建议我们进入第五阶段的收尾工作：**集成与验证 (Phase 5: Integration & Verification)**。

具体来说，我将创建一个新的集成测试 `tests/integration/test_ref_architecture.py`，它将端到端地验证整个“出境-入境”数据流，确保 `Dispatcher`、`ComputeService` 和 `Reactor` 之间的交互完全符合预期。

如果你同意，我将开始制定并执行这个计划。
