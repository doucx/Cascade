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
        Compiles the root node. Arguments of the root node are treated as 
        Blueprint inputs.
        """
        # 1. Compile Input Arguments
        # Instead of compiling them recursively as fixed dependencies, 
        # we allocate registers for them immediately and mark them as inputs.
        
        args_operands: List[Operand] = []
        for i, arg in enumerate(target.args):
            reg = self._allocate_register()
            self._input_args_map.append(reg.index)
            # Future: If arg is a nested LazyResult, we might want to compile it 
            # and use its output as the default value? 
            # For TCO/Agent loop, we assume inputs are values passed from outside.
            # If the user passed a LazyResult as an arg to the root task, 
            # it is treated as a value (the LazyResult object itself) passed to the function.
            args_operands.append(reg)

        # Handle kwargs
        kwargs_source = target.kwargs
        if isinstance(target, MappedLazyResult):
            kwargs_source = target.mapping_kwargs

        kwargs_operands: Dict[str, Operand] = {}
        for k, v in kwargs_source.items():
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