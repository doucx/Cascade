import inspect
import asyncio
from typing import Any, List, Dict, Optional
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

# Use local protocols to avoid circular dependency with engine
from .protocols import ResourceManager, ConstraintManager

# We need a Node-like object for ConstraintManager interaction.
# Since we can't import Node from cascade-graph (it might depend on engine or be heavy),
# we define a minimal StubNode that satisfies the contract expected by ConstraintManager.
# However, usually Node is just a data class from cascade-graph. 
# To stay strictly decoupled, we can assume the ConstraintManager accepts any object 
# with the necessary attributes (duck typing), or we import Node if cascade-graph is a safe dependency.
# For this refactor, let's try to import Node from cascade-graph as it should be a low-level definition.
# If cascade-graph is not safe, we'll use a local stub.
# Looking at the dependency graph: cascade-graph depends on cascade-spec. Safe.
from cascade.graph.model import Node


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
        initial_args: Optional[List[Any]] = None,
        initial_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        current_blueprint = blueprint

        # 1. Allocate Frame
        frame = Frame(current_blueprint.register_count)

        # 2. Load Initial Inputs
        self._load_inputs(
            frame, current_blueprint, initial_args or [], initial_kwargs or {}
        )

        # 3. Main Execution Loop
        while True:
            pc = 0
            instructions = current_blueprint.instructions
            last_result = None

            while pc < len(instructions):
                instr = instructions[pc]

                # Handle Control Flow
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

                # Handle Standard Instructions
                last_result = await self._dispatch(instr, frame)
                pc += 1

            # TCO Logic
            if isinstance(last_result, TailCall):
                if last_result.target_blueprint_id:
                    if last_result.target_blueprint_id not in self._blueprints:
                        raise ValueError(
                            f"Unknown target blueprint ID: {last_result.target_blueprint_id}"
                        )
                    current_blueprint = self._blueprints[
                        last_result.target_blueprint_id
                    ]
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

    async def _dispatch(self, instr: Instruction, frame: Frame) -> Any:
        if isinstance(instr, Call):
            return await self._execute_call(instr, frame)
        elif isinstance(instr, MapCall):
            return await self._execute_map_call(instr, frame)
        else:
            raise NotImplementedError(f"Unknown instruction: {type(instr)}")

    async def _execute_map_call(self, instr: MapCall, frame: Frame) -> Any:
        # 1. Load all arguments from frame
        loaded_kwargs = {k: frame.load(op) for k, op in instr.kwargs.items()}
        
        # 2. Separate iterables from constants
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

        if iterable_len == -1: # No iterables found, treat as empty map
            iterable_len = 0

        # 3. Prepare individual calls
        calls_to_make = []
        for i in range(iterable_len):
            call_kwargs = constants.copy()
            for key, values_list in iterables.items():
                call_kwargs[key] = values_list[i]
            
            calls_to_make.append(instr.func(**call_kwargs))

        # 4. Execute calls concurrently if async, sequentially otherwise
        if not calls_to_make:
            results = []
        elif inspect.iscoroutinefunction(instr.func):
            results = await asyncio.gather(*calls_to_make)
        else:
            results = [res for res in calls_to_make]
            
        # 5. Store result and return
        frame.store(instr.output, results)
        return results

    async def _execute_call(self, instr: Call, frame: Frame) -> Any:
        requirements: Dict[str, Any] = {}
        temp_node = None

        # Build requirement set and temp node for validation
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

        # 1. Check Permissions
        if self.constraint_manager and temp_node:
            while not self.constraint_manager.check_permission(temp_node):
                if self.wakeup_event:
                    await self.wakeup_event.wait()
                    self.wakeup_event.clear()
                else:
                    await asyncio.sleep(0.1)

        # 2. Resolve Resources
        if temp_node:
            if instr.constraints:
                requirements.update(instr.constraints.requirements)
            if self.constraint_manager:
                requirements.update(self.constraint_manager.get_extra_requirements(temp_node))

        # 3. Acquire
        if self.resource_manager and requirements:
            await self.resource_manager.acquire(requirements)

        try:
            # 4. Execute
            args = [frame.load(op) for op in instr.args]
            kwargs = {k: frame.load(op) for k, op in instr.kwargs.items()}
            
            if instr.func is None:
                raise ValueError(f"Instruction for task '{instr.task_name}' has no function to call.")
            
            result = instr.func(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result

            frame.store(instr.output, result)
            return result
        finally:
            # 5. Release
            if self.resource_manager and requirements:
                await self.resource_manager.release(requirements)