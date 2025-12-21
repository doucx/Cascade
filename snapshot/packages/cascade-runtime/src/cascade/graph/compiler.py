from typing import Any, Dict, List, Optional
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

    def build(self, target: Any) -> Blueprint:
        self.instructions.clear()
        self._visited.clear()
        self._register_counter = 0
        
        self._visit(target)
        
        return Blueprint(
            instructions=self.instructions,
            register_count=self._register_counter
        )

    def _allocate_register(self) -> Register:
        reg = Register(self._register_counter)
        self._register_counter += 1
        return reg

    def _to_operand(self, value: Any) -> Operand:
        """
        Converts a value into an Operand. 
        If value is a LazyResult, it recursively visits it and returns a Register.
        Otherwise returns a Literal.
        """
        if isinstance(value, (LazyResult, MappedLazyResult)):
            reg_index = self._visit(value)
            return Register(reg_index)
        
        # Future: Handle lists/dicts containing LazyResults (CompoundOperand)
        # For now, we treat complex structures as Literals if they don't contain LazyResults at top level
        # A more robust implementation would scan recursively.
        return Literal(value)

    def _visit(self, target: Any) -> int:
        """
        Visits a node, compiles it and its dependencies, and returns the 
        register index where its result will be stored.
        """
        # Handle non-LazyResult (literals passed as target)
        if not isinstance(target, (LazyResult, MappedLazyResult)):
            # This case shouldn't strictly happen if _visit is called correctly,
            # but allows compiling a simple literal into a NO-OP or handling edge cases.
            # For now, we assume target is always LazyResult/MappedLazyResult.
            raise TypeError(f"Cannot compile non-LazyResult type: {type(target)}")

        # Memoization (Graph Reuse)
        if target._uuid in self._visited:
            return self._visited[target._uuid]

        # 1. Compile Arguments (Recursion)
        # This ensures dependencies are emitted BEFORE the current instruction (Post-order traversal)
        args_operands = [self._to_operand(a) for a in target.args]
        
        # Determine kwargs source
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
            # Mapped tasks need special handling in VM, but for now compile as Call
            # The VM will need to handle map logic. 
            # For Phase 1, we treat it as calling the factory (incorrect semantically but fits structure).
            # TODO: Add Map instruction type.
            callable_obj = target.factory

        instr = Call(
            func=callable_obj,
            output=output_reg,
            args=args_operands,
            kwargs=kwargs_operands
        )
        self.instructions.append(instr)

        # 4. Mark Visited
        self._visited[target._uuid] = output_reg.index
        
        return output_reg.index