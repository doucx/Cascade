import pytest
from typing import List

from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.blueprint import Blueprint, Call, Register, Literal

# RED State: Backend not implemented
try:
    from cascade.compiler.backend import Backend
except ImportError:
    pass


def _create_dummy_task_def(name: str) -> TaskDef:
    fp = Fingerprint.from_dict({"current_code_structure_hash": f"hash_{name}"})
    return TaskDef(name=name, args=[], fingerprint=fp)


@pytest.mark.xfail(reason="Backend not implemented", raises=(ImportError, NameError))
def test_compile_single_node_literals():
    """
    Case 1: Single Node with Literals.
    Verify that Backend generates a Blueprint with a single Call instruction,
    and correctly maps literal inputs to Literal operands.
    """
    # 1. Setup IR
    # Node A(x=1, y="hello")
    task_def = _create_dummy_task_def("task_A")
    node = NodeIR(id="A", definition=task_def, inputs={"x": 1, "y": "hello"})
    
    ir = GraphIR(nodes=[node], edges=[])
    plan = [["A"]] # Single stage

    # 2. Execute Backend
    blueprint = Backend.compile(ir, plan)

    # 3. Assertions
    assert isinstance(blueprint, Blueprint)
    assert len(blueprint.instructions) == 1
    
    instr = blueprint.instructions[0]
    assert isinstance(instr, Call)
    assert instr.task_name == "task_A"
    
    # Check outputs
    assert isinstance(instr.output, Register)
    
    # Check inputs (Literals)
    assert "x" in instr.kwargs
    arg_x = instr.kwargs["x"]
    assert isinstance(arg_x, Literal)
    assert arg_x.value == 1
    
    assert "y" in instr.kwargs
    arg_y = instr.kwargs["y"]
    assert isinstance(arg_y, Literal)
    assert arg_y.value == "hello"


@pytest.mark.xfail(reason="Backend not implemented", raises=(ImportError, NameError))
def test_compile_dependency_registers():
    """
    Case 2: Dependency (A -> B).
    Verify that Backend correctly allocates registers for data flow.
    The output register of A must be used as a Register operand for B.
    """
    # 1. Setup IR
    # A produces result. B consumes result as 'val'.
    node_a = NodeIR(id="A", definition=_create_dummy_task_def("producer"))
    node_b = NodeIR(id="B", definition=_create_dummy_task_def("consumer"))
    
    edge = EdgeIR(source_id="A", target_id="B", target_arg="val")
    
    ir = GraphIR(
        nodes=[node_a, node_b],
        edges=[edge]
    )
    plan = [["A"], ["B"]] # Two stages

    # 2. Execute Backend
    blueprint = Backend.compile(ir, plan)

    # 3. Assertions
    assert len(blueprint.instructions) == 2
    
    # We expect instructions in topological order based on the plan
    instr_a = blueprint.instructions[0]
    instr_b = blueprint.instructions[1]
    
    assert instr_a.task_name == "producer"
    assert instr_b.task_name == "consumer"
    
    # Critical Check: Register Linkage
    # A's output -> Register R_k
    # B's input 'val' -> Register R_k
    reg_out_a = instr_a.output
    
    assert "val" in instr_b.kwargs
    operand_in_b = instr_b.kwargs["val"]
    
    assert isinstance(operand_in_b, Register)
    assert operand_in_b.index == reg_out_a.index