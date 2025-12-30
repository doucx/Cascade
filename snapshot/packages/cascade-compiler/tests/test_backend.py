import pytest

from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.blueprint import Blueprint, Call, Literal, Register

# NOTE: The Backend is not yet implemented.
# We expect an ImportError, which will cause the tests to fail (RED state).
try:
    from cascade.compiler.backend import Backend
except ImportError:
    pass


def _create_dummy_task_def(name: str, args: list = None) -> TaskDef:
    """Helper to create a minimal TaskDef."""
    fp = Fingerprint.from_dict({"current_code_structure_hash": f"hash_for_{name}"})
    arg_defs = [ArgumentDef(name=arg, kind=ArgumentKind.POSITIONAL_OR_KEYWORD) for arg in (args or [])]
    return TaskDef(name=name, args=arg_defs, fingerprint=fp)


@pytest.mark.xfail(reason="Backend not implemented", raises=(ImportError, NameError))
def test_backend_generates_call_instruction():
    """
    Case 1: Function Call Generation
    Verify a single Node IR with a literal input generates a correct CALL instruction.
    """
    task_def = _create_dummy_task_def("simple_task", args=["x"])
    node = NodeIR(id="node1", definition=task_def, inputs={"x": 42})
    ir = GraphIR(nodes=[node], edges=[])

    # This call will fail until Backend is implemented
    blueprint: Blueprint = Backend.generate(ir)

    assert isinstance(blueprint, Blueprint)
    assert len(blueprint.instructions) == 1
    
    instr = blueprint.instructions[0]
    assert isinstance(instr, Call)
    
    # Verify operands
    assert len(instr.args) == 0
    assert "x" in instr.kwargs
    assert isinstance(instr.kwargs["x"], Literal)
    assert instr.kwargs["x"].value == 42
    
    # Verify output
    assert isinstance(instr.output, Register)


@pytest.mark.xfail(reason="Backend not implemented", raises=(ImportError, NameError))
def test_backend_allocates_registers_for_dependency():
    """
    Case 2: Register Allocation for a dependency (A -> B)
    Verify the output register of A is used as an input operand for B.
    """
    # IR for A -> B where B takes the result of A as argument 'val'
    def_a = _create_dummy_task_def("producer")
    def_b = _create_dummy_task_def("consumer", args=["val"])
    node_a = NodeIR(id="A", definition=def_a)
    node_b = NodeIR(id="B", definition=def_b)
    ir = GraphIR(
        nodes=[node_a, node_b],
        edges=[EdgeIR(source_id="A", target_id="B", target_arg="val")]
    )

    blueprint: Blueprint = Backend.generate(ir)

    assert len(blueprint.instructions) == 2
    
    call_a, call_b = blueprint.instructions
    
    # Instruction A: producer() -> r0
    assert isinstance(call_a, Call)
    assert call_a.task_name == "producer"
    assert isinstance(call_a.output, Register)
    register_a_out = call_a.output
    
    # Instruction B: consumer(val=r0) -> r1
    assert isinstance(call_b, Call)
    assert call_b.task_name == "consumer"
    assert "val" in call_b.kwargs
    
    # Key assertion: input operand of B must be the output register of A
    input_operand = call_b.kwargs["val"]
    assert isinstance(input_operand, Register)
    assert input_operand.index == register_a_out.index
    
    assert isinstance(call_b.output, Register)
    assert call_b.output.index != register_a_out.index