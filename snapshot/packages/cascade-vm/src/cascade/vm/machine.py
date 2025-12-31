import inspect
import asyncio
from typing import Any, List, Dict, Optional, Callable
from uuid import uuid4

from cascade.spec.blueprint import (
    Blueprint,
    Instruction,
    Call,
    MapCall,
    Literal,
    Register,
    Operand,
    TailCall,
    Jump,
    JumpIfFalse,
)
from cascade.spec.ir.models import TaskDef
from cascade.spec.fingerprint import Fingerprint
from cascade.graph.model import Node

# Use local protocols to avoid circular dependency with engine
from .protocols import ResourceManager, ConstraintManager


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
    def __init__(
        self,
        resource_manager: Optional[ResourceManager] = None,
        constraint_manager: Optional[ConstraintManager] = None,
        wakeup_event: Optional[asyncio.Event] = None,
    ):
        self._blueprints: Dict[str, Blueprint] = {}
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.wakeup_event = wakeup_event

    def register_blueprint(self, bp_id: str, blueprint: Blueprint):
        self._blueprints[bp_id] = blueprint

    async def execute(
        self,
        blueprint: Blueprint,
        symbol_table: Dict[str, Callable],
        initial_args: Optional[List[Any]] = None,
        initial_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        current_blueprint = blueprint
        current_symbol_table = symbol_table

        frame = Frame(current_blueprint.register_count)
        self._load_inputs(
            frame, current_blueprint, initial_args or [], initial_kwargs or {}
        )

        while True:
            pc = 0
            instructions = current_blueprint.instructions
            last_result = None

            while pc < len(instructions):
                instr = instructions[pc]

                if isinstance(instr, Jump):
                    pc += instr.offset
                    continue

                if isinstance(instr, JumpIfFalse):
                    val = frame.load(instr.condition)
                    if not val:
                        pc += instr.offset
                    else:
                        pc += 1
                    continue

                last_result = await self._dispatch(instr, frame, current_symbol_table)
                pc += 1

            if isinstance(last_result, TailCall):
                if last_result.target_blueprint_id:
                    if last_result.target_blueprint_id not in self._blueprints:
                        raise ValueError(
                            f"Unknown target blueprint ID: {last_result.target_blueprint_id}"
                        )
                    current_blueprint = self._blueprints[
                        last_result.target_blueprint_id
                    ]
                    # NOTE: In a multi-blueprint world, we'd need a way to get the
                    # symbol table for the new blueprint. For now, we assume self-recursion.
                    frame = Frame(current_blueprint.register_count)

                self._load_inputs(
                    frame, current_blueprint, last_result.args, last_result.kwargs
                )
                await asyncio.sleep(0)
                continue

            return last_result

    def _load_inputs(
        self,
        frame: Frame,
        blueprint: Blueprint,
        args: List[Any],
        kwargs: Dict[str, Any],
    ):
        for i, val in enumerate(args):
            if i < len(blueprint.input_args):
                reg_index = blueprint.input_args[i]
                frame.registers[reg_index] = val

        for k, val in kwargs.items():
            if k in blueprint.input_kwargs:
                reg_index = blueprint.input_kwargs[k]
                frame.registers[reg_index] = val

    async def _dispatch(
        self, instr: Instruction, frame: Frame, symbol_table: Dict[str, Callable]
    ) -> Any:
        if isinstance(instr, Call):
            return await self._execute_call(instr, frame, symbol_table)
        elif isinstance(instr, MapCall):
            return await self._execute_map_call(instr, frame, symbol_table)
        else:
            raise NotImplementedError(f"Unknown instruction: {type(instr)}")

    async def _execute_map_call(
        self, instr: MapCall, frame: Frame, symbol_table: Dict[str, Callable]
    ) -> Any:
        func = symbol_table.get(instr.structure_hash)
        if func is None:
            raise RuntimeError(
                f"Linking failed: structure_hash '{instr.structure_hash}' "
                f"for task '{instr.task_name}' not found in symbol table."
            )
            
        loaded_kwargs = {k: frame.load(op) for k, op in instr.kwargs.items()}
        
        iterables = {}
        constants = {}
        iterable_len = -1

        for key, value in loaded_kwargs.items():
            if isinstance(value, list):
                iterables[key] = value
                if iterable_len == -1:
                    iterable_len = len(value)
                elif len(value) != iterable_len:
                    raise ValueError(f"Mismatched lengths in MapCall iterables for task '{instr.task_name}'")
            else:
                constants[key] = value

        if iterable_len == -1:
            iterable_len = 0

        calls_to_make = []
        for i in range(iterable_len):
            call_kwargs = constants.copy()
            for key, values_list in iterables.items():
                call_kwargs[key] = values_list[i]
            
            calls_to_make.append(func(**call_kwargs))

        if not calls_to_make:
            results = []
        elif inspect.iscoroutinefunction(func):
            results = await asyncio.gather(*calls_to_make)
        else:
            results = [res for res in calls_to_make]
            
        frame.store(instr.output, results)
        return results

    async def _execute_call(
        self, instr: Call, frame: Frame, symbol_table: Dict[str, Callable]
    ) -> Any:
        func = symbol_table.get(instr.structure_hash)
        if func is None:
            raise RuntimeError(
                f"Linking failed: structure_hash '{instr.structure_hash}' "
                f"for task '{instr.task_name}' not found in symbol table."
            )

        requirements: Dict[str, Any] = {}
        temp_node = None

        if self.constraint_manager or (
            instr.constraints and not instr.constraints.is_empty()
        ):
            stub_def = TaskDef(
                name=instr.task_name,
                args=[],
                fingerprint=Fingerprint(),
            )
            temp_node = Node(
                structural_id=str(uuid4()),
                definition=stub_def,
                node_type="task",
                constraints=instr.constraints,
            )

        if self.constraint_manager and temp_node:
            while not self.constraint_manager.check_permission(temp_node):
                if self.wakeup_event:
                    await self.wakeup_event.wait()
                    self.wakeup_event.clear()
                else:
                    await asyncio.sleep(0.1)

        if temp_node:
            if instr.constraints:
                requirements.update(instr.constraints.requirements)
            if self.constraint_manager:
                requirements.update(self.constraint_manager.get_extra_requirements(temp_node))

        if self.resource_manager and requirements:
            await self.resource_manager.acquire(requirements)

        try:
            args = [frame.load(op) for op in instr.args]
            kwargs = {k: frame.load(op) for k, op in instr.kwargs.items()}
            
            result = func(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result

            frame.store(instr.output, result)
            return result
        finally:
            if self.resource_manager and requirements:
                await self.resource_manager.release(requirements)