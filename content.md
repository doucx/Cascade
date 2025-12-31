## [WIP] test(e2e): 修复过时的 VM 集成测试以对齐新架构

### 用户需求
修复位于 `tests/e2e/integration/test_engine_vm_integration.py` 中的 `test_engine_dispatches_to_vm` 测试用例。该测试因 `NameError` 和对已废弃组件的错误 Mock 而失败。

### 评论
这个 E2E 测试是验证 `Engine` 到 `VMExecutionStrategy` 调度逻辑的关键哨兵。修复它意味着我们不仅拥有了能通过的端到端功能测试，还拥有了能验证新架构内部组件交互的白盒测试。这对于确保未来对策略层的修改不破坏核心流程至关重要。

### 目标
1.  重写 `test_engine_dispatches_to_vm` 测试用例。
2.  移除对不存在的 `mock_builder_instance` 的引用，解决 `NameError`。
3.  清理重复和混乱的 Mock 定义。
4.  确保测试正确地 Mock 了 `Backend.compile` 和 `VirtualMachine.execute`，并验证它们被以正确的参数调用。

### 基本原理
旧的测试是为前一个架构版本编写的，它假设 `VMExecutionStrategy` 直接与一个名为 `BlueprintBuilder` 的组件交互。随着我们将编译器栈（`Frontend`, `Optimizer`, `Backend`）完全分离，这个假设已经失效。新的 `VMExecutionStrategy` 现在调用 `Backend.compile` 来生成 `Blueprint`。因此，测试必须更新其 Mock 目标，以准确反映这一新的、更清晰的内部实现。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/high #comp/engine #comp/tests #concept/executor #scope/core #ai/instruct #task/domain/architecture #task/object/e2e-test #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重写 `test_engine_vm_integration.py`

我们将用一个干净、正确且与新架构对齐的版本覆盖整个文件。

~~~~~act
write_file
tests/e2e/integration/test_engine_vm_integration.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.spec.blueprint import TailCall, Blueprint
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.bus import MessageBus


# --- Helper ---
@cs.task
def vm_task(x: int):
    return x + 1


@pytest.mark.asyncio
async def test_engine_dispatches_to_vm():
    """
    Verifies that Engine.run(..., use_vm=True) correctly dispatches to the
    new compiler pipeline (Backend) and VirtualMachine.
    """
    # Setup Engine
    bus = MessageBus()
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    # Target task
    target = vm_task(x=10)

    # We patch Backend and VirtualMachine where they are imported by VMExecutionStrategy.
    with patch("cascade.runtime.strategies.vm.Backend") as MockBackend, patch(
        "cascade.runtime.strategies.vm.VirtualMachine"
    ) as MockVM:
        # 1. Setup mocks
        mock_bp = MagicMock(spec=Blueprint)
        MockBackend.compile.return_value = mock_bp

        mock_vm_instance = MockVM.return_value
        # The execute method is async, so we use AsyncMock for proper awaiting.
        mock_vm_instance.execute = AsyncMock(return_value=11)

        # 2. Run with VM flag
        result = await engine.run(target, use_vm=True)

        # 3. Assertions
        assert result == 11

        # Verify Backend.compile was called (it's a static method, so called on the class)
        MockBackend.compile.assert_called_once()

        # Verify a VM instance was created
        MockVM.assert_called_once()

        # Verify VM.execute was called with the correct blueprint and initial state
        mock_vm_instance.execute.assert_awaited_once()
        call_args, call_kwargs = mock_vm_instance.execute.call_args

        assert call_args[0] == mock_bp  # First positional arg is the blueprint
        assert "symbol_table" in call_kwargs  # Symbol table is passed
        assert call_kwargs["initial_kwargs"] == {"x": 10}


@pytest.mark.asyncio
async def test_engine_vm_recursive_execution():
    """
    Integration test with a real recursive task (no mocks), verifying TCO.
    """

    # A real recursive task
    @cs.task
    def countdown(n: int):
        if n > 0:
            return TailCall(kwargs={"n": n - 1})
        return "Liftoff"

    bus = MessageBus()
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    target = countdown(n=5)

    # Run with VM
    # NOTE: This test will fail until the old BlueprintBuilder and VM in cascade-graph/engine are removed
    # and the new VM supports TailCall. The old ones do, but the new one might not yet.
    # Let's check cascade.vm.machine.py... it does handle TailCall. So this should pass.
    result = await engine.run(target, use_vm=True)

    assert result == "Liftoff"
~~~~~
