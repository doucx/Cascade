from cascade.spec.ir.models import NodeIR, TaskDef
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.ports import PortRole
from cascade.compiler.backend.expander import Expander


def test_expander_generates_sovereign_ports():
    # 1. Setup IR
    fp = Fingerprint({"canonical_code_structure_hash": "abc"})
    task_def = TaskDef(name="my_task", args=[], fingerprint=fp)
    node_ir = NodeIR(
        current_node_instance_hash="node_sov", name="SovereignNode", task=task_def
    )

    # 2. Expand
    expander = Expander()
    subgraph = expander.expand_node(node_ir)
    stainer = subgraph.stainer

    # 3. Assert Ports
    assert "output_default" in stainer.output_ports
    assert "output_error" in stainer.output_ports

    # Check roles
    assert stainer.output_ports["output_default"].role == PortRole.DATA
    assert stainer.output_ports["output_error"].role == PortRole.DATA

    # Ensure legacy 'output' is gone
    assert "output" not in stainer.output_ports
