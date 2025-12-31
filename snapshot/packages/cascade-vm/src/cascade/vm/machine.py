import inspect
import asyncio
from typing import Any, List, Dict, Optional, Callable, Awaitable
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
from .middleware import Middleware, ExecutionContext, NextHandler


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
        self._middlewares: List[Middleware] = []

    def set_middlewares(self, middlewares: List[Middleware]):
        self._middlewares = list(middlewares)

    def register_blueprint(self, bp_id: str, blueprint: Blueprint):
        self._blueprints[bp_id] = blueprint

    async def execute(
        self,
        blueprint: Blueprint,
        symbol_table: Dict[str, Callable],
        initial_args: Optional[List[Any]] = None,
        initial_kwargs: Optional[Dict[str, Any]] = None,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        current_blueprint = blueprint
        current_symbol_table = symbol_table
        # Store context data for this execution run
        self._current_context_data = context_data or {}

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

    async def _execute_via_pipeline(
        self,
        instr: Instruction,
        frame: Frame,
        symbol_table: Dict[str, Callable],
        core_logic: Callable[[ExecutionContext], Awaitable[Any]],
    ) -> Any:
        # 1. Initialize Context
        # Load initial operands from Frame. 
        # Note: Operands themselves are loaded, but ContextOperand/ResourceOperand
        # might evaluate to objects that need further resolution by Middleware.
        # However, frame.load(op) usually handles Register/Literal resolution.
        # ResourceOperand is NOT a Literal/Register, frame doesn't know it.
        # We need to make frame robust or handle it here.
        # CURRENT STATE: Frame.load(op) raises TypeError for unknown operands.
        # We must extend Frame or handle raw operands.
        # DECISION: We pass raw Operands to Context if they are not Registers.
        # Registers must be resolved to values (or Operands if they point to Operands? No, Registers hold values).
        # Actually, let's keep it simple: 
        # Middleware is responsible for resolving ComplexOperands.
        # Frame is responsible for resolving Registers -> Values.
        
        args = []
        for op in instr.args:
            if isinstance(op, Register):
                args.append(frame.load(op))
            elif isinstance(op, Literal):
                args.append(op.value)
            else:
                # ContextOperand, ResourceOperand pass through raw
                args.append(op)
                
        kwargs = {}
        for k, op in instr.kwargs.items():
            if isinstance(op, Register):
                kwargs[k] = frame.load(op)
            elif isinstance(op, Literal):
                kwargs[k] = op.value
            else:
                kwargs[k] = op

        ctx = ExecutionContext(
            vm=self,
            instruction=instr,
            frame=frame,
            symbol_table=symbol_table,
            resolved_args=args,
            resolved_kwargs=kwargs,
            context_data=getattr(self, "_current_context_data", {}),
        )

        # 2. Build Onion
        # Index tracks which middleware to call next
        idx = 0
        middlewares = self._middlewares

        async def dispatch() -> Any:
            nonlocal idx
            if idx < len(middlewares):
                mw = middlewares[idx]
                idx += 1
                return await mw.handle(ctx, dispatch)
            else:
                # End of pipeline: Execute Core
                return await core_logic(ctx)

        # 3. Launch
        return await dispatch()

    async def _core_call_invoker(self, ctx: ExecutionContext) -> Any:
        instr: Call = ctx.instruction
        func = ctx.symbol_table.get(instr.structure_hash)
        # Fallback to function resolution logic if instruction has it (legacy or specialized)
        # But generally symbol_table is source of truth.
        
        if func is None:
             raise RuntimeError(
                f"Linking failed: structure_hash '{instr.structure_hash}' "
                f"for task '{instr.task_name}' not found in symbol table."
            )
            
        # Execute logic (Resources/Constraints currently STRIPPED for plain pipeline test,
        # they should come back as Middleware later)
        
        # But wait, to keep existing behavior for legacy tests, we need to preserve the
        # hardcoded resource logic IF no middleware is set?
        # No, "Scorched Earth": we are replacing the logic.
        # The tests `test_vm_instruction_execution` etc. use simple functions, no resources.
        # The `test_middleware_pipeline` uses mocks.
        # So stripping logic is correct for the pure specific logic.
        # BUT: What about integration tests using resources? 
        # They will fail unless we add default middlewares!
        # ACTION: In VM.__init__, we should install default middlewares 
        # if we want to preserve behavior. Or for now, keep it stripped and fail fast 
        # to drive middleware creation.
        # Given "Infinite Resources" and "Refactor", we choose clean architecture.
        # We will add default middlewares in Phase 3.
        
        result = func(*ctx.resolved_args, **ctx.resolved_kwargs)
        if inspect.isawaitable(result):
            result = await result
            
        ctx.frame.store(instr.output, result)
        return result

    async def _core_map_invoker(self, ctx: ExecutionContext) -> Any:
        instr: MapCall = ctx.instruction
        func = ctx.symbol_table.get(instr.structure_hash)
        if func is None:
             raise RuntimeError(f"Linking failed for map task '{instr.task_name}'")

        # Map Logic with resolved args
        # Identify lists vs scalars
        iterables = {}
        constants = {}
        iterable_len = -1
        
        # MapCall usually only maps kwargs. If we support positioned args mapping, handled here.
        # Note: current spec seems to rely on kwargs for mapping mostly?
        # Blueprint only has kwargs for map inputs in the old Backend logic?
        # Let's support both to be safe, assuming args can be lists too.
        
        # Current VM Implementation Logic:
        # only kwargs supported for mapping in Phase 1 tests?
        # Let's look at `_execute_map_call` impl I am replacing:
        # "loaded_kwargs = {k: frame.load(op) for k, op in instr.kwargs.items()}"
        # It processed kwargs.
        
        for key, value in ctx.resolved_kwargs.items():
            if isinstance(value, list) and key not in instr.kwargs: 
                # Wait, if it's a list literal passed as constant?
                # We need to know if it was INTENDED to be mapped.
                # In IR/Backend, we don't have explicit "map this arg" flag on instruction execution side easily
                # except by convention: if it came from the map source.
                # The old logic: "if isinstance(value, list): iterables[k]=value"
                # This is heuristic and fragile (what if user passes a static list?)
                # But it is the current behavior to preserve.
                iterables[key] = value
                if iterable_len == -1: iterable_len = len(value)
                elif len(value) != iterable_len: raise ValueError("Mismatched lengths")
            elif isinstance(value, list):
                 # This repeats the heuristic: all lists are iterated.
                 iterables[key] = value
                 if iterable_len == -1: iterable_len = len(value)
                 elif len(value) != iterable_len: raise ValueError("Mismatched lengths")
            else:
                constants[key] = value
                
        # What about positional args?
        # If args are present, assume they are static for now (common case)
        # or implement same heuristic.
        # For safety, let's treat resolved_args as constants for now unless we need mapping there.
        
        if iterable_len == -1: iterable_len = 0
        
        results = []
        calls = []
        for i in range(iterable_len):
            ikwargs = constants.copy()
            for k, vals in iterables.items():
                ikwargs[k] = vals[i]
            # Merge positional args (static)
            full_args = ctx.resolved_args 
            calls.append(func(*full_args, **ikwargs))
            
        if calls:
            if inspect.iscoroutinefunction(func):
                results = await asyncio.gather(*calls)
            else:
                results = [c for c in calls]
        
        ctx.frame.store(instr.output, results)
        return results

    # Replaces old _execute_call
    async def _execute_call(
        self, instr: Call, frame: Frame, symbol_table: Dict[str, Callable]
    ) -> Any:
        return await self._execute_via_pipeline(
            instr, frame, symbol_table, self._core_call_invoker
        )

    # Replaces old _execute_map_call
    async def _execute_map_call(
        self, instr: MapCall, frame: Frame, symbol_table: Dict[str, Callable]
    ) -> Any:
        return await self._execute_via_pipeline(
            instr, frame, symbol_table, self._core_map_invoker
        )
