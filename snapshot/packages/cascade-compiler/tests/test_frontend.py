import pytest
from cascade.compiler.frontend import Frontend
from cascade.spec.task import task
from cascade.spec.ir.models import GraphIR


def test_compile_single_task_structure():
    """
    Case 1: Single Task
    Verify that Frontend.compile transforms a single LazyResult into a GraphIR.
    Also verifies the 'Hash Naming Axiom' by checking fingerprint keys.
    """
    @task
    def simple_task(x: int) -> int:
        return x + 1

    # 1. Prepare Input
    lazy = simple_task(x=10)

    # 2. Execute Compilation (Will fail here)
    ir = Frontend.compile(lazy)

    # 3. Verify Graph Structure
    assert isinstance(ir, GraphIR)
    assert len(ir.nodes) == 1
    assert len(ir.edges) == 0
    
    node = ir.nodes[0]
    assert node.definition.name == "simple_task"
    assert node.inputs["x"] == 10
    
    # 4. Axiom Check: Enforce Long Hash Naming
    # We don't check the value, but the KEY must be the long form.
    fp = node.definition.fingerprint
    assert "current_code_structure_hash" in fp
    # Ensure no short names are present
    assert "hash" not in fp
    assert "id" not in fp
    assert "structure_hash" not in fp


def test_compile_linear_dependency():
    """
    Case 2: Linear Dependency (t2 -> t1)
    Verify that EdgeIR is correctly generated for dependencies.
    """
    @task
    def producer(): return 1
    
    @task
    def consumer(val): return val + 1

    # t2 depends on t1
    t1 = producer()
    t2 = consumer(val=t1)

    ir = Frontend.compile(t2)

    assert len(ir.nodes) == 2
    assert len(ir.edges) == 1
    
    edge = ir.edges[0]
    
    # Verify edge connectivity
    target_node = next(n for n in ir.nodes if n.definition.name == "consumer")
    source_node = next(n for n in ir.nodes if n.definition.name == "producer")
    
    assert edge.source_id == source_node.id
    assert edge.target_id == target_node.id
    assert edge.target_arg == "val"