import pytest
from cascade.spec.ir.models import GraphIR, NodeIR, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint
from cascade.compiler.backend.builder import Builder
from cascade.spec.environment import EnvironmentDef


@pytest.fixture
def sample_graph_ir():
    fp = Fingerprint.from_dict({"canonical_code_structure_hash": "abc"})
    task_a_def = TaskDef(name="task_a", args=[], fingerprint=fp)
    task_b_def = TaskDef(
        name="task_b",
        args=[ArgumentDef("data", ArgumentKind.POSITIONAL_OR_KEYWORD)],
        fingerprint=fp,
    )

    node_a = NodeIR(id="node_a", name="NodeA", task=task_a_def)
    node_b = NodeIR(
        id="node_b",
        name="NodeB",
        task=task_b_def,
        inputs={"data": "node_a"},  # task_b.data comes from node_a
    )

    return GraphIR(nodes=[node_a, node_b])


def test_builder_expands_and_wires_nodes(sample_graph_ir):
    builder = Builder()
    graph = builder.build(sample_graph_ir, environment=EnvironmentDef())

    # Assert nodes: 2 triads (6 nodes each) + 1 D_life + 1 F_obs = 14 nodes
    assert len(graph.nodes) == 14
    assert "global_d_life" in graph.nodes
    assert "global_f_obs" in graph.nodes
    assert "node_a_stain" in graph.nodes
    assert "node_b_bleach" in graph.nodes

    # Assert channels
    # 2 triads (6 internal) = 12
    # 1 data dependency = 1
    # 2 triads * 2 obs channels to D_life = 4
    # 1 D_life -> F_obs channel = 1
    # Total = 12 + 1 + 4 + 1 = 18
    assert len(graph.channels) == 18

    # 1. Test data dependency wiring
    data_channel = next(
        c
        for c in graph.channels
        if c.source_node_id == "node_a_stain" and c.target_node_id == "node_b_bleach"
    )
    assert data_channel is not None
    assert data_channel.source_port == "output"

    # 2. Test observability wiring
    d_life_id = "global_d_life"
    obs_channels = [c for c in graph.channels if c.target_node_id == d_life_id]

    assert len(obs_channels) == 4  # 2 starts, 2 ends

    source_ids = {c.source_node_id for c in obs_channels}
    assert "node_a_bleach" in source_ids
    assert "node_a_stain" in source_ids
    assert "node_b_bleach" in source_ids
    assert "node_b_stain" in source_ids
