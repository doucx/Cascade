## [WIP] 第二阶段：虚拟机核心 (The Virtual Machine Core)

### Script

#### Acts 1: 创建虚拟机测试用例

创建 `test_vm.py`。我们使用 `MagicMock` 来模拟任务函数的行为，以验证 VM 正确地解析了操作数、执行了调用并将结果存储到了寄存器中。

~~~~~act
write_file
tests/cascade-runtime/runtime/test_vm.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
from cascade.runtime.blueprint import Blueprint, Call, Literal, Register
from cascade.runtime.vm import VirtualMachine, Frame

def test_vm_executes_single_call():
    """
    Test execution of a simple blueprint: R0 = func(a=1)
    """
    # 1. Define Blueprint manually
    mock_func = MagicMock(return_value=42)
    
    # Instruction: R0 = mock_func(val=10)
    instr = Call(
        func=mock_func,
        output=Register(0),
        args=[],
        kwargs={"val": Literal(10)}
    )
    blueprint = Blueprint(instructions=[instr], register_count=1)

    # 2. Execute
    vm = VirtualMachine()
    result = vm.execute(blueprint)

    # 3. Verify
    assert result == 42
    mock_func.assert_called_once_with(val=10)

def test_vm_handles_data_dependency():
    """
    Test R0 = func1(1); R1 = func2(R0)
    """
    func1 = MagicMock(return_value=100)
    func2 = MagicMock(return_value=200)

    # I1: R0 = func1(1)
    i1 = Call(
        func=func1,
        output=Register(0),
        args=[Literal(1)],
        kwargs={}
    )
    # I2: R1 = func2(R0)
    i2 = Call(
        func=func2,
        output=Register(1),
        args=[Register(0)],
        kwargs={}
    )
    
    blueprint = Blueprint(instructions=[i1, i2], register_count=2)

    vm = VirtualMachine()
    result = vm.execute(blueprint)

    assert result == 200
    func1.assert_called_once_with(1)
    func2.assert_called_once_with(100) # Should receive result of func1

def test_vm_async_execution():
    """
    Test handling of async functions.
    """
    import asyncio
    
    async def async_add(x):
        return x + 1

    blueprint = Blueprint(
        instructions=[
            Call(
                func=async_add,
                output=Register(0),
                args=[],
                kwargs={"x": Literal(5)}
            )
        ],
        register_count=1
    )

    vm = VirtualMachine()
    # execute is sync wrapper for now? Or should it be async?
    # Engine.run is async. VM.execute should likely be async too.
    # We'll make VM.execute async.
    
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(vm.execute(blueprint))
    assert result == 6
~~~~~

#### Acts 2: 实现虚拟机核心

创建 `vm.py`。
*   **Frame**: 一个简单的列表，用于存储寄存器值。
*   **VirtualMachine**: 包含指令分发逻辑。
*   **注意**: 我们将 `execute` 实现为 `async` 方法，以支持原生异步任务。如果任务是同步的，我们直接调用；如果是协程，我们 `await` 它。这保持了 Cascade 对同步/异步混合工作流的支持。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/vm.py
~~~~~
~~~~~python
import inspect
from typing import Any, List, Dict
from cascade.runtime.blueprint import Blueprint, Instruction, Call, Literal, Register, Operand

class Frame:
    """
    Represents the runtime stack frame for a blueprint execution.
    It holds the values of virtual registers.
    """
    def __init__(self, size: int):
        self.registers: List[Any] = [None] * size

    def load(self, operand: Operand) -> Any:
        if isinstance(operand, Literal):
            return operand.value
        elif isinstance(operand, Register):
            return self.registers[operand.index]
        else:
            raise TypeError(f"Unknown operand type: {type(operand)}")

    def store(self, register: Register, value: Any):
        self.registers[register.index] = value


class VirtualMachine:
    """
    Executes compiled Blueprints.
    """
    async def execute(self, blueprint: Blueprint) -> Any:
        # 1. Allocate Frame
        frame = Frame(blueprint.register_count)
        
        # 2. Execute Instructions
        last_result = None
        for instr in blueprint.instructions:
            last_result = await self._dispatch(instr, frame)
            
        # Return the result of the last instruction (implicit return of the workflow)
        return last_result

    async def _dispatch(self, instr: Instruction, frame: Frame) -> Any:
        if isinstance(instr, Call):
            return await self._execute_call(instr, frame)
        else:
            raise NotImplementedError(f"Unknown instruction: {type(instr)}")

    async def _execute_call(self, instr: Call, frame: Frame) -> Any:
        # 1. Resolve Arguments
        args = [frame.load(op) for op in instr.args]
        kwargs = {k: frame.load(op) for k, op in instr.kwargs.items()}

        # 2. Invoke Callable
        result = instr.func(*args, **kwargs)
        
        # Handle Async
        if inspect.isawaitable(result):
            result = await result

        # 3. Store Result
        frame.store(instr.output, result)
        
        return result
~~~~~
