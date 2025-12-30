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