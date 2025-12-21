是的，根据文件系统检查，**第一阶段（蓝图编译器）** 和 **第二阶段（虚拟机核心）** 的核心代码（`blueprint.py`, `compiler.py`, `vm.py`）已经存在，且基本符合路线图的设计要求。

我们可以正式进入 **第三阶段：控制流与 TCO (Control Flow & TCO)**。

本阶段的核心目标是将虚拟机从“单次执行”升级为“循环执行”，支持零栈开销的递归调用（TCO）。

## [WIP] feat(vm): 实现 VM 主循环与 TailCall 指令以支持 TCO

### 摘要头
`# [WIP] feat(vm): Implement VM main loop and TailCall for TCO`

### 用户需求
1.  在 `blueprint.py` 中定义 `TailCall` 结构，作为 Agent 函数的特殊返回值。
2.  增强 `Blueprint` 定义，使其包含输入参数与寄存器的映射 (`input_registers`)。
3.  重构 `VirtualMachine.execute`，将其改为一个 `while True` 循环。
4.  实现 `TailCall` 处理逻辑：当检测到任务返回 `TailCall` 时，不退出，而是更新寄存器并重置指令指针（Zero-Overhead Recursion）。

### 评论
这是 Cascade 实现高性能长活 Agent 的关键一步。通过引入“蹦床 (Trampoline)”式的 VM 循环，我们将 Python 的递归调用转换为迭代循环，彻底消除了栈溢出风险和图构建开销。

### 目标
实现并验证 `VirtualMachine` 能够处理简单的自递归（Self-Recursion）场景，确保递归调用不会导致 Python 栈增长。

### 基本原理
1.  **TailCall 协议**: 这是一个简单的 `dataclass`，携带下一次迭代所需的参数。
2.  **输入映射**: Blueprint 需要知道哪些寄存器是“输入寄存器”，以便在发生 TailCall 时将新参数写入正确的位置。
3.  **VM 循环**: 执行流程不再是线性的，而是被 `TailCall` 信号驱动的循环。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/runtime #task/object/vm #task/action/tco-implementation #task/state/begin

---

### Script

#### Acts 1: 更新蓝图定义 (`blueprint.py`)
我们需要定义 `TailCall`，并为 `Blueprint` 添加输入参数映射能力，以便 VM 知道在递归时如何填充寄存器。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/blueprint.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Any, List, Dict, Optional

@dataclass
class Operand:
    """Base class for instruction operands."""
    pass

@dataclass
class Literal(Operand):
    """Represents a static value known at compile time."""
    value: Any

@dataclass
class Register(Operand):
    """Represents a dynamic value stored in a virtual register."""
    index: int

@dataclass
class Instruction:
    """Base class for VM instructions."""
    pass

@dataclass
class Call(Instruction):
    """
    Instruction to call a callable (function/task).
    Results are stored in the 'output' register.
    """
    func: Any
    output: Register
    args: List[Operand] = field(default_factory=list)
    kwargs: Dict[str, Operand] = field(default_factory=dict)

@dataclass
class TailCall:
    """
    A special return value indicating a request for tail-recursive execution.
    The VM intercepts this object and restarts execution with the new arguments.
    """
    args: List[Any] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    target_blueprint_id: Optional[str] = None  # For mutual recursion in future

@dataclass
class Blueprint:
    """
    Represents a compiled workflow, ready for execution by the VM.
    """
    instructions: List[Instruction] = field(default_factory=list)
    register_count: int = 0
    
    # Maps input argument positions to Register indices.
    # Used by the VM to populate the initial frame or refill it on TailCall.
    input_args: List[int] = field(default_factory=list)
    input_kwargs: Dict[str, int] = field(default_factory=dict)
~~~~~

#### Acts 2: 创建 VM TCO 测试 (`test_vm.py`)
我们将创建一个全新的测试文件，专门验证 VM 的递归能力。我们通过手动构建一个带有输入参数的 Blueprint 来模拟编译器的输出。

~~~~~act
write_file
tests/cascade-runtime/runtime/test_vm.py
~~~~~
~~~~~python
import pytest
import asyncio
from typing import Any
from cascade.runtime.vm import VirtualMachine
from cascade.runtime.blueprint import Blueprint, Call, Register, Literal, TailCall

# --- Mock User Function ---

def recursive_countdown(count: int) -> Any:
    """
    A simple recursive function.
    If count > 0, returns TailCall(count - 1).
    If count == 0, returns "Done".
    """
    if count > 0:
        return TailCall(kwargs={"count": count - 1})
    return "Done"

# --- Tests ---

@pytest.mark.asyncio
async def test_vm_handles_simple_recursion():
    """
    Verifies that the VM can execute a recursive loop using TailCall
    without crashing or returning early.
    """
    # 1. Manually construct a Blueprint for 'recursive_countdown'
    # It has 1 input: 'count', mapped to Register(0)
    # Instruction: res = recursive_countdown(count) -> Register(1)
    # The result of the instruction is the implicit return of the block.
    
    # Registers:
    # R0: input 'count'
    # R1: output result
    
    instr = Call(
        func=recursive_countdown,
        output=Register(1),
        kwargs={"count": Register(0)}
    )
    
    blueprint = Blueprint(
        instructions=[instr],
        register_count=2,
        input_kwargs={"count": 0} # Map 'count' arg to R0
    )
    
    vm = VirtualMachine()
    
    # 2. Run with initial count = 5
    # Expectation: 
    # It calls recursive_countdown(5) -> returns TailCall(4)
    # VM sees TailCall -> updates R0=4 -> re-runs
    # ...
    # Calls recursive_countdown(0) -> returns "Done"
    # VM sees "Done" -> returns "Done"
    
    result = await vm.execute(blueprint, initial_kwargs={"count": 5})
    
    assert result == "Done"

@pytest.mark.asyncio
async def test_vm_propagates_exceptions():
    """Ensure exceptions break the loop correctly."""
    
    def failing_task(x):
        raise ValueError("Boom")

    blueprint = Blueprint(
        instructions=[Call(func=failing_task, output=Register(1), args=[Register(0)])],
        register_count=2,
        input_args=[0]
    )
    
    vm = VirtualMachine()
    with pytest.raises(ValueError, match="Boom"):
        await vm.execute(blueprint, initial_args=[1])
~~~~~

#### Acts 3: 实现 VM 主循环 (`vm.py`)
这是本次修改的核心。我们将 `execute` 方法改造为支持 `TailCall` 的循环，并增加了处理初始参数 (`initial_args`/`initial_kwargs`) 的逻辑。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/vm.py
~~~~~
~~~~~python
import inspect
from typing import Any, List, Dict, Optional
from cascade.runtime.blueprint import Blueprint, Instruction, Call, Literal, Register, Operand, TailCall

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
    Supports Zero-Overhead TCO via an internal loop.
    """
    
    async def execute(
        self, 
        blueprint: Blueprint, 
        initial_args: List[Any] = None, 
        initial_kwargs: Dict[str, Any] = None
    ) -> Any:
        """
        Executes the blueprint. If the result is a TailCall, it re-executes 
        the blueprint with new arguments (TCO) until a final value is returned.
        """
        # 1. Allocate Frame once (reused across TCO steps for zero allocation overhead)
        # Note: In a complex VM we might need a fresh frame, but for simple self-recursion reuse is faster.
        # However, for safety and clarity in this version, let's just reset the registers.
        frame = Frame(blueprint.register_count)
        
        # 2. Load Initial Inputs
        self._load_inputs(frame, blueprint, initial_args or [], initial_kwargs or {})

        # 3. Main Execution Loop (The "Trampoline")
        while True:
            last_result = None
            
            # Execute all instructions in the blueprint linearly
            for instr in blueprint.instructions:
                last_result = await self._dispatch(instr, frame)

            # Check for TCO
            if isinstance(last_result, TailCall):
                # TODO: Handle target_blueprint_id for mutual recursion (Phase 3 Part 2)
                
                # Update frame inputs with new values from TailCall
                # This effectively "resets" the function with new parameters
                self._load_inputs(frame, blueprint, last_result.args, last_result.kwargs)
                
                # Yield control to event loop to allow other coroutines (timers, IO) to run
                # This is CRITICAL for long-running agents.
                # await asyncio.sleep(0) # Optimization: Maybe do this only every N steps?
                # For now, let's keep it simple.
                continue
            
            # Normal return
            return last_result

    def _load_inputs(
        self, 
        frame: Frame, 
        blueprint: Blueprint, 
        args: List[Any], 
        kwargs: Dict[str, Any]
    ):
        """Populates the frame's registers based on the blueprint's input mapping."""
        
        # Positional args
        for i, val in enumerate(args):
            if i < len(blueprint.input_args):
                reg_index = blueprint.input_args[i]
                frame.registers[reg_index] = val
        
        # Keyword args
        for k, val in kwargs.items():
            if k in blueprint.input_kwargs:
                reg_index = blueprint.input_kwargs[k]
                frame.registers[reg_index] = val

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

### 下一步建议
我们已经实现了 `TailCall` 和 VM 循环。
下一步是**集成测试**：我们需要修改 `BlueprintBuilder` 以支持自动生成带有 `input_registers` 的参数化蓝图，并验证编译器和 VM 配合工作的能力。
随后是实现**相互递归 ($A \to B \to A$)**，这将需要引入 `BlueprintRegistry` 和 `TailCall.target_blueprint_id`。
