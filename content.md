## [WIP] test(engine): 创建新编译器栈的集成测试 (RED)

### 用户需求
开始 "Phase 5: 集成与 API 门面 (Integration)" 的开发。首要任务是创建一个处于 RED 状态的集成测试，用于验证 `cascade-engine` 是否正确集成了新的 `cascade-compiler` 组件栈。

### 评论
当前 `cascade-engine` 中的 `VMExecutionStrategy` 仍然依赖于旧的 `cascade.graph.compiler.BlueprintBuilder` 和 `cascade.runtime.vm.VirtualMachine`。
为了驱动重构，我们需要编写一个测试，断言当调用 `Engine.run(..., use_vm=True)` 时，系统调用的是 **新** 包 `cascade.compiler` 中的 `Frontend.compile` 方法。由于目前代码尚未修改，该断言必然失败（RED 状态），从而证实了旧逻辑仍在运行。

### 目标
1.  确保 `packages/cascade-engine/tests/integration` 目录存在。
2.  创建 `packages/cascade-engine/tests/integration/test_compiler_integration.py`。
3.  编写测试用例 `test_engine_activates_new_compiler_pipeline`，使用 `mock.patch` 验证 `cascade.compiler.frontend.Frontend.compile` 是否被调用。

### 基本原理
此测试充当“探针”。如果它通过，说明我们成功地切断了旧的 VM 执行路径，并将其重定向到了新的 Compiler->VM 管线。我们选择 Mock `Frontend.compile` 作为切入点，因为它是新管线的入口。

### 标签
#intent/tooling #flow/ready #priority/high #comp/engine #concept/integration #scope/core #ai/instruct #task/domain/refactor #task/object/integration-test #task/action/create #task/state/begin

---

### Script

#### Acts 1: 创建集成测试目录

确保测试目录存在。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-engine/tests/integration
~~~~~

#### Acts 2: 创建 RED 状态的集成测试

该测试断言 `Engine` 在 `use_vm=True` 模式下会调用新的编译器前端。目前这会失败，因为 Engine 还在用旧的 `BlueprintBuilder`。

~~~~~act
write_file
packages/cascade-engine/tests/integration/test_compiler_integration.py
~~~~~
~~~~~python
import pytest
from unittest.mock import patch
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.bus import MessageBus

# NOTE: We expect this test to FAIL (AssertionError) initially.
# The current Engine implementation uses the old 'cascade.graph.compiler.BlueprintBuilder',
# so it will NOT call 'cascade.compiler.frontend.Frontend.compile'.

@pytest.mark.asyncio
async def test_engine_activates_new_compiler_pipeline():
    """
    Verifies that Engine.run(use_vm=True) delegates to the new cascade.compiler package
    instead of the legacy cascade.graph.compiler implementation.
    """
    # 1. Define a simple workflow
    @cs.task
    def add_one(x: int) -> int:
        return x + 1

    workflow = add_one(x=10)

    # 2. Setup Engine
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

    # 3. Patch the NEW Frontend to verify it gets called.
    # We patch it where it is defined.
    with patch("cascade.compiler.frontend.Frontend.compile") as mock_frontend_compile:
        # Mock the return value to avoid cascading errors downstream (if the wiring were partially complete)
        # But in the RED state, we expect the code to completely bypass this and use the old logic.
        # The run might succeed (using old VM) or fail (if old VM is broken), but our assertion
        # focuses solely on whether the NEW path was taken.
        
        # We wrap in try/except because running the OLD vm logic might trigger unrelated errors
        # depending on the environment, but we only care about the spy.
        try:
            await engine.run(workflow, use_vm=True)
        except Exception:
            # We ignore execution errors, we just want to know if the new compiler was invoked.
            pass
        
        # This assertion MUST FAIL for the test to be valid in the RED stage.
        mock_frontend_compile.assert_called_once()
~~~~~
