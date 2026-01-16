import pytest
from cascade.spec.ir.graph import GraphIR, NodeIR, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.ir.fingerprint import Fingerprint
from cascade.compiler.backend.builder import Builder
from cascade.spec.physical.environment import EnvironmentDef
from cascade.reflection import PhysicalIdGenerator
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.specs.dyad import LauncherSpec


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
    artifact = builder.build(sample_graph_ir, environment=EnvironmentDef())
    assembly = artifact.assembly
    graph = assembly.graph
    symbol_table = assembly.symbol_table

    # Assert Symbol Table
    # launcher nodes should be in symbol table
    assert "node_a.launch" in symbol_table
    assert symbol_table["node_a.launch"] == "abc"
    assert "node_b.launch" in symbol_table
    assert symbol_table["node_b.launch"] == "abc"

    # Assert nodes: 2 dyad (3*2=6) + 1 D_life + 1 F_obs + 1 D_dep + 1 D_pulse = 10 nodes
    assert len(graph.nodes) == 10
    assert "global.observability.bus" in graph.nodes
    assert "global.observability.observer" in graph.nodes
    assert "node_a.land" in graph.nodes
    assert "node_b.launch" in graph.nodes
    assert "dep.node_a.to.node_b.data" in graph.nodes
    assert "pulse.source.node_a" in graph.nodes

    # Assert channels
    # 2 dyad (1 internal * 2) = 2
    # 1 data dependency = 2 (F->D, D->F)
    # 2 dyad * 2 obs channels to D_life = 4
    # 1 D_life -> F_obs channel = 1
    # 1 D_pulse -> F_launcher channel = 1
    # Total = 2 + 2 + 4 + 1 + 1 = 10
    assert len(graph.channels) == 10

    # 1. Test data dependency wiring (Lander -> D -> Launcher)
    land_to_dep = next(
        c
        for c in graph.channels
        if c.source_node_id == "node_a.land"
        and c.target_node_id == "dep.node_a.to.node_b.data"
    )
    assert land_to_dep is not None

    dep_to_launch = next(
        c
        for c in graph.channels
        if c.source_node_id == "dep.node_a.to.node_b.data"
        and c.target_node_id == "node_b.launch"
    )
    assert dep_to_launch is not None
    assert dep_to_launch.target_port == "data"

    # 2. Test observability wiring
    d_life_id = "global.observability.bus"
    obs_channels = [c for c in graph.channels if c.target_node_id == d_life_id]

    assert len(obs_channels) == 4  # 2 starts, 2 ends

    source_ids = {c.source_node_id for c in obs_channels}
    assert "node_a.launch" in source_ids
    assert "node_a.land" in source_ids
    assert "node_b.launch" in source_ids
    assert "node_b.land" in source_ids


def test_builder_creates_pulse_for_source_node(source_only_graph_ir):
    builder = Builder()
    artifact = builder.build(source_only_graph_ir, environment=EnvironmentDef())
    assembly = artifact.assembly
    graph = assembly.graph

    # 1. Assert Pulse node creation
    pulse_id = PhysicalIdGenerator.pulse_source("source_node")
    assert pulse_id in graph.nodes

    pulse_node = graph.nodes[pulse_id]
    assert isinstance(pulse_node, PhysicsDataNode)
    assert pulse_node.initial_tokens == 1

    # 2. Assert Launcher port definition
    launcher_id = "source_node.launch"
    launcher_node = graph.nodes[launcher_id]

    assert LauncherSpec.pulse.name in launcher_node.input_ports

    # 3. Assert Connection: D_pulse -> F_launch
    pulse_channel = next(
        c
        for c in graph.channels
        if c.source_node_id == pulse_id and c.target_node_id == launcher_id
    )
    assert pulse_channel is not None
    assert pulse_channel.target_port == LauncherSpec.pulse.name
