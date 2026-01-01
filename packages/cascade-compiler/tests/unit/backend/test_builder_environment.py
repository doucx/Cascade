import pytest
from cascade.spec.ir.models import GraphIR, NodeIR, TaskDef
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.environment import EnvironmentDef, ResourceDef
from cascade.compiler.backend.builder import Builder


@pytest.fixture
def simple_graph_ir():
    fp = Fingerprint({"canonical_code_structure_hash": "abc"})
    task_def = TaskDef(name="task_a", args=[], fingerprint=fp)

    # Node requesting a 'gpu' resource
    node = NodeIR(id="node_a", name="NodeA", task=task_def, constraints={"gpu": 1})
    return GraphIR(nodes=[node])


def test_builder_creates_resources_from_env(simple_graph_ir):
    # 1. Define Environment with 'gpu'
    env = EnvironmentDef(
        resources=[
            ResourceDef(name="gpu", capacity=4),
            ResourceDef(name="cpu", capacity=8),  # Unused resource
        ]
    )

    # 2. Build (Expect this to fail currently due to signature mismatch)
    builder = Builder()
    graph = builder.build(simple_graph_ir, environment=env)

    # 3. Assert D_res creation
    # Used resource should exist
    assert "global_res_gpu" in graph.nodes
    gpu_node = graph.nodes["global_res_gpu"]
    assert gpu_node.capacity == 4
    # Initial tokens should match capacity (potential energy)
    assert gpu_node.initial_tokens == 4

    # Unused resource should ALSO exist (Physics is objective)
    assert "global_res_cpu" in graph.nodes
    cpu_node = graph.nodes["global_res_cpu"]
    assert cpu_node.capacity == 8


def test_builder_raises_on_missing_resource(simple_graph_ir):
    # 1. Empty Environment (No GPU)
    env = EnvironmentDef(resources=[])

    builder = Builder()

    # 2. Build should fail because Graph requests 'gpu' but Env has none
    with pytest.raises(
        ValueError, match="Resource 'gpu' required by node 'node_a' is not defined"
    ):
        builder.build(simple_graph_ir, environment=env)
