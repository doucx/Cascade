## [WIP] test(vm): 为虚拟机创建 RED 状态测试

### 用户需求
根据 TDD 重构路线图的 "Phase 4: VM Runtime"，我们需要创建 `VirtualMachine` 的测试用例。虚拟机是执行编译器生成的 `Blueprint` 的运行时组件。它不依赖任何图构建逻辑，只负责执行线性的指令集。
用户强调“绝对严谨的测试”，这意味着测试必须基于纯粹的指令集操作，不依赖编译器的输出，而是手动构造 `Blueprint` 进行测试，从而实现 VM 的独立验证。

### 评论
VM 的核心职责是：加载指令、管理寄存器帧（Frame）、分发指令（Dispatch）并执行。
我们的测试策略将包括：
1.  **CPU 测试 (The CPU Test)**: 不使用任何编译器，手动构造包含 `Literal` 和 `Register` 操作数的 `Call` 指令，验证 VM 能否正确加载字面量、传递寄存器值，并将结果写回寄存器。这将验证 "Fetch-Decode-Execute" 循环的基本功能。
2.  **异步支持测试**: 验证 VM 能否正确处理 `async` 函数的 `await` 操作。

### 目标
1.  创建 `packages/cascade-compiler/tests/test_vm.py`。
2.  实现 `test_vm_instruction_execution`：手动编排包含 `add` 操作的指令序列，验证数据在寄存器间的流动。
3.  实现 `test_vm_async_execution`：验证 VM 对异步 `Call` 的支持。

### 基本原理
通过手动构造 `Blueprint`，我们将 VM 的测试与编译器的正确性解耦。如果 VM 测试失败，那是 VM 的问题；如果 VM 测试通过但端到端失败，那是编译器的问题。这种隔离对于复杂系统的调试至关重要。
此外，我们将在测试中显式定义一个简单的加法函数，以确保测试环境是完全受控的。

### 标签
#intent/tooling #flow/ready #priority/high #comp/runtime #concept/vm #scope/core #ai/instruct #task/domain/refactor #task/object/vm #task/action/define #task/state/continue

---

### Script

#### Acts 1: 创建 VM 的 RED 测试文件

此文件定义了 VM 作为纯指令执行器的行为契约。

~~~~~act
write_file
packages/cascade-compiler/tests/test_vm.py
~~~~~
~~~~~python
import pytest
import asyncio
from cascade.spec.blueprint import Blueprint, Call, Register, Literal

# RED State: VM not yet implemented in the new package location
try:
    from cascade.compiler.vm import VirtualMachine
except ImportError:
    pass


def _add(a: int, b: int) -> int:
    """Helper function for testing synchronous execution."""
    return a + b


async def _async_add(a: int, b: int) -> int:
    """Helper function for testing asynchronous execution."""
    await asyncio.sleep(0.01)
    return a + b


@pytest.mark.asyncio
@pytest.mark.xfail(reason="VM not implemented", raises=(ImportError, NameError))
async def test_vm_instruction_execution():
    """
    Case 1: The CPU Test (Synchronous).
    Manually construct a program:
      r0 = add(1, 2)
      r1 = add(r0, 3)
    Verify that r1 contains 6.
    """
    # Program:
    # 1. r0 = _add(1, 2)
    instr1 = Call(
        func=_add,
        output=Register(0),
        args=[Literal(1), Literal(2)],
        kwargs={},
        task_name="add_1"
    )
    
    # 2. r1 = _add(r0, 3)
    instr2 = Call(
        func=_add,
        output=Register(1),
        args=[Register(0), Literal(3)],
        kwargs={},
        task_name="add_2"
    )
    
    blueprint = Blueprint(
        instructions=[instr1, instr2],
        register_count=2
    )

    vm = VirtualMachine()
    result = await vm.execute(blueprint)

    # The result of the last instruction should be returned
    assert result == 6


@pytest.mark.asyncio
@pytest.mark.xfail(reason="VM not implemented", raises=(ImportError, NameError))
async def test_vm_async_execution():
    """
    Case 2: Async Execution.
    Manually construct a program:
      r0 = async_add(10, 20)
    Verify that VM awaits the result correctly.
    """
    instr = Call(
        func=_async_add,
        output=Register(0),
        args=[Literal(10), Literal(20)],
        kwargs={},
        task_name="async_add"
    )
    
    blueprint = Blueprint(
        instructions=[instr],
        register_count=1
    )

    vm = VirtualMachine()
    result = await vm.execute(blueprint)

    assert result == 30
~~~~~
