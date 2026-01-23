from cascade.spec.dsl.task import task
from cascade.spec.ir.graph import GraphIR
from cascade.compiler.frontend.generator import IRGenerator


# --- Test Fixtures ---


@task
def add(a: int, b: int) -> int:
    return a + b


@task
def process_data(data: dict) -> str:
    return str(data.get("key"))


# --- Test Cases ---


def test_generate_simple_task():
    # Arrange
    generator = IRGenerator()
    target = add(1, 2)

    # Act
    generation_result = generator.generate(target)
    graph_ir = generation_result.ir

    # Assert
    assert isinstance(graph_ir, GraphIR)
    assert len(graph_ir.nodes) == 1

    node_ir = graph_ir.nodes[0]
    assert node_ir.name == "add"
    assert node_ir.task.name == "add"
    assert "canonical_code_structure_hash" in node_ir.task.fingerprint

    # Verify that positional arguments are correctly mapped to string keys
    assert node_ir.args == [1, 2]
    assert node_ir.kwargs == {}
    assert node_ir.constraints == {}


def test_generate_task_with_kwargs():
    # Arrange
    generator = IRGenerator()
    target = process_data(data={"key": "value"})

    # Act
    generation_result = generator.generate(target)
    graph_ir = generation_result.ir

    # Assert
    assert len(graph_ir.nodes) == 1
    node_ir = graph_ir.nodes[0]
    assert node_ir.name == "process_data"
    assert node_ir.kwargs == {"data": {"key": "value"}}
    assert node_ir.args == []


def test_generate_task_with_dependency():
    # Arrange
    generator = IRGenerator()
    upstream_lr = add(1, 2)
    downstream_lr = add(upstream_lr, 3)

    # Act
    generation_result = generator.generate(downstream_lr)
    graph_ir = generation_result.ir

    # Assert
    assert len(graph_ir.nodes) == 2

    # The generator produces a topologically sorted list due to post-order traversal
    upstream_node = graph_ir.nodes[0]
    downstream_node = graph_ir.nodes[1]

    # Verify upstream node is correct
    assert upstream_node.name == "add"
    assert upstream_node.args == [1, 2]

    # Verify downstream node correctly references the upstream node's ID
    assert downstream_node.name == "add"
    assert downstream_node.args == [
        upstream_node.current_node_instance_hash,
        3,
    ]
