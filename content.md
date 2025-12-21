## [WIP] feat(compiler): Support input registers in BlueprintBuilder for TCO

### 用户需求
1.  修改 `BlueprintBuilder`，使其在编译根 `LazyResult` 时，将其参数（`args` 和 `kwargs`）映射为 Blueprint 的 **输入寄存器**，而不是硬编码的字面量。
2.  这样生成的 Blueprint 就变成了一个可重用的“函数模板”，可以通过改变输入寄存器的值来多次执行（支持 VM 的 TCO 循环）。

### 评论
这是 TCO 实现中最关键的编译期变更。之前编译器将所有内容都“烘焙”进了指令中。现在，根节点的参数成为了 Blueprint 的“接口”，允许 VM 在运行时通过 `TailCall` 动态注入新的参数值。

### 目标
1.  重构 `BlueprintBuilder.build`。
2.  确保根节点的参数被分配了寄存器，并记录在 `Blueprint.input_args/input_kwargs` 中。
3.  确保 `Call` 指令引用这些输入寄存器。

### 基本原理
为了让 `recursive_task(n)` 能在 VM 中以 `n=5` 启动，并在随后以 `n=4` 重启，Blueprint 必须有一个 `Register(X)` 对应于参数 `n`。VM 在启动时将 5 放入 `R(X)`，在接收到 `TailCall(n=4)` 时将 4 放入 `R(X)`。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/parser #scope/core #ai/instruct #task/domain/runtime #task/object/compiler #task/action/tco-implementation #task/state/continue

---

### Script

#### Acts 1: 重构 `BlueprintBuilder`

我们将修改 `BlueprintBuilder`。在处理根节点时，我们先为其所有参数分配寄存器，并将这些寄存器记录为输入。然后我们在生成根节点的 `Call` 指令时使用这些寄存器。

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
            instructions=self.instructions,
            register_count=self._register_counter,
            input_args=self._input_args_map,
            input_kwargs=self._input_kwargs_map
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
~~~~~

#### Acts 2: 更新编译器测试 (`test_compiler.py`)
我们需要验证新的编译器行为：根节点的参数是否正确地映射为了 `input_args` 和 `input_kwargs`。

~~~~~act
patch_file
tests/cascade-runtime/graph/test_compiler.py
~~~~~
~~~~~python
def test_compile_single_node():
    """Verify compiling a single task with literal arguments."""
    target = add_one(x=10)

    builder = BlueprintBuilder()
    blueprint = builder.build(target)

    assert blueprint.register_count == 1
    assert len(blueprint.instructions) == 1

    instr = blueprint.instructions[0]
    assert isinstance(instr, Call)
    assert instr.func == add_one.func
    assert isinstance(instr.output, Register)
    assert instr.output.index == 0
    
    # Check kwargs
    assert "x" in instr.kwargs
    arg_op = instr.kwargs["x"]
    assert isinstance(arg_op, Literal)
    assert arg_op.value == 10
~~~~~
~~~~~python
def test_compile_single_node_as_root():
    """
    Verify compiling a single task as root.
    Arguments should be promoted to Input Registers.
    """
    target = add_one(x=10) # 10 here acts as the 'default' or 'template' value structure

    builder = BlueprintBuilder()
    blueprint = builder.build(target)

    # Expected Registers:
    # R0: input 'x'
    # R1: output result
    assert blueprint.register_count == 2
    assert len(blueprint.instructions) == 1

    # Check Input Mapping
    assert "x" in blueprint.input_kwargs
    assert blueprint.input_kwargs["x"] == 0 # Mapped to Register 0

    # Check Instruction
    instr = blueprint.instructions[0]
    assert isinstance(instr, Call)
    assert instr.func == add_one.func
    assert instr.output.index == 1
    
    # Argument for 'x' should be Register(0), NOT Literal(10)
    assert "x" in instr.kwargs
    arg_op = instr.kwargs["x"]
    assert isinstance(arg_op, Register)
    assert arg_op.index == 0
~~~~~

#### Acts 3: 增加 VM 集成测试 (`test_vm_integration.py`)
现在我们可以编写一个真正的集成测试，连接 `BlueprintBuilder` 和 `VirtualMachine`，验证它们是否能协同工作来实现 TCO。

~~~~~act
write_file
tests/cascade-runtime/runtime/test_vm_integration.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.graph.compiler import BlueprintBuilder
from cascade.runtime.vm import VirtualMachine
from cascade.runtime.blueprint import TailCall

# --- Define a recursive task using TailCall ---

@cs.task
def recursive_countdown(count: int) -> Any:
    if count > 0:
        return TailCall(kwargs={"count": count - 1})
    return "Done"

@pytest.mark.asyncio
async def test_vm_tco_integration():
    """
    End-to-end test of TCO:
    1. Define a recursive task.
    2. Compile it using BlueprintBuilder.
    3. Execute it using VirtualMachine.
    """
    
    # 1. Define the workflow template
    # We pass an initial value (5), but this mainly sets the structure.
    # The VM will override this with the initial_kwargs we pass to execute().
    target = recursive_countdown(count=0) 

    # 2. Compile
    builder = BlueprintBuilder()
    blueprint = builder.build(target)
    
    # Verify compilation structure
    # Should have 1 input ('count') and 1 output
    assert "count" in blueprint.input_kwargs
    
    # 3. Execute
    vm = VirtualMachine()
    # Start with count=5
    result = await vm.execute(blueprint, initial_kwargs={"count": 5})
    
    assert result == "Done"
~~~~~

### 下一步建议
我们已经完成了单机 TCO 的核心路径：编译器支持输入提升，VM 支持循环执行。
接下来的挑战是 **相互递归 ($A \to B \to A$)**。
这需要：
1.  `TailCall` 支持 `target_blueprint_id`。
2.  VM 需要一个 `BlueprintRegistry` 来查找和切换蓝图。
3.  编译器需要能够编译多个相关的蓝图并注册它们。
