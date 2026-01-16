from cascade.spec.ir.graph import NodeIR, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.ir.fingerprint import Fingerprint
from cascade.spec.physical.ports import PortRole
from cascade.compiler.backend.expander import Expander
from cascade.spec.physical.dyad import LauncherNode, LanderNode
from cascade.spec.physical.nodes import PhysicsDataNode


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
    # We expect 3 nodes: Launcher, Lander, D_result
    assert len(subgraph.nodes) == 3

    launcher = subgraph.launcher
    lander = subgraph.lander
    d_result = subgraph.nodes["node_1.result"]

    assert isinstance(launcher, LauncherNode)
    assert isinstance(lander, LanderNode)
    assert isinstance(d_result, PhysicsDataNode)

    assert launcher.id == "node_1.launch"
    assert lander.id == "node_1.land"

    # 4. Assert Launcher Properties
    assert launcher.canonical_code_structure_hash == "abc"
    assert launcher.reply_to_nid == "node_1.result"

    # 5. Assert Internal Channel
    # Only one connection: D_result -> Lander
    assert len(subgraph.channels) == 1
    channel = subgraph.channels[0]
    assert channel.source_node_id == "node_1.result"
    assert channel.target_node_id == "node_1.land"
    assert channel.target_port == "result_token"

    # 6. Assert Port Definitions
    assert "x" in launcher.input_ports
    assert launcher.input_ports["x"].role == PortRole.DATA
    assert launcher.output_ports["obs_output"].role == PortRole.OBSERVABILITY


def test_expander_generates_sovereign_ports_on_lander():
    # This test merges the intent of the old test_sovereignty.py
    # 1. Setup IR
    fp = Fingerprint({"canonical_code_structure_hash": "abc"})
    task_def = TaskDef(name="my_task", args=[], fingerprint=fp)
    node_ir = NodeIR(
        current_node_instance_hash="node_sov", name="SovereignNode", task=task_def
    )

    # 2. Expand
    expander = Expander()
    subgraph = expander.expand_node(node_ir)
    lander = subgraph.lander

    # 3. Assert Ports
    assert "output_default" in lander.output_ports
    assert "output_error" in lander.output_ports

    # Check roles
    assert lander.output_ports["output_default"].role == PortRole.DATA
    assert lander.output_ports["output_error"].role == PortRole.DATA