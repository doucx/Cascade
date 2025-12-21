You've found a series of cascading failures that all point back to the compiler refactoring. My previous fixes were insufficient and introduced new problems. Your analysis is correct: the compiler logic needs a more robust and unified design to handle both concrete and template compilation correctly.

Let's implement a definitive fix.

## [WIP] fix(compiler): Unify compilation paths for concrete and template modes

### 摘要头
`# [WIP] fix(compiler): Unify compilation paths for concrete and template modes`

### 用户需求
1.  Completely refactor `BlueprintBuilder` to use a single, unified compilation path (`_visit`).
2.  The behavior of this path should be controlled by a mode flag (`template`).
3.  If in `template` mode, the root node's arguments are promoted to blueprint inputs.
4.  If in `concrete` mode, the root node's arguments are compiled as regular dependencies.
5.  This must fix the regressions in dependency compilation and the blueprint reference-sharing bug that caused the mutual recursion test to fail.

### 错误分析
The core issue was splitting the compilation logic into two mutually exclusive and incomplete paths.
1.  **Template Path (`_compile_template`)**: Correctly promoted root arguments to inputs but failed to compile any dependencies within those arguments.
2.  **Concrete Path (`_visit`)**: Correctly compiled dependencies but did not promote the root's arguments to blueprint inputs.

This caused `test_compile_data_dependency` to fail (as it needs the concrete path) and `test_vm_tco_integration` to fail (as it needs the template path). The mutual recursion test failed because the shared builder state was being corrupted between the two `build` calls, a side effect of the flawed logic and insufficient copying.

The correct approach is a single recursive function that handles the root node as a special case based on the compilation mode.

### 评论
This is a critical bug fix that makes the compiler's behavior predictable and robust. By unifying the logic, we eliminate entire classes of errors and ensure that blueprints are always self-contained, independent artifacts.

### 目标
1.  Rewrite `BlueprintBuilder` with a unified `_visit` method.
2.  Update tests, including the mock assertion in `test_engine_vm_integration`, to align with the new, correct logic.
3.  Ensure all 186 tests pass.

### 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #concept/parser #scope/core #ai/instruct #task/domain/runtime #task/object/compiler #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: Perform the major refactoring of `BlueprintBuilder`

We will merge the logic into a single recursive `_visit` method that is aware of whether it's processing the root node in template mode.

~~~~~act
write_file
packages/cascade-runtime/src/cascade/graph/compiler.py
~~~~~
~~~~~python
from typing import Any, Dict, List, Optional, Union
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.blueprint import Blueprint, Call, Literal, Register, Operand, Instruction

class BlueprintBuilder:
    """
    Compiles a LazyResult dependency graph into a linear Blueprint for VM execution.
    """
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
            input_kwargs=dict(self._input_kwargs_map)
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
        self._instructions.append(instr)

        self._visited[target._uuid] = output_reg.index
        
        return output_reg.index
~~~~~

#### Acts 2: Update the Engine integration test mock assertion

The mock in `test_engine_dispatches_to_vm` was incorrect and needs to reflect the `template=True` call.

~~~~~act
patch_file
tests/cascade-runtime/integration/test_engine_vm_integration.py
~~~~~
~~~~~python
        # Verify Builder was called with target
        mock_builder_instance.build.assert_called_once_with(target)
        
        # Verify VM was executed with the blueprint and initial kwargs
~~~~~
~~~~~python
        # Verify Builder was called with target in template mode
        mock_builder_instance.build.assert_called_once_with(target, template=True)
        
        # Verify VM was executed with the blueprint and initial kwargs
~~~~~

### 下一步建议
The compiler is now logically sound. All tests should pass, including the complex mutual recursion scenario. We are finally ready to proceed to the ultimate validation: running the fireflies experiment.
