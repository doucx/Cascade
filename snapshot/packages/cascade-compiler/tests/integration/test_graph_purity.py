import pickle
import pytest

from cascade.spec.dsl.task import task
from cascade.spec.physical.environment import EnvironmentDef
from cascade.compiler.frontend import IRGenerator
from cascade.compiler.backend import Builder


@task
def add(a: int, b: int) -> int:
    return a + b


@task
def square(n: int) -> int:
    return n * n


def test_graph_is_serializable_and_pure():
    # 1. Define a representative workflow
    workflow = square(add(1, 2))

    # 2. Compile the workflow into a physical graph
    generator = IRGenerator()
    builder = Builder()
    environment = EnvironmentDef(resources=[])

    graph_ir = generator.generate(workflow)
    artifact = builder.build(graph_ir, environment)
    assembly = artifact.assembly
    physical_graph = assembly.graph

    # 3. The Purity Test: Attempt to serialize the graph
    try:
        serialized_graph = pickle.dumps(physical_graph)
        # Optional: check that it can be deserialized correctly
        deserialized_graph = pickle.loads(serialized_graph)
    except Exception as e:
        pytest.fail(
            "Graph purity test failed. The BipartiteGraph is not serializable. "
            f"This likely means a runtime object (like a function closure) has been "
            f"leaked into the graph structure. Error: {e}"
        )

    # 4. Verify basic integrity after deserialization
    assert len(physical_graph.nodes) == len(deserialized_graph.nodes)
    assert len(physical_graph.channels) == len(deserialized_graph.channels)

    # Instead of asserting a brittle, hash-based ID, we assert that nodes
    # with the expected stable properties exist in the graph.
    nodes_collection = deserialized_graph.nodes.values()

    # Check for the constant node for argument 'a' with value 1
    assert any(
        node.name == "Const(a)" and node.initial_payload == 1
        for node in nodes_collection
    ), "Constant node for value 1 not found after deserialization"

    # Check for the constant node for argument 'b' with value 2
    assert any(
        node.name == "Const(b)" and node.initial_payload == 2
        for node in nodes_collection
    ), "Constant node for value 2 not found after deserialization"
