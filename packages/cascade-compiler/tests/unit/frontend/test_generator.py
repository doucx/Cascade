import pytest

from cascade.spec.task import task
from cascade.spec.ir.models import GraphIR
from cascade.compiler.frontend.generator import IRGenerator


# --- Test Fixtures ---

@task
def add(a: int, b: int) -> int:
    """A simple task for testing."""
    return a + b


@task
def process_data(data: dict) -> str:
    """A task with more complex literal arguments."""
    return str(data.get("key"))


# --- Test Cases ---


def test_generate_simple_task():
    """
    Tests that a single LazyResult with literal arguments is converted
    into a valid GraphIR with a single NodeIR.
    """
    # Arrange
    generator = IRGenerator()
    target = add(1, 2)

    # Act
    graph_ir = generator.generate(target)

    # Assert
    assert isinstance(graph_ir, GraphIR)
    assert len(graph_ir.nodes) == 1

    node_ir = graph_ir.nodes[0]
    assert node_ir.name == "add"
    assert node_ir.task.name == "add"
    assert "current_code_structure_hash" in node_ir.task.fingerprint

    # Verify that positional arguments are correctly mapped to string keys
    assert node_ir.inputs == {"0": 1, "1": 2}
    assert node_ir.constraints == {}


def test_generate_task_with_kwargs():
    """
    Tests that a single LazyResult with literal keyword arguments is
    correctly converted.
    """
    # Arrange
    generator = IRGenerator()
    target = process_data(data={"key": "value"})

    # Act
    graph_ir = generator.generate(target)

    # Assert
    assert len(graph_ir.nodes) == 1
    node_ir = graph_ir.nodes[0]
    assert node_ir.name == "process_data"
    assert node_ir.inputs == {"data": {"key": "value"}}


def test_generate_task_with_dependency():
    """
    Tests that a LazyResult depending on another is converted into two
    NodeIRs with a correct ID reference.
    """
    # Arrange
    generator = IRGenerator()
    upstream_lr = add(1, 2)
    downstream_lr = add(upstream_lr, 3)

    # Act
    graph_ir = generator.generate(downstream_lr)

    # Assert
    assert len(graph_ir.nodes) == 2

    # The generator produces a topologically sorted list due to post-order traversal
    upstream_node = graph_ir.nodes[0]
    downstream_node = graph_ir.nodes[1]

    # Verify upstream node is correct
    assert upstream_node.name == "add"
    assert upstream_node.inputs == {"0": 1, "1": 2}

    # Verify downstream node correctly references the upstream node's ID
    assert downstream_node.name == "add"
    assert downstream_node.inputs == {"0": upstream_node.id, "1": 3}