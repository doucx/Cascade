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

def test_compile_single_node_as_root():
    """
    Verify compiling a single task as root in template mode.
    Arguments should be promoted to Input Registers.
    """
    target = add_one(x=10) # 10 here acts as the 'default' or 'template' value structure

    builder = BlueprintBuilder()
    blueprint = builder.build(target, template=True)

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