## [WIP] 这是第一阶段的实施。我们将创建蓝图 IR 定义，编写测试用例，并实现用于将 `LazyResult` DAG 编译为线性指令序列的编译器。

### Script

#### Acts 1: 定义蓝图 IR (Intermediate Representation)

创建 `blueprint.py`，定义用于虚拟机执行的核心数据结构。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/blueprint.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Any, List, Dict, Union

@dataclass
class Operand:
    """Base class for instruction operands."""
    pass

@dataclass
class Literal(Operand):
    """Represents a static value known at compile time."""
    value: Any

@dataclass
class Register(Operand):
    """Represents a dynamic value stored in a virtual register."""
    index: int

@dataclass
class Instruction:
    """Base class for VM instructions."""
    pass

@dataclass
class Call(Instruction):
    """
    Instruction to call a callable (function/task).
    Results are stored in the 'output' register.
    """
    func: Any
    output: Register
    args: List[Operand] = field(default_factory=list)
    kwargs: Dict[str, Operand] = field(default_factory=dict)

@dataclass
class Blueprint:
    """
    Represents a compiled workflow, ready for execution by the VM.
    """
    instructions: List[Instruction] = field(default_factory=list)
    register_count: int = 0
~~~~~

#### Acts 2: 创建编译器测试用例

创建 `test_compiler.py`。包含针对单个节点和数据依赖的测试。

~~~~~act
write_file
tests/cascade-runtime/graph/test_compiler.py
~~~~~
~~~~~python
import pytest
from typing import Any
import cascade as cs
from cascade.spec.lazy_types import LazyResult
from cascade.graph.compiler import BlueprintBuilder
from cascade.runtime.blueprint import Call, Literal, Register

# --- Helpers ---

@cs.task
def add_one(x: int) -> int:
    return x + 1

@cs.task
def add(x: int, y: int) -> int:
    return x + y

# --- Tests ---

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

def test_compile_data_dependency():
    """Verify compiling a task that depends on another task."""
    # dependency = add_one(1)  -> returns 2
    # target = add(dependency, 5) -> returns 7
    dep = add_one(1)
    target = add(dep, 5)

    builder = BlueprintBuilder()
    blueprint = builder.build(target)

    # Should have 2 registers (one for dep output, one for target output)
    assert blueprint.register_count == 2
    assert len(blueprint.instructions) == 2

    # First instruction: dep
    instr1 = blueprint.instructions[0]
    assert isinstance(instr1, Call)
    assert instr1.func == add_one.func
    assert instr1.output.index == 0 # First register

    # Second instruction: target
    instr2 = blueprint.instructions[1]
    assert isinstance(instr2, Call)
    assert instr2.func == add.func
    assert instr2.output.index == 1 # Second register

    # Check args of second instruction
    # First arg should be a Register pointing to instr1 output
    assert len(instr2.args) == 2
    arg0 = instr2.args[0]
    assert isinstance(arg0, Register)
    assert arg0.index == 0 
    
    # Second arg should be a Literal
    arg1 = instr2.args[1]
    assert isinstance(arg1, Literal)
    assert arg1.value == 5

def test_compile_diamond_dependency():
    """Verify reuse of results (diamond dependency)."""
    # A -> B, A -> C, D(B, C)
    # But simpler: A -> B(A), C(A)
    
    root = add_one(1) # reg 0
    b = add_one(root) # reg 1
    c = add_one(root) # reg 2
    target = add(b, c) # reg 3

    builder = BlueprintBuilder()
    blueprint = builder.build(target)

    # Should have 4 instructions
    assert len(blueprint.instructions) == 4
    # Register count 4
    assert blueprint.register_count == 4
    
    # Check that root is computed once (only one instruction for it)
    root_calls = [i for i in blueprint.instructions if i.func == add_one.func and isinstance(i.args[0], Literal)]
    assert len(root_calls) == 1
~~~~~

#### Acts 3: 实现蓝图编译器

创建 `compiler.py`，实现 `BlueprintBuilder`。它执行 DAG 的后序遍历（通过递归调用 `_visit` 并在处理参数后添加指令），从而生成拓扑排序的指令序列。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/graph/compiler.py
~~~~~
~~~~~python
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
~~~~~
