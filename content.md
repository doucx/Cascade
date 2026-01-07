好的，我们开始迁移。

这个重构将简化测试代码，并确保我们的测试套件自身也遵循了“快速失败”的最佳实践。

## [WIP] refactor(vm): 迁移集成测试以使用 Linker 校验的 Runner

### 用户需求
逐步将现有的集成测试（如 `test_ref_architecture.py`）迁移到使用 `EventDrivenRunner.from_assembly`，以消除手动构建 `func_map` 的冗余代码，并享受自动校验的好处。

### 评论
这是一个重要的代码健康度改进。通过在我们的核心集成测试中“吃自己的狗粮”，我们不仅简化了测试的设置，还增强了其健壮性。每次测试运行都将隐式地验证 `Linker` 的正确性。

### 目标
1.  移除 `test_ref_architecture.py` 中不再需要的手动导入的标准库实现。
2.  用对 `EventDrivenRunner.from_assembly(assembly, code_registry)` 的一次调用，替换掉手动构建 `function_map` 和实例化 `EventDrivenRunner` 的大段代码。

### 基本原理
`EventDrivenRunner.from_assembly` 工厂方法封装了从静态 `Assembly` 到可执行 `Runner` 的完整链接过程。在测试中使用此方法，可以消除重复的、容易出错的手动 `function_map` 构建逻辑，使测试更聚焦于验证业务流程本身。

### 标签
#intent/refine #flow/ready #priority/medium #comp/tests #concept/linking #scope/dx #ai/instruct #task/domain/vm #task/object/linker #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 移除未使用的标准库 IC 导入

由于 `Linker` 现在会自动处理标准库函数的映射，我们不再需要在测试文件中手动导入它们。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ref_architecture.py
~~~~~
~~~~~python.old
from cascade.runtime.services.observability.events import TaskExecutionFinished

# Standard library function imports
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.triad.dispatcher import standard_dispatcher


# --- User-defined tasks for the test ---
@task
~~~~~
~~~~~python.new
from cascade.runtime.services.observability.events import TaskExecutionFinished


# --- User-defined tasks for the test ---
@task
~~~~~

#### Acts 2: 使用 from_assembly 工厂方法简化 Runner 初始化

现在，我们将核心的 `function_map` 构建逻辑和 `Runner` 实例化替换为对新工厂方法的单次调用。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ref_architecture.py
~~~~~
~~~~~python.old
    register_task("add_one", add_one.func)
    register_task("square", square.func)

    # 4. Build the function map for the Reactor (Standard Library ICs)
    func_map = {}
    for node_id, node in physical_graph.nodes.items():
        if node_id.endswith(".bleach"):
            func_map[node_id] = standard_bleacher
        elif node_id.endswith(".stain"):
            func_map[node_id] = standard_stainer
        elif "observer" in node_id:
            func_map[node_id] = standard_observer
        # All user workers are now implemented by the dispatcher
        elif node_id in assembly.symbol_table:
            func_map[node_id] = standard_dispatcher

    # 5. Setup and prime the VM Harness
    runner = EventDrivenRunner(physical_graph, func_map, code_registry)
    runner.prime()

    # 6. Start the reactor and compute service loops
    await runner.start_loop()
~~~~~
~~~~~python.new
    register_task("add_one", add_one.func)
    register_task("square", square.func)

    # 4. Setup and prime the VM Harness using the Linker-validated factory
    runner = EventDrivenRunner.from_assembly(assembly, code_registry)
    runner.prime()

    # 5. Start the reactor and compute service loops
    await runner.start_loop()
~~~~~

### 下一步建议
迁移成功。现在 `test_ref_architecture.py` 更简洁且更安全了。

我们可以继续迁移其他集成测试，或者根据“战略分析”的指引，开始解决下一个核心问题：**实现双通道出口 (Dual-Channel Egress)**，以解决错误 Token 掉入虚空导致系统意外静止的问题。这将涉及增强 `Stainer` 的逻辑和 `ControlFlowWiringPolicy`。
