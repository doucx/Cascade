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
    result = Frontend.compile(lazy)
    ir = result.ir

    # 3. Verify Graph Structure

    assert isinstance(ir, GraphIR)
    assert len(ir.nodes) == 1
    assert len(ir.edges) == 0

    node = ir.nodes[0]
    assert node.definition.name == "simple_task"
    assert node.kwargs["x"] == 10

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
    def producer():
        return 1

    @task
    def consumer(val):
        return val + 1

    # t2 depends on t1
    t1 = producer()
    t2 = consumer(val=t1)

    result = Frontend.compile(t2)
    ir = result.ir

    assert len(ir.nodes) == 2
    assert len(ir.edges) == 1

    edge = ir.edges[0]

    # Verify edge connectivity
    target_node = next(n for n in ir.nodes if n.definition.name == "consumer")
    source_node = next(n for n in ir.nodes if n.definition.name == "producer")

    assert edge.source_node_instance_hash == source_node.current_node_instance_hash
    assert edge.target_node_instance_hash == target_node.current_node_instance_hash
    assert edge.target_arg == "val"


def test_compile_conditional_task():
    """
    Case 3: Conditional Execution (run_if).
    Verify that Frontend generates an EdgeKind.CONTROL edge.
    """

    @task
    def condition():
        return True

    @task
    def action():
        return "done"

    t_cond = condition()
    t_action = action().run_if(t_cond)

    result = Frontend.compile(t_action)
    ir = result.ir

    assert len(ir.edges) == 1
    edge = ir.edges[0]

    # We check for the new EdgeKind
    from cascade.spec.ir.models import EdgeKind

    assert edge.kind == EdgeKind.CONTROL
    assert edge.target_arg == "_condition"  # Internal convention, or explicit field


def test_compile_param_input():
    """
    Case 4: Param Input.
    Verify that cs.Param is compiled into a NodeIR with correct metadata.
    """
    import cascade as cs

    # cs.Param returns a LazyResult that wraps a special internal task
    p = cs.Param("my_param", default=42)

    @task
    def consume(x):
        return x

    workflow = consume(x=p)

    result = Frontend.compile(workflow)
    ir = result.ir

    # Should have 2 nodes: Param node and Consume node
    assert len(ir.nodes) == 2

    # Find param node
    param_node = next(n for n in ir.nodes if n.definition.name == "_get_param_value")

    # Check inputs
    # The Param LazyResult stores the param name in its args/kwargs
    assert param_node.kwargs.get("name") == "my_param" or (
        len(param_node.args) > 0 and param_node.args[0] == "my_param"
    )


def test_compile_map_node():
    """
    Case 5: Map Node.
    Verify that task.map() creates a node marked as a map operation.
    """

    @task
    def double(x):
        return x * 2

    # Map over a list literal
    workflow = double.map(x=[1, 2, 3])

    result = Frontend.compile(workflow)
    ir = result.ir

    assert len(ir.nodes) == 1
    node = ir.nodes[0]

    # The definition should point to the underlying 'double' task
    assert node.definition.name == "double"

    # But the NodeIR needs a way to distinguish itself as a Map.
    # We expect a 'type' or 'mode' field in NodeIR or TaskDef.
    # Currently NodeIR doesn't have it explicitly, let's assume we add it to inputs or separate field.
    # Driving the requirement: NodeIR should have an 'execution_strategy' or similar.
    # For now, let's assert that kwargs contain the list.
    assert node.kwargs["x"] == [1, 2, 3]

    # Spec Requirement: We need to know this is a MAP, not a single call with a list arg.
    # The Frontend must populate a field. Let's assume 'meta' in NodeIR for now.
    assert node.meta.get("is_map") is True
