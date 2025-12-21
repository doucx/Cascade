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
    Supports Zero-Overhead TCO via an internal loop and blueprint switching.
    """
    
    def __init__(self):
        self._blueprints: Dict[str, Blueprint] = {}

    def register_blueprint(self, bp_id: str, blueprint: Blueprint):
        self._blueprints[bp_id] = blueprint

    async def execute(
        self, 
        blueprint: Blueprint, 
        initial_args: List[Any] = None, 
        initial_kwargs: Dict[str, Any] = None
    ) -> Any:
        """
        Executes the initial blueprint. Handles TailCalls to self or other registered blueprints.
        """
        current_blueprint = blueprint
        
        # 1. Allocate Frame
        # We start with the frame for the initial blueprint
        frame = Frame(current_blueprint.register_count)
        
        # 2. Load Initial Inputs
        self._load_inputs(frame, current_blueprint, initial_args or [], initial_kwargs or {})

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
                        raise ValueError(f"Unknown target blueprint ID: {last_result.target_blueprint_id}")
                    current_blueprint = self._blueprints[last_result.target_blueprint_id]
                    
                    # For a new blueprint (mutual recursion), we MUST allocate a new frame
                    # because the register layout and count might differ.
                    frame = Frame(current_blueprint.register_count)
                else:
                    # Self-recursion: keep current_blueprint and current frame
                    # Optimization: We could reuse the frame, just ensuring inputs are overwritten correctly.
                    # Current Frame implementation allows overwriting, so reuse is fine.
                    pass
                
                # Load inputs into the (potentially new) frame
                self._load_inputs(frame, current_blueprint, last_result.args, last_result.kwargs)
                
                # Yield control to event loop
                # await asyncio.sleep(0) 
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