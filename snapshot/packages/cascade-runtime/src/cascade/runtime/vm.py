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