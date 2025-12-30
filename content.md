好的，我们进入 GREEN 阶段，实现 `VirtualMachine`。

## [WIP] feat(compiler): 实现 VirtualMachine 运行时

### 摘要头
## [WIP] feat(compiler): 实现 VirtualMachine 运行时

### 用户需求
实现 `cascade.compiler.vm.VirtualMachine` 类，使其能够执行 `Blueprint` 指令集并通过 "Phase 4" 的 TDD 测试。这要求 VM 能够处理同步和异步的函数调用，并正确管理寄存器状态。

### 评论
这是 "焦土政策" 路线图中的一个核心里程碑，我们正在构建新的运行时核心。此 VM 实现是一个经典的、基于寄存器的虚拟机，包含一个 `Frame` 用于状态管理和一个指令分发循环 (`_dispatch`)。它严格遵守 `Blueprint` 契约，与图构建和编译过程完全解耦，确保了其作为一个独立组件的可测试性和健壮性。

### 目标
1.  创建 `packages/cascade-compiler/src/cascade/compiler/vm.py` 文件。
2.  在 `vm.py` 中实现 `Frame` 类来管理寄存器。
3.  在 `vm.py` 中实现 `VirtualMachine` 类，包括 `execute` 和 `_dispatch` 循环。
4.  确保 `_dispatch` 逻辑能正确 `await` 异步函数。
5.  更新 `__init__.py` 导出 `VirtualMachine`。
6.  更新 `test_vm.py` 测试文件，移除 `xfail` 标记，验证 GREEN 状态。

### 基本原理
VM 的实现遵循了标准的 "Fetch-Decode-Execute" 模式：
1.  **Fetch**: `execute` 方法遍历 `Blueprint` 中的指令。
2.  **Decode**: `_dispatch` 方法判断指令类型（目前只有 `Call`）。
3.  **Execute**: `_execute_call` 方法执行具体操作：
    a.  **参数加载**: 使用 `Frame.load` 从 `Register` 或 `Literal` 操作数中解析出实际值。
    b.  **函数调用**: 执行 `Call` 指令中引用的函数。
    c.  **异步处理**: 使用 `inspect.isawaitable` 判断并 `await` 协程。
    d.  **结果存储**: 使用 `Frame.store` 将结果写回输出寄存器。

这种设计确保了 VM 的逻辑清晰、高效且易于扩展。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/vm #scope/core #ai/instruct #task/domain/refactor #task/object/vm #task/action/implement #task/state/continue

---

### Script

#### Acts 1: 实现 VirtualMachine 类

创建 `vm.py` 并实现 `Frame` 和 `VirtualMachine` 的核心逻辑。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/vm.py
~~~~~
~~~~~python
import inspect
import asyncio
from typing import Any, List, Dict, Optional

from cascade.spec.blueprint import (
    Blueprint,
    Instruction,
    Call,
    Literal,
    Register,
    Operand,
)


class Frame:
    """Represents the runtime stack frame for a blueprint execution."""

    def __init__(self, size: int):
        self.registers: List[Any] = [None] * size

    def load(self, operand: Operand) -> Any:
        """Loads a value from an operand (either a Literal or a Register)."""
        if isinstance(operand, Literal):
            return operand.value
        elif isinstance(operand, Register):
            if operand.index >= len(self.registers):
                raise IndexError(f"Invalid register index: {operand.index}")
            return self.registers[operand.index]
        else:
            raise TypeError(f"Unknown operand type: {type(operand)}")

    def store(self, register: Register, value: Any):
        """Stores a value into a register."""
        if register.index >= len(self.registers):
            raise IndexError(f"Invalid register index: {register.index}")
        self.registers[register.index] = value


class VirtualMachine:
    """Executes compiled Blueprints."""

    async def execute(self, blueprint: Blueprint) -> Any:
        """Executes the blueprint and returns the result of the final instruction."""
        frame = Frame(blueprint.register_count)
        last_result = None

        for instr in blueprint.instructions:
            last_result = await self._dispatch(instr, frame)

        return last_result

    async def _dispatch(self, instr: Instruction, frame: Frame) -> Any:
        """Decodes and executes a single instruction."""
        if isinstance(instr, Call):
            return await self._execute_call(instr, frame)
        else:
            raise NotImplementedError(f"Unknown instruction type: {type(instr)}")

    async def _execute_call(self, instr: Call, frame: Frame) -> Any:
        """Handles the Call instruction."""
        # 1. Resolve arguments from operands
        args = [frame.load(op) for op in instr.args]
        kwargs = {k: frame.load(op) for k, op in instr.kwargs.items()}

        # 2. Invoke the function
        if instr.func is None:
             raise ValueError(f"Instruction for task '{instr.task_name}' has no function to call.")
        result = instr.func(*args, **kwargs)

        # 3. Handle async functions
        if inspect.isawaitable(result):
            result = await result

        # 4. Store the result in the output register
        frame.store(instr.output, result)

        return result
~~~~~

#### Acts 2: 导出 VirtualMachine

更新 `__init__.py` 以便测试可以找到 `VirtualMachine`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/__init__.py
~~~~~
~~~~~python.old
from .frontend import Frontend
from .optimizer import Optimizer, ExecutionPlan
from .backend import Backend
from .exceptions import CompilerError, CycleDetectedError

__all__ = [
    "Frontend",
    "Optimizer",
    "ExecutionPlan",
    "Backend",
    "CompilerError",
    "CycleDetectedError",
]
~~~~~
~~~~~python.new
from .frontend import Frontend
from .optimizer import Optimizer, ExecutionPlan
from .backend import Backend
from .vm import VirtualMachine
from .exceptions import CompilerError, CycleDetectedError

__all__ = [
    "Frontend",
    "Optimizer",
    "ExecutionPlan",
    "Backend",
    "VirtualMachine",
    "CompilerError",
    "CycleDetectedError",
]
~~~~~

#### Acts 3: 更新测试用例 (GREEN)

移除 `xfail` 标记和 `try-except` 块，让测试可以运行。

~~~~~act
patch_file
packages/cascade-compiler/tests/test_vm.py
~~~~~
~~~~~python.old
# RED State: VM not yet implemented in the new package location
try:
    from cascade.compiler.vm import VirtualMachine
except ImportError:
    pass
~~~~~
~~~~~python.new
from cascade.compiler.vm import VirtualMachine
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/test_vm.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
@pytest.mark.xfail(reason="VM not implemented", raises=(ImportError, NameError))
async def test_vm_instruction_execution():
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_vm_instruction_execution():
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/test_vm.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
@pytest.mark.xfail(reason="VM not implemented", raises=(ImportError, NameError))
async def test_vm_async_execution():
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_vm_async_execution():
~~~~~
