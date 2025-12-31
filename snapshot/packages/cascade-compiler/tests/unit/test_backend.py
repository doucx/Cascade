import pytest
from typing import List

from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, EdgeKind, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.blueprint import Blueprint, Call, Register, Literal, JumpIfFalse, MapCall

from cascade.compiler.backend import Backend


def _create_dummy_task_def(name: str) -> TaskDef:
    fp = Fingerprint.from_dict({"current_code_structure_hash": f"hash_{name}"})
    return TaskDef(name=name, args=[], fingerprint=fp)


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


def test_compile_conditional_execution():
    """
    Case 3: Conditional Execution (A -[CONTROL]-> B).
    Verify that Backend generates a JumpIfFalse instruction before B.
    """
    # 1. Setup IR
    # A produces a boolean. B executes only if A is True.
    node_a = NodeIR(id="A", definition=_create_dummy_task_def("condition"))
    node_b = NodeIR(id="B", definition=_create_dummy_task_def("action"))
    
    # Control edge: A -> B
    # target_arg is typically ignored or used for metadata in control edges
    edge = EdgeIR(source_id="A", target_id="B", target_arg="_condition", kind=EdgeKind.CONTROL)
    
    ir = GraphIR(
        nodes=[node_a, node_b],
        edges=[edge]
    )
    plan = [["A"], ["B"]] # Two stages

    # 2. Execute Backend
    blueprint = Backend.compile(ir, plan)

    # 3. Assertions
    # Expected sequence:
    # 0: Call(condition) -> R_a
    # 1: JumpIfFalse(R_a, offset=2) -> Skip next instruction
    # 2: Call(action)
    
    assert len(blueprint.instructions) == 3
    
    instr_0 = blueprint.instructions[0]
    instr_1 = blueprint.instructions[1]
    instr_2 = blueprint.instructions[2]
    
    # Check 0: Condition
    assert isinstance(instr_0, Call)
    assert instr_0.task_name == "condition"
    reg_cond = instr_0.output
    
    # Check 1: Jump
    assert isinstance(instr_1, JumpIfFalse)
    assert instr_1.condition.index == reg_cond.index
    # Offset should skip exactly one instruction (instr_2)
    # The jump is relative to the jump instruction itself? 
    # Or usually relative to PC+1.
    # In our VM implementation:
    # if not val: pc += offset
    # So if we are at PC=1, and we want to go to PC=3 (after action),
    # 1 + offset = 3 => offset = 2.
    assert instr_1.offset == 2
    
    # Check 2: Action
    assert isinstance(instr_2, Call)
    assert instr_2.task_name == "action"


def test_compile_map_node_generates_map_call():
    """
    Case 4: Map Node (A -> Map(B)).
    Verify that Backend generates a MapCall instruction when NodeIR has meta['is_map'].
    """
    # Node B is a map over task "process"
    node_b = NodeIR(
        id="B", 
        definition=_create_dummy_task_def("process"),
        inputs={"scale": 2}, # Constant input
        meta={"is_map": True}
    )
    
    # Dynamic input from A (a list)
    node_a = NodeIR(id="A", definition=_create_dummy_task_def("list_gen"))
    edge = EdgeIR(source_id="A", target_id="B", target_arg="items")
    
    ir = GraphIR(nodes=[node_a, node_b], edges=[edge])
    plan = [["A"], ["B"]]
    
    blueprint = Backend.compile(ir, plan)
    
    # Should have 2 instructions: Call(list_gen) -> MapCall(process)
    assert len(blueprint.instructions) == 2
    instr_map = blueprint.instructions[1]
    
    assert isinstance(instr_map, MapCall)
    assert instr_map.task_name == "process"
    
    # Verify inputs: 'items' comes from Register, 'scale' is Literal
    assert isinstance(instr_map.kwargs["items"], Register)
    assert isinstance(instr_map.kwargs["scale"], Literal)