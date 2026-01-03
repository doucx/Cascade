import pytest
from cascade.spec.ir.models import GraphIR, NodeIR, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint
from cascade.compiler.backend.builder import Builder
from cascade.spec.environment import EnvironmentDef
from cascade.compiler.utils.naming import PhysicalIdGenerator
from cascade.spec.physics import PhysicsDataNode
from cascade.spec.ports import PortName


@pytest.fixture
def sample_graph_ir():
    fp = Fingerprint.from_dict({"canonical_code_structure_hash": "abc"})
    task_a_def = TaskDef(name="task_a", args=[], fingerprint=fp)
    task_b_def = TaskDef(
        name="task_b",
        args=[ArgumentDef("data", ArgumentKind.POSITIONAL_OR_KEYWORD)],
        fingerprint=fp,
    )

    node_a = NodeIR(current_node_instance_hash="node_a", name="NodeA", task=task_a_def)
    node_b = NodeIR(
        current_node_instance_hash="node_b",
        name="NodeB",
        task=task_b_def,
        inputs={"data": "node_a"},  # task_b.data comes from node_a
    )

    return GraphIR(nodes=[node_a, node_b])


@pytest.fixture
def source_only_graph_ir():
    fp = Fingerprint.from_dict({"canonical_code_structure_hash": "xyz"})
    task_def = TaskDef(name="source_task", args=[], fingerprint=fp)
    node = NodeIR(
        current_node_instance_hash="source_node", name="Source", task=task_def
    )
    return GraphIR(nodes=[node])


def test_builder_expands_and_wires_nodes(sample_graph_ir):
    builder = Builder()
    graph = builder.build(sample_graph_ir, environment=EnvironmentDef())

    # Assert nodes: 2 triads (6*2=12) + 1 D_life + 1 F_obs + 1 D_dep + 1 D_pulse = 16 nodes
    assert len(graph.nodes) == 16
    assert "global.observability.bus" in graph.nodes
    assert "global.observability.observer" in graph.nodes
    assert "node_a.stain" in graph.nodes
    assert "node_b.bleach" in graph.nodes
    assert "dep.node_a.to.node_b.data" in graph.nodes
    assert "pulse.source.node_a" in graph.nodes  # The new pulse node

    # Assert channels
    # 2 triads (6 internal * 2) = 12
    # 1 data dependency = 2 (F->D, D->F)
    # 2 triads * 2 obs channels to D_life = 4
    # 1 D_life -> F_obs channel = 1
    # 1 D_pulse -> F_bleach channel = 1
    # Total = 12 + 2 + 4 + 1 + 1 = 20
    assert len(graph.channels) == 20

    # 1. Test data dependency wiring (F -> D -> F)
    stain_to_dep = next(
        c
        for c in graph.channels
        if c.source_node_id == "node_a.stain"
        and c.target_node_id == "dep.node_a.to.node_b.data"
    )
    assert stain_to_dep is not None

    dep_to_bleach = next(
        c
        for c in graph.channels
        if c.source_node_id == "dep.node_a.to.node_b.data"
        and c.target_node_id == "node_b.bleach"
    )
    assert dep_to_bleach is not None
    assert dep_to_bleach.target_port == "data"

    # 2. Test observability wiring
    d_life_id = "global.observability.bus"
    obs_channels = [c for c in graph.channels if c.target_node_id == d_life_id]

    assert len(obs_channels) == 4  # 2 starts, 2 ends

    source_ids = {c.source_node_id for c in obs_channels}
    assert "node_a.bleach" in source_ids
    assert "node_a.stain" in source_ids
    assert "node_b.bleach" in source_ids
    assert "node_b.stain" in source_ids


def test_builder_creates_pulse_for_source_node(source_only_graph_ir):
    builder = Builder()
    graph = builder.build(source_only_graph_ir, environment=EnvironmentDef())

    # 1. Assert Pulse node creation
    pulse_id = PhysicalIdGenerator.pulse_source("source_node")
    assert pulse_id in graph.nodes

    pulse_node = graph.nodes[pulse_id]
    assert isinstance(pulse_node, PhysicsDataNode)
    assert pulse_node.initial_tokens == 1

    # 2. Assert Bleacher port definition
    bleacher_id = "source_node.bleach"
    bleacher_node = graph.nodes[bleacher_id]
    assert PortName.PULSE in bleacher_node.input_ports

    # 3. Assert Connection: D_pulse -> F_bleach
    pulse_channel = next(
        c
        for c in graph.channels
        if c.source_node_id == pulse_id and c.target_node_id == bleacher_id
    )
    assert pulse_channel is not None
    assert pulse_channel.target_port == PortName.PULSE
