import pytest
from cascade.compiler.backend.builder import Builder
from cascade.spec.ir.fingerprint import Fingerprint
from cascade.spec.ir.graph import GraphIR, NodeIR, TaskDef
from cascade.spec.physical.environment import EnvironmentDef, ResourceDef


@pytest.fixture
def simple_graph_ir():
    fp = Fingerprint({"canonical_code_structure_hash": "abc"})
    task_def = TaskDef(name="task_a", args=[], fingerprint=fp)

    # Node requesting a 'gpu' resource
    node = NodeIR(
        current_node_instance_hash="node_a",
        name="NodeA",
        task=task_def,
        constraints={"gpu": 1},
    )
    return GraphIR(nodes=[node])


def test_builder_creates_resources_from_env(simple_graph_ir):
    # 1. Define Environment with 'gpu'
    env = EnvironmentDef(
        resources=[
            ResourceDef(name="gpu", capacity=4),
            ResourceDef(name="cpu", capacity=8),  # Unused resource
        ]
    )

    # 2. Build
    builder = Builder()
    artifact = builder.build(simple_graph_ir, environment=env)
    assembly = artifact.assembly
    graph = assembly.graph

    # 3. Assert Broker/Ledger creation
    # Used resource
    ledger_id = "canonical.resource.ledger.gpu"
    allocator_id = "canonical.resource.allocator.gpu"
    reclaimer_id = "canonical.resource.reclaimer.gpu"

    assert ledger_id in graph.nodes
    assert allocator_id in graph.nodes
    assert reclaimer_id in graph.nodes

    ledger_node = graph.nodes[ledger_id]
    # The Ledger Node holds the DiscreteLedger object, capacity is just 1 (slot for the object)
    assert ledger_node.capacity == 1
    assert ledger_node.initial_tokens == 1
    # Check the payload of the initial token
    initial_ledger = ledger_node.initial_payload
    assert initial_ledger.total == 4
    assert initial_ledger.available == 4

    # Unused resource
    cpu_ledger_id = "canonical.resource.ledger.cpu"
    assert cpu_ledger_id in graph.nodes
    cpu_ledger = graph.nodes[cpu_ledger_id].initial_payload
    assert cpu_ledger.total == 8


def test_builder_raises_on_missing_resource(simple_graph_ir):
    # 1. Empty Environment (No GPU)
    env = EnvironmentDef(resources=[])

    builder = Builder()

    # 2. Build should fail because Graph requests 'gpu' but Env has none
    with pytest.raises(
        ValueError, match="Resource 'gpu' required by node 'node_a' is not defined"
    ):
        builder.build(simple_graph_ir, environment=env)
