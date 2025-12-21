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