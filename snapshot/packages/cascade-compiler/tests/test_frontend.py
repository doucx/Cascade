import pytest

# This import will fail, which is the point of this TDD step.
# We mark the tests as xfail to acknowledge this.
try:
    from cascade.compiler import Frontend
except ImportError:
    pass

# We need these to construct the test cases
from cascade.spec.task import task
from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR


@pytest.mark.xfail(raises=(ImportError, NameError), reason="Frontend not yet implemented")
def test_compile_single_task():
    """
    Tests compiling a single, dependency-free task.
    Asserts: The resulting IR contains exactly one node and zero edges.
    """
    @task
    def my_task():
        return "hello"

    target = my_task()
    frontend = Frontend()
    graph_ir: GraphIR = frontend.compile(target)

    assert isinstance(graph_ir, GraphIR)
    assert len(graph_ir.nodes) == 1
    assert len(graph_ir.edges) == 0

    node = graph_ir.nodes[0]
    assert isinstance(node, NodeIR)
    assert node.definition.name == "my_task"


@pytest.mark.xfail(raises=(ImportError, NameError), reason="Frontend not yet implemented")
def test_compile_linear_dependency():
    """
    Tests compiling two tasks where one depends on the other.
    Asserts: The resulting IR has two nodes and one connecting edge.
    """
    @task
    def upstream(data: str):
        return data.upper()

    @task
    def downstream():
        return "source"

    target = upstream(downstream())
    frontend = Frontend()
    graph_ir: GraphIR = frontend.compile(target)

    assert isinstance(graph_ir, GraphIR)
    assert len(graph_ir.nodes) == 2
    assert len(graph_ir.edges) == 1

    # Find nodes by name for easier assertion
    node_map = {n.definition.name: n for n in graph_ir.nodes}
    assert "upstream" in node_map
    assert "downstream" in node_map

    edge = graph_ir.edges[0]
    assert isinstance(edge, EdgeIR)
    
    # Verify the edge direction and argument name
    assert edge.source_id == node_map["downstream"].id
    assert edge.target_id == node_map["upstream"].id
    assert edge.target_arg == "data" # Matches the parameter name in 'upstream'