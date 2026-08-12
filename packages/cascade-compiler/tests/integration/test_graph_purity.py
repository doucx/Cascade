import pickle

import pytest
from cascade.compiler.backend import Builder
from cascade.compiler.frontend import IRGenerator
from cascade.spec.dsl.task import task
from cascade.spec.physical.environment import EnvironmentDef


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

    generation_result = generator.generate(workflow)
    artifact = builder.build(generation_result.ir, environment)
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

    # Check for the constant node for argument '0' (was 'a') with value 1
    assert any(
        node.name == "Const(0)" and node.initial_payload == 1
        for node in nodes_collection
    ), "Constant node for value 1 not found after deserialization"

    # Check for the constant node for argument '1' (was 'b') with value 2
    assert any(
        node.name == "Const(1)" and node.initial_payload == 2
        for node in nodes_collection
    ), "Constant node for value 2 not found after deserialization"
