import inspect
import asyncio
from typing import Any, List, Dict, Optional
from uuid import uuid4

from cascade.spec.blueprint import (
    Blueprint,
    Instruction,
    Call,
    Literal,
    Register,
    Operand,
    TailCall,
)
from cascade.spec.model import Node
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.constraints import ConstraintManager


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
    Supports Zero-Overhead TCO via an internal loop and blueprint switching.
    Now integrated with Resource and Constraint Managers.
    """

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
        initial_args: List[Any] = None,
        initial_kwargs: Dict[str, Any] = None,
    ) -> Any:
        """
        Executes the initial blueprint. Handles TailCalls to self or other registered blueprints.
        """
        current_blueprint = blueprint

        # 1. Allocate Frame
        # We start with the frame for the initial blueprint
        frame = Frame(current_blueprint.register_count)

        # 2. Load Initial Inputs
        self._load_inputs(
            frame, current_blueprint, initial_args or [], initial_kwargs or {}
        )

        # 3. Main Execution Loop (The "Trampoline")
        while True:
            last_result = None

            # Execute all instructions in the current blueprint
            for instr in current_blueprint.instructions:
                last_result = await self._dispatch(instr, frame)

            # Check for TCO
            if isinstance(last_result, TailCall):
                # Determine target blueprint
                if last_result.target_blueprint_id:
                    if last_result.target_blueprint_id not in self._blueprints:
                        raise ValueError(
                            f"Unknown target blueprint ID: {last_result.target_blueprint_id}"
                        )
                    current_blueprint = self._blueprints[
                        last_result.target_blueprint_id
                    ]

                    # For a new blueprint (mutual recursion), we MUST allocate a new frame
                    frame = Frame(current_blueprint.register_count)
                else:
                    # Self-recursion: reuse current_blueprint
                    pass

                # Load inputs into the (potentially new) frame
                self._load_inputs(
                    frame, current_blueprint, last_result.args, last_result.kwargs
                )

                # Yield control to event loop to allow IO/timers to process
                await asyncio.sleep(0)
                continue

            # Normal return
            return last_result

    def _load_inputs(
        self,
        frame: Frame,
        blueprint: Blueprint,
        args: List[Any],
        kwargs: Dict[str, Any],
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
        # --- Resource & Constraint Logic ---
        requirements = {}

        # Construct a temporary Node object for the ConstraintManager
        # We assume node_type="task" for standard calls
        temp_node = None

        if self.constraint_manager or (
            instr.constraints and not instr.constraints.is_empty()
        ):
            temp_node = Node(
                id=str(uuid4()),
                name=instr.task_name,
                node_type="task",
                constraints=instr.constraints,
            )

        # 1. Permission Check (e.g. Rate Limits, Pauses)
        if self.constraint_manager and temp_node:
            while not self.constraint_manager.check_permission(temp_node):
                if self.wakeup_event:
                    await self.wakeup_event.wait()
                    self.wakeup_event.clear()
                else:
                    # Fallback if no event provided (shouldn't happen in proper Engine setup)
                    await asyncio.sleep(0.1)

        # 2. Resource Resolution & Acquisition
        if temp_node:
            # Static constraints
            if instr.constraints:
                for res, amount in instr.constraints.requirements.items():
                    # For VM, we assume constraints are resolved literals or handled simply
                    # Dynamic constraints (LazyResults) inside VM are tricky, skipping for now
                    requirements[res] = amount

            # Global/Dynamic constraints from Manager
            if self.constraint_manager:
                extra = self.constraint_manager.get_extra_requirements(temp_node)
                requirements.update(extra)

        if self.resource_manager and requirements:
            await self.resource_manager.acquire(requirements)

        try:
            # --- Execution ---
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
        finally:
            # --- Resource Release ---
            if self.resource_manager and requirements:
                await self.resource_manager.release(requirements)
