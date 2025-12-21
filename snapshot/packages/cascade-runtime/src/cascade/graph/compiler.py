from typing import Any, Dict, List, Optional, Union
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.blueprint import Blueprint, Call, Literal, Register, Operand, Instruction

class BlueprintBuilder:
    """
    Compiles a LazyResult dependency graph into a linear Blueprint for VM execution.
    """
    def __init__(self):
        self.instructions: List[Instruction] = []
        # Maps LazyResult UUID to the Register index that holds its result
        self._visited: Dict[str, int] = {} 
        self._register_counter = 0
        
        # Track input registers for the blueprint
        self._input_args_map: List[int] = []
        self._input_kwargs_map: Dict[str, int] = {}

    def build(self, target: Any) -> Blueprint:
        self.instructions.clear()
        self._visited.clear()
        self._register_counter = 0
        self._input_args_map = []
        self._input_kwargs_map = {}
        
        # Special handling for the root node to lift its arguments to input registers
        if isinstance(target, (LazyResult, MappedLazyResult)):
            self._compile_root(target)
        else:
            # Fallback for simple literals (though unlikely in practice)
            raise TypeError(f"Cannot compile non-LazyResult type: {type(target)}")
        
        return Blueprint(
            instructions=list(self.instructions),
            register_count=self._register_counter,
            input_args=list(self._input_args_map),
            input_kwargs=dict(self._input_kwargs_map)
        )

    def _allocate_register(self) -> Register:
        reg = Register(self._register_counter)
        self._register_counter += 1
        return reg

    def _compile_root(self, target: Union[LazyResult, MappedLazyResult]):
        """
        Compiles the root node. 
        - Literal arguments are promoted to Input Registers (to support TCO updates).
        - LazyResult arguments are compiled recursively (inlined dependencies).
        """
        # 1. Compile Arguments
        args_operands: List[Operand] = []
        for i, arg in enumerate(target.args):
            if isinstance(arg, (LazyResult, MappedLazyResult)):
                # Compile dependency
                reg_idx = self._visit(arg)
                args_operands.append(Register(reg_idx))
                # Note: We do NOT add this to input_args_map because it's an internal value
                # derived from dependency execution, not an external input.
                # However, this means TCO cannot "replace" a dependency with a value easily.
                # This is a constraint: You can only TCO-update literal arguments.
                
                # Placeholder for positional input map to maintain index alignment?
                # No, input_args_map maps [Input Index -> Register Index].
                # If arg 0 is internal, Input 0 corresponds to arg 1 (if arg 1 is literal).
                # Wait, VM load_inputs uses index matching.
                # If we have mixed internal/external args, positional mapping gets messy.
                # For now, let's assume TCO usually uses kwargs or all-literal positional args.
                pass 
            else:
                # Promote literal to Input Register
                reg = self._allocate_register()
                self._input_args_map.append(reg.index)
                args_operands.append(reg)

        # Handle kwargs
        kwargs_source = target.kwargs
        if isinstance(target, MappedLazyResult):
            kwargs_source = target.mapping_kwargs

        kwargs_operands: Dict[str, Operand] = {}
        for k, v in kwargs_source.items():
            if isinstance(v, (LazyResult, MappedLazyResult)):
                # Compile dependency
                reg_idx = self._visit(v)
                kwargs_operands[k] = Register(reg_idx)
            else:
                # Promote literal to Input Register
                reg = self._allocate_register()
                self._input_kwargs_map[k] = reg.index
                kwargs_operands[k] = reg

        # 2. Allocate Output Register for the root task
        output_reg = self._allocate_register()

        # 3. Emit Root Call Instruction
        callable_obj = None
        if isinstance(target, LazyResult):
            callable_obj = target.task.func
        elif isinstance(target, MappedLazyResult):
            callable_obj = target.factory

        instr = Call(
            func=callable_obj,
            output=output_reg,
            args=args_operands,
            kwargs=kwargs_operands
        )
        self.instructions.append(instr)

        # 4. Mark Visited (though not strictly needed for root)
        self._visited[target._uuid] = output_reg.index

    def _to_operand(self, value: Any) -> Operand:
        """
        Converts a value into an Operand. 
        If value is a LazyResult, it recursively visits it and returns a Register.
        Otherwise returns a Literal.
        """
        if isinstance(value, (LazyResult, MappedLazyResult)):
            reg_index = self._visit(value)
            return Register(reg_index)
        
        return Literal(value)

    def _visit(self, target: Any) -> int:
        """
        Visits a generic inner node (NOT root), compiles it and its dependencies.
        """
        if not isinstance(target, (LazyResult, MappedLazyResult)):
            raise TypeError(f"Cannot compile non-LazyResult type: {type(target)}")

        if target._uuid in self._visited:
            return self._visited[target._uuid]

        # 1. Compile Arguments (Recursion)
        args_operands = [self._to_operand(a) for a in target.args]
        
        kwargs_source = target.kwargs
        if isinstance(target, MappedLazyResult):
            kwargs_source = target.mapping_kwargs

        kwargs_operands = {k: self._to_operand(v) for k, v in kwargs_source.items()}

        # 2. Allocate Output Register
        output_reg = self._allocate_register()

        # 3. Emit Instruction
        callable_obj = None
        if isinstance(target, LazyResult):
            callable_obj = target.task.func
        elif isinstance(target, MappedLazyResult):
            callable_obj = target.factory

        instr = Call(
            func=callable_obj,
            output=output_reg,
            args=args_operands,
            kwargs=kwargs_operands
        )
        self.instructions.append(instr)

        self._visited[target._uuid] = output_reg.index
        
        return output_reg.index