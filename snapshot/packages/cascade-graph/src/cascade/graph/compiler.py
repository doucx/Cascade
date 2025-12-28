from typing import Any, Dict, List
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.blueprint import (
    Blueprint,
    Call,
    Literal,
    Register,
    Operand,
    Instruction,
)


class BlueprintBuilder:
    def __init__(self):
        self._instructions: List[Instruction] = []
        self._visited: Dict[str, int] = {}
        self._register_counter = 0
        self._input_args_map: List[int] = []
        self._input_kwargs_map: Dict[str, int] = {}
        self._is_template_mode: bool = False

    def build(self, target: Any, template: bool = False) -> Blueprint:
        # Reset state for a fresh build
        self._instructions = []
        self._visited = {}
        self._register_counter = 0
        self._input_args_map = []
        self._input_kwargs_map = {}
        self._is_template_mode = template

        self._visit(target, is_root=True)

        # Return a new Blueprint with copies of the internal state
        return Blueprint(
            instructions=list(self._instructions),
            register_count=self._register_counter,
            input_args=list(self._input_args_map),
            input_kwargs=dict(self._input_kwargs_map),
        )

    def _allocate_register(self) -> Register:
        reg = Register(self._register_counter)
        self._register_counter += 1
        return reg

    def _to_operand(self, value: Any) -> Operand:
        if isinstance(value, (LazyResult, MappedLazyResult)):
            reg_index = self._visit(value, is_root=False)
            return Register(reg_index)
        return Literal(value)

    def _visit(self, target: Any, is_root: bool) -> int:
        if not isinstance(target, (LazyResult, MappedLazyResult)):
            raise TypeError(f"Cannot compile non-LazyResult type: {type(target)}")

        if target._uuid in self._visited:
            return self._visited[target._uuid]

        # 1. Determine Arguments
        args_operands: List[Operand] = []
        kwargs_operands: Dict[str, Operand] = {}

        kwargs_source = target.kwargs
        if isinstance(target, MappedLazyResult):
            kwargs_source = target.mapping_kwargs

        is_template_root = is_root and self._is_template_mode

        if is_template_root:
            # Template Mode: Promote arguments to input registers
            for arg in target.args:
                reg = self._allocate_register()
                self._input_args_map.append(reg.index)
                args_operands.append(reg)
            for k, v in kwargs_source.items():
                reg = self._allocate_register()
                self._input_kwargs_map[k] = reg.index
                kwargs_operands[k] = reg
        else:
            # Concrete Mode: Compile arguments as dependencies
            args_operands = [self._to_operand(a) for a in target.args]
            kwargs_operands = {k: self._to_operand(v) for k, v in kwargs_source.items()}

        # 2. Allocate Output Register
        output_reg = self._allocate_register()

        # 3. Emit Instruction
        callable_obj = None
        task_name = "unknown"
        constraints = None

        if isinstance(target, LazyResult):
            callable_obj = target.task.func
            task_name = target.task.name
            constraints = target._constraints
        elif isinstance(target, MappedLazyResult):
            callable_obj = target.factory
            task_name = getattr(target.factory, "name", "map")
            constraints = target._constraints

        instr = Call(
            func=callable_obj,
            output=output_reg,
            args=args_operands,
            kwargs=kwargs_operands,
            task_name=task_name,
            constraints=constraints,
        )
        self._instructions.append(instr)

        self._visited[target._uuid] = output_reg.index

        return output_reg.index
