import pytest
from cascade.foundation.definitions.model import TaskDef
from cascade.foundation.ir.ops import ComputeOp
from cascade.compiler.builder import Compiler

def func_a(x): return x
def func_b(y): return y + 1

def test_dependency_chain_lowering():
    # Construct: Task B -> Task A -> Literal
    
    # Task A depends on literal 10
    task_a = TaskDef(
        name="task_a",
        func=func_a,
        bindings={"x": 10}
    )
    
    # Task B depends on Task A
    task_b = TaskDef(
        name="task_b",
        func=func_b,
        bindings={"y": task_a}
    )
    
    compiler = Compiler()
    graph = compiler.compile(task_b)
    
    # 1. Check Root (Task B)
    root_op = graph.ops[graph.root_op_id]
    assert isinstance(root_op, ComputeOp)
    assert root_op.callable_ref.endswith("func_b")
    
    # 2. Check Dependency Link
    # root_op.inputs["y"] should be the ID of Task A's op
    op_a_id = root_op.inputs["y"]
    assert op_a_id in graph.ops
    op_a = graph.ops[op_a_id]
    
    assert isinstance(op_a, ComputeOp)
    assert op_a.callable_ref.endswith("func_a")
    
    # 3. Check Task A's input
    # op_a.inputs["x"] should be a ConstantOp
    const_id = op_a.inputs["x"]
    assert graph.ops[const_id].value == 10

def test_deterministic_identity():
    # Two separate compiler instances processing identical definitions
    # MUST produce identical Op IDs.
    
    t1 = TaskDef(name="t", func=func_a, bindings={"x": 1})
    c1 = Compiler()
    g1 = c1.compile(t1)
    
    t2 = TaskDef(name="t", func=func_a, bindings={"x": 1})
    c2 = Compiler()
    g2 = c2.compile(t2)
    
    assert g1.root_op_id == g2.root_op_id
    assert g1.root_op_id is not None
    # Ensure it's not using python object id (which would likely be numeric strings)
    # Fingerprint hashes are usually hex strings
    assert not g1.root_op_id.isdigit() 