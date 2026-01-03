from cascade.spec.ir.models import NodeIR, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.ports import PortRole
from cascade.compiler.backend.expander import Expander
from cascade.spec.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.physics import PhysicsDataNode


def test_expander_creates_triad_structure():
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
    # We expect 6 nodes: Bleach, Worker, Stain, D_in, D_out, D_trace
    assert len(subgraph.nodes) == 6

    bleacher = subgraph.bleacher
    stainer = subgraph.stainer

    assert isinstance(bleacher, BleachNode)
    assert isinstance(stainer, StainNode)
    assert bleacher.id == "node_1.bleach"
    assert stainer.id == "node_1.stain"

    # Check intermediate nodes
    worker = subgraph.nodes["node_1.worker"]
    assert isinstance(worker, WorkerNode)

    d_trace = subgraph.nodes["node_1.data.trace"]
    assert isinstance(d_trace, PhysicsDataNode)

    # 4. Assert Channels
    # We expect 6 internal channels
    assert len(subgraph.channels) == 6

    # Verify connections
    # Bleach -> Trace
    trace_channel = next(
        c
        for c in subgraph.channels
        if c.source_node_id == bleacher.id and c.target_node_id == d_trace.id
    )
    assert trace_channel.source_port == "trace_output"

    # Verify Port Definitions
    assert "x" in bleacher.input_ports
    assert bleacher.input_ports["x"].role == PortRole.DATA
    assert bleacher.output_ports["trace_output"].role == PortRole.DATA
    assert bleacher.output_ports["obs_output"].role == PortRole.OBSERVABILITY

    assert stainer.input_ports["worker_result"].role == PortRole.DATA
    assert stainer.output_ports["output_default"].role == PortRole.DATA

    # Trace -> Stain
    trace_in_channel = next(
        c
        for c in subgraph.channels
        if c.source_node_id == d_trace.id and c.target_node_id == stainer.id
    )
    assert trace_in_channel.source_port == "out"  # implicit port for data node
