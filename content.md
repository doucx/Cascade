简要回答
我们正在编写一个端到端的集成测试 `test_integration_map_control.py`，用于验证新架构下的 `VMExecutionStrategy` 能否正确处理包含 `run_if` 和 `map` 的复合工作流。

这将暴露出我们当前的缺失：`VMExecutionStrategy` 只是简单地运行了 VM，但没有解决 `Blueprint` 中 `func` 为 `None` 的问题，也没有正确处理 `Backend` 生成的控制流。

## [WIP] test(integration): 全流程验证 Map 与 Control Flow

### 用户需求
1.  创建一个集成测试，定义包含 `run_if` 和 `map` 的工作流。
2.  使用 `Engine(use_vm=True)` 运行该工作流。
3.  验证结果正确，且中间过程符合预期。

### 评论
目前的 `VMExecutionStrategy.execute` 还是个空壳，只实现了最基本的编译和运行，忽略了关键的“链接”步骤。如果没有这个步骤，VM 在执行指令时会因为 `func` 为 `None` 而崩溃。

### 目标
1.  创建一个真实的、复杂的测试场景。
2.  通过测试失败（RED）来驱动我们完善 `VMExecutionStrategy`。

### 基本原理
集成测试是验证组件间契约的最终手段。只有当所有组件（Spec, Compiler, VM, Strategy）都正确协作时，这个测试才能通过。

### 标签
#intent/test #flow/ready #priority/high #comp/tests #comp/integration #task/domain/core #task/object/integration #task/action/test #task/state/continue

---

### Script

#### Acts 1: 创建集成测试文件

~~~~~act
write_file
packages/cascade-engine/tests/integration/test_integration_map_control.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.bus import MessageBus

# --- Tasks ---

@cs.task
def get_numbers():
    return [1, 2, 3]

@cs.task
def double(x):
    return x * 2

@cs.task
def is_enabled():
    return True

@cs.task
def is_disabled():
    return False

@cs.task
def conditional_step(val):
    return f"Processed {val}"

# --- Tests ---

@pytest.mark.asyncio
async def test_vm_integration_map_flow():
    """
    Integration Test: Map
    Flow: get_numbers -> map(double)
    """
    workflow = double.map(x=get_numbers())
    
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )
    
    # Run with VM enabled
    results = await engine.run(workflow, use_vm=True)
    
    assert results == [2, 4, 6]


@pytest.mark.asyncio
async def test_vm_integration_control_flow_true():
    """
    Integration Test: Control Flow (True)
    Flow: is_enabled -> run_if(conditional_step)
    """
    workflow = conditional_step("A").run_if(is_enabled())
    
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )
    
    result = await engine.run(workflow, use_vm=True)
    assert result == "Processed A"


@pytest.mark.asyncio
async def test_vm_integration_control_flow_false():
    """
    Integration Test: Control Flow (False)
    Flow: is_disabled -> run_if(conditional_step)
    """
    workflow = conditional_step("B").run_if(is_disabled())
    
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )
    
    # Current behavior for skipping root node is raising DependencyMissingError or similar,
    # or returning None depending on implementation.
    # In VM execution, if the final instruction is skipped, what happens?
    # The VM returns the result of the last executed instruction?
    # Or we need a specific return mechanism.
    # For now, let's assume it might raise or return None.
    # Given our VM implementation, if it jumps over the call, last_result is None.
    
    result = await engine.run(workflow, use_vm=True)
    assert result is None
~~~~~

### 下一步建议
测试将会失败（RED），报错 `ValueError: Instruction for task '...' has no function to call`。

我们需要修改 `packages/cascade-engine/src/cascade/runtime/strategies/vm.py`。
1.  **链接器 (Linker)**: 实现一个逻辑，遍历 `GraphIR` 中的 `TaskDef`，或者是直接遍历原始 `LazyResult` 图，来构建 `task_name -> callable` 的映射表。
2.  **注入**: 将这些 callable 注入到 `Blueprint` 的指令中。

鉴于 `GraphIR` 已经丢失了原始 callable（只保留了元数据），我们需要在 `VMExecutionStrategy` 中利用 `Frontend` 构建过程中可能产生的副作用，或者重新遍历一次 `LazyResult` 来获取 callable。更优雅的方式是让 `Frontend` 返回一个包含 callable 引用的辅助结构。

我们可以修改 `Frontend.compile` 返回一个 `CompilationResult`，包含 `GraphIR` 和一个 `SymbolTable`。请确认是否采用此方案。
