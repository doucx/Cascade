from cascade.compiler.backend.expander import Expander
from cascade.spec.ir.fingerprint import Fingerprint
from cascade.spec.ir.graph import ArgumentDef, ArgumentKind, NodeIR, TaskDef
from cascade.spec.physical.dyad import LanderNode, LauncherNode
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.ports import PortRole
from cascade.spec.specs.dyad import LanderSpec


def test_expander_creates_dyad_structure():
    # 1. Setup IR
    fp = Fingerprint({"canonical_code_structure_hash": "abc"})
    task_def = TaskDef(
        name="my_task",
        args=[ArgumentDef("x", ArgumentKind.POSITIONAL_OR_KEYWORD)],
        fingerprint=fp,
    )
    node_ir = NodeIR(current_node_instance_hash="node_1", name="MyNode", task=task_def)

    # 2. Expand
    expander = Expander()
    subgraph = expander.expand_node(node_ir)

    # 3. Assert Nodes
    # We expect 3 nodes: Launcher, Result, Lander
    assert len(subgraph.nodes) == 3

    launcher = subgraph.launcher
    lander = subgraph.lander

    assert isinstance(launcher, LauncherNode)
    assert isinstance(lander, LanderNode)
    assert launcher.id == "node_1.launch"
    assert lander.id == "node_1.land"

    # Check intermediate node
    d_result = subgraph.nodes["node_1.result"]
    assert isinstance(d_result, PhysicsDataNode)

    # 4. Assert Channels
    # We expect 1 internal channel: D_result -> Lander
    assert len(subgraph.channels) == 1

    # Verify connections
    # D_result -> Lander
    result_channel = next(
        c
        for c in subgraph.channels
        if c.source_node_id == d_result.id and c.target_node_id == lander.id
    )
    assert result_channel.target_port == LanderSpec.result_token.name

    # Verify Port Definitions
    assert "x" in launcher.input_ports
    assert launcher.input_ports["x"].role == PortRole.DATA
    assert launcher.output_ports["obs_output"].role == PortRole.OBSERVABILITY

    assert lander.input_ports[LanderSpec.result_token.name].role == PortRole.DATA
    assert lander.output_ports["output_default"].role == PortRole.DATA
